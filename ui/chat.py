"""
Data Agents — UI de Chat (Streamlit)

Interface web local que substitui o terminal para uso mais amigável.
Porta padrão: 8502

Iniciar:
    ./start.sh                                         # UI + Monitoring juntos
    streamlit run ui/chat.py --server.port 8502        # somente UI

Arquitetura da sessão:
    Usa ClaudeSDKClient persistente (igual ao run_interactive de main.py):
      - Um event loop dedicado roda em background thread via loop.run_forever()
      - O cliente é conectado uma vez e reutilizado entre mensagens
      - Histórico de conversa é mantido — respostas de aprovação funcionam corretamente
      - "Nova conversa" desconecta e reconecta o cliente (limpa histórico)
"""

import asyncio
import sys
import threading
from pathlib import Path

import streamlit as st

# ── Garante que a raiz do projeto está no path ────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── Imports do projeto ────────────────────────────────────────────────────────
from commands.parser import parse_command, COMMAND_REGISTRY  # noqa: E402
from config.settings import settings  # noqa: E402

# ── Constantes ────────────────────────────────────────────────────────────────
MONITORING_URL = "http://localhost:8501"
CHAT_PORT = 8502
APP_TITLE = "Data Agents"
VERSION = "v2.0"

# Mapa de tool → label amigável (subconjunto representativo)
TOOL_LABELS: dict[str, str] = {
    "Agent": "🤖 Delegando para agente especialista",
    "Read": "📖 Lendo arquivo",
    "Write": "✍️  Salvando arquivo",
    "Grep": "🔍 Buscando conteúdo",
    "Glob": "📂 Listando arquivos",
    "Bash": "⚙️  Executando comando",
    "AskUserQuestion": "❓ Aguardando resposta",
    # Databricks
    "mcp__databricks__execute_sql": "🗄️  SQL no Databricks",
    "mcp__databricks__execute_sql_multi": "🗄️  SQL paralelo no Databricks",
    "mcp__databricks__list_catalogs": "📋 Unity Catalog — catálogos",
    "mcp__databricks__list_schemas": "📋 Unity Catalog — schemas",
    "mcp__databricks__list_tables": "📋 Unity Catalog — tabelas",
    "mcp__databricks__describe_table": "🔎 Inspecionando tabela",
    "mcp__databricks__get_table_stats_and_schema": "📊 Stats + schema da tabela",
    "mcp__databricks__run_job_now": "🚀 Disparando Job Databricks",
    "mcp__databricks__wait_for_run": "⏳ Aguardando conclusão do Job",
    "mcp__databricks__start_pipeline": "🚀 Iniciando Pipeline LakeFlow",
    "mcp__databricks__get_pipeline": "📡 Status do Pipeline",
    "mcp__databricks__execute_code": "⚡ Executando código serverless",
    "mcp__databricks__create_or_update_genie": "🧞 Configurando Genie Space",
    "mcp__databricks__create_or_update_dashboard": "📊 Criando AI/BI Dashboard",
    "mcp__databricks__manage_ka": "🧠 Knowledge Assistant",
    "mcp__databricks__manage_mas": "🤖 Mosaic AI Supervisor Agent",
    "mcp__databricks__query_serving_endpoint": "🔮 Consultando endpoint ML",
    # Fabric
    "mcp__fabric__list_workspaces": "📋 Workspaces do Fabric",
    "mcp__fabric_community__list_items": "📋 Itens do Fabric workspace",
    "mcp__fabric_sql__fabric_sql_execute": "🗄️  SQL no Fabric Lakehouse",
    "mcp__fabric_sql__fabric_sql_list_tables": "📋 Tabelas Fabric (todos schemas)",
    "mcp__fabric_rti__kusto_query": "🔍 Query KQL (Eventhouse)",
}

