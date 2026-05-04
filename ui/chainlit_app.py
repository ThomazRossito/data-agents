"""
ui/chainlit_app.py — Interface Chainlit para Data Agents

Dois modos de operação:

  Modo 1 — Data Agents:
    Supervisor completo com todos os agentes especialistas.
    Suporta slash commands (/sql, /spark, /dbt, /quality, etc.).
    Mostra cl.Step() para cada delegação e tool call em tempo real.

  Modo 2 — Dev Assistant:
    Claude direto (sem Supervisor), ferramentas de desenvolvimento habilitadas.
    Ferramentas: Read, Write, Bash, Grep, Glob.
    Mantém histórico de conversa para follow-ups.
    Usa settings.default_model (Bedrock) — custo zero pelo acordo da empresa.

Seleção de modo via cl.Action no início do chat.
Troca de modo a qualquer momento com /modo.

Iniciar:
    ./start_chainlit.sh
    chainlit run ui/chainlit_app.py --port 8503
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import chainlit as cl

# Chainlit chama load_dotenv() ao ser importado e injeta ANTHROPIC_API_KEY no
# os.environ a partir do .env. Isso força o subprocess `claude` (do SDK) a usar
# a chave de API em vez do OAuth do Claude Code — quebrando o fluxo quando a
# chave pertence a uma org sem saldo. Removemos aqui para que o CLI caia no
# OAuth, igual ao main.py (que não importa chainlit).
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("ANTHROPIC_BASE_URL", None)

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    UserMessage,
    query as sdk_query,
)
from claude_agent_sdk.types import StreamEvent

# ── Garante que a raiz do projeto está no path ────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from agents.loader import preload_registry  # noqa: E402
from commands.parser import parse_command  # noqa: E402
from ui.ui_config import (  # noqa: E402
    COMMAND_GROUPS as _COMMAND_GROUPS,
    agent_display_name as _agent_author_fn,
    enrich_tool_label as _enrich_tool_label,
    tool_label as _tool_label,
)

# ── Tier lookup para labels de delegação ─────────────────────────────────────
_AGENT_TIERS: dict[str, str] = {
    name: meta.tier for name, meta in preload_registry().items() if meta.tier
}

# ── Constantes ────────────────────────────────────────────────────────────────
MODE_SUPERVISOR = "supervisor"
MODE_DEV = "dev"

# System prompt do Dev Assistant — carregado inline
_DEV_SYSTEM_PROMPT = """\
Você é o **Dev Assistant** do projeto Data Agents.

## Sobre o Projeto
Sistema multi-agente construído sobre o Claude Agent SDK + MCP.
Orquestra agentes especialistas em Engenharia, Qualidade, Governança e Análise de Dados.
Stack: Python 3.12, pydantic-settings, claude-agent-sdk, Streamlit, Chainlit.
Plataformas alvo: Databricks (Unity Catalog, DLT, LakeFlow) + Microsoft Fabric.

## Estrutura de Diretórios
- agents/registry/     — definições .md dos agentes (frontmatter YAML + prompt)
- agents/loader.py     — carrega agentes do registry dinamicamente
- agents/supervisor.py — orquestra agentes + MCP + hooks
- mcp_servers/         — configuração dos MCP servers por plataforma
- config/settings.py   — Pydantic BaseSettings + credenciais
- commands/parser.py   — registry de slash commands DOMA
- hooks/               — PreToolUse / PostToolUse hooks
- kb/                  — Knowledge Bases por domínio
- tests/               — pytest (mínimo 80% cobertura)
- ui/chainlit_app.py   — interface Chainlit atual

## Papel
Assistente de desenvolvimento para tarefas no próprio projeto:
código Python, debugging, refatoração, testes, análise de arquivos, scripts.

Não acesse MCPs de plataformas de dados (Databricks, Fabric).
Para tarefas de pipeline, SQL ou PySpark, sugira o Modo Data Agents.

