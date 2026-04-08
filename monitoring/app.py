"""
monitoring/app.py — Dashboard de Monitoramento em Tempo Real
Data Agents Project

Uso:
   python -m streamlit run monitoring/app.py

Auto-refresh: use o seletor na sidebar para atualizar automaticamente.
"""

import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

SP_TZ = ZoneInfo("America/Sao_Paulo")


def to_sp(ts: str) -> str:
    """Converte timestamp ISO UTC para horário de São Paulo (America/Sao_Paulo)."""
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(SP_TZ).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts[:19].replace("T", " ")


# ── Configuração da página ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Data Agents — Monitoramento",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).parent.parent
AUDIT_LOG = ROOT / "logs" / "audit.jsonl"
APP_LOG = ROOT / "logs" / "app.jsonl"
REGISTRY = ROOT / "agents" / "registry"


# ── Leitura dos logs ──────────────────────────────────────────────────────────


@st.cache_data(ttl=5)  # recarrega a cada 5 segundos
def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


@st.cache_data(ttl=30)  # agentes mudam menos
def load_agents() -> list[dict]:
    agents = []
    if not REGISTRY.exists():
        return agents
    try:
        import yaml
    except ImportError:
        return agents
    for f in sorted(REGISTRY.glob("*.md")):
        if f.name.startswith("_"):
            continue
        content = f.read_text(encoding="utf-8")
        if not content.startswith("---"):
            continue
        try:
            end = content.index("---", 3)
            meta = yaml.safe_load(content[3:end])
            if meta:
                agents.append(meta)
        except Exception:
            continue
    return agents


# ── Análise ───────────────────────────────────────────────────────────────────


def analyse_audit(records: list[dict]) -> dict:
    by_date: dict[str, int] = defaultdict(int)
    by_tool: dict[str, int] = defaultdict(int)
    mcp_calls: list[dict] = []
    mcp_by_platform: dict[str, int] = defaultdict(int)

    for r in records:
        ts = r.get("timestamp", "")
        date = to_sp(ts)[:10] if ts else "unknown"
        tool = r.get("tool_name", "unknown")
        by_date[date] += 1
        by_tool[tool] += 1
        if tool.startswith("mcp__"):
            mcp_calls.append(r)
            # extrai plataforma: mcp__databricks__xxx → databricks
            parts = tool.split("__")
            if len(parts) >= 2:
                mcp_by_platform[parts[1]] += 1

    return {
        "total": len(records),
        "by_date": dict(sorted(by_date.items())),
        "by_tool": dict(sorted(by_tool.items(), key=lambda x: -x[1])),
        "mcp_calls": mcp_calls,
        "mcp_total": len(mcp_calls),
        "mcp_by_platform": dict(mcp_by_platform),
    }


def analyse_app(records: list[dict]) -> dict:
    by_level: dict[str, int] = defaultdict(int)
    warnings, errors, infos = [], [], []
    settings = {}

    for r in records:
        level = r.get("level", "")
        by_level[level] += 1
        if level == "WARNING":
            warnings.append(r)
        elif level == "ERROR":
            errors.append(r)
        elif level == "INFO":
            infos.append(r)
            msg = r.get("message", "")
            if "Configuração: model=" in msg:
                for part in msg.replace("📋 Configuração: ", "").split(", "):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        settings[k.strip()] = v.strip()

    return {
        "total": len(records),
        "by_level": dict(by_level),
        "warnings": warnings,
        "errors": errors,
        "infos": infos,
        "settings": settings,
        "recent_notable": sorted(
            warnings[-30:] + errors[-10:],
            key=lambda r: r.get("timestamp", ""),
            reverse=True,
        )[:40],
    }