# Grupos de comandos para a sidebar
COMMAND_GROUPS: dict[str, list[str]] = {
    "📋 Intake & Planejamento": ["/brief", "/plan", "/review", "/status"],
    "⚡ Databricks": ["/sql", "/spark", "/pipeline"],
    "🏭 Microsoft Fabric": ["/fabric", "/semantic"],
    "🔍 Qualidade & Gov.": ["/quality", "/governance"],
    "🔧 Sistema": ["/health"],
    "🧠 Memória": ["/memory"],
    "💬 Conversacional": ["/geral"],
}

# Comandos que executam sem precisar de texto adicional
COMMANDS_NO_ARGS = {"/health", "/status", "/review"}

# ── Configuração da página ────────────────────────────────────────────────────
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS customizado ───────────────────────────────────────────────────────────
st.markdown(
    """
<style>
    #MainMenu { visibility: hidden; }
    footer    { visibility: hidden; }

    [data-testid="stSidebar"] { min-width: 285px !important; }

    /* Botões de comando rápido */
    .stButton > button {
        font-family: 'Courier New', monospace !important;
        font-size: 0.80em !important;
        text-align: left !important;
        padding: 4px 10px !important;
    }

    /* Separador de grupo */
    .cmd-group-label {
        font-size: 0.72em;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin: 8px 0 2px 0;
    }

    /* Pill de métricas */
    .metric-row { font-size: 0.75em; color: #8899aa; margin-top: 4px; }

    /* Painel de memória */
    .mem-type-header { font-size: 0.78em; font-weight: 600; color: #ccd; margin: 6px 0 2px 0; }
    .mem-entry { font-size: 0.73em; color: #aab; line-height: 1.4; margin-bottom: 2px; }
    .mem-conf-bar { display: inline-block; height: 6px; border-radius: 3px; vertical-align: middle; margin-right: 4px; }
    .mem-tag { font-size: 0.68em; background: #334; border-radius: 3px; padding: 1px 4px; color: #99b; }
    .mem-injected { font-size: 0.70em; color: #5a8; background: #1a2e1a; border-radius: 4px; padding: 2px 7px; display: inline-block; margin-top: 3px; }
</style>
""",
    unsafe_allow_html=True,
)


# ── Session state ─────────────────────────────────────────────────────────────
def _init_state() -> None:
    defaults = {
        "messages": [],  # [{role, content, tools, metrics}]
        "pending_command": None,  # "/plan" | None
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_state()


# ── Sessão persistente com ClaudeSDKClient ────────────────────────────────────
# Equivale ao run_interactive() em main.py:
#   - Um event loop dedicado roda em background thread (loop.run_forever())
#   - ClaudeSDKClient conectado e mantido vivo entre mensagens
#   - Histórico de conversa preservado — "sim" após aprovação funciona corretamente
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="⚙️ Inicializando Data Agents e MCP servers...")
def _get_agent_session() -> dict:
    """
    Cria sessão persistente:
      - loop: asyncio EventLoop rodando em daemon thread (loop.run_forever)
      - client: ClaudeSDKClient conectado — mantém histórico entre queries
      - options: ClaudeOptions mutável — thinking é ajustado por query

    Padrão idêntico ao main.py run_interactive():
        async with ClaudeSDKClient(options=options) as client:
            while True:
                await client.query(prompt)
                async for msg in client.receive_response(): ...
    """
    import uuid

    from agents.supervisor import build_supervisor_options
    from claude_agent_sdk import ClaudeSDKClient
    from hooks.session_lifecycle import on_session_start

    # ── 1. Event loop em background thread (run_forever) ──────────────────────
    loop = asyncio.new_event_loop()

    def _loop_thread() -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()

    bg = threading.Thread(target=_loop_thread, daemon=True, name="data-agents-loop")
    bg.start()

    # ── 2. Opções base (thinking ajustado por query, não aqui) ────────────────
    options = build_supervisor_options(enable_thinking=False)
    options.include_partial_messages = True

    # ── 3. Cria e conecta o cliente no loop de background ─────────────────────
    client = ClaudeSDKClient(options=options)

    future = asyncio.run_coroutine_threadsafe(client.connect(), loop)
    try:
        future.result(timeout=45)
    except Exception as exc:
        raise RuntimeError(f"Falha ao conectar ClaudeSDKClient: {exc}") from exc

    # Ch.12 — Session Lifecycle: reseta contadores e prepara buffer de memória
    session_id = f"ui-{uuid.uuid4().hex[:8]}"
    on_session_start(session_id)

    return {"client": client, "options": options, "loop": loop, "session_id": session_id}


