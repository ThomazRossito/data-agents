"""
Data Agents — Entry Point Principal

Sistema Multi-Agentes para Engenharia e Análise de Dados.
Suporta dois modos:
  - Interativo: loop de chat no terminal com feedback visual em tempo real
  - Single-query: executa um único prompt (passado como argumento CLI)

Uso:
  python main.py                          # modo interativo
  python main.py "Analise a tabela X"     # single-query
"""

import asyncio
import atexit
import hashlib
import logging
import signal
import sys
import time

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text

from claude_agent_sdk import (
    ClaudeSDKClient,
    query,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)
from claude_agent_sdk.types import StreamEvent

from agents.supervisor import build_supervisor_options
from commands.parser import parse_command, get_help_text
from config.exceptions import (
    BudgetExceededError,
    DataAgentsError,
    MCPConnectionError,
)
from config.logging_config import setup_logging
from config.settings import settings
from hooks.session_logger import log_session_result
from hooks.cost_guard_hook import reset_session_counters
from hooks.session_lifecycle import on_session_end, on_session_start
from hooks.checkpoint import (
    save_checkpoint,
    load_checkpoint,
    clear_checkpoint,
    build_resume_prompt,
)
from hooks.memory_hook import flush_session_memories
from hooks.transcript_hook import append_turn as _append_transcript_turn
from memory.compiler import compile_daily_logs
from memory.store import MemoryStore
from agents.loader import inject_memory_context
from commands.geral import run_geral_query
from commands.party import run_party_query, parse_party_args

logger = logging.getLogger("data_agents.main")
console = Console()

# Cache de memory retrieval: {query_hash: (system_prompt_enriched, timestamp)}
# Evita chamar Sonnet lateral para queries idênticas dentro de 60 segundos
_retrieval_cache: dict[str, tuple[str, float]] = {}
_RETRIEVAL_CACHE_TTL = 60.0  # segundos

# Flag para garantir que apply_decay() só é executado 1x por sessão
_decay_applied: bool = False

# Estado exposto para atexit/signal handlers (T1.1).
# Atualizado a cada turn bem-sucedido em run_interactive; consumido pelo
# _emergency_checkpoint no encerramento para salvar checkpoint mesmo em
# saídas normais (sair) ou abruptas (SIGTERM, Ctrl+C no terminal).
_active_session: dict | None = None
_active_session_id: str | None = None
_checkpoint_saved_for_session: bool = False


def _emergency_checkpoint(reason: str = "abnormal_exit") -> None:
    """
    Salva checkpoint se houver sessão ativa e checkpoint ainda não gravado.

    Chamado por atexit (último recurso) e pelos signal handlers. Idempotente:
    se `_checkpoint_saved_for_session` já for True, sai sem fazer nada.

    Mantido minimalista — atexit não pode depender de event loop.
    """
    global _checkpoint_saved_for_session
    if _checkpoint_saved_for_session or _active_session is None:
        return
    state = _active_session
    if not state.get("last_prompt"):
        return
    try:
        save_checkpoint(
            last_prompt=state.get("last_prompt", ""),
            reason=reason,
            cost_usd=state.get("total_cost", 0.0),
            turns=state.get("total_turns", 0),
            session_id=_active_session_id,
        )
        _checkpoint_saved_for_session = True
    except Exception as e:
        logger.debug(f"Emergency checkpoint falhou ({reason}): {e}")


def _signal_handler(signum: int, _frame: object) -> None:
    """
    Handler de SIGTERM/SIGHUP: grava checkpoint e encerra com exit(0).

    SIGINT (Ctrl+C) é tratado pelo asyncio como KeyboardInterrupt dentro do
    event loop — mantemos o fluxo original, não registramos SIGINT aqui.
    """
    name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
    _emergency_checkpoint(reason=f"signal_{name.lower()}")
    # SystemExit é capturado pelo atexit que garante flush dos logs do Python
    sys.exit(0)


# ─── Mapeamento de tool → label amigável para o usuário ──────────────

TOOL_LABELS: dict[str, str] = {
    # Ferramentas do Supervisor
    "Agent": "🤖 Delegando para agente especialista",
    "Read": "📖 Lendo arquivo",
    "Grep": "🔍 Buscando conteúdo",
    "Glob": "📂 Listando arquivos",
    "Bash": "⚙️  Executando comando",
    "AskUserQuestion": "❓ Aguardando resposta do usuário",
    # Ferramentas MCP — Databricks
    "mcp__databricks__execute_sql": "🗄️  Executando SQL no Databricks",
    "mcp__databricks__list_catalogs": "📋 Listando catálogos do Unity Catalog",
    "mcp__databricks__list_schemas": "📋 Listando schemas",
    "mcp__databricks__list_tables": "📋 Listando tabelas",
    "mcp__databricks__describe_table": "🔎 Inspecionando tabela",
    "mcp__databricks__get_table_schema": "🔎 Obtendo schema da tabela",
    "mcp__databricks__create_or_update_pipeline": "🔧 Criando/atualizando Pipeline LakeFlow",
    "mcp__databricks__upload_to_volume": "⬆️  Enviando arquivo para Volume",
    "mcp__databricks__list_volume_files": "📂 Listando arquivos no Volume",
    "mcp__databricks__run_job_now": "🚀 Executando Job Databricks",
    "mcp__databricks__start_pipeline": "🚀 Iniciando Pipeline Databricks",
    "mcp__databricks__get_pipeline": "📊 Consultando status do Pipeline",
    # Ferramentas MCP — Fabric
    "mcp__fabric__list_workspaces": "📋 Listando workspaces do Fabric",
    "mcp__fabric__list_lakehouses": "📋 Listando Lakehouses",
    "mcp__fabric__onelake_upload_file": "⬆️  Enviando arquivo para OneLake",
    "mcp__fabric__onelake_list_files": "📂 Listando arquivos no OneLake",
    # Ferramentas MCP — Fabric RTI
    "mcp__fabric_rti__kusto_query": "🔍 Executando query KQL",
    "mcp__fabric_rti__kusto_command": "⚙️  Executando comando KQL",
    "mcp__fabric_rti__kusto_list_databases": "📋 Listando databases do Eventhouse",
}


