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
from datetime import date, datetime, timedelta, timezone
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
SESSIONS_LOG = ROOT / "logs" / "sessions.jsonl"
COMPRESSION_LOG = ROOT / "logs" / "compression.jsonl"
WORKFLOWS_LOG = ROOT / "logs" / "workflows.jsonl"
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
            "🔄 Workflows",
            "⚡ Execuções",
            "🔌 MCP Servers",
            "📋 Logs",
            "⚙️ Configurações",
            "💰 Custo & Tokens",
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
    _tz_options = ["America/Sao_Paulo", "America/New_York", "Europe/London", "UTC", "Asia/Tokyo"]
    _selected_tz = st.selectbox(
        "🕐 Timezone",
        _tz_options,
        index=0,
        label_visibility="visible",
    )
    try:
        import zoneinfo

        _DISPLAY_TZ = zoneinfo.ZoneInfo(_selected_tz)
    except Exception:
        import pytz  # type: ignore[import]

        _DISPLAY_TZ = pytz.timezone(_selected_tz)  # type: ignore[assignment]

    # Freshness indicator
    _load_ts = datetime.now(timezone.utc)
    st.caption(f"🕐 Dados: `{_load_ts.strftime('%H:%M:%S')} UTC`")
    st.divider()
    st.caption(f"Logs: `{AUDIT_LOG.relative_to(ROOT)}`")
    st.caption(f"`{APP_LOG.relative_to(ROOT)}`")


# ── Carrega dados ─────────────────────────────────────────────────────────────

_all_audit_records = load_jsonl(AUDIT_LOG)
_all_app_records = load_jsonl(APP_LOG)
_all_session_records = load_jsonl(SESSIONS_LOG)
_all_compression_records = load_jsonl(COMPRESSION_LOG)
_all_workflow_records = load_jsonl(WORKFLOWS_LOG)
agents = load_agents()


# ── Filtro de Datas (sidebar) ────────────────────────────────────────────────


def _extract_date(record: dict) -> date | None:
    """Extrai a data de um record a partir do campo 'timestamp'."""
    ts = record.get("timestamp", "")
    if not ts or len(ts) < 10:
        return None
    try:
        return date.fromisoformat(ts[:10])
    except ValueError:
        return None


def _date_bounds(records_list: list[list[dict]]) -> tuple[date, date]:
    """Encontra as datas mínima e máxima entre várias listas de records."""
    all_dates: list[date] = []
    for records in records_list:
        for r in records:
            d = _extract_date(r)
            if d:
                all_dates.append(d)
    if not all_dates:
        today = date.today()
        return today - timedelta(days=30), today
    return min(all_dates), max(all_dates)


def _filter_by_date(records: list[dict], start: date, end: date) -> list[dict]:
    """Filtra records pelo range de datas (inclusivo)."""
    filtered = []
    for r in records:
        d = _extract_date(r)
        if d is None or (start <= d <= end):
            filtered.append(r)
    return filtered


min_date, max_date = _date_bounds(
    [_all_audit_records, _all_app_records, _all_session_records, _all_workflow_records]
)

with st.sidebar:
    st.divider()
    st.markdown("**📅 Filtro de Período**")
    date_range = st.date_input(
        "Intervalo de datas",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        format="DD/MM/YYYY",
        label_visibility="collapsed",
    )
    # Trata seleção parcial (apenas uma data)
    if isinstance(date_range, tuple) and len(date_range) == 2:
        filter_start, filter_end = date_range
    else:
        filter_start = date_range[0] if isinstance(date_range, tuple) else date_range
        filter_end = max_date

    if filter_start != min_date or filter_end != max_date:
        st.caption(f"🔍 {filter_start.strftime('%d/%m/%Y')} → {filter_end.strftime('%d/%m/%Y')}")