def _reset_agent_session() -> None:
    """
    Desconecta e reconecta o cliente — limpa histórico de conversa.
    Equivalente ao comando 'limpar' do CLI (client.disconnect + client.connect).

    Ch.12: dispara on_session_end (flush de memória) antes de reconectar,
    e on_session_start (reset de contadores) após reconectar.
    """
    import uuid

    from hooks.session_lifecycle import on_session_end, on_session_start

    try:
        session = _get_agent_session()

        # Ch.12 — encerra sessão atual: flush de memória + log de contexto
        on_session_end(session.get("session_id", "ui-unknown"))

        async def _do_reset() -> None:
            await session["client"].disconnect()
            await session["client"].connect()

        future = asyncio.run_coroutine_threadsafe(_do_reset(), session["loop"])
        future.result(timeout=20)

        # Ch.12 — inicia nova sessão: reseta contadores
        new_session_id = f"ui-{uuid.uuid4().hex[:8]}"
        session["session_id"] = new_session_id
        on_session_start(new_session_id)

    except Exception:
        pass  # Falha no reset não deve travar a UI — próxima query cria contexto novo


# ── Helpers ───────────────────────────────────────────────────────────────────
def _tool_label(name: str) -> str:
    if name in TOOL_LABELS:
        return TOOL_LABELS[name]
    clean = name.replace("mcp__", "").replace("__", " → ").replace("_", " ").title()
    return f"🔧 {clean}"


def _strip_rich(text: str) -> str:
    """Remove markup Rich do texto de display dos comandos."""
    import re

    return re.sub(r"\[/?[^\]]+\]", "", text).strip()


# ── Execução do agente (ClaudeSDKClient persistente) ─────────────────────────
def _run_agent(prompt: str, enable_thinking: bool = False, session_type: str = "ui") -> dict:
    """
    Envia prompt para o ClaudeSDKClient persistente e aguarda a resposta.

    Diferença crítica em relação a query() stateless:
      - Usa client.query() + client.receive_response() (como main.py)
      - Histórico de conversa é MANTIDO entre chamadas
      - Quando o agente pede aprovação e o usuário responde "sim",
        o cliente já tem o contexto completo — PRD é lido, SPEC é gerada

    O modo thinking é ajustado em options antes de cada query:
      - /plan, /brief → enable_thinking=True  → 8000 tokens de budget
      - demais        → enable_thinking=False → thinking disabled
    """
    from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock
    from claude_agent_sdk.types import StreamEvent

    session = _get_agent_session()
    client = session["client"]
    options = session["options"]
    loop = session["loop"]

    # Ajusta thinking antes de cada query (igual a main.py lines 462-465)
    options.thinking = (
        {"type": "enabled", "budget_tokens": 8000} if enable_thinking else {"type": "disabled"}
    )

    result: dict = {
        "text": "",
        "tools": [],
        "cost": 0.0,
        "turns": 0,
        "duration": 0.0,
        "error": None,
    }

    async def _async() -> None:
        try:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, StreamEvent):
                    ev = message.event
                    if ev.get("type") == "content_block_start":
                        blk = ev.get("content_block", {})
                        if blk.get("type") == "tool_use":
                            result["tools"].append(blk.get("name", ""))

                elif isinstance(message, AssistantMessage):
                    for blk in message.content:
                        if isinstance(blk, TextBlock) and blk.text.strip():
                            result["text"] += blk.text

                elif isinstance(message, ResultMessage):
                    result["cost"] = float(message.total_cost_usd or 0)
                    result["turns"] = int(message.num_turns or 0)
                    result["duration"] = float(message.duration_ms or 0) / 1000
                    # Persiste métricas no sessions.jsonl para o monitoramento
                    from hooks.session_logger import log_session_result

                    log_session_result(
                        message, prompt_preview=prompt[:100], session_type=session_type
                    )

        except Exception as exc:
            result["error"] = str(exc)

    # Submete a coroutine ao loop de background e aguarda conclusão
    exc_holder: list[Exception] = []

    def _submit() -> None:
        future = asyncio.run_coroutine_threadsafe(_async(), loop)
        try:
            future.result()
        except Exception as e:
            exc_holder.append(e)

    t = threading.Thread(target=_submit, daemon=True)
    t.start()
    t.join()

    if exc_holder:
        result["error"] = str(exc_holder[0])

    return result