def _get_tool_label(tool_name: str) -> str:
    """Retorna um label amigável para o nome da tool."""
    if tool_name in TOOL_LABELS:
        return TOOL_LABELS[tool_name]
    # Fallback: formata o nome da tool de forma legível
    clean = tool_name.replace("mcp__", "").replace("__", " → ").replace("_", " ").title()
    return f"🔧 {clean}"


def _get_agent_label(tool_input_json: str) -> str:
    """Extrai o nome do agente de um input JSON de tool Agent."""
    try:
        import json

        data = json.loads(tool_input_json) if tool_input_json else {}
        agent_name = data.get("agent_name") or data.get("name") or ""
        if agent_name:
            return f"🤖 Delegando para → [bold yellow]{agent_name}[/bold yellow]"
    except Exception:
        pass
    return "🤖 Delegando para agente especialista"


def print_banner() -> None:
    """Exibe o banner de boas-vindas com informações do projeto."""
    banner = Text()
    banner.append("  DATA AGENTS\n", style="bold cyan")
    banner.append("  Sistema Multi-Agentes · Databricks + Microsoft Fabric\n", style="dim")
    banner.append("  Powered by Claude Agent SDK + MCP\n\n", style="dim")

    banner.append("  Desenvolvido por: \n", style="bold cyan")
    banner.append("  Thomaz Antonio Rossito Neto\n", style="bold")
    banner.append(
        "  Specialist Data & AI Solutions Architect | Center of Excellence CoE @CI&T\n", style="dim"
    )
    banner.append("  LinkedIn: ", style="bold")
    banner.append("https://www.linkedin.com/in/thomaz-antonio-rossito-neto/\n", style="dim")
    banner.append("  GitHub: ", style="bold")
    banner.append("https://github.com/ThomazRossito/\n", style="dim")
    console.print(Panel(banner, border_style="cyan"))
    console.print()
    console.print("[dim]Digite sua solicitação em linguagem natural.[/dim]")
    console.print(
        "[dim]Comandos: [bold]sair[/bold] para encerrar | [bold]limpar[/bold] para nova sessão "
        "| [bold]continuar[/bold] para retomar | [bold]/help[/bold] para ajuda[/dim]"
    )
    console.print(
        "[dim]Slash: [bold]/plan[/bold] | [bold]/sql[/bold] | [bold]/spark[/bold] | "
        "[bold]/pipeline[/bold] | [bold]/fabric[/bold] | [bold]/semantic[/bold] | "
        "[bold]/quality[/bold] | [bold]/governance[/bold] | "
        "[bold]/health[/bold] | [bold]/status[/bold] | [bold]/review[/bold] | "
        "[bold magenta]/party[/bold magenta] [magenta](multi-agente paralelo)[/magenta] | "
        "[bold cyan]/geral[/bold cyan] [cyan](Haiku)[/cyan] | "
        "[bold cyan]/memory[/bold cyan] [cyan](memória persistente)[/cyan][/dim]\n"
    )