audit_records = _filter_by_date(_all_audit_records, filter_start, filter_end)
app_records = _filter_by_date(_all_app_records, filter_start, filter_end)
session_records = _filter_by_date(_all_session_records, filter_start, filter_end)
compression_records = _filter_by_date(_all_compression_records, filter_start, filter_end)
workflow_records = _filter_by_date(_all_workflow_records, filter_start, filter_end)

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

    # Custo total das sessões registradas + Cache Hit Rate
    if session_records:
        total_session_cost = sum(r.get("total_cost_usd", 0) or 0 for r in session_records)

        # Cache hit rate (campos da API Anthropic: cache_read_input_tokens / input_tokens)
        total_input = sum(r.get("total_input_tokens", 0) or 0 for r in session_records)
        total_cache_read = sum(r.get("cache_read_input_tokens", 0) or 0 for r in session_records)
        cache_hit_rate = (total_cache_read / total_input * 100) if total_input > 0 else None

        cost_cols = st.columns([2, 1])
        with cost_cols[0]:
            st.info(
                f"💰 Custo total acumulado: **${total_session_cost:.4f}** em **{len(session_records)}** sessões registradas"
            )
        with cost_cols[1]:
            if cache_hit_rate is not None:
                color = (
                    "green" if cache_hit_rate >= 40 else "orange" if cache_hit_rate >= 15 else "red"
                )
                st.metric(
                    "🗃️ Cache Hit Rate",
                    f"{cache_hit_rate:.1f}%",
                    help="Tokens reutilizados do prompt cache Anthropic. >40% = excelente, >15% = bom.",
                    delta=f"{'✅' if cache_hit_rate >= 40 else '⚠️' if cache_hit_rate >= 15 else '❌'} {'Excelente' if cache_hit_rate >= 40 else 'Baixo'}",
                )
            else:
                st.info("🗃️ Cache Hit Rate: sem dados (sessions log não contém token breakdown)")

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
        # ── Performance por Agente (dados do workflows.jsonl) ──
        agent_delegations: dict[str, int] = defaultdict(int)
        agent_in_workflows: dict[str, int] = defaultdict(int)
        for wr in workflow_records:
            evt = wr.get("event", "")
            ag = wr.get("agent", "")
            if evt in ("agent_delegation", "workflow_step") and ag:
                agent_delegations[ag] += 1
            if evt == "workflow_step" and ag:
                agent_in_workflows[ag] += 1

        # Dados do audit: chamadas MCP por agente (inferido pela tool)
        agent_tool_counts: dict[str, int] = defaultdict(int)
        agent_errors: dict[str, int] = defaultdict(int)
        for ar in audit_records:
            tool = ar.get("tool_name", "")
            if tool.startswith("mcp__"):
                # Inferir agente pela plataforma (aproximação)
                platform = ar.get("platform", "")
                if platform:
                    agent_tool_counts[platform] += 1
            if ar.get("has_error"):
                cat = ar.get("error_category", "unknown")
                agent_errors[cat] = agent_errors.get(cat, 0) + 1

        # ── KPIs de Performance ──
        total_delegations = sum(agent_delegations.values())
        total_wf_steps = sum(agent_in_workflows.values())
        total_errors = sum(agent_errors.values())

        if total_delegations > 0 or total_errors > 0:
            st.subheader("📈 Performance dos Agentes")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total de Delegações", total_delegations, help="workflows.jsonl")
            c2.metric("Em Workflows", total_wf_steps, help="Delegações dentro de WF-01 a WF-05")
            c3.metric("Erros Detectados", total_errors, help="audit.jsonl (has_error=true)")
            if total_delegations > 0:
                error_rate = round(total_errors / (total_delegations + audit["total"]) * 100, 1)
                c4.metric("Taxa de Erro", f"{error_rate}%")
            else:
                c4.metric("Taxa de Erro", "—")

            if agent_delegations:
                import pandas as pd

                col_perf1, col_perf2 = st.columns(2)
                with col_perf1:
                    st.markdown("**Delegações por Agente:**")
                    df_deleg = pd.DataFrame(
                        [
                            {"Agente": k, "Delegações": v}
                            for k, v in sorted(agent_delegations.items(), key=lambda x: -x[1])
                        ]
                    )
                    st.dataframe(
                        df_deleg,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Delegações": st.column_config.ProgressColumn(
                                max_value=max(agent_delegations.values())
                                if agent_delegations
                                else 1
                            )
                        },
                    )

                with col_perf2:
                    if agent_errors:
                        st.markdown("**Erros por Categoria:**")
                        df_errors = pd.DataFrame(
                            [
                                {"Categoria": k, "Ocorrências": v}
                                for k, v in sorted(agent_errors.items(), key=lambda x: -x[1])
                            ]
                        )
                        st.dataframe(df_errors, use_container_width=True, hide_index=True)
                    else:
                        st.success("Nenhum erro categorizado detectado.")

            st.divider()

        # ── Cards dos Agentes ──
        _TIER_BADGE = {
            "T1": '<span style="background:#0F1A0F;color:#3FB950;border:1px solid #3FB950;padding:2px 8px;border-radius:10px;font-size:0.75em;font-weight:600">T1 Core</span>',
            "T2": '<span style="background:#1A0F1A;color:#A78BFA;border:1px solid #A78BFA;padding:2px 8px;border-radius:10px;font-size:0.75em;font-weight:600">T2 Especialista</span>',
            "T3": '<span style="background:#1A1510;color:#FCD34D;border:1px solid #FCD34D;padding:2px 8px;border-radius:10px;font-size:0.75em;font-weight:600">T3 Conversacional</span>',
        }
        cols = st.columns(2)
        for i, agent in enumerate(
            sorted(agents, key=lambda a: (a.get("tier", "T9"), a.get("name", "")))
        ):
            with cols[i % 2]:
                tier = agent.get("tier", "?")
                model = agent.get("model", "?")
                mcps = agent.get("mcp_servers", [])
                tools = agent.get("tools", [])
                kb = agent.get("kb_domains", [])
                agent_name = agent.get("name", "?")
                deleg_count = agent_delegations.get(agent_name, 0)
                wf_count = agent_in_workflows.get(agent_name, 0)
                with st.container(border=True):
                    badge = _TIER_BADGE.get(tier, f"<code>{tier}</code>")
                    st.markdown(f"### {agent_name} {badge}", unsafe_allow_html=True)
                    st.caption(agent.get("description", "")[:200])
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Tier", tier)
                    c2.metric("Modelo", model.replace("claude-", "").replace("-", " "))
                    c3.metric("Delegações", deleg_count)
                    c4.metric("Em Workflows", wf_count)
                    if tools:
                        st.markdown("**Tools:**")
                        st.code(" · ".join(tools[:12]) + ("..." if len(tools) > 12 else ""))
                    if mcps:
                        st.markdown("**MCP Servers:** " + " · ".join([f"`{m}`" for m in mcps]))
                    if kb:
                        st.markdown("**KB Domains:** " + " · ".join([f"`{k}`" for k in kb]))