Always respond in English (EN-US). Use code blocks with syntax highlighting.
Seja direto e objetivo — sem preambles desnecessários.
"""

# ── Helpers ───────────────────────────────────────────────────────────────────
# _tool_label, _enrich_tool_label importados de ui/config.py


def _agent_author(raw_name: str) -> str:
    """Retorna o nome de exibição do agente para cl.Message(author=...)."""
    return _agent_author_fn(raw_name)


def _format_tool_result(content: str | list | None) -> str:
    """Formata o conteúdo retornado por uma tool call para exibição no cl.Step."""
    _MAX_CHARS = 3000
    if content is None:
        return ""
    if isinstance(content, str):
        if len(content) > _MAX_CHARS:
            return content[:_MAX_CHARS] + f"\n\n*… truncado ({len(content)} chars)*"
        return content
    if isinstance(content, list):
        parts = [
            item.get("text", "") if isinstance(item, dict) and item.get("type") == "text" else ""
            for item in content
        ]
        result = "\n".join(p for p in parts if p)
        if len(result) > _MAX_CHARS:
            return result[:_MAX_CHARS] + f"\n\n*… truncado ({len(result)} chars)*"
        return result or ""
    return str(content)[:_MAX_CHARS]


def _build_dev_options(stderr_lines: list[str] | None = None) -> ClaudeAgentOptions:
    """
    ClaudeAgentOptions para o Dev Assistant.

    Usa settings.default_model (Bedrock) — custo zero pelo acordo da empresa.
    Ferramentas de desenvolvimento habilitadas. Zero MCPs de plataforma.

    stderr_lines: lista mutável onde as linhas do stderr do processo serão
    acumuladas — útil para exibir o erro real quando o processo falha com
    exit code 1 (por padrão o SDK só retorna "Check stderr output for details").
    """
    from config.settings import settings  # importação local — evita circular import

    opts = ClaudeAgentOptions(
        cwd=ROOT,
        model=settings.default_model,
        system_prompt=_DEV_SYSTEM_PROMPT,
        allowed_tools=["Read", "Write", "Bash", "Grep", "Glob"],
        agents=None,
        mcp_servers={},
        max_turns=15,
        permission_mode="bypassPermissions",
    )
    opts.include_partial_messages = True
    if stderr_lines is not None:
        opts.stderr = stderr_lines.append  # type: ignore[assignment]
    return opts


def _commands_help_text() -> str:
    """Formata comandos disponíveis para o welcome message do Supervisor."""
    lines: list[str] = []
    for group, cmds in _COMMAND_GROUPS.items():
        lines.append(f"\n**{group}:** " + "  ".join(f"`{c}`" for c in cmds))
    return "".join(lines)


# ── Step manager — abre/fecha cl.Step() durante streaming ────────────────────


class _StepManager:
    """
    Gerencia cl.Step() durante o loop de streaming.

    Dois modos de fechamento:
      - close(output): fecha imediatamente com output fornecido (Agent tool e erros)
      - park(tool_use_id): estaciona o step aguardando o ToolResultBlock no UserMessage
        → quando receive_result(tool_use_id, content) for chamado, fecha com o conteúdo real

    Múltiplos steps podem ficar estacionados simultaneamente (tool calls em paralelo).
    """

    def __init__(self) -> None:
        self._step: cl.Step | None = None  # step "ativo" (ainda acumulando input)
        self._start: float = 0.0
        # steps estacionados aguardando resultado: tool_use_id → (step, start_time)
        self._parked: dict[str, tuple[cl.Step, float]] = {}

    async def open(self, name: str, step_type: str = "tool") -> None:
        """Abre um novo Step. Fecha o anterior se ainda estiver aberto (sem resultado)."""
        await self.close()
        self._step = cl.Step(name=name, type=step_type)
        self._start = time.monotonic()
        await self._step.send()

    async def rename(self, name: str) -> None:
        """Atualiza o nome do Step ativo sem fechar."""
        if self._step is None:
            return
        self._step.name = name
        await self._step.update()

    async def close(self, output: str = "") -> None:
        """Fecha o Step ativo imediatamente (usado para Agent tool e erros)."""
        if self._step is None:
            return
        elapsed = time.monotonic() - self._start
        self._step.output = output or f"Concluído em {elapsed:.1f}s"
        await self._step.update()
        self._step = None
        self._start = 0.0

    async def park(self, tool_use_id: str) -> None:
        """
        Estaciona o step ativo aguardando o resultado da tool.
        O step permanece visível mas sem output final até receive_result() ser chamado.
        """
        if self._step is None:
            return
        self._parked[tool_use_id] = (self._step, self._start)
        self._step = None
        self._start = 0.0

    async def receive_result(self, tool_use_id: str, content: str) -> None:
        """Fecha um step estacionado com o conteúdo real retornado pela tool."""
        entry = self._parked.pop(tool_use_id, None)
        if entry is None:
            return
        step, start = entry
        elapsed = time.monotonic() - start
        step.output = content or f"Concluído em {elapsed:.1f}s"
        await step.update()

    async def close_all_parked(self) -> None:
        """Fecha todos os steps estacionados sem resultado (fallback no fim do stream)."""
        for tool_use_id, (step, start) in list(self._parked.items()):
            elapsed = time.monotonic() - start
            step.output = f"Concluído em {elapsed:.1f}s"
            await step.update()
        self._parked.clear()

    async def close_error(self, error: str) -> None:
        """Fecha o Step ativo com mensagem de erro."""
        if self._step is None:
            return
        self._step.output = f"❌ {error}"
        await self._step.update()
        self._step = None


# ── Cache de módulo do Supervisor ────────────────────────────────────────────
# O ClaudeSDKClient e os MCP servers são processos pesados (~3-5s de cold start).
# Mantê-los em um cache de módulo evita reconectar a cada refresh do browser —
# o cl.user_session é destruído no refresh, mas este cache persiste enquanto o
# processo Chainlit estiver vivo.
#
# Acesso protegido por asyncio.Lock: garante que apenas uma sessão conecta de
# cada vez (evita race condition se dois tabs abrirem ao mesmo tempo).

_supervisor_cache: dict = {}
# Campos do cache:
#   "client"          → ClaudeSDKClient conectado
#   "options"         → ClaudeAgentOptions (mutável por query)
#   "needs_reconnect" → True quando budget foi excedido — força reconexão na próxima ativação
#   "created_at"      → timestamp float (time.monotonic) — para TTL de 2h
_supervisor_lock = asyncio.Lock()

# TTL do cache do Supervisor: 2 horas. Após este período a conexão é renovada
# para evitar vazamento de memória em instâncias de longa duração.
_SUPERVISOR_CACHE_TTL = 7200.0


async def _get_or_create_supervisor() -> dict:
    """
    Retorna o cliente do Supervisor do cache, criando-o na primeira chamada.

    Thread-safe via asyncio.Lock. Reconecta se:
      - `needs_reconnect` está marcado (budget excedido)
      - O cache tem mais de 2h (TTL expirado — evita vazamento de memória)
    """
    from agents.supervisor import build_supervisor_options
    from claude_agent_sdk import ClaudeSDKClient

    async with _supervisor_lock:
        # Expirar cache após TTL
        created_at = _supervisor_cache.get("created_at", 0.0)
        ttl_expired = (time.monotonic() - created_at) > _SUPERVISOR_CACHE_TTL

        if (ttl_expired or _supervisor_cache.get("needs_reconnect")) and _supervisor_cache.get(
            "client"
        ):
            try:
                await _supervisor_cache["client"].disconnect()
            except Exception:
                pass
            _supervisor_cache.clear()

        if _supervisor_cache.get("client") is None:
            options = build_supervisor_options(enable_thinking=False)
            options.include_partial_messages = True
            client = ClaudeSDKClient(options=options)
            await client.connect()
            _supervisor_cache["client"] = client
            _supervisor_cache["options"] = options
            _supervisor_cache["needs_reconnect"] = False
            _supervisor_cache["created_at"] = time.monotonic()

    return _supervisor_cache


async def _invalidate_supervisor_cache() -> None:
    """Desconecta e remove o cliente do cache (ex: ao trocar de modo)."""
    async with _supervisor_lock:
        client = _supervisor_cache.pop("client", None)
        _supervisor_cache.pop("options", None)
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass


# ── Activação dos modos ───────────────────────────────────────────────────────


_BANNER = """\
**DATA AGENTS**
Sistema Multi-Agentes · Databricks + Microsoft Fabric
Powered by Claude Agent SDK + MCP

