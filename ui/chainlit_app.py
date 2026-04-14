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

import json
import sys
import time
from pathlib import Path
from typing import Any

import chainlit as cl
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query as sdk_query,
)
from claude_agent_sdk.types import StreamEvent

# ── Garante que a raiz do projeto está no path ────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from commands.parser import parse_command  # noqa: E402

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
- commands/parser.py   — registry de slash commands BMAD
- hooks/               — PreToolUse / PostToolUse hooks
- kb/                  — Knowledge Bases por domínio
- tests/               — pytest (mínimo 80% cobertura)
- ui/chat.py           — interface Streamlit atual

## Papel
Assistente de desenvolvimento para tarefas no próprio projeto:
código Python, debugging, refatoração, testes, análise de arquivos, scripts.

Não acesse MCPs de plataformas de dados (Databricks, Fabric).
Para tarefas de pipeline, SQL ou PySpark, sugira o Modo Data Agents.

Responda em português brasileiro. Use code blocks com syntax highlighting.
Seja direto e objetivo — sem preambles desnecessários.
"""

# Mapa de tool → label amigável
_TOOL_LABELS: dict[str, str] = {
    "Agent": "🤖 Delegando para agente especialista",
    "Read": "📖 Lendo arquivo",
    "Write": "✍️  Salvando arquivo",
    "Grep": "🔍 Buscando conteúdo",
    "Glob": "📂 Listando arquivos",
    "Bash": "⚙️  Executando comando",
    "AskUserQuestion": "❓ Aguardando resposta",
    "mcp__databricks__execute_sql": "🗄️  SQL no Databricks",
    "mcp__databricks__execute_sql_multi": "🗄️  SQL paralelo no Databricks",
    "mcp__databricks__list_catalogs": "📋 Unity Catalog — catálogos",
    "mcp__databricks__list_schemas": "📋 Unity Catalog — schemas",
    "mcp__databricks__list_tables": "📋 Unity Catalog — tabelas",
    "mcp__databricks__describe_table": "🔎 Inspecionando tabela",
    "mcp__databricks__execute_code": "⚡ Executando código serverless",
    "mcp__databricks__create_or_update_genie": "🧞 Configurando Genie Space",
    "mcp__databricks__create_or_update_dashboard": "📊 Criando AI/BI Dashboard",
    "mcp__databricks__run_job_now": "🚀 Disparando Job Databricks",
    "mcp__databricks__wait_for_run": "⏳ Aguardando conclusão do Job",
    "mcp__databricks__start_pipeline": "🚀 Iniciando Pipeline LakeFlow",
    "mcp__databricks__get_pipeline": "📡 Status do Pipeline",
    "mcp__fabric__list_workspaces": "📋 Workspaces do Fabric",
    "mcp__fabric_community__list_items": "📋 Itens do Fabric workspace",
    "mcp__fabric_sql__fabric_sql_execute": "🗄️  SQL no Fabric Lakehouse",
    "mcp__fabric_sql__fabric_sql_list_tables": "📋 Tabelas Fabric",
    "mcp__fabric_rti__kusto_query": "🔍 Query KQL (Eventhouse)",
    "mcp__context7__get-library-docs": "📚 Consultando documentação",
    "mcp__context7__resolve-library-id": "📚 Resolvendo biblioteca",
    "mcp__postgres__query": "🐘 Query PostgreSQL",
    "mcp__tavily__tavily-search": "🌐 Buscando na web",
    "mcp__github__search_repositories": "🐙 Buscando repositórios GitHub",
    "mcp__memory_mcp__read_graph": "🧠 Lendo knowledge graph",
    "mcp__memory_mcp__add_entities": "🧠 Atualizando knowledge graph",
}

# Nomes de exibição por agente (para author nos cl.Message)
_AGENT_AUTHORS: dict[str, str] = {
    "sql-expert": "SQL Expert",
    "spark-expert": "Spark Expert",
    "pipeline-architect": "Pipeline Architect",
    "data-quality-steward": "Data Quality Steward",
    "governance-auditor": "Governance Auditor",
    "semantic-modeler": "Semantic Modeler",
    "business-analyst": "Business Analyst",
    "dbt-expert": "dbt Expert",
    "geral": "Geral",
}

# Grupos de comandos para o welcome message
_COMMAND_GROUPS: dict[str, list[str]] = {
    "📋 Intake & Planejamento": ["/brief", "/plan", "/review", "/status"],
    "⚡ Databricks": ["/sql", "/spark", "/pipeline", "/dbt"],
    "🏭 Microsoft Fabric": ["/fabric", "/semantic"],
    "🔍 Qualidade & Gov.": ["/quality", "/governance"],
    "🔧 Sistema": ["/health"],
}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _tool_label(name: str) -> str:
    if name in _TOOL_LABELS:
        return _TOOL_LABELS[name]
    clean = name.replace("mcp__", "").replace("__", " → ").replace("_", " ").title()
    return f"🔧 {clean}"


def _enrich_tool_label(tool_name: str, data: dict[str, Any]) -> str:
    """Retorna label enriquecido com args reais da tool. Retorna '' se não houver info relevante."""
    if tool_name == "Read":
        path = data.get("file_path") or data.get("path", "")
        if path:
            return f"📖 Lendo {path}..."
    elif tool_name == "Write":
        path = data.get("file_path", "")
        if path:
            return f"✏️ Escrevendo {path}..."
    elif tool_name == "Bash":
        cmd = data.get("command", "")
        if cmd:
            truncated = cmd[:60] + "..." if len(cmd) > 60 else cmd
            return f"⚙️ Executando: {truncated}"
    elif tool_name == "Grep":
        pattern = data.get("pattern", "")
        search_path = data.get("path", "")
        if pattern and search_path:
            return f"🔍 Buscando: '{pattern}' em {search_path}"
        elif pattern:
            return f"🔍 Buscando: '{pattern}'"
    elif tool_name == "Glob":
        pattern = data.get("pattern", "")
        if pattern:
            return f"📂 Listando: {pattern}"
    return ""


def _agent_author(raw_name: str) -> str:
    """Retorna o nome de exibição do agente para cl.Message(author=...)."""
    return _AGENT_AUTHORS.get(raw_name, raw_name.replace("-", " ").title())


def _build_dev_options() -> ClaudeAgentOptions:
    """
    ClaudeAgentOptions para o Dev Assistant.

    Usa settings.default_model (Bedrock) — custo zero pelo acordo da empresa.
    Ferramentas de desenvolvimento habilitadas. Zero MCPs de plataforma.
    """
    from config.settings import settings  # importação local — evita circular import

    opts = ClaudeAgentOptions(
        model=settings.default_model,
        system_prompt=_DEV_SYSTEM_PROMPT,
        allowed_tools=["Read", "Write", "Bash", "Grep", "Glob"],
        agents=None,
        mcp_servers={},
        max_turns=15,
        permission_mode="bypassPermissions",
    )
    opts.include_partial_messages = True
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

    cl.Step é um async context manager, mas no loop de streaming não podemos
    usar `async with` que cruze iterações. Então gerenciamos manualmente:
      - open(name, step_type)  → await step.send()
      - update(output)         → step.output = ...; await step.update()
      - close(output)          → finaliza com output e fecha
    """

    def __init__(self) -> None:
        self._step: cl.Step | None = None
        self._start: float = 0.0

    async def open(self, name: str, step_type: str = "tool") -> None:
        """Abre um novo Step. Fecha o anterior se ainda estiver aberto."""
        await self.close()
        self._step = cl.Step(name=name, type=step_type)
        self._start = time.monotonic()
        await self._step.send()

    async def rename(self, name: str) -> None:
        """Atualiza o nome do Step sem fechar — usado quando o agent_name fica disponível."""
        if self._step is None:
            return
        self._step.name = name
        await self._step.update()

    async def close(self, output: str = "") -> None:
        """Fecha o Step atual com o output fornecido."""
        if self._step is None:
            return
        elapsed = time.monotonic() - self._start
        self._step.output = output or f"Concluído em {elapsed:.1f}s"
        await self._step.update()
        self._step = None
        self._start = 0.0

    async def close_error(self, error: str) -> None:
        """Fecha o Step com mensagem de erro."""
        if self._step is None:
            return
        self._step.output = f"❌ {error}"
        await self._step.update()
        self._step = None