async def _stream_response(
    client: ClaudeSDKClient,
    prompt: str = "",
    session_type: str = "interactive",
    session_id: str | None = None,
) -> dict:
    """
    Processa o stream de resposta do agente com feedback visual em tempo real.

    Exibe:
      - Spinner animado enquanto o agente está pensando
      - Notificação imediata quando uma tool call é iniciada
      - Texto da resposta final em Markdown
      - Resumo de custo/turns/tempo ao finalizar

    T4.1 — Transcript: se `session_id` for fornecido, o turno do assistente
    (texto acumulado + lista de tools disparadas + métricas) é persistido em
    `logs/sessions/<session_id>.jsonl`.

    Args:
        client: Instância ativa do ClaudeSDKClient para receber o stream.
        prompt: Prompt original enviado ao agente. Apenas os primeiros 100
            caracteres são usados para o log de sessão.
        session_type: Tipo da sessão ("interactive", "plan", "sql", etc.).
        session_id: ID da sessão para persistência do transcript. Se None,
            o transcript não é gravado (backcompat com testes/single-query).

    Returns:
        Dict com: cost (float), turns (int), text (str — resposta completa),
        tools_used (list[str]), duration_ms (int).
    """
    # Estado do streaming
    current_tool: str | None = None
    tool_input_buffer: str = ""
    response_started: bool = False
    turn_count: int = 0
    live_status: Live | None = None
    metrics: dict = {
        "cost": 0.0,
        "turns": 0,
        "text": "",
        "tools_used": [],
        "duration_ms": 0,
    }
    _assistant_text_parts: list[str] = []
    _tools_used: list[str] = []

    # Rastreia tempo de início por tool call para exibir elapsed time
    _step_start: float = time.monotonic()
    _current_agent: str | None = None  # nome do agente em delegação ativa

    def _start_spinner(message: str) -> Live:
        """Inicia um spinner animado com a mensagem fornecida."""
        spinner = Spinner("dots", text=Text(message, style="dim"))
        live = Live(spinner, console=console, refresh_per_second=10, transient=True)
        live.start()
        return live

    def _stop_spinner(live: Live | None) -> None:
        """Para o spinner se estiver ativo."""
        if live and live.is_started:
            live.stop()

    def _elapsed() -> str:
        """Retorna o tempo decorrido desde o início do passo atual."""
        secs = time.monotonic() - _step_start
        return f"{secs:.1f}s"

    # Inicia o spinner de "pensando"
    live_status = _start_spinner("Agente pensando...")

    async for message in client.receive_response():
        # ── StreamEvent: feedback em tempo real ──────────────────────
        if isinstance(message, StreamEvent):
            event = message.event
            event_type = event.get("type", "")

            # Tool call iniciando
            if event_type == "content_block_start":
                block = event.get("content_block", {})
                if block.get("type") == "tool_use":
                    current_tool = block.get("name", "unknown")
                    tool_input_buffer = ""
                    _step_start = time.monotonic()
                    _current_agent = None
                    _tools_used.append(current_tool)
                    label = _get_tool_label(current_tool)
                    _stop_spinner(live_status)
                    live_status = _start_spinner(f"{label}...")

            # Acumulando input da tool (para detectar nome do agente)
            elif event_type == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "input_json_delta":
                    tool_input_buffer += delta.get("partial_json", "")
                    # Quando for Agent tool, mostra o nome do agente assim que disponível
                    if current_tool == "Agent" and _current_agent is None:
                        try:
                            import json as _json

                            data = _json.loads(tool_input_buffer)
                            agent_name = (
                                data.get("agent_name")
                                or data.get("subagent_type")
                                or data.get("name")
                                or ""
                            )
                            if agent_name:
                                _current_agent = agent_name
                                _stop_spinner(live_status)
                                live_status = _start_spinner(
                                    f"🤖 Delegando para → [bold yellow]{agent_name}[/bold yellow]..."
                                )
                        except Exception:
                            pass

            # Tool call finalizada
            elif event_type == "content_block_stop":
                if current_tool:
                    elapsed = _elapsed()
                    if current_tool == "Agent" and _current_agent:
                        # Mostra conclusão do agente especialista com tempo
                        _stop_spinner(live_status)
                        console.print(
                            f"[dim]  ✅ [bold]{_current_agent}[/bold] concluído ({elapsed})[/dim]"
                        )
                    elif current_tool != "Agent":
                        # Para tools não-Agent, mostra conclusão discreta
                        label = _get_tool_label(current_tool)
                        _stop_spinner(live_status)
                        console.print(f"[dim]  ✓ {label} ({elapsed})[/dim]")
                    else:
                        _stop_spinner(live_status)

                    current_tool = None
                    tool_input_buffer = ""
                    _current_agent = None
                    turn_count += 1
                    _step_start = time.monotonic()
                    live_status = _start_spinner(f"Processando... (etapa {turn_count})")

        # ── AssistantMessage: resposta final completa ─────────────────
        elif isinstance(message, AssistantMessage):
            _stop_spinner(live_status)
            live_status = None

            for block in message.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    if not response_started:
                        console.print("[bold blue]Agente:[/bold blue]")
                        response_started = True
                    _assistant_text_parts.append(block.text)
                    console.print(Markdown(block.text))
                    console.print()

                elif isinstance(block, ToolUseBlock):
                    # Tool use visível na resposta final (ex: AskUserQuestion)
                    if block.name == "AskUserQuestion":
                        question = block.input.get("question", "") if block.input else ""
                        if question:
                            console.print(
                                f"\n[bold yellow]❓ Agente pergunta:[/bold yellow] {question}\n"
                            )

            # Reinicia spinner para próximo turn se não for a mensagem final
            if not response_started:
                live_status = _start_spinner("Agente processando resultado...")

        # ── ResultMessage: métricas finais ────────────────────────────
        elif isinstance(message, ResultMessage):
            _stop_spinner(live_status)
            live_status = None

            parts = []
            if message.total_cost_usd:
                parts.append(f"Custo: ${message.total_cost_usd:.4f}")
            if message.num_turns:
                parts.append(f"Turns: {message.num_turns}")
            if message.duration_ms:
                parts.append(f"Tempo: {message.duration_ms / 1000:.1f}s")
            if parts:
                console.print(f"[dim]💰 {' | '.join(parts)}[/dim]\n")

            # Persistir métricas da sessão para o dashboard de monitoramento
            log_session_result(message, prompt_preview=prompt[:100], session_type=session_type)

            # Capturar métricas para checkpoint
            metrics["cost"] = float(message.total_cost_usd or 0)
            metrics["turns"] = int(message.num_turns or 0)
            metrics["duration_ms"] = int(message.duration_ms or 0)

    # Garante que o spinner seja parado em qualquer caso
    _stop_spinner(live_status)

    # Consolida texto + tools para o transcript
    assistant_text = "\n\n".join(p for p in _assistant_text_parts if p.strip())
    metrics["text"] = assistant_text
    metrics["tools_used"] = list(dict.fromkeys(_tools_used))  # dedupe preservando ordem

    # T4.1: persistir turno do assistente no transcript, se session_id foi passado.
    # Falhas são absorvidas pelo próprio hook — não propagam para o loop interativo.
    if session_id and assistant_text:
        _append_transcript_turn(
            session_id=session_id,
            role="assistant",
            content=assistant_text,
            tools_used=metrics["tools_used"],
            cost_usd=metrics["cost"],
            turns=metrics["turns"],
            duration_ms=metrics["duration_ms"],
            metadata={"session_type": session_type},
        )

    return metrics