def infer_mcp_status(audit: dict, app_records: list[dict]) -> dict:
    """
    Status real = se houver chamadas MCP para a plataforma → Configurado.
    Fallback: lê warnings do app.jsonl apenas se NUNCA houve chamada.
    """
    platforms = {
        "databricks": {
            "label": "Databricks",
            "icon": "🟠",
            "configured": False,
            "calls": audit["mcp_by_platform"].get("databricks", 0),
            "missing": [],
        },
        "fabric": {
            "label": "Microsoft Fabric",
            "icon": "🔵",
            "configured": False,
            "calls": audit["mcp_by_platform"].get("fabric", 0),
            "missing": [],
        },
        "fabric_rti": {
            "label": "Fabric Real-Time Intelligence",
            "icon": "🟣",
            "configured": False,
            "calls": audit["mcp_by_platform"].get("fabric_rti", 0),
            "missing": [],
        },
        "fabric_community": {
            "label": "Fabric Community",
            "icon": "🟢",
            "configured": False,
            "calls": audit["mcp_by_platform"].get("fabric_community", 0),
            "missing": [],
        },
    }

    # Se houve chamadas reais → configurado (fonte mais confiável)
    for key, plat in platforms.items():
        if plat["calls"] > 0:
            plat["configured"] = True

    # Para plataformas sem chamadas, checa warnings mais recentes do app.jsonl
    recent_warns = [r.get("message", "") for r in app_records[-500:] if r.get("level") == "WARNING"]
    warn_text = "\n".join(recent_warns)

    if not platforms["databricks"]["configured"]:
        if "DATABRICKS: variáveis ausentes:" in warn_text:
            for line in recent_warns:
                if "DATABRICKS: variáveis ausentes:" in line:
                    missing = line.split("variáveis ausentes:")[-1].split(".")[0].strip()
                    platforms["databricks"]["missing"] = [v.strip() for v in missing.split(",")]
        else:
            # Sem warning recente e sem chamadas → estado desconhecido
            platforms["databricks"]["configured"] = None  # type: ignore

    if not platforms["fabric"]["configured"]:
        if "FABRIC: variáveis ausentes:" in warn_text:
            for line in recent_warns:
                if "FABRIC: variáveis ausentes:" in line and "FABRIC_RTI" not in line:
                    missing = line.split("variáveis ausentes:")[-1].split(".")[0].strip()
                    platforms["fabric"]["missing"] = [v.strip() for v in missing.split(",")]
        else:
            # Sem warning e sem chamadas → ainda não foi utilizado nesta sessão
            platforms["fabric"]["configured"] = None  # type: ignore

    if not platforms["fabric_rti"]["configured"]:
        if "FABRIC_RTI: variáveis ausentes:" in warn_text:
            for line in recent_warns:
                if "FABRIC_RTI: variáveis ausentes:" in line:
                    missing = line.split("variáveis ausentes:")[-1].split(".")[0].strip()
                    platforms["fabric_rti"]["missing"] = [v.strip() for v in missing.split(",")]
        else:
            # Sem warning e sem chamadas → ainda não foi utilizado nesta sessão
            platforms["fabric_rti"]["configured"] = None  # type: ignore

    return platforms


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🤖 Data Agents")
    st.caption("Monitoramento em Tempo Real")
    st.divider()

    page = st.radio(
        "Navegação",
        [
            "📊 Overview",
            "🤖 Agentes",
            "⚡ Execuções",
            "🔌 MCP Servers",
            "📋 Logs",
            "⚙️ Configurações",
            "ℹ️ Sobre",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    refresh_interval = st.select_slider(
        "Auto-refresh",
        options=[0, 5, 10, 30, 60],
        value=0,
        format_func=lambda x: "Manual" if x == 0 else f"{x}s",
    )
    if st.button("🔄 Atualizar agora", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.caption(f"Logs: `{AUDIT_LOG.relative_to(ROOT)}`")
    st.caption(f"`{APP_LOG.relative_to(ROOT)}`")


# ── Carrega dados ─────────────────────────────────────────────────────────────

audit_records = load_jsonl(AUDIT_LOG)
app_records = load_jsonl(APP_LOG)
agents = load_agents()
audit = analyse_audit(audit_records)
app = analyse_app(app_records)
mcp_status = infer_mcp_status(audit, app_records)

# Auto-refresh
if refresh_interval > 0:
    time.sleep(refresh_interval)
    st.cache_data.clear()
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGES
# ══════════════════════════════════════════════════════════════════════════════

# ── OVERVIEW ──────────────────────────────────────────────────────────────────
if page == "📊 Overview":
    st.title("📊 Overview")
    st.caption(
        f"Baseado em **{audit['total']}** entradas no audit.jsonl e **{app['total']}** no app.jsonl"
    )

    # KPIs
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tool Calls", f"{audit['total']:,}", help="Total no audit.jsonl")
    c2.metric("Chamadas MCP", audit["mcp_total"], help="Ferramentas mcp__*")
    c3.metric("Agentes Registrados", len(agents), help="agents/registry/*.md")
    c4.metric("Warnings", app["by_level"].get("WARNING", 0), help="app.jsonl")
    c5.metric("Errors", app["by_level"].get("ERROR", 0), help="app.jsonl")

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📅 Atividade por Data")
        if audit["by_date"]:
            import pandas as pd

            df_date = pd.DataFrame(
                {
                    "Data": list(audit["by_date"].keys()),
                    "Tool Calls": list(audit["by_date"].values()),
                }
            ).set_index("Data")
            st.bar_chart(df_date, color="#6366f1")

        st.subheader("🔧 Top Ferramentas")
        import pandas as pd

        top10 = dict(list(audit["by_tool"].items())[:10])
        st.bar_chart(pd.Series(top10), color="#22c55e")

    with col_right:
        st.subheader("🔌 MCP Servers")
        for key, plat in mcp_status.items():
            configured = plat["configured"]
            if configured is True:
                st.success(f"{plat['icon']} **{plat['label']}** — {plat['calls']} chamadas")
            elif configured is False:
                missing_str = ", ".join(plat["missing"])
                st.warning(f"{plat['icon']} **{plat['label']}** — ausentes: `{missing_str}`")
            else:
                st.info(f"{plat['icon']} **{plat['label']}** — não utilizado nesta sessão")

        st.divider()
        st.subheader("📋 Níveis do App Log")
        level_data = {k: v for k, v in app["by_level"].items() if k}
        if level_data:
            import pandas as pd

            df_levels = pd.Series(level_data)
            st.bar_chart(df_levels, color="#f59e0b")

    # Avisos recentes
    if app["recent_notable"]:
        st.divider()
        st.subheader("⚠️ Avisos e Erros Recentes")
        for r in app["recent_notable"][:10]:
            level = r.get("level", "")
            ts = to_sp(r.get("timestamp", ""))
            msg = r.get("message", "")
            if level == "ERROR":
                st.error(f"`{ts}` {msg}")
            else:
                st.warning(f"`{ts}` {msg}")


# ── AGENTES ───────────────────────────────────────────────────────────────────
elif page == "🤖 Agentes":
    st.title("🤖 Agentes Especialistas")
    st.caption(f"Definidos em `agents/registry/` — **{len(agents)}** agentes carregados")

    if not agents:
        st.error(
            "Nenhum agente encontrado. Verifique se pyyaml está instalado: `pip install pyyaml`"
        )
    else:
        tier_colors = {"T1": "🔵", "T2": "🟢"}
        cols = st.columns(2)
        for i, agent in enumerate(agents):
            with cols[i % 2]:
                tier = agent.get("tier", "?")
                model = agent.get("model", "?")
                mcps = agent.get("mcp_servers", [])
                tools = agent.get("tools", [])
                kb = agent.get("kb_domains", [])
                with st.container(border=True):
                    st.markdown(f"### {tier_colors.get(tier, '⚪')} {agent.get('name', '?')}")
                    st.caption(agent.get("description", "")[:200])
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Tier", tier)
                    c2.metric("Modelo", model.replace("claude-", "").replace("-", " "))
                    c3.metric("MCP Servers", len(mcps))
                    if tools:
                        st.markdown("**Tools:**")
                        st.code(" · ".join(tools[:12]) + ("..." if len(tools) > 12 else ""))
                    if mcps:
                        st.markdown("**MCP Servers:** " + " · ".join([f"`{m}`" for m in mcps]))
                    if kb:
                        st.markdown("**KB Domains:** " + " · ".join([f"`{k}`" for k in kb]))


# ── EXECUÇÕES ─────────────────────────────────────────────────────────────────
elif page == "⚡ Execuções":
    st.title("⚡ Execuções — Audit Log")
    st.caption(f"**{audit['total']}** tool calls em **{len(audit['by_date'])}** dias")

    import pandas as pd

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de Chamadas", f"{audit['total']:,}")
    c2.metric("Ferramentas Distintas", len(audit["by_tool"]))
    c3.metric("Chamadas MCP", audit["mcp_total"])
    top = list(audit["by_tool"].items())[0] if audit["by_tool"] else ("—", 0)
    c4.metric("Mais Usada", f"{top[0]} ({top[1]}×)")

    st.divider()
    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader("Todas as Ferramentas")
        df_tools = pd.DataFrame(
            [{"Ferramenta": k, "Chamadas": v} for k, v in audit["by_tool"].items()]
        )
        st.dataframe(
            df_tools,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Chamadas": st.column_config.ProgressColumn(max_value=df_tools["Chamadas"].max())
            },
        )

    with col2:
        st.subheader("Chamadas MCP por Plataforma")
        if audit["mcp_by_platform"]:
            df_mcp = pd.DataFrame(
                [{"Plataforma": k, "Chamadas": v} for k, v in audit["mcp_by_platform"].items()]
            )
            st.dataframe(df_mcp, use_container_width=True, hide_index=True)

            st.subheader("MCP por Ferramenta")
            mcp_by_tool = defaultdict(int)
            for r in audit["mcp_calls"]:
                mcp_by_tool[r.get("tool_name", "?")] += 1
            df_mcp_tools = pd.DataFrame(
                [
                    {"Tool": k, "Chamadas": v}
                    for k, v in sorted(mcp_by_tool.items(), key=lambda x: -x[1])
                ]
            )
            st.dataframe(df_mcp_tools, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma chamada MCP registrada ainda.")

    st.divider()
    st.subheader("📅 Atividade por Data")
    df_date = pd.DataFrame(
        [{"Data": k, "Tool Calls": v} for k, v in audit["by_date"].items()]
    ).set_index("Data")
    st.bar_chart(df_date, color="#6366f1")


# ── MCP SERVERS ───────────────────────────────────────────────────────────────
elif page == "🔌 MCP Servers":
    st.title("🔌 MCP Servers")
    st.caption(
        "Status baseado em chamadas reais no `audit.jsonl` "
        "(mais confiável que os logs de inicialização)"
    )

    for key, plat in mcp_status.items():
        configured = plat["configured"]
        with st.container(border=True):
            col_title, col_status = st.columns([3, 1])
            with col_title:
                st.markdown(f"### {plat['icon']} {plat['label']}")
            with col_status:
                if configured is True:
                    st.success("✓ Ativo")
                elif configured is False:
                    st.error("✗ Credenciais ausentes")
                else:
                    st.info("— Não utilizado")

            col_a, col_b = st.columns(2)
            col_a.metric("Chamadas Registradas", plat["calls"])
            if configured is False and plat["missing"]:
                col_b.markdown("**Variáveis ausentes:**")
                for m in plat["missing"]:
                    col_b.code(m)

    st.divider()
    st.subheader("📞 Histórico de Chamadas MCP")
    if audit["mcp_calls"]:
        import pandas as pd

        df_mcp = pd.DataFrame(
            [
                {
                    "Timestamp": to_sp(r.get("timestamp", "")),
                    "Tool": r.get("tool_name", ""),
                    "Inputs": ", ".join(r.get("input_keys", [])),
                    "ID": r.get("tool_use_id", "")[-12:],
                }
                for r in reversed(audit["mcp_calls"])
            ]
        )
        st.dataframe(df_mcp, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma chamada MCP registrada no audit.jsonl.")


# ── LOGS ──────────────────────────────────────────────────────────────────────
elif page == "📋 Logs":
    st.title("📋 Logs em Tempo Real")

    tab1, tab2 = st.tabs(["📄 app.jsonl", "🔍 audit.jsonl"])

    with tab1:
        col_f1, col_f2 = st.columns([2, 2])
        level_filter = col_f1.multiselect(
            "Filtrar nível",
            options=["INFO", "WARNING", "ERROR", "DEBUG"],
            default=["INFO", "WARNING", "ERROR"],
        )
        search_term = col_f2.text_input("Buscar mensagem", placeholder="ex: MCP, Databricks...")

        filtered_app = [
            r
            for r in app_records
            if r.get("level") in level_filter
            and (not search_term or search_term.lower() in r.get("message", "").lower())
        ]

        st.caption(
            f"Mostrando **{min(200, len(filtered_app))}** de **{len(filtered_app)}** entradas"
        )

        import pandas as pd

        if filtered_app:
            df_app = pd.DataFrame(
                [
                    {
                        "Timestamp": to_sp(r.get("timestamp", "")),
                        "Nível": r.get("level", ""),
                        "Logger": r.get("logger", "").replace("data_agents.", ""),
                        "Mensagem": r.get("message", "")[:200],
                    }
                    for r in reversed(filtered_app[-200:])
                ]
            )
            st.dataframe(
                df_app,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Nível": st.column_config.TextColumn(width="small"),
                    "Timestamp": st.column_config.TextColumn(width="medium"),
                },
            )

    with tab2:
        col_a1, col_a2 = st.columns([2, 2])
        tool_filter = col_a1.multiselect(
            "Filtrar tipo",
            options=["Todos", "MCP", "Agent", "Bash", "Read", "Write"],
            default=["Todos"],
        )
        search_audit = col_a2.text_input(
            "Buscar tool", placeholder="ex: databricks, execute_sql..."
        )

        filtered_audit = audit_records
        if "Todos" not in tool_filter and tool_filter:
            filtered_audit = [
                r
                for r in audit_records
                if any(
                    (f == "MCP" and r.get("tool_name", "").startswith("mcp__"))
                    or r.get("tool_name") == f
                    for f in tool_filter
                )
            ]
        if search_audit:
            filtered_audit = [
                r for r in filtered_audit if search_audit.lower() in r.get("tool_name", "").lower()
            ]

        st.caption(
            f"Mostrando **{min(200, len(filtered_audit))}** de **{len(filtered_audit)}** entradas"
        )

        if filtered_audit:
            import pandas as pd

            df_audit = pd.DataFrame(
                [
                    {
                        "Timestamp": to_sp(r.get("timestamp", "")),
                        "Tool": r.get("tool_name", ""),
                        "Inputs": ", ".join(r.get("input_keys", [])),
                        "ID": r.get("tool_use_id", "")[-12:],
                    }
                    for r in reversed(filtered_audit[-200:])
                ]
            )
            st.dataframe(df_audit, use_container_width=True, hide_index=True)


# ── CONFIGURAÇÕES ─────────────────────────────────────────────────────────────
elif page == "⚙️ Configurações":
    st.title("⚙️ Configurações do Sistema")
    st.caption("Detectado do último run registrado em `logs/app.jsonl`")

    settings = app["settings"]
    if settings:
        c1, c2, c3 = st.columns(3)
        c1.metric("Modelo Padrão", settings.get("model", "—"))
        c2.metric("Budget Máximo", settings.get("budget", "—"))
        c3.metric("Max Turns", settings.get("max_turns", "—"))
    else:
        st.warning(
            "Nenhuma configuração encontrada no app.jsonl. Execute o agente ao menos uma vez."
        )

    st.divider()
    st.subheader("📁 Arquivos do Projeto")

    import pandas as pd

    files_info = [
        ("config/settings.py", "Settings: modelo, budget, max_turns, credenciais"),
        ("config/mcp_servers.py", "Build dos MCP servers por plataforma"),
        ("config/logging_config.py", "Setup do logging estruturado JSONL"),
        (f"agents/registry/ ({len(agents)} agentes)", "Definições YAML/Markdown dos agentes"),
        ("agents/loader.py", "Loader dinâmico do registry"),
        ("agents/supervisor.py", "Factory do ClaudeAgentOptions"),
        ("hooks/security_hook.py", "Bloqueia comandos destrutivos (PreToolUse)"),
        ("hooks/audit_hook.py", "Registra todas as tool calls (PostToolUse)"),
        ("hooks/cost_guard_hook.py", "Alerta operações de alto custo (PostToolUse)"),
        (f"logs/audit.jsonl ({audit['total']} entradas)", "Histórico completo de tool calls"),
        (f"logs/app.jsonl ({app['total']} entradas)", "Log estruturado da aplicação"),
    ]
    df_files = pd.DataFrame(files_info, columns=["Arquivo", "Finalidade"])
    st.dataframe(df_files, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("🔄 Sobre o Dashboard")
    st.info(
        "Este dashboard lê os arquivos de log em tempo real. "
        "Use o **auto-refresh** na sidebar para atualizações automáticas enquanto os agentes rodam. "
        "O cache é de 5 segundos para `audit.jsonl` e `app.jsonl`."
    )


# ── SOBRE ─────────────────────────────────────────────────────────────────────
elif page == "ℹ️ Sobre":
    st.title("ℹ️ Sobre este Dashboard")
    st.divider()

    # Cabeçalho de identidade
    col_meta, col_badge = st.columns([3, 1])
    with col_meta:
        st.markdown("## Data Agents — Monitoramento")
        st.caption("Dashboard de observabilidade para o sistema multi-agente Data Agents")
    with col_badge:
        st.markdown(
            """
            <div style='text-align:right;margin-top:8px'>
                <span style='background:#dcfce7;color:#16a34a;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:700'>● Ativo</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    # Metadados
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("**👤 Autor**")
        st.markdown("Thomaz Antonio Rossito Neto")
    with c2:
        st.markdown("**📅 Data de Criação**")
        st.markdown("Abril de 2026")
    with c3:
        st.markdown("**🔖 Versão**")
        st.markdown("`v1.0.0`")
    with c4:
        st.markdown("**📄 Licença**")
        st.markdown("MIT License")

    st.divider()

    # O que é este dashboard
    st.subheader("📋 O que é este monitoramento?")
    st.markdown(
        """
        Este dashboard oferece **observabilidade em tempo real** para o projeto **Data Agents** —
        um sistema multi-agente baseado no Claude Agent SDK que orquestra especialistas de dados
        contra plataformas Databricks e Microsoft Fabric.

        O monitoramento lê diretamente os arquivos de log gerados pelos hooks do sistema
        (`logs/audit.jsonl` e `logs/app.jsonl`) e apresenta as informações de forma estruturada,
        sem necessidade de infraestrutura adicional.
        """
    )

    st.divider()

    # O que cada aba monitora
    st.subheader("🗂️ O que cada aba monitora")

    abas = [
        (
            "📊 Overview",
            "Visão consolidada do sistema: total de tool calls, chamadas MCP reais, "
            "agentes registrados, warnings e erros. Inclui gráfico de atividade por data, ranking "
            "de ferramentas mais usadas e status rápido dos MCP servers.",
        ),
        (
            "🤖 Agentes",
            "Todos os agentes especialistas definidos em `agents/registry/*.md`. "
            "Exibe tier (T1/T2), modelo Claude utilizado, tools disponíveis, MCP servers "
            "conectados e domínios de Knowledge Base de cada agente.",
        ),
        (
            "⚡ Execuções",
            "Histórico completo de execuções a partir do `audit.jsonl`. Mostra "
            "volume de uso por ferramenta, chamadas MCP agrupadas por plataforma e por tool "
            "específica, e evolução da atividade ao longo dos dias.",
        ),
        (
            "🔌 MCP Servers",
            "Status real das plataformas de dados: Databricks, Microsoft Fabric, "
            "Fabric Real-Time Intelligence e Fabric Community. O status é derivado das chamadas "
            "reais no audit.jsonl — se houve chamadas, a plataforma estava configurada. "
            "Exibe histórico completo de todas as chamadas MCP com timestamp e inputs.",
        ),
        (
            "📋 Logs",
            "Visualizador ao vivo dos dois arquivos de log do projeto. "
            "`app.jsonl` filtrável por nível (INFO/WARNING/ERROR/DEBUG) e por texto. "
            "`audit.jsonl` filtrável por tipo de ferramenta (MCP, Agent, Bash etc.). "
            "Ambos atualizam automaticamente com o auto-refresh ativado.",
        ),
        (
            "⚙️ Configurações",
            "Parâmetros do sistema detectados do último run: modelo padrão, "
            "budget máximo por sessão e limite de turns. Mapa de todos os arquivos relevantes "
            "do projeto com sua finalidade.",
        ),
    ]

    for titulo, descricao in abas:
        with st.expander(titulo, expanded=False):
            st.markdown(descricao)

    st.divider()

    # Fontes de dados
    st.subheader("📂 Fontes de Dados")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**`logs/audit.jsonl`** — gerado pelo `audit_hook.py`")
        st.markdown(
            "Registra **toda tool call** executada pelo sistema (PostToolUse hook). "
            "Cada linha contém: timestamp, nome da ferramenta, tool_use_id e chaves de input."
        )
    with col_b:
        st.markdown("**`logs/app.jsonl`** — gerado pelo `logging_config.py`**")
        st.markdown(
            "Log estruturado da aplicação usando `JSONLFormatter`. "
            "Registra inicialização, status dos MCP servers, configurações carregadas, "
            "warnings de credenciais e erros de runtime."
        )

    st.divider()

    # Arquitetura do sistema monitorado
    st.subheader("🏗️ Arquitetura do Sistema Monitorado")
    st.markdown(
        """
        O **Data Agents** é um sistema multi-agente que segue a arquitetura **BMAD**
        (Business Model Agents Design):

        - **Supervisor** — orquestra os agentes especialistas, gerencia MCP servers e aplica hooks
        - **SQL Expert** (T1) — queries SQL/KQL em Databricks e Fabric RTI
        - **Spark Expert** (T1) — código PySpark, Delta Lake e pipelines DLT
        - **Pipeline Architect** (T1) — design e execução de pipelines ETL/ELT cross-platform
        - **Data Quality Steward** (T2) — validação, profiling e alertas de qualidade
        - **Governance Auditor** (T2) — auditoria de acesso, linhagem e conformidade LGPD
        - **Semantic Modeler** (T2) — modelos semânticos DAX e Metric Views

        Os **hooks** interceptam cada execução de ferramenta:
        `security_hook` bloqueia comandos destrutivos,
        `audit_hook` registra todas as chamadas,
        `cost_guard_hook` alerta sobre operações de alto custo.
        """
    )

    st.divider()

    # Licença
    st.subheader("📄 Licença")
    st.code(
        "MIT License\n\n"
        "Copyright (c) 2026 Thomaz Antonio Rossito Neto\n\n"
        "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
        'of this software and associated documentation files (the "Software"), to deal\n'
        "in the Software without restriction, including without limitation the rights\n"
        "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n"
        "copies of the Software, and to permit persons to whom the Software is\n"
        "furnished to do so, subject to the following conditions:\n\n"
        "The above copyright notice and this permission notice shall be included in all\n"
        "copies or substantial portions of the Software.\n\n"
        'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n'
        "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n"
        "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.",
        language="text",
    )