# ── Execução direta via SDK (sem Supervisor) ─────────────────────────────────
# /geral: delega para commands/geral.py — módulo compartilhado com main.py.
# Lógica única → sem duplicação, sem risco de divergência entre CLI e UI.
def _run_geral(user_message: str) -> dict:
    """
    Wrapper Streamlit para run_geral_query() de commands/geral.py.

    Gerencia histórico em st.session_state["geral_history"] e submete a
    coroutine ao loop de background da sessão — mesmo padrão de _run_agent().
    """
    from commands.geral import run_geral_query

    result: dict = {
        "text": "",
        "tools": [],
        "cost": 0.0,
        "turns": 1,
        "duration": 0.0,
        "error": None,
    }

    # Histórico de conversa para follow-ups (persistido na sessão Streamlit)
    if "geral_history" not in st.session_state:
        st.session_state["geral_history"] = []

    st.session_state["geral_history"].append({"role": "user", "content": user_message})
    history = st.session_state["geral_history"]

    # Reutiliza o loop de background da sessão do Supervisor
    session = _get_agent_session()
    loop = session["loop"]

    async def _async() -> None:
        try:
            text, metrics = await run_geral_query(user_message, history)
            result["text"] = text
            result["cost"] = metrics["cost"]
            result["turns"] = int(metrics["turns"])
            result["duration"] = metrics["duration"]
        except Exception as exc:
            result["error"] = str(exc)

    # Submete ao loop de background e aguarda — mesmo padrão de _run_agent()
    exc_holder: list[Exception] = []

    def _submit() -> None:
        future = asyncio.run_coroutine_threadsafe(_async(), loop)
        try:
            future.result()
        except Exception as e:
            exc_holder.append(e)

    t = threading.Thread(target=_submit, daemon=True)
    t.start()
    t.join()

    if exc_holder:
        result["error"] = str(exc_holder[0])

    if result["error"]:
        # Desfaz push do histórico em caso de erro
        if st.session_state["geral_history"]:
            st.session_state["geral_history"].pop()
    elif result["text"]:
        st.session_state["geral_history"].append({"role": "assistant", "content": result["text"]})

    return result


# ── Helpers de Memória ────────────────────────────────────────────────────────
_MEMORY_TYPE_ICONS: dict[str, str] = {
    "user": "👤",
    "feedback": "💬",
    "architecture": "🏗️",
    "progress": "📈",
}

_MEMORY_TYPE_LABELS: dict[str, str] = {
    "user": "Usuário",
    "feedback": "Feedback",
    "architecture": "Arquitetura",
    "progress": "Progresso",
}


def _memory_available() -> bool:
    """True se o módulo de memória está acessível e habilitado."""
    try:
        return settings.memory_enabled  # type: ignore[attr-defined]
    except AttributeError:
        return False