async def _handle_memory_command(user_input: str) -> None:
    """
    Processa o slash command /memory localmente (sem Supervisor).

    Subcomandos:
      /memory status   — Exibe estatísticas do sistema de memória
      /memory flush    — Força o flush do buffer de sessão
      /memory compile  — Compila daily logs em knowledge articles
      /memory lint     — Executa health checks
      /memory search <query> — Busca memórias relevantes via Sonnet
    """
    from memory.lint import lint_memories
    from hooks.memory_hook import get_buffer_stats

    parts = user_input.split(maxsplit=2)
    sub = parts[1].lower() if len(parts) > 1 else "status"

    store = MemoryStore()

    if sub == "status":
        stats = store.get_stats()
        buf = get_buffer_stats()
        console.print(
            Panel(
                f"[bold]Memórias:[/bold] {stats['active']} ativas / {stats['total']} total\n"
                f"[bold]Por tipo:[/bold]\n"
                + "\n".join(
                    f"  {t}: {v['active']}/{v['total']}"
                    for t, v in stats.get("by_type", {}).items()
                )
                + f"\n[bold]Superseded:[/bold] {stats.get('superseded', 0)}\n"
                f"\n[bold]Buffer da sessão:[/bold] {buf['entries']} entradas, "
                f"{buf['total_chars']} chars, {buf['instant_captures']} capturas instantâneas",
                title="🧠 Memory Status",
                border_style="cyan",
            )
        )

    elif sub == "flush":
        console.print("[dim]🧠 Flush: extraindo memórias do buffer da sessão...[/dim]")
        n = flush_session_memories(session_id="manual_flush")
        console.print(f"[bold cyan]🧠 Flush: {n} memórias extraídas e salvas.[/bold cyan]\n")

    elif sub == "compile":
        console.print("[dim]🧠 Compilando daily logs...[/dim]")
        metrics = compile_daily_logs(store)
        console.print(
            f"[bold cyan]🧠 Compilação: {metrics['new_memories']} novas, "
            f"{metrics['superseded']} substituídas, "
            f"{metrics['skipped_dupes']} duplicatas ignoradas.[/bold cyan]\n"
        )

    elif sub == "lint":
        console.print("[dim]🧠 Executando health checks...[/dim]")
        report = lint_memories(store)
        console.print(Markdown(report.to_markdown()))
        console.print()

    elif sub == "search":
        query_text = parts[2] if len(parts) > 2 else ""
        if not query_text:
            console.print("[yellow]Uso: /memory search <sua query>[/yellow]")
            return

        console.print(f"[dim]🧠 Buscando memórias para: {query_text}...[/dim]")
        from memory.retrieval import retrieve_relevant_memories, format_memories_for_injection

        memories = retrieve_relevant_memories(query_text, store)
        if memories:
            formatted = format_memories_for_injection(memories)
            console.print(Markdown(formatted))
        else:
            console.print("[dim]Nenhuma memória relevante encontrada.[/dim]")
        console.print()

    else:
        console.print("[yellow]Subcomandos: status, flush, compile, lint, search <query>[/yellow]")


# Histórico de conversa do /geral — mantido na sessão CLI.
# A lógica central está em commands/geral.py (compartilhada com ui/chainlit_app.py).
_geral_history: list[dict] = []


async def _stream_geral(
    user_message: str, session_type: str = "geral", session_id: str | None = None
) -> dict[str, float]:
    """
    Wrapper CLI para run_geral_query() — adiciona feedback visual (spinner, Rich).

    A lógica de query está em commands/geral.py (importada também pela UI).
    Esta função lida apenas com apresentação específica do terminal.

    T4.1 — Transcript: se `session_id` for passado, grava os turnos user e
    assistant no transcript da sessão.
    """
    _geral_history.append({"role": "user", "content": user_message})
    if session_id:
        _append_transcript_turn(
            session_id=session_id,
            role="user",
            content=user_message,
            metadata={"session_type": session_type, "command": "/geral"},
        )

    spinner = Spinner("dots", text=Text("💬 Geral pensando...", style="dim"))
    live = Live(spinner, console=console, refresh_per_second=10, transient=True)
    live.start()

    metrics: dict[str, float] = {"cost": 0.0}

    try:
        response_text, raw_metrics = await run_geral_query(
            user_message, _geral_history, session_type=session_type
        )
    except Exception as e:
        if live.is_started:
            live.stop()
        console.print(f"\n[bold red]Erro no /geral:[/bold red] {e}\n")
        logger.error("Geral SDK call error: %s", e, exc_info=True)
        if _geral_history and _geral_history[-1]["role"] == "user":
            _geral_history.pop()
        return metrics

    if live.is_started:
        live.stop()

    if response_text:
        console.print("[bold cyan]💬 Geral:[/bold cyan]")
        console.print(Markdown(response_text))
        console.print()
        _geral_history.append({"role": "assistant", "content": response_text})
        if session_id:
            _append_transcript_turn(
                session_id=session_id,
                role="assistant",
                content=response_text,
                cost_usd=raw_metrics.get("cost"),
                turns=int(raw_metrics.get("turns") or 0) or None,
                duration_ms=int((raw_metrics.get("duration") or 0) * 1000) or None,
                metadata={"session_type": session_type, "command": "/geral"},
            )

    cost = raw_metrics["cost"]
    parts = [f"💰 Custo: ${cost:.5f}"]
    if raw_metrics["turns"]:
        parts.append(f"🔢 turns: {int(raw_metrics['turns'])}")
    if raw_metrics["duration"]:
        parts.append(f"⏱ {raw_metrics['duration']:.1f}s")
    console.print(f"[dim]{' | '.join(parts)}[/dim]\n")

    metrics["cost"] = cost
    return metrics


async def _stream_party(user_input: str, session_id: str | None = None) -> dict[str, float]:
    """
    DOMA Party Mode — spawna múltiplos agentes em paralelo e exibe perspectivas independentes.

    Cada agente recebe a mesma query e responde com seu próprio contexto e expertise,
    sem influência dos demais. O resultado é apresentado com cabeçalho por agente.

    T4.1 — Transcript: se `session_id` for passado, grava o turno do usuário e
    um turno consolidado do assistente contendo todas as respostas dos agentes.

    Args:
        user_input: Input completo do usuário incluindo /party e flags.
        session_id: ID da sessão para persistência do transcript.

    Returns:
        Dict com métricas consolidadas: {"cost": float}.
    """
    agent_names, query = parse_party_args(user_input)

    if not query.strip():
        console.print(
            "[yellow]Party Mode: forneça uma query após o comando.\n"
            "Exemplos:\n"
            "  /party qual a diferença entre Delta Lake e Parquet?\n"
            "  /party --quality como validar dados incrementais?\n"
            "  /party --arch descreva a arquitetura Medallion[/yellow]\n"
        )
        return {"cost": 0.0}

    if session_id:
        _append_transcript_turn(
            session_id=session_id,
            role="user",
            content=user_input,
            metadata={
                "session_type": "party",
                "command": "/party",
                "agents": agent_names,
            },
        )

    console.print(
        f"[bold magenta]🎉 [DOMA Party Mode][/bold magenta] "
        f"Convocando: [yellow]{', '.join(agent_names)}[/yellow]"
    )
    console.print(f"[dim]Query: {query[:120]}{'...' if len(query) > 120 else ''}[/dim]\n")

    # Spinner global enquanto todos os agentes processam em paralelo
    spinner = Spinner("dots", text=Text("Agentes processando em paralelo...", style="dim"))
    live = Live(spinner, console=console, refresh_per_second=10, transient=True)
    live.start()

    try:
        results = await run_party_query(query, agent_names)
    finally:
        if live.is_started:
            live.stop()

    # Exibe cada resposta com cabeçalho do agente
    total_cost = 0.0
    agent_icons = {
        "sql-expert": "🗄️",
        "spark-expert": "⚡",
        "pipeline-architect": "🏗️",
        "data-quality-steward": "🔍",
        "governance-auditor": "🔐",
        "semantic-modeler": "📊",
    }

    for name, text, cost in results:
        icon = agent_icons.get(name, "🤖")
        console.print(f"[bold yellow]{icon} {name}:[/bold yellow]")
        if text.strip():
            console.print(Markdown(text))
        else:
            console.print("[dim]_Agente não retornou resposta._[/dim]")
        console.print()
        total_cost += cost

    console.print(
        f"[dim]💰 Party Mode — {len(results)} agentes | Custo total: ${total_cost:.5f}[/dim]\n"
    )

    # Grava um turno consolidado no transcript contendo todas as respostas.
    if session_id and results:
        consolidated = "\n\n".join(
            f"## {name}\n{text.strip()}" for name, text, _ in results if text.strip()
        )
        if consolidated:
            _append_transcript_turn(
                session_id=session_id,
                role="assistant",
                content=consolidated,
                cost_usd=total_cost,
                metadata={
                    "session_type": "party",
                    "command": "/party",
                    "agents": [name for name, _, _ in results],
                },
            )

    return {"cost": total_cost}