**Desenvolvido por:**
Thomaz Antonio Rossito Neto
Specialist Data & AI Solutions Architect | Center of Excellence CoE @CI&T
**LinkedIn:** https://www.linkedin.com/in/thomaz-antonio-rossito-neto/
**GitHub:** https://github.com/ThomazRossito/
"""

# Porta do dashboard de monitoramento (Streamlit — start.sh)
_MONITOR_PORT = 8501


async def _show_mode_selection() -> None:
    """Apresenta banner de boas-vindas e botões de seleção de modo."""
    await cl.Message(content=_BANNER, author="Sistema").send()

    actions = [
        cl.Action(
            name="select_supervisor",
            label="🤖 Data Agents",
            payload={"value": "supervisor"},
            description="Supervisor + 8 agentes especialistas (SQL, Spark, dbt, Qualidade...)",
        ),
        cl.Action(
            name="select_dev",
            label="💻 Dev Assistant",
            payload={"value": "dev"},
            description="Claude direto com ferramentas de desenvolvimento (Read, Write, Bash...)",
        ),
        cl.Action(
            name="open_monitoring",
            label="📊 Monitoramento",
            payload={"value": "monitoring"},
            description=f"Abre o dashboard de monitoramento (porta {_MONITOR_PORT})",
        ),
    ]
    await cl.Message(
        content=(
            "**Selecione o modo de operação:**\n\n"
            "- **🤖 Data Agents** — Supervisor com agentes especialistas, slash commands e MCPs de plataforma\n"
            "- **💻 Dev Assistant** — Claude direto para tarefas de desenvolvimento no projeto (Bedrock, custo zero)\n"
            f"- **📊 Monitoramento** — Dashboard de custos e métricas de sessão (porta {_MONITOR_PORT})\n\n"
            "*(Troque de modo a qualquer momento com `/modo`)*"
        ),
        actions=actions,
    ).send()


async def _activate_supervisor() -> None:
    """
    Ativa o modo Supervisor para esta sessão do Chainlit.

    Usa o cache de módulo (_get_or_create_supervisor) — na primeira ativação
    conecta os MCP servers (~3-5s); nas seguintes reutiliza o cliente existente
    (~0s, mesmo após refresh do browser).
    """
    # Só exibe spinner se for a primeira conexão (cache vazio)
    is_cold_start = _supervisor_cache.get("client") is None
    loading_msg = None
    if is_cold_start:
        loading_msg = await cl.Message(
            content="⏳ Inicializando Supervisor e MCP servers (primeira vez)..."
        ).send()

    try:
        cached = await _get_or_create_supervisor()
        client = cached["client"]
        options = cached["options"]

        cl.user_session.set("mode", MODE_SUPERVISOR)
        cl.user_session.set("supervisor_client", client)
        cl.user_session.set("supervisor_options", options)

        if loading_msg:
            await loading_msg.remove()

        warm_note = (
            "" if is_cold_start else "\n\n*(MCP servers reutilizados do cache — sem cold start)*"
        )
        await cl.Message(
            content=(
                "✅ **Modo: Data Agents** ativado.\n\n"
                f"{_commands_help_text()}\n\n"
                "---\n"
                "💡 **Dica:** Use `/plan <objetivo>` para o fluxo completo DOMA com PRD e aprovação.\n"
                f"Digite `/modo` a qualquer momento para trocar de modo.{warm_note}"
            )
        ).send()

        # ── Checkpoint: notifica se há sessão anterior interrompida ──────────
        from hooks.checkpoint import load_checkpoint

        checkpoint = load_checkpoint()
        if checkpoint:
            reason = checkpoint.get("reason", "unknown")
            cost = checkpoint.get("cost_usd", 0)
            last = checkpoint.get("last_prompt", "")[:80]
            files = checkpoint.get("output_files", [])

            reason_labels = {
                "budget_exceeded": "orçamento excedido",
                "user_reset": "reset manual",
                "idle_timeout": "timeout de inatividade",
            }
            reason_text = reason_labels.get(reason, reason)

            files_note = f"\n- **Arquivos gerados:** {len(files)}" if files else ""
            await cl.Message(
                content=(
                    f"🔄 **Sessão anterior interrompida** ({reason_text})\n\n"
                    f"- **Custo acumulado:** `${cost:.4f}`\n"
                    f"- **Último prompt:** _{last}{'...' if len(checkpoint.get('last_prompt', '')) > 80 else ''}_"
                    f"{files_note}\n\n"
                    "Digite **`continuar`** para retomar ou ignore para nova sessão."
                ),
                author="Sistema",
            ).send()
            cl.user_session.set("_pending_checkpoint", checkpoint)

    except Exception as exc:
        if loading_msg:
            await loading_msg.remove()
        await cl.Message(
            content=f"❌ Erro ao inicializar Supervisor: `{exc}`\n\nVerifique as credenciais no `.env`."
        ).send()


async def _activate_dev() -> None:
    """Ativa o modo Dev Assistant."""
    from config.settings import settings  # importação local

    cl.user_session.set("mode", MODE_DEV)
    cl.user_session.set("dev_history", [])

    await cl.Message(
        content=(
            "✅ **Modo: Dev Assistant** ativado.\n\n"
            f"Modelo: `{settings.default_model}`\n\n"
            "Ferramentas: `Read`, `Write`, `Bash`, `Grep`, `Glob`\n\n"
            "Histórico de conversa mantido para follow-ups.\n\n"
            "---\n"
            "💡 Para tarefas de pipeline, SQL ou PySpark, use o Modo Data Agents (`/modo`)."
        )
    ).send()


# ── Handlers de mensagem ──────────────────────────────────────────────────────


async def _handle_supervisor(user_input: str) -> None:
    """
    Envia prompt ao Supervisor e transmite resposta em tempo real via Chainlit.

    Para cada tool call detectada via StreamEvent:
      - Abre um cl.Step() com o label da ferramenta
      - Quando for Agent: atualiza o nome com o agente especialista assim que
        disponível no JSON buffer
      - Ao fechar: registra o tempo decorrido no output do Step

    A resposta final é enviada como cl.Message com author = agente responsável
    (ex: "SQL Expert") quando há delegação, ou "Supervisor" para o texto geral.
    """
    from claude_agent_sdk import ClaudeSDKClient

    client: ClaudeSDKClient | None = cl.user_session.get("supervisor_client")
    options = cl.user_session.get("supervisor_options")

    if client is None:
        await cl.Message(
            content="❌ Cliente não inicializado. Digite `/modo` para reiniciar a sessão."
        ).send()
        return

    # Parse de slash command
    command_result = parse_command(user_input)
    prompt = command_result.doma_prompt if command_result else user_input

    # Ajusta thinking: ativo apenas para DOMA Full (/plan, /brief)
    enable_thinking = command_result is not None and command_result.doma_mode == "full"
    options.thinking = (
        {"type": "enabled", "budget_tokens": 8000} if enable_thinking else {"type": "disabled"}
    )

    # Badge de modo DOMA
    if command_result:
        mode_badge = "🗺️ DOMA Full" if enable_thinking else "🚀 DOMA Express"
        agent_label = f" → `{command_result.agent}`" if command_result.agent else ""
        await cl.Message(content=f"*{mode_badge}{agent_label}*", author="Sistema").send()

    # ── Estado do streaming ───────────────────────────────────────────────────
    steps = _StepManager()
    current_tool: str | None = None
    current_tool_use_id: str | None = None  # id da tool call ativa (para park/receive_result)
    tool_input_buffer: str = ""
    current_agent: str | None = None  # nome do agente em delegação ativa
    last_agent: str | None = None  # último agente que respondeu (para author)
    tool_names: list[str] = []
    streamed_text = ""
    final_text = ""
    _result_cost: float = 0.0  # preenchido no ResultMessage; acessível no except
    _result_turns: int = 0
    _thinking_msg: cl.Step | None = None  # indicador "Supervisor sintetizando..." temporário

    # Mensagem de resposta principal (recebe o texto gerado pelo modelo)
    response_msg = cl.Message(content="", author="Supervisor")
    await response_msg.send()

    # Timeout por mensagem: se o SDK ficar mais de 3 min sem emitir nenhuma
    # mensagem (StreamEvent, AssistantMessage ou ResultMessage), cancela e
    # reporta o erro. Evita que a UI trave indefinidamente em hangs do SDK.
    _MSG_TIMEOUT = 180  # segundos

    async def _next_with_timeout(gen):
        """Retorna o próximo item do generator com timeout."""
        return await asyncio.wait_for(gen.__anext__(), timeout=_MSG_TIMEOUT)

    try:
        await client.query(prompt)

        _gen = client.receive_response().__aiter__()
        while True:
            try:
                message = await _next_with_timeout(_gen)
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                await steps.close_error(f"⏱️ Timeout: nenhuma resposta em {_MSG_TIMEOUT}s")
                await response_msg.stream_token(
                    f"\n\n⏱️ **Timeout** — o agente não respondeu em {_MSG_TIMEOUT // 60} minutos. "
                    "Tente novamente ou use `/modo` para reiniciar a sessão."
                )
                break

            # ── StreamEvent ───────────────────────────────────────────────────
            if isinstance(message, StreamEvent):
                ev = message.event
                evtype = ev.get("type")

                # ── Tool call iniciando ───────────────────────────────────────
                if evtype == "content_block_start":
                    blk = ev.get("content_block", {})
                    if blk.get("type") == "tool_use":
                        current_tool = blk.get("name", "")
                        current_tool_use_id = blk.get("id", "")
                        tool_input_buffer = ""
                        current_agent = None
                        tool_names.append(current_tool)

                        if current_tool == "Agent":
                            # Label genérico até detectar o nome do agente no JSON
                            await steps.open("🤖 Delegando...", step_type="run")
                        else:
                            label = _tool_label(current_tool)
                            await steps.open(label, step_type="tool")

                # ── Acumulando input JSON (detecta nome do agente) ────────────
                elif evtype == "content_block_delta":
                    delta = ev.get("delta", {})
                    delta_type = delta.get("type")

                    if delta_type == "input_json_delta":
                        tool_input_buffer += delta.get("partial_json", "")
                        # Tenta detectar nome do agente assim que o campo aparece
                        if current_tool == "Agent" and current_agent is None:
                            try:
                                data: dict[str, Any] = json.loads(tool_input_buffer)
                                agent_name = (
                                    data.get("agent_name")
                                    or data.get("subagent_type")
                                    or data.get("name")
                                    or ""
                                )
                                if agent_name:
                                    current_agent = agent_name
                                    last_agent = agent_name
                                    display = _agent_author(agent_name)
                                    _tier = _AGENT_TIERS.get(agent_name, "")
                                    _tier_label = f" · T{_tier[1:]}" if _tier else ""
                                    await steps.rename(f"🤖 {display}{_tier_label}")
                            except (json.JSONDecodeError, TypeError):
                                pass

                    elif delta_type == "text_delta":
                        token = delta.get("text", "")
                        if token:
                            # Fecha step "sintetizando" ao receber o primeiro token real
                            if _thinking_msg is not None:
                                _thinking_msg.output = "✅ Resposta gerada"
                                await _thinking_msg.update()
                                _thinking_msg = None
                            streamed_text += token
                            await response_msg.stream_token(token)

                # ── Tool call finalizada ──────────────────────────────────────
                elif evtype == "content_block_stop":
                    if current_tool == "Agent" and current_agent:
                        # Agent tool: fecha imediatamente — resultado vem como mensagem
                        display = _agent_author(current_agent)
                        _tier = _AGENT_TIERS.get(current_agent, "")
                        _tier_label = f" · T{_tier[1:]}" if _tier else ""
                        await steps.close(f"✅ {display}{_tier_label} concluído")
                        # Após retorno de sub-agente, abre step "sintetizando" que
                        # fecha naturalmente quando o primeiro token da resposta chegar.
                        _thinking_msg = cl.Step(name="⚙️ Supervisor sintetizando...", type="run")
                        await _thinking_msg.send()
                    elif current_tool and current_tool_use_id:
                        # Demais tools: estaciona aguardando ToolResultBlock no UserMessage
                        await steps.park(current_tool_use_id)
                    else:
                        await steps.close()

                    current_tool = None
                    current_tool_use_id = None
                    tool_input_buffer = ""
                    current_agent = None

            # ── UserMessage: contém os resultados reais das tool calls ────────
            elif isinstance(message, UserMessage):
                if isinstance(message.content, list):
                    for blk in message.content:
                        if isinstance(blk, ToolResultBlock):
                            content_str = _format_tool_result(blk.content)
                            if blk.is_error:
                                content_str = f"❌ {content_str}" if content_str else "❌ Erro"
                            await steps.receive_result(blk.tool_use_id, content_str)

            # ── AssistantMessage: fallback se não houve streaming ────────────
            elif isinstance(message, AssistantMessage):
                # Só fecha o step ativo se não há tool_use em andamento —
                # o SDK emite AssistantMessage intermediários entre START e STOP da tool.
                if current_tool is None:
                    await steps.close()
                # Não fecha steps estacionados — UserMessage com resultados reais
                # pode chegar DEPOIS do AssistantMessage (ordem real do stream)
                if _thinking_msg is not None:
                    _thinking_msg.output = "✅ Resposta gerada"
                    await _thinking_msg.update()
                    _thinking_msg = None
                for blk in message.content:
                    if isinstance(blk, TextBlock) and blk.text.strip():
                        final_text += blk.text

            # ── ResultMessage: métricas finais ────────────────────────────────
            elif isinstance(message, ResultMessage):
                await steps.close()
                await steps.close_all_parked()  # fallback final — fecha qualquer step sem resultado
                if _thinking_msg is not None:
                    _thinking_msg.output = "✅ Resposta gerada"
                    await _thinking_msg.update()
                    _thinking_msg = None

                # Usa texto final como fallback se não houve streaming
                if not streamed_text and final_text:
                    await response_msg.stream_token(final_text)

                _result_cost = float(message.total_cost_usd or 0)
                _result_turns = int(message.num_turns or 0)
                duration = float(message.duration_ms or 0) / 1000

                # Atualiza author da resposta para o último agente que respondeu
                if last_agent:
                    response_msg.author = _agent_author(last_agent)

                # Rodapé com métricas
                metrics_str = f"\n\n---\n*💰 `${_result_cost:.4f}` · 🔄 `{_result_turns} turns` · ⏱️ `{duration:.1f}s`*"
                await response_msg.stream_token(metrics_str)

    except Exception as exc:
        from config.exceptions import BudgetExceededError
        from config.settings import settings as _settings
        from hooks.checkpoint import save_checkpoint

        await steps.close_error(str(exc))

        if isinstance(exc, BudgetExceededError):
            # Marca o cache para reconexão na próxima sessão — reseta o budget
            _supervisor_cache["needs_reconnect"] = True

            # Salva checkpoint para retomada na próxima sessão
            cost_val = getattr(exc, "current_cost", _result_cost)
            turns_val = _result_turns
            save_checkpoint(
                last_prompt=prompt[:500],
                reason="budget_exceeded",
                cost_usd=cost_val,
                turns=turns_val,
            )

            await response_msg.stream_token(
                f"\n\n💰 **Orçamento excedido** — `${cost_val:.4f}` / `${_settings.max_budget_usd:.2f}`\n\n"
                "O contexto desta sessão foi salvo automaticamente.\n"
                "Abra um **Novo Chat**, selecione **Data Agents** e digite **`continuar`** para retomar."
            )
        else:
            await response_msg.stream_token(f"\n\n❌ **Erro:** `{exc}`")

    await response_msg.update()

    # ── Tracking de resposta para export ─────────────────────────────────────
    from datetime import datetime as _dt

    if response_msg.content:
        _hist = cl.user_session.get("chat_history") or []
        _hist.append(
            {
                "role": "assistant",
                "author": response_msg.author or "Supervisor",
                "content": response_msg.content,
                "timestamp": _dt.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        cl.user_session.set("chat_history", _hist)


async def _handle_dev(user_input: str) -> None:
    """
    Executa query no Dev Assistant via sdk_query (stateless).

    Para cada tool call do Dev Assistant (Read, Write, Bash, Grep, Glob):
      - Abre um cl.Step() com o label da ferramenta
      - Fecha o Step ao concluir com tempo decorrido

    A resposta final é enviada como cl.Message(author="Dev Assistant").
    Mantém histórico no cl.user_session para suportar follow-ups.
    """
    from commands.geral import build_prompt_with_history
    from hooks.session_logger import log_session_result

    history: list[dict] = cl.user_session.get("dev_history") or []
    history.append({"role": "user", "content": user_input})

    prompt = build_prompt_with_history(user_input, history)
    stderr_lines: list[str] = []
    options = _build_dev_options(stderr_lines=stderr_lines)

    # ── Estado do streaming ───────────────────────────────────────────────────
    steps = _StepManager()
    current_tool: str | None = None
    current_tool_use_id: str | None = None
    tool_input_buffer: str = ""
    streamed_text = ""
    final_text = ""

    response_msg = cl.Message(content="", author="Dev Assistant")
    await response_msg.send()

    try:
        async for message in sdk_query(prompt=prompt, options=options):
            # ── StreamEvent ───────────────────────────────────────────────────
            if isinstance(message, StreamEvent):
                ev = message.event
                evtype = ev.get("type")

                if evtype == "content_block_start":
                    blk = ev.get("content_block", {})
                    if blk.get("type") == "tool_use":
                        current_tool = blk.get("name", "")
                        current_tool_use_id = blk.get("id", "")
                        tool_input_buffer = ""
                        label = _tool_label(current_tool)
                        await steps.open(label, step_type="tool")

                elif evtype == "content_block_delta":
                    delta = ev.get("delta", {})
                    delta_type = delta.get("type")

                    if delta_type == "input_json_delta":
                        # Acumula JSON do input da tool para enriquecer o label
                        tool_input_buffer += delta.get("partial_json", "")
                        if current_tool:
                            try:
                                data: dict[str, Any] = json.loads(tool_input_buffer)
                                enriched = _enrich_tool_label(current_tool, data)
                                if enriched:
                                    await steps.rename(enriched)
                            except (json.JSONDecodeError, TypeError):
                                pass

                    elif delta_type == "text_delta":
                        token = delta.get("text", "")
                        if token:
                            streamed_text += token
                            await response_msg.stream_token(token)

                elif evtype == "content_block_stop":
                    if current_tool and current_tool_use_id:
                        # Estaciona aguardando ToolResultBlock no UserMessage
                        await steps.park(current_tool_use_id)
                    current_tool = None
                    current_tool_use_id = None
                    tool_input_buffer = ""

            # ── UserMessage: contém os resultados reais das tool calls ────────
            elif isinstance(message, UserMessage):
                if isinstance(message.content, list):
                    for blk in message.content:
                        if isinstance(blk, ToolResultBlock):
                            content_str = _format_tool_result(blk.content)
                            if blk.is_error:
                                content_str = f"❌ {content_str}" if content_str else "❌ Erro"
                            await steps.receive_result(blk.tool_use_id, content_str)

            # ── AssistantMessage: fallback ────────────────────────────────────
            elif isinstance(message, AssistantMessage):
                # Só fecha o step ativo se não há tool_use em andamento.
                # O SDK emite AssistantMessage intermediários entre tool_use START e STOP —
                # chamar close() nesses casos descartaria o step antes de park() ser chamado.
                if current_tool is None:
                    await steps.close()
                for blk in message.content:
                    if isinstance(blk, TextBlock) and blk.text.strip():
                        final_text += blk.text

            # ── ResultMessage: métricas ───────────────────────────────────────
            elif isinstance(message, ResultMessage):
                await steps.close()
                await steps.close_all_parked()  # fallback final — fecha qualquer step sem resultado

                if not streamed_text and final_text:
                    await response_msg.stream_token(final_text)
                    streamed_text = final_text

                cost = float(message.total_cost_usd or 0)
                turns = int(message.num_turns or 0)
                duration = float(message.duration_ms or 0) / 1000

                log_session_result(
                    message, prompt_preview=user_input[:100], session_type="dev-assistant"
                )

                footer = f"\n\n---\n*💰 `${cost:.4f}` · 🔄 `{turns} turns` · ⏱️ `{duration:.1f}s`*"
                await response_msg.stream_token(footer)

    except Exception as exc:
        await steps.close_error(str(exc))
        # Inclui o stderr real se foi capturado (exit code 1, etc.)
        if stderr_lines:
            stderr_preview = "\n".join(stderr_lines[-20:])  # últimas 20 linhas
            error_detail = f"\n\n❌ **Erro:** `{exc}`\n\n```\n{stderr_preview}\n```"
        else:
            error_detail = f"\n\n❌ **Erro:** `{exc}`"
        await response_msg.stream_token(error_detail)
        history.pop()  # reverte o push do histórico em caso de erro
        cl.user_session.set("dev_history", history)
        await response_msg.update()
        return

    # Atualiza histórico com a resposta
    response_text = streamed_text or final_text
    if response_text:
        history.append({"role": "assistant", "content": response_text})
    cl.user_session.set("dev_history", history)

    await response_msg.update()

    # ── Tracking de resposta para export ─────────────────────────────────────
    from datetime import datetime as _dt

    if response_msg.content:
        _hist = cl.user_session.get("chat_history") or []
        _hist.append(
            {
                "role": "assistant",
                "author": "Dev Assistant",
                "content": response_msg.content,
                "timestamp": _dt.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        cl.user_session.set("chat_history", _hist)


# ── Export ────────────────────────────────────────────────────────────────────


async def _handle_export() -> None:
    """
    Exporta o histórico da sessão para Markdown e PDF.
    Acionado pelo comando /export ou /exportar.
    """
    history: list = cl.user_session.get("chat_history") or []

    if not history:
        await cl.Message(
            content="⚠️ Nenhuma mensagem para exportar. Inicie uma conversa primeiro.",
            author="Sistema",
        ).send()
        return

    await cl.Message(content="⏳ Gerando arquivos de export...", author="Sistema").send()

    try:
        title = f"Data Agents — {len(history)} mensagens"

        from ui.exporter import export_html

        html_path = export_html(history, title=title)

        elements = [
            cl.File(name="conversa.html", path=html_path, mime="text/html"),
        ]
        await cl.Message(
            content=(
                f"✅ **Export concluído** — {len(history)} mensagens exportadas.\n\n"
                "📄 Baixe o arquivo HTML abaixo.\n"
                "💡 **Para PDF:** abra no browser e use **Cmd+P → Salvar como PDF**."
            ),
            elements=elements,
            author="Sistema",
        ).send()

    except Exception as exc:
        await cl.Message(
            content=f"❌ Erro ao gerar export: `{exc}`",
            author="Sistema",
        ).send()


# ── Event handlers do Chainlit ────────────────────────────────────────────────


@cl.on_chat_start
async def on_chat_start() -> None:
    """Apresenta seleção de modo ao iniciar o chat.

    Marca o supervisor para reconexão — cada novo chat recebe um budget zerado,
    evitando que o custo acumulado da sessão anterior bloqueie o novo chat.
    """
    _supervisor_cache["needs_reconnect"] = True
    cl.user_session.set("chat_history", [])
    await _show_mode_selection()


@cl.action_callback("select_supervisor")
async def on_supervisor_selected(action: cl.Action) -> None:
    await action.remove()
    await _activate_supervisor()


@cl.action_callback("select_dev")
async def on_dev_selected(action: cl.Action) -> None:
    await action.remove()
    await _activate_dev()


def _monitor_is_running() -> bool:
    """Retorna True se já há algo escutando em _MONITOR_PORT."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", _MONITOR_PORT)) == 0