def _get_memory_store():
    """Retorna instância do MemoryStore ou None em caso de erro."""
    try:
        from memory.store import MemoryStore

        return MemoryStore()
    except Exception:
        return None


def _run_memory_flush() -> str:
    """
    Roda flush_session_memories() no background loop do agente.
    Retorna mensagem de status.
    """
    try:
        from hooks.memory_hook import flush_session_memories

        session = _get_agent_session()
        future = asyncio.run_coroutine_threadsafe(flush_session_memories(), session["loop"])
        future.result(timeout=30)
        return "✅ Flush concluído"
    except Exception as exc:
        return f"❌ {exc}"


def _run_memory_compile() -> str:
    """
    Roda compile_daily_logs() — processa logs diários e gera memórias.
    Retorna resumo de métricas.
    """
    try:
        from memory.compiler import compile_daily_logs

        store = _get_memory_store()
        if store is None:
            return "❌ Store indisponível"
        metrics = compile_daily_logs(store, apply_decay_on_compile=True)
        created = metrics.get("created", 0)
        updated = metrics.get("updated", 0)
        skipped = metrics.get("skipped_dupes", 0)
        superseded = metrics.get("superseded", 0)
        return f"✅ +{created} criadas, {updated} atualizadas, {skipped} dupes, {superseded} superseded"
    except Exception as exc:
        return f"❌ {exc}"


def _run_memory_lint() -> str:
    """
    Roda lint_memories() e retorna relatório em Markdown.
    """
    try:
        from memory.lint import lint_memories

        store = _get_memory_store()
        if store is None:
            return "❌ Store indisponível"
        report = lint_memories(store)
        return report.to_markdown()
    except Exception as exc:
        return f"❌ {exc}"