async def run_interactive() -> None:
    """Loop interativo com histórico de sessão mantido entre mensagens."""

    # Estado de sessão para checkpoint
    _session_state: dict = {
        "last_prompt": "",
        "total_cost": 0.0,
        "total_turns": 0,
    }

    # T1.1: registra o estado como "sessão ativa" para que atexit/signal handlers
    # possam gravar checkpoint em saídas normais (sair) ou abruptas (SIGTERM).
    # Os handlers só são registrados uma vez por processo (idempotência via flag global).
    global _active_session, _active_session_id, _checkpoint_saved_for_session
    _active_session = _session_state
    _checkpoint_saved_for_session = False
    if not getattr(run_interactive, "_handlers_installed", False):
        atexit.register(_emergency_checkpoint, "atexit")
        signal.signal(signal.SIGTERM, _signal_handler)
        if hasattr(signal, "SIGHUP"):  # não existe no Windows
            signal.signal(signal.SIGHUP, _signal_handler)
        run_interactive._handlers_installed = True  # type: ignore[attr-defined]

    # ── 1. Banner primeiro — antes de qualquer inicialização ─────────────────
    print_banner()

    # ── 2. Logging + diagnósticos aparecem DEPOIS do banner ──────────────────
    setup_logging(
        log_level=settings.log_level,
        console_log_level=settings.console_log_level,
    )
    if hasattr(settings, "startup_diagnostics"):
        settings.startup_diagnostics()

    # ── 2.5 Compilar daily logs de memória pendentes (cost-free, apenas I/O) ──
    try:
        store = MemoryStore()
        compile_metrics = compile_daily_logs(store)
        if compile_metrics["new_memories"] > 0:
            console.print(
                f"[dim]🧠 Memória: {compile_metrics['new_memories']} novas memórias compiladas "
                f"({compile_metrics['superseded']} atualizadas)[/dim]"
            )
    except Exception as e:
        logger.debug(f"Compilação de memória ignorada: {e}")

    # ── 3. build_supervisor_options emite "MCP servers ativos..." aqui ───────
    try:
        options = build_supervisor_options()
        # Habilita streaming parcial para feedback em tempo real
        options.include_partial_messages = True
    except Exception as e:
        console.print(f"\n[bold red]Erro ao inicializar o Supervisor:[/bold red] {e}")
        logger.error(f"Falha na inicialização: {e}", exc_info=True)
        return

    # ── 4. ClaudeSDKClient emite "Using bundled Claude Code CLI..." aqui ─────
    import uuid

    _session_id = f"cli-{uuid.uuid4().hex[:8]}"
    _active_session_id = _session_id  # T1.2: expõe para _emergency_checkpoint
    try:
        async with ClaudeSDKClient(options=options) as client:
            # Ch.12 — Session Lifecycle: reseta contadores e prepara buffer de memória
            on_session_start(_session_id)

            # ── 4.1 Verificar checkpoint de sessão anterior ────────────────
            checkpoint = load_checkpoint()
            if checkpoint:
                reason = checkpoint.get("reason", "unknown")
                cost = checkpoint.get("cost_usd", 0)
                last = checkpoint.get("last_prompt", "")
                files = checkpoint.get("output_files", [])

                console.print(
                    Panel(
                        f"[bold yellow]Sessão anterior interrompida[/bold yellow] "
                        f"({reason.replace('_', ' ')})\n"
                        f"[dim]Custo: ${cost:.4f} | Último prompt: {last[:80]}{'...' if len(last) > 80 else ''}[/dim]\n"
                        f"[dim]Arquivos gerados: {len(files)}[/dim]\n\n"
                        f'[bold]Digite [cyan]"continuar"[/cyan] para retomar ou qualquer outra coisa para nova sessão.[/bold]',
                        title="🔄 Checkpoint Detectado",
                        border_style="yellow",
                    )
                )

            while True:
                # T1.1: reset do flag a cada iteração — estado potencialmente
                # novo significa que _emergency_checkpoint deve salvar de novo
                # se o processo morrer abruptamente antes do próximo save explícito.
                _checkpoint_saved_for_session = False
                try:
                    # Input com idle timeout: detecta inatividade e oferece reset
                    try:
                        user_input = await asyncio.wait_for(
                            asyncio.get_event_loop().run_in_executor(
                                None,
                                lambda: console.input("[bold green]Você:[/bold green] ").strip(),
                            ),
                            timeout=settings.idle_timeout_minutes * 60
                            if settings.idle_timeout_minutes > 0
                            else None,
                        )
                    except asyncio.TimeoutError:
                        # Salvar checkpoint antes do reset por inatividade
                        if _session_state["last_prompt"]:
                            save_checkpoint(
                                last_prompt=_session_state["last_prompt"],
                                reason="idle_timeout",
                                cost_usd=_session_state["total_cost"],
                                turns=_session_state["total_turns"],
                                session_id=_session_id,
                            )
                            _checkpoint_saved_for_session = True
                        console.print(
                            f"\n[yellow]⏰ Inatividade detectada "
                            f"({settings.idle_timeout_minutes} min). "
                            f"Resetando sessão para economizar tokens...[/yellow]"
                        )
                        if _session_state["last_prompt"]:
                            console.print(
                                "[dim]💾 Checkpoint salvo. Digite [bold]continuar[/bold] "
                                "para retomar.[/dim]"
                            )
                        reset_session_counters()
                        _session_state["last_prompt"] = ""
                        _session_state["total_cost"] = 0.0
                        _session_state["total_turns"] = 0
                        await client.disconnect()
                        await client.connect()
                        checkpoint = load_checkpoint()
                        logger.info(
                            f"Sessão resetada automaticamente por idle "
                            f"({settings.idle_timeout_minutes} min)."
                        )
                        continue

                    if not user_input:
                        continue

                    # --- Comandos internos do CLI ---
                    if user_input.lower() in ("sair", "exit", "quit", "q", "/exit"):
                        # T1.1: salva checkpoint em saída normal — até hoje a sessão
                        # perdia contexto nesse caminho; agora é recuperável via `continuar`.
                        if _session_state["last_prompt"]:
                            save_checkpoint(
                                last_prompt=_session_state["last_prompt"],
                                reason="normal_exit",
                                cost_usd=_session_state["total_cost"],
                                turns=_session_state["total_turns"],
                                session_id=_session_id,
                            )
                            _checkpoint_saved_for_session = True
                            console.print(
                                "[dim]💾 Checkpoint salvo. Digite [bold]continuar[/bold] "
                                "na próxima sessão para retomar.[/dim]"
                            )
                        # Flush de memória antes de encerrar
                        try:
                            n_mem = flush_session_memories(session_id="interactive")
                            if n_mem > 0:
                                console.print(
                                    f"[dim]🧠 {n_mem} memórias capturadas desta sessão.[/dim]"
                                )
                        except Exception as e:
                            logger.debug(f"Flush de memória ignorado: {e}")
                        console.print("\n[bold cyan]Encerrando sessão. Até a próxima![/bold cyan]")
                        break

                    if user_input.lower() in ("limpar", "clear", "reset"):
                        # Flush de memória antes de limpar
                        try:
                            flush_session_memories(session_id="interactive")
                        except Exception:
                            pass
                        # Salvar checkpoint antes de limpar
                        if _session_state["last_prompt"]:
                            save_checkpoint(
                                last_prompt=_session_state["last_prompt"],
                                reason="user_reset",
                                cost_usd=_session_state["total_cost"],
                                turns=_session_state["total_turns"],
                                session_id=_session_id,
                            )
                            _checkpoint_saved_for_session = True
                            console.print(
                                "[dim]💾 Checkpoint salvo. Use [bold]continuar[/bold] "
                                "na próxima sessão para retomar.[/dim]\n"
                            )
                        console.clear()
                        print_banner()
                        reset_session_counters()
                        _geral_history.clear()  # Limpa histórico do /geral
                        _session_state["last_prompt"] = ""
                        _session_state["total_cost"] = 0.0
                        _session_state["total_turns"] = 0
                        await client.disconnect()
                        await client.connect()
                        # Verificar checkpoint recém-salvo
                        checkpoint = load_checkpoint()
                        if checkpoint:
                            console.print(
                                Panel(
                                    "[bold yellow]Sessão anterior salva.[/bold yellow]\n"
                                    '[bold]Digite [cyan]"continuar"[/cyan] para retomar '
                                    "ou qualquer outra coisa para nova sessão.[/bold]",
                                    title="🔄 Checkpoint Disponível",
                                    border_style="yellow",
                                )
                            )
                        logger.info(
                            "Sessão reiniciada pelo usuário (contadores de custo resetados)."
                        )
                        continue

                    if user_input.lower() in ("/help", "help", "ajuda"):
                        console.print(get_help_text())
                        continue

                    # --- Retomar sessão anterior via checkpoint ---
                    if (
                        user_input.lower() in ("continuar", "continue", "retomar", "resume")
                        and checkpoint
                    ):
                        resume_prompt = build_resume_prompt(checkpoint)
                        clear_checkpoint()
                        checkpoint = None  # Consumido
                        console.print("[bold cyan]🔄 Retomando sessão anterior...[/bold cyan]\n")
                        _append_transcript_turn(
                            session_id=_session_id,
                            role="user",
                            content=user_input,
                            metadata={"session_type": "resume"},
                        )
                        await client.query(resume_prompt)
                        result_metrics = await _stream_response(
                            client,
                            prompt="[RESUME] " + resume_prompt[:100],
                            session_type="resume",
                            session_id=_session_id,
                        )
                        _session_state["last_prompt"] = resume_prompt[:200]
                        _session_state["total_cost"] += result_metrics.get("cost", 0)
                        _session_state["total_turns"] += result_metrics.get("turns", 0)
                        continue

                    # Se havia checkpoint mas o usuário não quis continuar, limpar
                    if checkpoint:
                        clear_checkpoint()
                        checkpoint = None

                    console.print()

                    # --- DOMA: Slash Commands Parsing ---
                    command_result = parse_command(user_input)

                    if command_result:
                        doma_prompt = command_result.doma_prompt
                        _session_type = command_result.command.lstrip("/")
                        console.print(command_result.display_message)
                        logger.info(
                            f"Slash command: {command_result.command} "
                            f"(mode={command_result.doma_mode}, agent={command_result.agent})"
                        )
                    else:
                        doma_prompt = user_input
                        _session_type = "interactive"

                    # --- /memory → Gerenciamento local de memória, sem Supervisor ---
                    if command_result and command_result.command == "/memory":
                        await _handle_memory_command(user_input)
                        continue

                    # --- /sessions → Lista sessões registradas (local, sem Supervisor) ---
                    if command_result and command_result.command == "/sessions":
                        from commands.sessions import handle_sessions_command

                        handle_sessions_command(user_input, console)
                        continue

                    # --- /resume <id>|last → Retoma sessão anterior via transcript ---
                    if command_result and command_result.command == "/resume":
                        from commands.sessions import (
                            build_resume_prompt_for_session,
                            find_last_session_id,
                        )

                        parts = user_input.split(maxsplit=1)
                        arg = parts[1].strip() if len(parts) > 1 else "last"
                        target_id: str | None
                        if arg.lower() == "last":
                            target_id = find_last_session_id()
                            if not target_id:
                                console.print(
                                    "[yellow]Nenhuma sessão disponível para retomar. "
                                    "Use `/sessions` para listar.[/yellow]"
                                )
                                continue
                        else:
                            target_id = arg

                        resume_prompt = build_resume_prompt_for_session(target_id)
                        if not resume_prompt:
                            console.print(
                                f"[yellow]Sessão `{target_id}` não encontrada "
                                f"ou sem dados para retomar.[/yellow]"
                            )
                            continue

                        console.print(
                            f"[bold cyan]🔄 Retomando sessão `{target_id}` "
                            f"({len(resume_prompt)} chars de contexto)...[/bold cyan]\n"
                        )
                        _append_transcript_turn(
                            session_id=_session_id,
                            role="user",
                            content=user_input,
                            metadata={
                                "session_type": "resume",
                                "command": "/resume",
                                "resumed_from": target_id,
                            },
                        )
                        await client.query(resume_prompt)
                        result_metrics = await _stream_response(
                            client,
                            prompt=f"[RESUME {target_id}] " + resume_prompt[:80],
                            session_type="resume",
                            session_id=_session_id,
                        )
                        _session_state["last_prompt"] = f"/resume {target_id}"
                        _session_state["total_cost"] += result_metrics.get("cost", 0)
                        _session_state["total_turns"] += result_metrics.get("turns", 0)
                        continue

                    # --- /geral → Haiku direto, sem Supervisor ---
                    if command_result and command_result.command == "/geral":
                        result_metrics = await _stream_geral(
                            user_input, session_type="geral", session_id=_session_id
                        )
                        _session_state["last_prompt"] = user_input
                        _session_state["total_cost"] += result_metrics.get("cost", 0)
                        continue

                    # --- /party → DOMA Party Mode: múltiplos agentes em paralelo ---
                    if command_result and command_result.command == "/party":
                        result_metrics = await _stream_party(user_input, session_id=_session_id)
                        _session_state["last_prompt"] = user_input
                        _session_state["total_cost"] += result_metrics.get("cost", 0)
                        continue

                    # --- /monitor → Business Monitor autônomo (on/off/status/run/ask) ---
                    if command_result and command_result.command == "/monitor":
                        from commands.monitor import run_monitor_command

                        args_str = user_input[len("/monitor") :].strip()
                        response = await run_monitor_command(
                            args_str, console=console, client=client
                        )
                        console.print(Markdown(response))
                        continue

                    # Ativa thinking apenas para DOMA Full (/plan) — planejamento complexo
                    if command_result and command_result.doma_mode == "full":
                        options.thinking = {"type": "enabled", "budget_tokens": 8000}
                    else:
                        options.thinking = {"type": "disabled"}

                    # --- Memory Retrieval: injeta memórias relevantes no system prompt ---
                    if settings.memory_enabled and settings.memory_retrieval_enabled:
                        global _decay_applied
                        try:
                            # Cache por query hash (TTL 60s) — evita Sonnet lateral redundante
                            query_hash = hashlib.md5(
                                doma_prompt[:200].encode(), usedforsecurity=False
                            ).hexdigest()
                            cached = _retrieval_cache.get(query_hash)
                            if cached and (time.monotonic() - cached[1]) < _RETRIEVAL_CACHE_TTL:
                                options.system_prompt = cached[0]
                                logger.debug("Memory retrieval: usando contexto cacheado.")
                            else:
                                enriched_prompt = inject_memory_context(
                                    query=doma_prompt,
                                    system_prompt=options.system_prompt or "",
                                    apply_decay=not _decay_applied,
                                )
                                _decay_applied = True
                                if enriched_prompt != (options.system_prompt or ""):
                                    options.system_prompt = enriched_prompt
                                    _retrieval_cache[query_hash] = (
                                        enriched_prompt,
                                        time.monotonic(),
                                    )
                                    logger.debug(
                                        "System prompt enriquecido com memórias relevantes."
                                    )
                        except Exception as e:
                            logger.warning(f"Memory retrieval falhou: {e}")

                    # T4.1: registrar o turno do usuário no transcript ANTES de enviar
                    # para o Supervisor. Assim, mesmo se o turno quebrar (erro/budget),
                    # o prompt original fica no histórico da sessão.
                    _append_transcript_turn(
                        session_id=_session_id,
                        role="user",
                        content=user_input,
                        metadata={
                            "session_type": _session_type,
                            "command": command_result.command if command_result else None,
                        },
                    )

                    # --- Enviar para o Supervisor e processar com feedback visual ---
                    await client.query(doma_prompt)
                    result_metrics = await _stream_response(
                        client,
                        prompt=doma_prompt,
                        session_type=_session_type,
                        session_id=_session_id,
                    )

                    # Atualizar estado da sessão para checkpoint
                    _session_state["last_prompt"] = doma_prompt
                    _session_state["total_cost"] += result_metrics.get("cost", 0)
                    _session_state["total_turns"] += result_metrics.get("turns", 0)

                except KeyboardInterrupt:
                    console.print("\n[yellow]Interrompido. Digite 'sair' para encerrar.[/yellow]")
                    continue

                except BudgetExceededError as e:
                    # Flush de memória antes do checkpoint
                    try:
                        flush_session_memories(session_id="interactive")
                    except Exception:
                        pass
                    # Salvar checkpoint automaticamente ao exceder budget
                    save_checkpoint(
                        last_prompt=_session_state["last_prompt"],
                        reason="budget_exceeded",
                        cost_usd=_session_state["total_cost"],
                        turns=_session_state["total_turns"],
                        session_id=_session_id,
                    )
                    _checkpoint_saved_for_session = True
                    console.print(f"\n[bold red]Orçamento excedido:[/bold red] {e.message}")
                    console.print(
                        "[bold yellow]💾 Checkpoint salvo automaticamente![/bold yellow]\n"
                        "[dim]Na próxima sessão, digite [bold]continuar[/bold] para retomar "
                        "de onde parou.[/dim]\n"
                        "[dim]Ou aumente MAX_BUDGET_USD no .env para mais orçamento.[/dim]\n"
                    )
                    logger.warning(f"Budget exceeded: {e.message}")
                    continue

                except MCPConnectionError as e:
                    console.print(
                        f"\n[bold red]Erro de conexão MCP:[/bold red] {e.message}\n"
                        f"[dim]Plataforma: {e.platform}. Verifique credenciais e conectividade.[/dim]\n"
                    )
                    logger.error(f"MCP connection error: {e.message}")
                    continue

                except DataAgentsError as e:
                    console.print(f"\n[bold red]Erro do sistema:[/bold red] {e.message}\n")
                    logger.error(f"DataAgentsError: {e.message}", exc_info=True)
                    continue

                except Exception as e:
                    console.print(f"\n[bold red]Erro inesperado:[/bold red] {e}\n")
                    logger.error(f"Unexpected error: {e}", exc_info=True)
                    continue
    except Exception as e:
        # Captura erros durante o encerramento do SDK (ex: hooks de teardown)
        # Erros de teardown não devem ser exibidos ao usuário — apenas logados em debug
        logger.debug(f"Erro no encerramento do SDK (ignorado): {e}")
    finally:
        # Ch.12 — Session Lifecycle: flush de memória e log de estatísticas de uso
        on_session_end(_session_id)


