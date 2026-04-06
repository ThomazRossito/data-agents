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
import logging
import sys

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

logger = logging.getLogger("data_agents.main")
console = Console()


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
        "[dim]Comandos: [bold]sair[/bold] para encerrar | [bold]limpar[/bold] para nova sessão | [bold]/help[/bold] para ajuda[/dim]"
    )
    console.print(
        "[dim]Slash: [bold]/plan[/bold] | [bold]/sql[/bold] | [bold]/spark[/bold] | "
        "[bold]/pipeline[/bold] | [bold]/fabric[/bold] | [bold]/health[/bold] | "
        "[bold]/status[/bold] | [bold]/review[/bold][/dim]\n"
    )


async def _stream_response(client: ClaudeSDKClient) -> None:
    """
    Processa o stream de resposta do agente com feedback visual em tempo real.

    Exibe:
      - Spinner animado enquanto o agente está pensando
      - Notificação imediata quando uma tool call é iniciada
      - Texto da resposta final em Markdown
      - Resumo de custo/turns/tempo ao finalizar
    """
    # Estado do streaming
    current_tool: str | None = None
    tool_input_buffer: str = ""
    response_started: bool = False
    turn_count: int = 0
    live_status: Live | None = None

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
                    label = _get_tool_label(current_tool)
                    _stop_spinner(live_status)
                    live_status = _start_spinner(f"{label}...")

            # Acumulando input da tool (para detectar nome do agente)
            elif event_type == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "input_json_delta":
                    tool_input_buffer += delta.get("partial_json", "")
                    # Quando for Agent tool, tenta mostrar o nome do agente assim que disponível
                    if current_tool == "Agent" and "agent_name" in tool_input_buffer:
                        label = _get_agent_label(tool_input_buffer)
                        _stop_spinner(live_status)
                        live_status = _start_spinner(label)

            # Tool call finalizada
            elif event_type == "content_block_stop":
                if current_tool:
                    current_tool = None
                    tool_input_buffer = ""
                    turn_count += 1
                    _stop_spinner(live_status)
                    live_status = _start_spinner(f"Agente processando... (etapa {turn_count})")

        # ── AssistantMessage: resposta final completa ─────────────────
        elif isinstance(message, AssistantMessage):
            _stop_spinner(live_status)
            live_status = None

            for block in message.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    if not response_started:
                        console.print("[bold blue]Agente:[/bold blue]")
                        response_started = True
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

    # Garante que o spinner seja parado em qualquer caso
    _stop_spinner(live_status)


async def run_interactive() -> None:
    """Loop interativo com histórico de sessão mantido entre mensagens."""

    # ── 1. Banner primeiro — antes de qualquer inicialização ─────────────────
    print_banner()

    # ── 2. Logging + diagnósticos aparecem DEPOIS do banner ──────────────────
    setup_logging(log_level=settings.log_level)
    if hasattr(settings, "startup_diagnostics"):
        settings.startup_diagnostics()

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
    try:
        async with ClaudeSDKClient(options=options) as client:
            while True:
                try:
                    user_input = console.input("[bold green]Você:[/bold green] ").strip()

                    if not user_input:
                        continue

                    # --- Comandos internos do CLI ---
                    if user_input.lower() in ("sair", "exit", "quit", "q", "/exit"):
                        console.print("\n[bold cyan]Encerrando sessão. Até a próxima![/bold cyan]")
                        break

                    if user_input.lower() in ("limpar", "clear", "reset"):
                        console.clear()
                        print_banner()
                        await client.disconnect()
                        await client.connect()
                        logger.info("Sessão reiniciada pelo usuário.")
                        continue

                    if user_input.lower() in ("/help", "help", "ajuda"):
                        console.print(get_help_text())
                        continue

                    console.print()

                    # --- BMAD-METHOD: Slash Commands Parsing ---
                    command_result = parse_command(user_input)

                    if command_result:
                        bmad_prompt = command_result.bmad_prompt
                        console.print(command_result.display_message)
                        logger.info(
                            f"Slash command: {command_result.command} "
                            f"(mode={command_result.bmad_mode}, agent={command_result.agent})"
                        )
                        # Ativa thinking apenas para BMAD Full (/plan) — planejamento complexo
                        if command_result.bmad_mode == "full":
                            options.thinking = {"type": "enabled", "budget_tokens": 8000}
                        else:
                            options.thinking = {"type": "disabled"}
                    else:
                        # Texto livre → BMAD Auto (Supervisor decide), sem thinking extra
                        bmad_prompt = user_input
                        options.thinking = {"type": "disabled"}

                    # --- Enviar para o Supervisor e processar com feedback visual ---
                    await client.query(bmad_prompt)
                    await _stream_response(client)

                except KeyboardInterrupt:
                    console.print("\n[yellow]Interrompido. Digite 'sair' para encerrar.[/yellow]")
                    continue

                except BudgetExceededError as e:
                    console.print(f"\n[bold red]Orçamento excedido:[/bold red] {e.message}")
                    console.print(
                        "[dim]Aumente MAX_BUDGET_USD no .env ou inicie nova sessão.[/dim]\n"
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


def main() -> None:
    """Entry point principal do Data Agents."""
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        asyncio.run(run_single_query(prompt))
    else:
        asyncio.run(run_interactive())


if __name__ == "__main__":
    main()