def _conf_pill(conf: float) -> str:
    """Retorna emoji colorido de acordo com o nível de confiança."""
    if conf >= 0.8:
        return "🟢"
    if conf >= 0.5:
        return "🟡"
    if conf >= 0.2:
        return "🟠"
    return "🔴"


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"## 🤖 {APP_TITLE}")
    st.caption(f"{VERSION} · Claude Agent SDK + MCP")

    # Link para o Monitoring
    st.link_button(
        "📊 Abrir Monitoring Dashboard",
        MONITORING_URL,
        use_container_width=True,
        type="primary",
    )

    st.divider()

    # Info do sistema
    with st.expander("⚙️ Configurações", expanded=False):
        try:
            st.caption(f"**Modelo:**  `{settings.default_model}`")
            st.caption(f"**Budget:**  `${settings.max_budget_usd:.2f}`")
            st.caption(f"**Turns:**   `{settings.max_turns}`")
        except Exception:
            st.caption("_Carregue o `.env` para ver configs._")

    st.divider()

    # ── Comandos rápidos ──────────────────────────────────────────
    st.markdown("#### ⚡ Comandos Rápidos")
    st.caption("Selecione um comando para usá-lo no chat.")

    for group, cmds in COMMAND_GROUPS.items():
        st.markdown(f"<div class='cmd-group-label'>{group}</div>", unsafe_allow_html=True)
        cols = st.columns(2)
        for i, cmd in enumerate(cmds):
            key = cmd.lstrip("/")
            defn = COMMAND_REGISTRY.get(key)
            tip = defn.description if defn else cmd
            if cols[i % 2].button(
                cmd, key=f"sidebar_btn_{cmd}", help=tip, use_container_width=True
            ):
                st.session_state.pending_command = cmd
                st.rerun()

    st.divider()

    # ── Outputs gerados (por subpasta) ───────────────────────────
    st.markdown("#### 📁 Outputs Recentes")
    output_dir = ROOT / "output"

    SUBFOLDER_ICONS = {
        "prd": ("📄 PRD", "prd"),
        "specs": ("📐 SPEC", "specs"),
        "backlog": ("📋 Backlog", "backlog"),
    }

    any_files = False
    if output_dir.exists():
        for sub, (label, _) in SUBFOLDER_ICONS.items():
            sub_dir = output_dir / sub
            if sub_dir.exists():
                files = sorted(sub_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)[
                    :3
                ]
                if files:
                    any_files = True
                    st.caption(f"**{label}**")
                    for f in files:
                        st.caption(f"&nbsp;&nbsp;• `{f.name}`")
    if not any_files:
        st.caption("_Nenhum arquivo gerado ainda._")

    # ── Painel de Memória ─────────────────────────────────────────
    if _memory_available():
        st.divider()
        st.markdown("#### 🧠 Memória")

        store = _get_memory_store()
        if store is None:
            st.caption("_Módulo de memória indisponível._")
        else:
            try:
                stats = store.get_stats()
                total = stats.get("total", 0)
                active = stats.get("active", 0)

                # Pill de status
                if total == 0:
                    st.caption("_Nenhuma memória registrada ainda._")
                else:
                    col_t, col_a = st.columns(2)
                    col_t.metric("Total", total)
                    col_a.metric("Ativas", active)

                    # Lista por tipo
                    with st.expander("📋 Ver memórias", expanded=False):
                        from memory.types import MemoryType

                        any_mems = False
                        for mt in MemoryType:
                            mems = store.list_all(memory_type=mt, active_only=True)
                            if not mems:
                                continue
                            any_mems = True
                            icon = _MEMORY_TYPE_ICONS.get(mt.value, "•")
                            label = _MEMORY_TYPE_LABELS.get(mt.value, mt.value)
                            st.markdown(
                                f"<div class='mem-type-header'>{icon} {label} ({len(mems)})</div>",
                                unsafe_allow_html=True,
                            )
                            # Mostra até 6 por tipo, ordenado por confiança desc
                            for mem in sorted(mems, key=lambda m: m.confidence, reverse=True)[:6]:
                                pill = _conf_pill(mem.confidence)
                                summary = (
                                    mem.summary[:55] + "…" if len(mem.summary) > 55 else mem.summary
                                )
                                tags_html = "".join(
                                    f"<span class='mem-tag'>{t}</span> " for t in mem.tags[:3]
                                )
                                conf_pct = int(mem.confidence * 100)
                                st.markdown(
                                    f"<div class='mem-entry'>"
                                    f"{pill} {summary}<br>"
                                    f"<small style='color:#667'>conf {conf_pct}%</small> {tags_html}"
                                    f"</div>",
                                    unsafe_allow_html=True,
                                )
                        if not any_mems:
                            st.caption("_Nenhuma memória ativa._")

                # Logs diários pendentes
                pending_logs = store.list_daily_logs(unprocessed_only=True)
                if pending_logs:
                    st.caption(f"📝 `{len(pending_logs)}` log(s) aguardando compilação")

                # Botões de ação
                st.markdown("")
                col_f, col_c = st.columns(2)
                if col_f.button(
                    "⚡ Flush",
                    key="mem_flush_btn",
                    help="Captura memórias do buffer da sessão atual",
                    use_container_width=True,
                ):
                    with st.spinner("Fazendo flush..."):
                        msg = _run_memory_flush()
                    st.toast(msg)
                    st.rerun()

                if col_c.button(
                    "🔨 Compilar",
                    key="mem_compile_btn",
                    help="Processa logs diários e gera memórias",
                    use_container_width=True,
                ):
                    with st.spinner("Compilando..."):
                        msg = _run_memory_compile()
                    st.toast(msg)
                    st.rerun()

                if st.button(
                    "🔍 Lint",
                    key="mem_lint_btn",
                    help="Verifica saúde das memórias (7 checks)",
                    use_container_width=True,
                ):
                    report_md = _run_memory_lint()
                    st.session_state["_mem_lint_report"] = report_md
                    st.rerun()

                # Exibe relatório de lint se disponível
                if st.session_state.get("_mem_lint_report"):
                    with st.expander("🔍 Relatório de Lint", expanded=True):
                        st.markdown(st.session_state["_mem_lint_report"])
                        if st.button("✕ Fechar lint", key="close_lint"):
                            st.session_state.pop("_mem_lint_report", None)
                            st.rerun()

            except Exception as _mem_err:
                st.caption(f"_Erro ao carregar memórias: {_mem_err}_")

    st.divider()

    # Limpar conversa (desconecta/reconecta cliente para limpar histórico)
    if st.button("🗑️  Nova conversa", use_container_width=True):
        # Flush das memórias antes de resetar (captura o contexto da sessão)
        if _memory_available():
            try:
                _run_memory_flush()
            except Exception:
                pass  # Falha no flush não deve bloquear o reset
        st.session_state.messages = []
        st.session_state.pending_command = None
        st.session_state.pop("_mem_lint_report", None)
        _reset_agent_session()
        st.rerun()