async def run_single_query(prompt: str) -> None:
    """Executa uma única solicitação e exibe o resultado."""
    setup_logging(log_level=settings.log_level, enable_console=False)

    options = build_supervisor_options()
    options.include_partial_messages = True

    current_tool: str | None = None

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, StreamEvent):
            event = message.event
            event_type = event.get("type", "")
            if event_type == "content_block_start":
                block = event.get("content_block", {})
                if block.get("type") == "tool_use":
                    current_tool = block.get("name", "unknown")
                    label = _get_tool_label(current_tool)
                    console.print(f"[dim]{label}...[/dim]")
            elif event_type == "content_block_stop":
                current_tool = None

        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    console.print(Markdown(block.text))

        elif isinstance(message, ResultMessage):
            if message.total_cost_usd:
                console.print(
                    f"\n[dim]Custo: ${message.total_cost_usd:.4f} | "
                    f"Turns: {message.num_turns or 0}[/dim]"
                )
            log_session_result(message, prompt_preview=prompt[:100], session_type="single_query")


def _configure_local_mode() -> None:
    """
    Ativa o modo local: roteia agentes T2/T3 para Ollama via LiteLLM proxy.

    O LiteLLM proxy (localhost:4000) age como bridge entre o Claude Agent SDK
    (protocolo Anthropic) e o Ollama (protocolo OpenAI). O campo
    `anthropic_base_url` redireciona o SDK para o proxy local.

    T1 permanece na Anthropic por padrão — agentes críticos (sql-expert,
    spark-expert, pipeline-architect, migration-expert) onde qualidade máxima
    é mais importante do que custo.

    Setup necessário (rodar antes de iniciar com --local):
        pip install litellm
        ollama pull qwen2.5-coder:32b
        litellm --model ollama_chat/qwen2.5-coder:32b --port 4000
    """
    # Redireciona o Anthropic SDK para o proxy LiteLLM local
    settings.anthropic_base_url = settings.local_llm_proxy_url

    # Monta o tier_model_map apenas para os tiers com modelo local definido
    local_map: dict[str, str] = {}
    if settings.local_llm_model_t1:
        local_map["T1"] = settings.local_llm_model_t1
    if settings.local_llm_model_t2:
        local_map["T2"] = settings.local_llm_model_t2
    if settings.local_llm_model_t3:
        local_map["T3"] = settings.local_llm_model_t3

    # Merge com tier_model_map existente (.env), priorizando .env
    merged = {**local_map, **settings.tier_model_map}
    settings.tier_model_map = merged

    console.print(
        Panel(
            f"[bold green]🦙 Modo Local Ativado[/bold green]\n\n"
            f"[dim]Proxy:[/dim]  {settings.local_llm_proxy_url}\n"
            f"[dim]T1   :[/dim]  {local_map.get('T1', '[dim]Anthropic (mantido)[/dim]')}\n"
            f"[dim]T2   :[/dim]  {local_map.get('T2', '[dim]não configurado[/dim]')}\n"
            f"[dim]T3   :[/dim]  {local_map.get('T3', '[dim]não configurado[/dim]')}\n\n"
            "[yellow]⚠️  Certifique-se que Ollama e LiteLLM estão rodando.[/yellow]",
            title="[bold]Local LLM Mode[/bold]",
            border_style="green",
        )
    )


def main() -> None:
    """Entry point principal do Data Agents.

    Flags disponíveis:
      --local   Roteia agentes T2/T3 para Ollama via LiteLLM proxy (custo zero).
                Requer: ollama + litellm rodando localmente.

    Exemplos:
      python main.py                        # modo Anthropic (padrão)
      python main.py --local                # modo local interativo
      python main.py --local "liste tabelas"  # single-query em modo local
    """
    args = sys.argv[1:]

    # Detecta e remove a flag --local antes de processar o prompt
    use_local = "--local" in args
    if use_local:
        args = [a for a in args if a != "--local"]
        _configure_local_mode()

    if args:
        prompt = " ".join(args)
        asyncio.run(run_single_query(prompt))
    else:
        asyncio.run(run_interactive())


if __name__ == "__main__":
    main()