# ── Activação dos modos ───────────────────────────────────────────────────────


async def _show_mode_selection() -> None:
    """Apresenta os dois botões de seleção de modo."""
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
    ]
    await cl.Message(
        content=(
            "## 🤖 Data Agents\n\n"
            "**Selecione o modo de operação:**\n\n"
            "- **🤖 Data Agents** — Supervisor com agentes especialistas, slash commands e MCPs de plataforma\n"
            "- **💻 Dev Assistant** — Claude direto para tarefas de desenvolvimento no projeto (Bedrock, custo zero)\n\n"
            "*(Troque de modo a qualquer momento com `/modo`)*"
        ),
        actions=actions,
    ).send()


async def _activate_supervisor() -> None:
    """Inicializa e conecta o ClaudeSDKClient do Supervisor para esta sessão."""
    from agents.supervisor import build_supervisor_options
    from claude_agent_sdk import ClaudeSDKClient

    loading_msg = await cl.Message(content="⏳ Inicializando Supervisor e MCP servers...").send()

    try:
        options = build_supervisor_options(enable_thinking=False)
        options.include_partial_messages = True

        client = ClaudeSDKClient(options=options)
        await client.connect()

        cl.user_session.set("mode", MODE_SUPERVISOR)
        cl.user_session.set("supervisor_client", client)
        cl.user_session.set("supervisor_options", options)

        await loading_msg.remove()

        await cl.Message(
            content=(
                "✅ **Modo: Data Agents** ativado.\n\n"
                f"{_commands_help_text()}\n\n"
                "---\n"
                "💡 **Dica:** Use `/plan <objetivo>` para o fluxo completo BMAD com PRD e aprovação.\n"
                "Digite `/modo` a qualquer momento para trocar de modo."
            )
        ).send()

    except Exception as exc:
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
    prompt = command_result.bmad_prompt if command_result else user_input

    # Ajusta thinking: ativo apenas para BMAD Full (/plan, /brief)
    enable_thinking = command_result is not None and command_result.bmad_mode == "full"
    options.thinking = (
        {"type": "enabled", "budget_tokens": 8000} if enable_thinking else {"type": "disabled"}
    )

    # Badge de modo BMAD
    if command_result:
        mode_badge = "🗺️ BMAD Full" if enable_thinking else "🚀 BMAD Express"
        agent_label = f" → `{command_result.agent}`" if command_result.agent else ""
        await cl.Message(content=f"*{mode_badge}{agent_label}*", author="Sistema").send()

    # ── Estado do streaming ───────────────────────────────────────────────────
    steps = _StepManager()
    current_tool: str | None = None
    tool_input_buffer: str = ""
    current_agent: str | None = None  # nome do agente em delegação ativa
    last_agent: str | None = None  # último agente que respondeu (para author)
    tool_names: list[str] = []
    streamed_text = ""
    final_text = ""

    # Mensagem de resposta principal (recebe o texto gerado pelo modelo)
    response_msg = cl.Message(content="", author="Supervisor")
    await response_msg.send()

    try:
        await client.query(prompt)

        async for message in client.receive_response():
            # ── StreamEvent ───────────────────────────────────────────────────
            if isinstance(message, StreamEvent):
                ev = message.event
                evtype = ev.get("type")

                # ── Tool call iniciando ───────────────────────────────────────
                if evtype == "content_block_start":
                    blk = ev.get("content_block", {})
                    if blk.get("type") == "tool_use":
                        current_tool = blk.get("name", "")
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
                                    await steps.rename(f"🤖 {display}")
                            except (json.JSONDecodeError, TypeError):
                                pass

                    elif delta_type == "text_delta":
                        token = delta.get("text", "")
                        if token:
                            streamed_text += token
                            await response_msg.stream_token(token)

                # ── Tool call finalizada ──────────────────────────────────────
                elif evtype == "content_block_stop":
                    if current_tool == "Agent" and current_agent:
                        display = _agent_author(current_agent)
                        await steps.close(f"✅ {display} concluído")
                    elif current_tool:
                        label = _tool_label(current_tool)
                        await steps.close(f"✅ {label}")
                    else:
                        await steps.close()

                    current_tool = None
                    tool_input_buffer = ""
                    current_agent = None

            # ── AssistantMessage: fallback se não houve streaming ────────────
            elif isinstance(message, AssistantMessage):
                await steps.close()  # garante que não ficou nenhum step aberto
                for blk in message.content:
                    if isinstance(blk, TextBlock) and blk.text.strip():
                        final_text += blk.text

            # ── ResultMessage: métricas finais ────────────────────────────────
            elif isinstance(message, ResultMessage):
                await steps.close()

                # Usa texto final como fallback se não houve streaming
                if not streamed_text and final_text:
                    await response_msg.stream_token(final_text)

                cost = float(message.total_cost_usd or 0)
                turns = int(message.num_turns or 0)
                duration = float(message.duration_ms or 0) / 1000

                # Atualiza author da resposta para o último agente que respondeu
                if last_agent:
                    response_msg.author = _agent_author(last_agent)

                # Rodapé com métricas
                metrics_str = (
                    f"\n\n---\n*💰 `${cost:.4f}` · 🔄 `{turns} turns` · ⏱️ `{duration:.1f}s`*"
                )
                await response_msg.stream_token(metrics_str)

    except Exception as exc:
        await steps.close_error(str(exc))
        await response_msg.stream_token(f"\n\n❌ **Erro:** `{exc}`")

    await response_msg.update()


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
    options = _build_dev_options()

    # ── Estado do streaming ───────────────────────────────────────────────────
    steps = _StepManager()
    current_tool: str | None = None
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
                    if current_tool:
                        # Usa label enriquecido se disponível, senão label genérico
                        try:
                            data = json.loads(tool_input_buffer) if tool_input_buffer else {}
                            enriched = _enrich_tool_label(current_tool, data)
                        except (json.JSONDecodeError, TypeError):
                            enriched = None
                        close_label = enriched or _tool_label(current_tool)
                        await steps.close(f"✅ {close_label}")
                    current_tool = None
                    tool_input_buffer = ""

            # ── AssistantMessage: fallback ────────────────────────────────────
            elif isinstance(message, AssistantMessage):
                await steps.close()
                for blk in message.content:
                    if isinstance(blk, TextBlock) and blk.text.strip():
                        final_text += blk.text

            # ── ResultMessage: métricas ───────────────────────────────────────
            elif isinstance(message, ResultMessage):
                await steps.close()

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
        await response_msg.stream_token(f"\n\n❌ **Erro:** `{exc}`")
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