# ── Área principal ────────────────────────────────────────────────────────────
st.markdown("### 💬 Chat")

# Exibe histórico
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            # Ferramentas (expansível)
            tools = msg.get("tools", [])
            if tools:
                with st.expander(f"🔧 {len(tools)} ferramenta(s) executada(s)", expanded=False):
                    for t in tools:
                        st.caption(f"• {_tool_label(t)}")
            # Resposta
            st.markdown(msg["content"])
            # Métricas
            m = msg.get("metrics", {})
            if m.get("cost") or m.get("turns"):
                parts = []
                if m.get("cost"):
                    parts.append(f"💰 `${m['cost']:.4f}`")
                if m.get("turns"):
                    parts.append(f"🔄 `{m['turns']} turns`")
                if m.get("duration"):
                    parts.append(f"⏱️ `{m['duration']:.1f}s`")
                if m.get("mem_injected"):
                    parts.append(f"🧠 `{m['mem_injected']} mem`")
                st.markdown(
                    "<div class='metric-row'>" + " &nbsp;·&nbsp; ".join(parts) + "</div>",
                    unsafe_allow_html=True,
                )


# ── Área de composição ────────────────────────────────────────────────────────
pending = st.session_state.get("pending_command")

if pending:
    # Comando selecionado via botão da sidebar
    cmd_defn = COMMAND_REGISTRY.get(pending.lstrip("/"))
    st.info(f"Comando selecionado: **`{pending}`**  —  {cmd_defn.description if cmd_defn else ''}")

    if pending in COMMANDS_NO_ARGS:
        # Executa imediatamente sem precisar de texto
        col1, col2 = st.columns([1, 5])
        if col1.button("▶  Executar", type="primary"):
            final_input = pending
            st.session_state.pending_command = None
        elif col2.button("✕ Cancelar"):
            st.session_state.pending_command = None
            st.rerun()
        else:
            st.stop()
    else:
        # Precisa de descrição da tarefa
        task_text = st.text_area(
            "Descreva a tarefa:",
            placeholder="Ex: pipeline de vendas no Databricks com Star Schema...",
            height=80,
            key="task_area",
        )
        col1, col2 = st.columns([1, 5])
        send_btn = col1.button("▶  Enviar", type="primary", disabled=not task_text.strip())
        cancel_btn = col2.button("✕ Cancelar")

        if cancel_btn:
            st.session_state.pending_command = None
            st.rerun()
        elif send_btn and task_text.strip():
            final_input = f"{pending} {task_text.strip()}"
            st.session_state.pending_command = None
        else:
            st.stop()

else:
    # Input livre via chat
    chat_input = st.chat_input(
        "Digite uma solicitação ou resposta (ex: 'sim, pode prosseguir') →",
    )
    if not chat_input:
        st.stop()
    final_input = chat_input


# ── Processamento da mensagem ─────────────────────────────────────────────────
# Adiciona mensagem do usuário ao histórico e exibe
st.session_state.messages.append({"role": "user", "content": final_input})
with st.chat_message("user"):
    st.markdown(final_input)