def _start_monitor() -> None:
    """Inicia o Streamlit de monitoramento em background (processo filho independente)."""
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ROOT / "monitoring" / "app.py"),
            "--server.port",
            str(_MONITOR_PORT),
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
            "--theme.base",
            "dark",
        ],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        # Desvincula do processo pai — sobrevive ao encerramento do Chainlit
        start_new_session=True,
    )


@cl.action_callback("open_monitoring")
async def on_monitoring_selected(action: cl.Action) -> None:
    await action.remove()

    url = f"http://localhost:{_MONITOR_PORT}"

    if _monitor_is_running():
        await cl.Message(
            content=f"📊 **Dashboard de Monitoramento**\n\nJá está rodando → [{url}]({url})",
            author="Sistema",
        ).send()
        return

    # Inicia o Streamlit em background
    await cl.Message(
        content="⏳ Iniciando dashboard de monitoramento...",
        author="Sistema",
    ).send()

    try:
        _start_monitor()
    except Exception as exc:
        await cl.Message(
            content=f"❌ Não foi possível iniciar o monitoramento: `{exc}`",
            author="Sistema",
        ).send()
        return

    # Aguarda o Streamlit subir (até 15s)
    for _ in range(30):
        await asyncio.sleep(0.5)
        if _monitor_is_running():
            break

    if _monitor_is_running():
        await cl.Message(
            content=f"✅ **Dashboard de Monitoramento** iniciado → [{url}]({url})",
            author="Sistema",
        ).send()
    else:
        await cl.Message(
            content=(
                f"⚠️ O serviço foi iniciado mas ainda não respondeu na porta {_MONITOR_PORT}. "
                f"Aguarde alguns segundos e acesse [{url}]({url})"
            ),
            author="Sistema",
        ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    user_input = message.content.strip()
    if not user_input:
        return

    # Comando global /modo — funciona em qualquer estado
    if user_input.lower() in ("/modo", "/mode"):
        # Limpa apenas a sessão local — o cliente do Supervisor fica no cache
        # de módulo para ser reutilizado por esta ou outras sessões.
        cl.user_session.set("supervisor_client", None)
        cl.user_session.set("supervisor_options", None)
        cl.user_session.set("mode", None)
        cl.user_session.set("dev_history", [])
        await _show_mode_selection()
        return

    # Comando global /export — exporta histórico para Markdown e PDF
    if user_input.lower() in ("/export", "/exportar"):
        await _handle_export()
        return

    # Comando global /eval — resumo de avaliações de qualidade (sem Supervisor)
    if user_input.lower().startswith("/eval"):
        from commands.eval import get_eval_summary

        summary = get_eval_summary()
        if summary["total"] == 0:
            md = "Nenhuma avaliação registrada ainda. As avaliações são coletadas ao encerrar sessões."
        else:
            lines = [f"### Avaliações de Qualidade — {summary['total']} sessões\n"]
            lines.append("| Tipo | Sessões | Média |")
            lines.append("|------|---------|-------|")
            for stype, stats in summary["by_type"].items():
                avg = stats["avg"]
                filled = round(avg)
                stars = "★" * filled + "☆" * (5 - filled)
                lines.append(f"| `{stype}` | {stats['count']} | {stars} {avg:.1f} |")
            lines.append(f"\n**Média geral: {summary['avg_rating']:.1f}/5.0**")
            md = "\n".join(lines)
        await cl.Message(content=md, author="Sistema").send()
        return

    # Comando global /mcp — status dos MCP servers (sem Supervisor)
    if user_input.lower().startswith("/mcp"):
        from commands.mcp import handle_mcp_command_chainlit

        md = handle_mcp_command_chainlit(user_input)
        await cl.Message(content=md, author="Sistema").send()
        return

    # Comando global /memory — gerenciamento local de memória (sem Supervisor)
    if user_input.lower().startswith("/memory"):
        from memory.store import MemoryStore
        from memory.types import MemoryType
        from hooks.checkpoint import clear_checkpoint

        parts = user_input.split(maxsplit=2)
        sub = parts[1].lower() if len(parts) > 1 else "status"
        scope = parts[2].lower() if len(parts) > 2 else "all"
        store = MemoryStore()

        if sub == "clear":
            clear_ckpt = scope == "full"
            types_to_clear = list(MemoryType)
            removed = 0
            for mem_type in types_to_clear:
                for mem in store.list_all(memory_type=mem_type):
                    if store.delete(mem.id, mem_type):
                        removed += 1
            ckpt_msg = ""
            if clear_ckpt:
                clear_checkpoint()
                cl.user_session.set("_pending_checkpoint", None)
                ckpt_msg = " + checkpoint removido"
            await cl.Message(
                content=f"🧠 **Clear:** {removed} memória(s) removida(s){ckpt_msg}.",
                author="Sistema",
            ).send()
        elif sub == "status":
            stats = store.get_stats()
            lines = [f"**Memórias:** {stats['active']} ativas / {stats['total']} total"]
            for t, v in stats.get("by_type", {}).items():
                lines.append(f"- {t}: {v['active']}/{v['total']}")
            await cl.Message(content="\n".join(lines), author="Sistema").send()
        else:
            await cl.Message(
                content="Subcomandos disponíveis: `status`, `clear`, `clear all`, `clear full`",
                author="Sistema",
            ).send()
        return

    mode: str | None = cl.user_session.get("mode")

    # Nenhum modo selecionado ainda
    if mode is None:
        await cl.Message(
            content="⚠️ Selecione um modo primeiro usando os botões acima.",
        ).send()
        return

    # ── Tracking de mensagem do usuário para export ───────────────────────────
    from datetime import datetime as _dt

    _chat_history: list = cl.user_session.get("chat_history") or []
    _chat_history.append(
        {
            "role": "user",
            "author": "Você",
            "content": user_input,
            "timestamp": _dt.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    cl.user_session.set("chat_history", _chat_history)

    # ── Checkpoint: "continuar" retoma sessão anterior ────────────────────────
    if mode == MODE_SUPERVISOR and user_input.lower() in ("continuar", "continue", "retomar"):
        checkpoint = cl.user_session.get("_pending_checkpoint")
        if checkpoint:
            from hooks.checkpoint import build_resume_prompt, clear_checkpoint

            resume_prompt = build_resume_prompt(checkpoint)
            clear_checkpoint()
            cl.user_session.set("_pending_checkpoint", None)
            await cl.Message(content="🔄 **Retomando sessão anterior...**", author="Sistema").send()
            await _handle_supervisor(resume_prompt)
            return
        # Nenhum checkpoint pendente — trata como mensagem normal

    if mode == MODE_SUPERVISOR:
        await _handle_supervisor(user_input)
    elif mode == MODE_DEV:
        await _handle_dev(user_input)


@cl.on_chat_end
async def on_chat_end() -> None:
    """
    Limpa referências da sessão e coleta avaliação de qualidade.
    """
    cl.user_session.set("supervisor_client", None)
    cl.user_session.set("supervisor_options", None)

    # Solicita avaliação via action buttons
    actions = [
        cl.Action(name=f"rate_{i}", value=str(i), label=("★" * i + "☆" * (5 - i)))
        for i in range(1, 6)
    ]
    await cl.Message(
        content="Como foi esta sessão?",
        actions=actions,
        author="Sistema",
    ).send()


@cl.action_callback("rate_1")
@cl.action_callback("rate_2")
@cl.action_callback("rate_3")
@cl.action_callback("rate_4")
@cl.action_callback("rate_5")
async def on_session_rated(action: cl.Action) -> None:
    """Salva a avaliação da sessão no log de evals."""
    from commands.eval import save_eval

    session_id = cl.user_session.get("session_id") or "chainlit"
    rating = int(action.value)
    stars = "★" * rating + "☆" * (5 - rating)
    save_eval(session_id=session_id, rating=rating, session_type="chainlit")
    await cl.Message(content=f"Avaliação registrada: {stars} ({rating}/5)", author="Sistema").send()