# ── Event handlers do Chainlit ────────────────────────────────────────────────


@cl.on_chat_start
async def on_chat_start() -> None:
    """Apresenta seleção de modo ao iniciar o chat."""
    await _show_mode_selection()


@cl.action_callback("select_supervisor")
async def on_supervisor_selected(action: cl.Action) -> None:
    await action.remove()
    await _activate_supervisor()


@cl.action_callback("select_dev")
async def on_dev_selected(action: cl.Action) -> None:
    await action.remove()
    await _activate_dev()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    user_input = message.content.strip()
    if not user_input:
        return

    # Comando global /modo — funciona em qualquer estado
    if user_input.lower() in ("/modo", "/mode"):
        client = cl.user_session.get("supervisor_client")
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass
            cl.user_session.set("supervisor_client", None)

        cl.user_session.set("mode", None)
        cl.user_session.set("dev_history", [])
        await _show_mode_selection()
        return

    mode: str | None = cl.user_session.get("mode")

    # Nenhum modo selecionado ainda
    if mode is None:
        await cl.Message(
            content="⚠️ Selecione um modo primeiro usando os botões acima.",
        ).send()
        return

    if mode == MODE_SUPERVISOR:
        await _handle_supervisor(user_input)
    elif mode == MODE_DEV:
        await _handle_dev(user_input)


@cl.on_chat_end
async def on_chat_end() -> None:
    """Desconecta o cliente do Supervisor ao encerrar a sessão."""
    client = cl.user_session.get("supervisor_client")
    if client is not None:
        try:
            await client.disconnect()
        except Exception:
            pass