# Determina modo BMAD e monta prompt
command_result = parse_command(final_input)
enable_thinking = command_result is not None and command_result.bmad_mode == "full"
bmad_prompt = command_result.bmad_prompt if command_result else final_input

# Badge de modo
if command_result:
    mode_label = "🗺️ BMAD Full (planejamento)" if enable_thinking else "🚀 BMAD Express"
    agent_label = f"→ `{command_result.agent}`" if command_result.agent else ""
    st.caption(f"{mode_label} {agent_label}")

# Indicador de memórias injetadas (não /geral — que não usa o Supervisor)
_mem_injected_count = 0
if _memory_available() and not (command_result and command_result.command == "/geral"):
    try:
        from memory.store import MemoryStore
        from memory.decay import apply_decay
        from memory.retrieval import retrieve_relevant_memories

        _store_tmp = MemoryStore()
        _all_tmp = _store_tmp.list_all(active_only=False)
        if _all_tmp:
            apply_decay(_all_tmp, save_fn=_store_tmp.save)
        _rel_tmp = retrieve_relevant_memories(final_input, _store_tmp, max_memories=8)
        _mem_injected_count = len(_rel_tmp)
    except Exception:
        pass  # Sem Sonnet key ou store vazio — silencioso

# Executa o agente
with st.chat_message("assistant"):
    tools_box = st.empty()
    text_box = st.empty()
    metric_box = st.empty()

    # session_type = nome do comando (ex: "geral", "sql") ou "ui" para texto livre
    _session_type = command_result.command.lstrip("/") if command_result else "ui"
    is_geral = command_result is not None and command_result.command == "/geral"

    if is_geral:
        # Bypass do Supervisor — chama Haiku diretamente (~$0.002 vs ~$0.15 com Supervisor)
        with st.spinner("💬 Haiku pensando..."):
            result = _run_geral(bmad_prompt)
    else:
        with st.spinner("⏳ Agente processando..."):
            result = _run_agent(
                bmad_prompt, enable_thinking=enable_thinking, session_type=_session_type
            )

    # Ferramentas usadas (apenas para Claude — Gemini não usa ferramentas)
    if result["tools"]:
        with tools_box.expander(
            f"🔧 {len(result['tools'])} ferramenta(s) executada(s)", expanded=False
        ):
            for t in result["tools"]:
                st.caption(f"• {_tool_label(t)}")

    # Resposta ou erro
    if result["error"]:
        response_text = f"❌ **Erro:** {result['error']}"
        text_box.error(response_text)
    elif result["text"]:
        response_text = result["text"]
        text_box.markdown(response_text)
    else:
        response_text = "_Agente concluiu sem resposta textual._"
        text_box.caption(response_text)

    # Métricas
    parts = []
    if result["cost"]:
        parts.append(f"💰 `${result['cost']:.4f}`")
    if result["turns"]:
        parts.append(f"🔄 `{result['turns']} turns`")
    if result["duration"]:
        parts.append(f"⏱️ `{result['duration']:.1f}s`")
    if _mem_injected_count:
        parts.append(f"🧠 `{_mem_injected_count} mem`")
    if parts:
        metric_box.markdown(
            "<div class='metric-row'>" + " &nbsp;·&nbsp; ".join(parts) + "</div>",
            unsafe_allow_html=True,
        )

# Salva no histórico
st.session_state.messages.append(
    {
        "role": "assistant",
        "content": response_text,
        "tools": result["tools"],
        "metrics": {
            "cost": result["cost"],
            "turns": result["turns"],
            "duration": result["duration"],
            "mem_injected": _mem_injected_count,
        },
    }
)

# ── FIX: força refresh da página para exibir st.chat_input novamente ──────────
# Sem st.rerun(), o Streamlit não atualiza a área de composição após o agente
# responder — o usuário ficaria sem campo de input para digitar "sim" ou continuar.
st.rerun()