# ── WORKFLOWS ────────────────────────────────────────────────────────────────
elif page == "🔄 Workflows":
    st.title("🔄 Workflows & Clarity Checkpoint")
    st.caption(
        f"Rastreamento de workflows colaborativos, delegações e validação de clareza — "
        f"**{len(workflow_records)}** eventos registrados"
    )

    import pandas as pd

    if not workflow_records:
        st.info(
            "Nenhum evento de workflow registrado ainda em `logs/workflows.jsonl`.\n\n"
            "Os eventos são gravados automaticamente quando o supervisor:\n"
            "- Delega tarefas para agentes especialistas\n"
            "- Executa o Clarity Checkpoint (Passo 0.5)\n"
            "- Gera specs (Passo 0.9)\n"
            "- Aciona workflows WF-01 a WF-05"
        )
    else:
        # Classificar eventos
        delegations = [r for r in workflow_records if r.get("event") == "agent_delegation"]
        wf_steps = [r for r in workflow_records if r.get("event") == "workflow_step"]
        clarity = [r for r in workflow_records if r.get("event") == "clarity_checkpoint"]
        clarifications = [
            r for r in workflow_records if r.get("event") == "clarity_clarification_requested"
        ]
        specs = [r for r in workflow_records if r.get("event") == "spec_generated"]

        # ── KPIs ──
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Delegações", len(delegations) + len(wf_steps))
        c2.metric("Workflows", len(wf_steps), help="Etapas dentro de WF-01 a WF-05")
        c3.metric("Clarity Checks", len(clarity))
        c4.metric(
            "Esclarecimentos",
            len(clarifications),
            help="Vezes que o Clarity Checkpoint pediu mais informações",
        )
        c5.metric("Specs Gerados", len(specs))

        st.divider()

        col_left, col_right = st.columns(2)

        with col_left:
            # ── Delegações por Agente ──
            st.subheader("🤖 Delegações por Agente")
            all_delegs = delegations + wf_steps
            if all_delegs:
                agent_counts: dict[str, int] = defaultdict(int)
                for d in all_delegs:
                    agent_counts[d.get("agent", "unknown")] += 1
                df_agents = pd.DataFrame(
                    [
                        {"Agente": k, "Delegações": v}
                        for k, v in sorted(agent_counts.items(), key=lambda x: -x[1])
                    ]
                )
                st.bar_chart(df_agents.set_index("Agente"), color="#6366f1")
            else:
                st.info("Nenhuma delegação registrada.")

            # ── Workflows Acionados ──
            st.subheader("🔄 Workflows Acionados")
            if wf_steps:
                wf_names = {
                    "WF-01": "Pipeline End-to-End",
                    "WF-02": "Star Schema",
                    "WF-03": "Migração Cross-Platform",
                    "WF-04": "Auditoria Governança",
                    "WF-05": "Migração Relacional → Nuvem",
                }
                wf_counts: dict[str, int] = defaultdict(int)
                for ws in wf_steps:
                    wf_id = ws.get("workflow", "unknown")
                    wf_counts[wf_id] += 1
                df_wf = pd.DataFrame(
                    [
                        {"Workflow": f"{k} — {wf_names.get(k, k)}", "Etapas": v}
                        for k, v in sorted(wf_counts.items())
                    ]
                )
                st.dataframe(df_wf, use_container_width=True, hide_index=True)
                # Download CSV
                st.download_button(
                    "⬇️ Exportar CSV",
                    df_wf.to_csv(index=False).encode("utf-8"),
                    "workflows.csv",
                    "text/csv",
                    key="dl_wf",
                )
            else:
                st.info("Nenhum workflow colaborativo acionado ainda.")

        with col_right:
            # ── Clarity Checkpoint ──
            st.subheader("🎯 Clarity Checkpoint")
            if clarity:
                passed = sum(1 for c in clarity if c.get("passed", False))
                failed = len(clarity) - passed
                pass_rate = round(passed / len(clarity) * 100, 1) if clarity else 0

                cc1, cc2, cc3 = st.columns(3)
                cc1.metric("Aprovados", passed)
                cc2.metric("Reprovados", failed)
                cc3.metric("Taxa Aprovação", f"{pass_rate}%")

                # Scores
                scores = [c.get("score", 0) for c in clarity]
                avg_score = round(sum(scores) / len(scores), 1)
                st.metric("Score Médio", f"{avg_score}/5")

                # Histórico de checks
                df_clarity = pd.DataFrame(
                    [
                        {
                            "Timestamp": to_sp(c.get("timestamp", "")),
                            "Score": f"{c.get('score', 0)}/5",
                            "Status": "✅ Aprovado" if c.get("passed") else "❌ Reprovado",
                        }
                        for c in reversed(clarity[-20:])
                    ]
                )
                st.dataframe(df_clarity, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum Clarity Checkpoint executado ainda.")

            # ── Specs Gerados ──
            if specs:
                st.subheader("📋 Specs Gerados")
                df_specs = pd.DataFrame(
                    [
                        {
                            "Timestamp": to_sp(s.get("timestamp", "")),
                            "Tipo": s.get("spec_type", "—"),
                            "Arquivo": s.get("file_path", "—").split("/")[-1],
                        }
                        for s in reversed(specs[-10:])
                    ]
                )
                st.dataframe(df_specs, use_container_width=True, hide_index=True)

        st.divider()

        # ── Atividade por Data ──
        st.subheader("📅 Eventos por Data")
        date_counts: dict[str, int] = defaultdict(int)
        for wr in workflow_records:
            ts = wr.get("timestamp", "")
            date = to_sp(ts)[:10] if ts else "unknown"
            date_counts[date] += 1
        if date_counts:
            df_dates = pd.DataFrame(
                [{"Data": k, "Eventos": v} for k, v in sorted(date_counts.items())]
            ).set_index("Data")
            st.bar_chart(df_dates, color="#10b981")

        # ── Histórico Completo ──
        st.subheader("📋 Histórico de Eventos")
        df_history = pd.DataFrame(
            [
                {
                    "Timestamp": to_sp(r.get("timestamp", "")),
                    "Evento": r.get("event", ""),
                    "Agente": r.get("agent", "—"),
                    "Workflow": r.get("workflow", "—"),
                    "Preview": (
                        r.get("prompt_preview")
                        or r.get("question_preview")
                        or r.get("file_path")
                        or ""
                    )[:80],
                }
                for r in reversed(workflow_records[-100:])
            ]
        )
        st.dataframe(df_history, use_container_width=True, hide_index=True)


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
            st.download_button(
                "⬇️ Exportar audit.jsonl (filtrado)",
                "\n".join(__import__("json").dumps(r, ensure_ascii=False) for r in filtered_audit),
                "audit_export.jsonl",
                "application/jsonl",
                key="dl_audit",
            )


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
        (
            "hooks/audit_hook.py",
            "Registra todas as tool calls com categorização de erros (PostToolUse)",
        ),
        ("hooks/cost_guard_hook.py", "Alerta operações de alto custo (PostToolUse)"),
        (
            "hooks/output_compressor_hook.py",
            "Comprime outputs MCP (PostToolUse) — economia de tokens",
        ),
        (
            "hooks/workflow_tracker.py",
            "Rastreia workflows, Clarity Checkpoint e delegações (PostToolUse)",
        ),
        ("hooks/session_logger.py", "Grava métricas de sessão em sessions.jsonl"),
        (f"logs/audit.jsonl ({audit['total']} entradas)", "Histórico completo de tool calls"),
        (f"logs/app.jsonl ({app['total']} entradas)", "Log estruturado da aplicação"),
        ("logs/workflows.jsonl", "Eventos de workflows, delegações e Clarity Checkpoint"),
    ]
    df_files = pd.DataFrame(files_info, columns=["Arquivo", "Finalidade"])
    st.dataframe(df_files, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("🔄 Sobre o Dashboard")
    st.info(
        "Este dashboard lê os arquivos de log em tempo real. "
        "Use o **auto-refresh** na sidebar para atualizações automáticas enquanto os agentes rodam. "
        "O cache é de 5 segundos para `audit.jsonl`, `app.jsonl` e `workflows.jsonl`."
    )


# ── CUSTO & TOKENS ────────────────────────────────────────────────────────────
elif page == "💰 Custo & Tokens":
    st.title("💰 Custo & Tokens")

    if not session_records:
        st.warning(
            "Nenhum dado de sessão encontrado em `logs/sessions.jsonl`. "
            "Execute ao menos uma query para ver métricas de custo."
        )
    else:
        import pandas as pd

        # Preparar DataFrame
        df_sessions = pd.DataFrame(session_records)
        df_sessions["total_cost_usd"] = df_sessions["total_cost_usd"].fillna(0).astype(float)
        df_sessions["num_turns"] = df_sessions["num_turns"].fillna(0).astype(int)
        df_sessions["duration_s"] = df_sessions["duration_s"].fillna(0).astype(float)
        df_sessions["cost_per_turn"] = df_sessions["cost_per_turn"].fillna(0).astype(float)
        df_sessions["date"] = df_sessions["timestamp"].str[:10]

        st.caption(
            f"Baseado em **{len(session_records)}** sessões registradas em `logs/sessions.jsonl`"
        )

        # ── KPIs ──
        total_cost = df_sessions["total_cost_usd"].sum()
        avg_cost = df_sessions["total_cost_usd"].mean()
        total_turns = df_sessions["num_turns"].sum()
        avg_turns = df_sessions["num_turns"].mean()
        total_duration = df_sessions["duration_s"].sum()
        total_sessions = len(df_sessions)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Custo Total", f"${total_cost:.4f}", help="Soma de total_cost_usd")
        c2.metric("Custo Médio/Sessão", f"${avg_cost:.4f}", help="Média por sessão")
        c3.metric("Total de Turns", f"{total_turns:,}", help="Soma de num_turns")
        c4.metric("Média Turns/Sessão", f"{avg_turns:.1f}", help="Média por sessão")
        c5.metric("Tempo Total", f"{total_duration:.0f}s", help="Soma de duration_s")

        st.divider()

        col_left, col_right = st.columns(2)

        with col_left:
            # ── Custo por Data ──
            st.subheader("💵 Custo por Data")
            cost_by_date = df_sessions.groupby("date")["total_cost_usd"].sum().reset_index()
            cost_by_date.columns = ["Data", "Custo (USD)"]
            cost_by_date = cost_by_date.set_index("Data")
            st.line_chart(cost_by_date, color="#22c55e")

            # ── Sessões por Data ──
            st.subheader("📅 Sessões por Data")
            sessions_by_date = df_sessions.groupby("date").size().reset_index(name="Sessões")
            sessions_by_date = sessions_by_date.set_index("date")
            st.bar_chart(sessions_by_date, color="#6366f1")

        with col_right:
            # ── Custo por Tipo de Sessão ──
            st.subheader("🏷️ Custo por Tipo de Sessão")
            if "session_type" in df_sessions.columns:
                cost_by_type = (
                    df_sessions.groupby("session_type")
                    .agg(
                        Sessões=("session_type", "count"),
                        Custo_Total=("total_cost_usd", "sum"),
                        Custo_Médio=("total_cost_usd", "mean"),
                        Turns_Total=("num_turns", "sum"),
                    )
                    .reset_index()
                )
                cost_by_type.columns = [
                    "Tipo",
                    "Sessões",
                    "Custo Total",
                    "Custo Médio",
                    "Turns Total",
                ]
                st.dataframe(cost_by_type, use_container_width=True, hide_index=True)

            # ── Distribuição de Custo por Sessão ──
            st.subheader("📊 Custo por Sessão")
            st.bar_chart(
                df_sessions[["total_cost_usd"]].reset_index(drop=True),
                color="#f59e0b",
            )

        st.divider()

        # ── Tabela de Sessões (histórico completo) ──
        st.subheader("📋 Histórico de Sessões")

        # Formatar para exibição
        df_display = df_sessions[
            [
                "timestamp",
                "session_type",
                "total_cost_usd",
                "num_turns",
                "duration_s",
                "cost_per_turn",
                "prompt_preview",
            ]
        ].copy()
        df_display.columns = [
            "Timestamp",
            "Tipo",
            "Custo (USD)",
            "Turns",
            "Duração (s)",
            "Custo/Turn",
            "Prompt",
        ]
        df_display = df_display.sort_values("Timestamp", ascending=False)
        df_display["Prompt"] = df_display["Prompt"].str[:80]  # truncar preview

        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Custo (USD)": st.column_config.NumberColumn(format="$%.4f"),
                "Custo/Turn": st.column_config.NumberColumn(format="$%.5f"),
                "Duração (s)": st.column_config.NumberColumn(format="%.1f"),
                "Tipo": st.column_config.TextColumn(width="small"),
                "Turns": st.column_config.NumberColumn(format="%d"),
            },
        )

        st.divider()

        # ── Estimativa de pricing ──
        st.subheader("💡 Referência de Pricing (Anthropic API)")
        st.caption("Valores de referência — o custo real é calculado pelo SDK")

        pricing_data = pd.DataFrame(
            [
                {
                    "Modelo": "claude-opus-4-6",
                    "Input ($/1M tokens)": "$15.00",
                    "Output ($/1M tokens)": "$75.00",
                    "Cache Read": "$1.50",
                    "Cache Write": "$18.75",
                },
                {
                    "Modelo": "claude-sonnet-4-20250514",
                    "Input ($/1M tokens)": "$3.00",
                    "Output ($/1M tokens)": "$15.00",
                    "Cache Read": "$0.30",
                    "Cache Write": "$3.75",
                },
                {
                    "Modelo": "claude-haiku-3-5",
                    "Input ($/1M tokens)": "$0.80",
                    "Output ($/1M tokens)": "$4.00",
                    "Cache Read": "$0.08",
                    "Cache Write": "$1.00",
                },
            ]
        )
        st.dataframe(pricing_data, use_container_width=True, hide_index=True)

        # ══════════════════════════════════════════════════════════════════
        # ECONOMIA DO OUTPUT COMPRESSOR
        # ══════════════════════════════════════════════════════════════════
        st.divider()
        st.header("🗜️ Economia do Output Compressor")
        st.caption(
            "O `output_compressor_hook` trunca outputs de ferramentas MCP antes de atingirem o modelo, "
            "economizando tokens de input e reduzindo custos."
        )

        if not compression_records:
            st.info(
                "Nenhum dado de compressão registrado ainda em `logs/compression.jsonl`. "
                "A economia será registrada automaticamente quando o compressor truncar outputs."
            )
        else:
            df_comp = pd.DataFrame(compression_records)
            df_comp["saved_chars"] = df_comp["saved_chars"].fillna(0).astype(int)
            df_comp["saved_tokens_est"] = df_comp["saved_tokens_est"].fillna(0).astype(int)
            df_comp["saved_cost_est_usd"] = df_comp["saved_cost_est_usd"].fillna(0).astype(float)
            df_comp["reduction_pct"] = df_comp["reduction_pct"].fillna(0).astype(float)
            df_comp["original_chars"] = df_comp["original_chars"].fillna(0).astype(int)
            df_comp["compressed_chars"] = df_comp["compressed_chars"].fillna(0).astype(int)
            df_comp["date"] = df_comp["timestamp"].str[:10]

            # KPIs de economia
            total_saved_chars = df_comp["saved_chars"].sum()
            total_saved_tokens = df_comp["saved_tokens_est"].sum()
            total_saved_cost = df_comp["saved_cost_est_usd"].sum()
            total_original = df_comp["original_chars"].sum()
            total_compressed = df_comp["compressed_chars"].sum()
            avg_reduction = df_comp["reduction_pct"].mean()
            total_compressions = len(df_comp)

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric(
                "Tokens Economizados",
                f"{total_saved_tokens:,}",
                help="Estimativa: 1 token ≈ 4 caracteres",
            )
            c2.metric(
                "Economia Estimada",
                f"${total_saved_cost:.4f}",
                help="Baseado em $9/1M tokens (média opus+sonnet input)",
            )
            c3.metric(
                "Chars Originais",
                f"{total_original:,}",
                help="Total de caracteres antes da compressão",
            )
            c4.metric(
                "Chars Após Compressão",
                f"{total_compressed:,}",
                help="Total de caracteres após truncamento",
            )
            c5.metric(
                "Redução Média",
                f"{avg_reduction:.1f}%",
                help="Percentual médio de redução por compressão",
            )

            st.divider()

            col_left2, col_right2 = st.columns(2)

            with col_left2:
                # Economia por data
                st.subheader("📈 Economia por Data")
                savings_by_date = (
                    df_comp.groupby("date")
                    .agg(
                        Tokens_Economizados=("saved_tokens_est", "sum"),
                        Economia_USD=("saved_cost_est_usd", "sum"),
                        Compressoes=("saved_chars", "count"),
                    )
                    .reset_index()
                )
                savings_by_date = savings_by_date.set_index("date")
                st.line_chart(savings_by_date[["Tokens_Economizados"]], color="#10b981")

                # Comparativo visual
                st.subheader("⚖️ Antes vs Depois (Caracteres)")
                compare_data = pd.DataFrame(
                    {
                        "Métrica": ["Output Original", "Após Compressão", "Economia"],
                        "Caracteres": [total_original, total_compressed, total_saved_chars],
                    }
                )
                st.bar_chart(compare_data.set_index("Métrica"), color="#6366f1")

            with col_right2:
                # Top tools por economia
                st.subheader("🏆 Top Tools por Economia")
                savings_by_tool = (
                    df_comp.groupby("tool_name")
                    .agg(
                        Compressoes=("tool_name", "count"),
                        Chars_Economizados=("saved_chars", "sum"),
                        Tokens_Economizados=("saved_tokens_est", "sum"),
                        Economia_USD=("saved_cost_est_usd", "sum"),
                        Reducao_Media=("reduction_pct", "mean"),
                    )
                    .sort_values("Tokens_Economizados", ascending=False)
                    .reset_index()
                )
                savings_by_tool.columns = [
                    "Ferramenta",
                    "Compressões",
                    "Chars Economizados",
                    "Tokens Economizados",
                    "Economia (USD)",
                    "Redução Média %",
                ]
                st.dataframe(
                    savings_by_tool,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Economia (USD)": st.column_config.NumberColumn(format="$%.4f"),
                        "Redução Média %": st.column_config.NumberColumn(format="%.1f%%"),
                    },
                )

                # Custo com vs sem compressão
                st.subheader("💡 Impacto no Custo Total")
                if total_cost > 0:
                    hypothetical_cost = total_cost + total_saved_cost
                    savings_pct = (
                        round((total_saved_cost / hypothetical_cost) * 100, 1)
                        if hypothetical_cost > 0
                        else 0
                    )
                    st.markdown(
                        f"- **Custo real (com compressão):** `${total_cost:.4f}`\n"
                        f"- **Custo hipotético (sem compressão):** `${hypothetical_cost:.4f}`\n"
                        f"- **Economia pelo compressor:** `${total_saved_cost:.4f}` (**{savings_pct}%** de redução)"
                    )
                else:
                    st.info("Execute sessões para ver o impacto comparativo.")

            st.divider()

            # Histórico de compressões
            st.subheader("📋 Histórico de Compressões")
            df_comp_display = df_comp[
                [
                    "timestamp",
                    "tool_name",
                    "original_chars",
                    "compressed_chars",
                    "saved_chars",
                    "reduction_pct",
                    "saved_tokens_est",
                    "saved_cost_est_usd",
                ]
            ].copy()
            df_comp_display.columns = [
                "Timestamp",
                "Ferramenta",
                "Original (chars)",
                "Comprimido (chars)",
                "Economizado (chars)",
                "Redução %",
                "Tokens Economizados",
                "Economia (USD)",
            ]
            df_comp_display = df_comp_display.sort_values("Timestamp", ascending=False)
            df_comp_display["Timestamp"] = df_comp_display["Timestamp"].apply(
                lambda x: to_sp(x) if isinstance(x, str) else x
            )
            st.dataframe(
                df_comp_display.head(100),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Economia (USD)": st.column_config.NumberColumn(format="$%.6f"),
                    "Redução %": st.column_config.NumberColumn(format="%.1f%%"),
                },
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
        st.markdown("`v1.1.0`")
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
        (`logs/audit.jsonl`, `logs/app.jsonl` e `logs/workflows.jsonl`) e apresenta as informações
        de forma estruturada, sem necessidade de infraestrutura adicional.
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
            "conectados e domínios de Knowledge Base de cada agente. "
            "Inclui KPIs de performance (delegações, erros, taxa de erro) e "
            "erros categorizados (auth, timeout, rate_limit, not_found, validation, mcp_connection).",
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
            "🔄 Workflows",
            "Rastreamento de workflows colaborativos (WF-01 a WF-05), delegações de agentes, "
            "Clarity Checkpoint (score, pass rate, histórico) e specs gerados. "
            "Inclui gráfico de atividade por data e histórico completo de eventos.",
        ),
        (
            "⚙️ Configurações",
            "Parâmetros do sistema detectados do último run: modelo padrão, "
            "budget máximo por sessão e limite de turns. Mapa de todos os arquivos relevantes "
            "do projeto com sua finalidade.",
        ),
        (
            "💰 Custo & Tokens",
            "Rastreamento completo de custos da API Anthropic por sessão. "
            "Exibe custo total acumulado, custo médio por sessão, total de turns e duração. "
            "Inclui gráficos de custo por data, sessões por data, breakdown por tipo, "
            "tabela de histórico de todas as sessões com prompt preview, e a seção "
            "**Economia do Output Compressor** com métricas detalhadas de tokens economizados, "
            "comparativo custo real vs hipotético (sem compressão) e ranking de tools por economia.",
        ),
    ]

    for titulo, descricao in abas:
        with st.expander(titulo, expanded=False):
            st.markdown(descricao)

    st.divider()

    # Fontes de dados
    st.subheader("📂 Fontes de Dados")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown("**`logs/audit.jsonl`** — gerado pelo `audit_hook.py`")
        st.markdown(
            "Registra **toda tool call** executada pelo sistema (PostToolUse hook). "
            "Cada linha contém: timestamp, nome da ferramenta, tool_use_id, chaves de input, "
            "plataforma MCP e categorização de erros."
        )
    with col_b:
        st.markdown("**`logs/app.jsonl`** — gerado pelo `logging_config.py`")
        st.markdown(
            "Log estruturado da aplicação usando `JSONLFormatter`. "
            "Registra inicialização, status dos MCP servers, configurações carregadas, "
            "warnings de credenciais e erros de runtime."
        )
    with col_c:
        st.markdown("**`logs/workflows.jsonl`** — gerado pelo `workflow_tracker.py`")
        st.markdown(
            "Eventos de workflows colaborativos, delegações de agentes, "
            "Clarity Checkpoint (scores e resultados) e specs gerados."
        )

    st.divider()

    # Arquitetura do sistema monitorado
    st.subheader("🏗️ Arquitetura do Sistema Monitorado")
    st.markdown(
        """
        O **Data Agents** é um sistema multi-agente que segue a arquitetura **DOMA**
        (Data Orchestration Method for Agents):

        - **Supervisor** — orquestra os agentes especialistas, gerencia MCP servers e aplica hooks
        - **SQL Expert** (T1) — queries SQL/KQL em Databricks e Fabric RTI
        - **Spark Expert** (T1) — código PySpark, Delta Lake e pipelines DLT
        - **Pipeline Architect** (T1) — design e execução de pipelines ETL/ELT cross-platform
        - **Data Quality Steward** (T2) — validação, profiling e alertas de qualidade
        - **Governance Auditor** (T2) — auditoria de acesso, linhagem e conformidade LGPD
        - **Semantic Modeler** (T2) — modelos semânticos DAX e Metric Views

        Os **hooks** interceptam cada execução de ferramenta:
        `security_hook` bloqueia comandos destrutivos e queries SQL custosas,
        `audit_hook` registra todas as chamadas com categorização de erros,
        `cost_guard_hook` alerta sobre operações de alto custo,
        `workflow_tracker` rastreia delegações, workflows e Clarity Checkpoint,
        `output_compressor_hook` filtra e trunca outputs para economia de tokens.
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
