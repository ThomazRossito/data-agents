"""
monitoring/generate.py
Lê os logs reais do projeto data-agents e gera monitoring/dashboard.html.

Uso:
    python monitoring/generate.py
"""

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
AUDIT_LOG = ROOT / "logs" / "audit.jsonl"
APP_LOG = ROOT / "logs" / "app.jsonl"
REGISTRY = ROOT / "agents" / "registry"
OUTPUT = Path(__file__).parent / "dashboard.html"


# ── Leitura dos logs ──────────────────────────────────────────────────────────


def load_jsonl(path: Path) -> list[dict]:
    records = []
    if not path.exists():
        return records
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def parse_audit(records: list[dict]) -> dict:
    by_date: dict[str, int] = defaultdict(int)
    by_tool: dict[str, int] = defaultdict(int)
    mcp_calls: list[dict] = []

    for r in records:
        ts = r.get("timestamp", "")
        date = ts[:10] if ts else "unknown"
        tool = r.get("tool_name", "unknown")
        by_date[date] += 1
        by_tool[tool] += 1
        if tool.startswith("mcp__"):
            mcp_calls.append(r)

    return {
        "total": len(records),
        "by_date": dict(sorted(by_date.items())),
        "by_tool": dict(sorted(by_tool.items(), key=lambda x: -x[1])),
        "mcp_calls": mcp_calls,
        "mcp_total": len(mcp_calls),
    }


def parse_app_log(records: list[dict]) -> dict:
    by_level: dict[str, int] = defaultdict(int)
    warnings: list[dict] = []
    errors: list[dict] = []
    recent: list[dict] = []

    for r in records:
        level = r.get("level", "")
        by_level[level] += 1
        if level == "WARNING":
            warnings.append(r)
        elif level == "ERROR":
            errors.append(r)
        if level in ("INFO", "WARNING", "ERROR"):
            recent.append(r)

    return {
        "total": len(records),
        "by_level": dict(by_level),
        "warnings": warnings[-20:],
        "errors": errors[-10:],
        "recent": recent[-50:],
    }


def parse_registry() -> list[dict]:
    agents = []
    if not REGISTRY.exists():
        return agents
    for f in sorted(REGISTRY.glob("*.md")):
        if f.name.startswith("_"):
            continue
        content = f.read_text(encoding="utf-8")
        if not content.startswith("---"):
            continue
        end = content.index("---", 3)
        import yaml  # type: ignore[import-untyped]

        try:
            meta = yaml.safe_load(content[3:end])
        except Exception:
            continue
        if meta:
            agents.append(meta)
    return agents


def infer_mcp_status(app_records: list[dict]) -> dict:
    """Detecta status dos MCP servers a partir dos warnings do app.jsonl."""
    platforms = {
        "databricks": {"label": "Databricks", "configured": True, "missing": []},
        "fabric": {"label": "Microsoft Fabric", "configured": True, "missing": []},
        "fabric_rti": {"label": "Fabric Real-Time Intelligence", "configured": True, "missing": []},
        "fabric_community": {"label": "Fabric Community", "configured": True, "missing": []},
    }
    for r in app_records:
        msg = r.get("message", "")
        if "DATABRICKS: variáveis ausentes:" in msg:
            missing = msg.split("variáveis ausentes:")[-1].split(".")[0].strip()
            platforms["databricks"]["configured"] = False
            platforms["databricks"]["missing"] = [v.strip() for v in missing.split(",")]
        elif "FABRIC: variáveis ausentes:" in msg:
            missing = msg.split("variáveis ausentes:")[-1].split(".")[0].strip()
            platforms["fabric"]["configured"] = False
            platforms["fabric"]["missing"] = [v.strip() for v in missing.split(",")]
        elif "FABRIC_RTI: variáveis ausentes:" in msg:
            missing = msg.split("variáveis ausentes:")[-1].split(".")[0].strip()
            platforms["fabric_rti"]["configured"] = False
            platforms["fabric_rti"]["missing"] = [v.strip() for v in missing.split(",")]
    return platforms


# ── Leitura das settings ──────────────────────────────────────────────────────


def read_settings_from_app_log(app_records: list[dict]) -> dict:
    for r in reversed(app_records):
        msg = r.get("message", "")
        if "Configuração: model=" in msg:
            # model=claude-opus-4-6, budget=$5.0, max_turns=50
            parts = {}
            for part in msg.replace("📋 Configuração: ", "").split(", "):
                if "=" in part:
                    k, v = part.split("=", 1)
                    parts[k.strip()] = v.strip()
            return parts
    return {}


# ── Geração do HTML ───────────────────────────────────────────────────────────


def generate_html(audit: dict, app: dict, agents: list[dict], mcp: dict, settings: dict) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Serialise data for JS
    audit_json = json.dumps(audit, ensure_ascii=False, default=str)
    app_json = json.dumps(app, ensure_ascii=False, default=str)
    agents_json = json.dumps(agents, ensure_ascii=False, default=str)
    mcp_json = json.dumps(mcp, ensure_ascii=False, default=str)
    settings_json = json.dumps(settings, ensure_ascii=False, default=str)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Data Agents — Monitoramento</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f6fa;color:#1a1a2e;}}
  /* ── Layout ── */
  .header{{background:#1a1a2e;color:#fff;padding:0 32px;height:56px;display:flex;align-items:center;justify-content:space-between;}}
  .header-logo{{display:flex;align-items:center;gap:10px;font-size:16px;font-weight:700;}}
  .header-logo .dot{{width:10px;height:10px;border-radius:50%;background:#4ade80;}}
  .header-meta{{font-size:12px;color:#94a3b8;}}
  .nav{{background:#fff;border-bottom:1px solid #e2e8f0;padding:0 32px;display:flex;gap:0;}}
  .nav-item{{padding:14px 20px;font-size:13px;font-weight:500;color:#64748b;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px;transition:all .15s;display:flex;align-items:center;gap:7px;}}
  .nav-item:hover{{color:#1a1a2e;}}
  .nav-item.active{{color:#6366f1;border-bottom-color:#6366f1;font-weight:600;}}
  .main{{padding:28px 32px;}}
  .page{{display:none;}}
  .page.active{{display:block;}}
  /* ── Cards ── */
  .card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:20px;}}
  .card-title{{font-size:13px;font-weight:700;color:#475569;margin-bottom:14px;display:flex;align-items:center;gap:7px;text-transform:uppercase;letter-spacing:.4px;}}
  /* ── Stat cards ── */
  .stats-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px;}}
  .stat-card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:18px 20px;}}
  .stat-label{{font-size:11px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;}}
  .stat-val{{font-size:28px;font-weight:800;}}
  .stat-sub{{font-size:11px;color:#94a3b8;margin-top:4px;}}
  .c-indigo{{color:#6366f1;}}.c-green{{color:#22c55e;}}.c-amber{{color:#f59e0b;}}.c-red{{color:#ef4444;}}.c-slate{{color:#64748b;}}
  /* ── Grids ── */
  .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px;}}
  .three-col{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:24px;}}
  /* ── Tables ── */
  table{{width:100%;border-collapse:collapse;font-size:13px;}}
  th{{text-align:left;font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.5px;padding:8px 10px;border-bottom:1px solid #f1f5f9;}}
  td{{padding:9px 10px;border-bottom:1px solid #f8fafc;vertical-align:middle;}}
  tr:last-child td{{border-bottom:none;}}
  tr:hover td{{background:#fafbff;}}
  /* ── Badges ── */
  .badge{{display:inline-block;font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;}}
  .badge-green{{background:#dcfce7;color:#16a34a;}}
  .badge-amber{{background:#fef9c3;color:#b45309;}}
  .badge-red{{background:#fee2e2;color:#dc2626;}}
  .badge-slate{{background:#f1f5f9;color:#475569;}}
  .badge-indigo{{background:#eef2ff;color:#4f46e5;}}
  .badge-blue{{background:#dbeafe;color:#1d4ed8;}}
  /* ── Agent cards ── */
  .agents-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;}}
  .agent-card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:18px;}}
  .agent-name{{font-size:14px;font-weight:700;margin-bottom:3px;}}
  .agent-desc{{font-size:11px;color:#64748b;line-height:1.5;margin-bottom:12px;max-height:52px;overflow:hidden;}}
  .agent-meta{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px;}}
  .agent-mcps{{font-size:11px;color:#94a3b8;margin-top:8px;border-top:1px solid #f1f5f9;padding-top:8px;}}
  /* ── MCP cards ── */
  .mcp-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-bottom:24px;}}
  .mcp-card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:18px 20px;}}
  .mcp-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;}}
  .mcp-name{{font-size:14px;font-weight:700;}}
  .mcp-missing{{font-size:11px;color:#94a3b8;margin-top:8px;}}
  .mcp-missing span{{display:inline-block;background:#f1f5f9;color:#64748b;border-radius:4px;padding:1px 6px;margin:2px;font-family:monospace;font-size:10px;}}
  .mcp-calls{{font-size:12px;color:#64748b;margin-top:8px;border-top:1px solid #f1f5f9;padding-top:8px;}}
  /* ── Log viewer ── */
  .log-toolbar{{display:flex;gap:10px;margin-bottom:12px;align-items:center;}}
  .log-filter-btn{{background:#f1f5f9;border:none;border-radius:6px;padding:5px 12px;font-size:12px;cursor:pointer;font-weight:500;color:#475569;}}
  .log-filter-btn.active{{background:#6366f1;color:#fff;}}
  .log-count{{font-size:12px;color:#94a3b8;margin-left:auto;}}
  .log-box{{background:#0f172a;border-radius:10px;padding:16px;max-height:450px;overflow-y:auto;font-family:monospace;font-size:11px;line-height:1.7;}}
  .log-entry{{display:flex;gap:12px;padding:2px 0;border-bottom:1px solid rgba(255,255,255,.04);}}
  .log-ts{{color:#64748b;white-space:nowrap;flex-shrink:0;}}
  .log-level{{width:52px;flex-shrink:0;font-weight:700;}}
  .log-logger{{color:#94a3b8;min-width:160px;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
  .log-msg{{color:#e2e8f0;}}
  .lvl-INFO{{color:#22c55e;}}.lvl-WARNING{{color:#f59e0b;}}.lvl-ERROR{{color:#ef4444;}}.lvl-DEBUG{{color:#475569;}}
  /* ── Bar chart ── */
  .bar-chart{{display:flex;align-items:flex-end;gap:8px;height:120px;padding-bottom:4px;}}
  .bar-col{{display:flex;flex-direction:column;align-items:center;gap:4px;flex:1;}}
  .bar{{background:#6366f1;border-radius:4px 4px 0 0;width:100%;min-height:4px;transition:height .3s;}}
  .bar-label{{font-size:10px;color:#94a3b8;white-space:nowrap;}}
  .bar-val{{font-size:10px;font-weight:700;color:#6366f1;}}
  /* ── Tool list ── */
  .tool-row{{display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid #f8fafc;}}
  .tool-name{{font-size:12px;font-weight:600;width:180px;flex-shrink:0;}}
  .tool-bar-bg{{flex:1;background:#f1f5f9;border-radius:4px;height:8px;overflow:hidden;}}
  .tool-bar-fill{{height:100%;background:#6366f1;border-radius:4px;transition:width .5s;}}
  .tool-val{{font-size:11px;font-weight:700;color:#475569;width:36px;text-align:right;}}
  /* ── Settings ── */
  .settings-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;}}
  .setting-card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px 20px;}}
  .setting-key{{font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;}}
  .setting-val{{font-size:18px;font-weight:700;color:#1a1a2e;font-family:monospace;}}
  .setting-desc{{font-size:11px;color:#94a3b8;margin-top:4px;}}
  /* ── Section header ── */
  .section-header{{font-size:16px;font-weight:700;margin-bottom:16px;color:#1a1a2e;}}
  .section-sub{{font-size:13px;color:#64748b;margin-bottom:20px;}}
</style>
</head>
<body>

<div class="header">
  <div class="header-logo">
    <div class="dot"></div>
    Data Agents — Monitoramento
  </div>
  <div class="header-meta">Gerado em {generated_at} · logs/audit.jsonl + logs/app.jsonl</div>
</div>

<nav class="nav">
  <div class="nav-item active" onclick="showPage('overview')">📊 Overview</div>
  <div class="nav-item" onclick="showPage('agents')">🤖 Agentes</div>
  <div class="nav-item" onclick="showPage('execucoes')">⚡ Execuções</div>
  <div class="nav-item" onclick="showPage('mcp')">🔌 MCP Servers</div>
  <div class="nav-item" onclick="showPage('logs')">📋 Logs</div>
  <div class="nav-item" onclick="showPage('config')">⚙️ Configurações</div>
</nav>

<div class="main">

<!-- ═══════════════════════════ OVERVIEW ═══════════════════════════ -->
<div class="page active" id="page-overview">
  <div class="stats-grid" id="overview-stats"></div>
  <div class="two-col">
    <div class="card">
      <div class="card-title">📅 Atividade por Data</div>
      <div class="bar-chart" id="activity-chart"></div>
    </div>
    <div class="card">
      <div class="card-title">🔧 Top Ferramentas Usadas</div>
      <div id="top-tools-list"></div>
    </div>
  </div>
  <div class="two-col">
    <div class="card">
      <div class="card-title">📋 App Log por Nível</div>
      <div id="log-levels-overview"></div>
    </div>
    <div class="card">
      <div class="card-title">🔌 Status dos MCP Servers</div>
      <div id="mcp-overview"></div>
    </div>
  </div>
</div>

<!-- ═══════════════════════════ AGENTES ═══════════════════════════ -->
<div class="page" id="page-agents">
  <div class="section-header">Agentes Especialistas</div>
  <div class="section-sub">Definidos em <code>agents/registry/*.md</code> — carregados dinamicamente pelo loader.</div>
  <div class="agents-grid" id="agents-grid"></div>
</div>

<!-- ═══════════════════════════ EXECUÇÕES ═══════════════════════════ -->
<div class="page" id="page-execucoes">
  <div class="stats-grid" id="exec-stats"></div>
  <div class="two-col">
    <div class="card">
      <div class="card-title">🔧 Todas as Ferramentas — Volume</div>
      <div id="all-tools-list"></div>
    </div>
    <div class="card">
      <div class="card-title">🔌 Chamadas MCP (Plataformas)</div>
      <div id="mcp-calls-table"></div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">📋 Audit Log — Últimas Chamadas</div>
    <div id="audit-recent-table"></div>
  </div>
</div>

<!-- ═══════════════════════════ MCP SERVERS ═══════════════════════════ -->
<div class="page" id="page-mcp">
  <div class="section-header">Status dos MCP Servers</div>
  <div class="section-sub">Status detectado automaticamente a partir dos logs de inicialização (<code>logs/app.jsonl</code>).</div>
  <div class="mcp-grid" id="mcp-cards"></div>
  <div class="card">
    <div class="card-title">📞 Histórico de Chamadas MCP</div>
    <table id="mcp-history-table">
      <thead><tr><th>Timestamp</th><th>Tool</th><th>Inputs</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>
</div>

<!-- ═══════════════════════════ LOGS ═══════════════════════════ -->
<div class="page" id="page-logs">
  <div class="two-col" style="margin-bottom:20px">
    <div class="card">
      <div class="card-title">📄 logs/app.jsonl</div>
      <div class="log-toolbar">
        <button class="log-filter-btn active" onclick="filterAppLog('ALL',this)">Todos</button>
        <button class="log-filter-btn" onclick="filterAppLog('INFO',this)">INFO</button>
        <button class="log-filter-btn" onclick="filterAppLog('WARNING',this)">WARNING</button>
        <button class="log-filter-btn" onclick="filterAppLog('ERROR',this)">ERROR</button>
        <span class="log-count" id="app-log-count"></span>
      </div>
      <div class="log-box" id="app-log-box"></div>
    </div>
    <div class="card">
      <div class="card-title">🔍 logs/audit.jsonl</div>
      <div class="log-toolbar">
        <button class="log-filter-btn active" onclick="filterAuditLog('ALL',this)">Todos</button>
        <button class="log-filter-btn" onclick="filterAuditLog('MCP',this)">Só MCP</button>
        <button class="log-filter-btn" onclick="filterAuditLog('Agent',this)">Agent</button>
        <span class="log-count" id="audit-log-count"></span>
      </div>
      <div class="log-box" id="audit-log-box"></div>
    </div>
  </div>
</div>

<!-- ═══════════════════════════ CONFIG ═══════════════════════════ -->
<div class="page" id="page-config">
  <div class="section-header">Configurações do Sistema</div>
  <div class="section-sub">Lido de <code>config/settings.py</code> (valores do último run detectados em <code>logs/app.jsonl</code>).</div>
  <div class="settings-grid" id="settings-grid"></div>
  <div style="margin-top:24px" class="card">
    <div class="card-title">📁 Estrutura de Arquivos Relevantes</div>
    <table>
      <thead><tr><th>Arquivo</th><th>Finalidade</th><th>Tamanho</th></tr></thead>
      <tbody id="files-table"></tbody>
    </table>
  </div>
</div>

</div><!-- /main -->

<script>
// ═══════════════════ DATA (gerado pelo Python) ═══════════════════
const AUDIT = {audit_json};
const APP   = {app_json};
const AGENTS = {agents_json};
const MCP   = {mcp_json};
const SETTINGS = {settings_json};

// ═══════════════════ NAVIGATION ═══════════════════
function showPage(id) {{
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + id).classList.add('active');
  event.currentTarget.classList.add('active');
}}

// ═══════════════════ HELPERS ═══════════════════
function badge(text, cls) {{
  return `<span class="badge badge-${{cls}}">${{text}}</span>`;
}}
function fmtTs(ts) {{
  if (!ts) return '—';
  return ts.replace('T', ' ').replace('+00:00', '').slice(0, 19);
}}

// ═══════════════════ OVERVIEW ═══════════════════
function buildOverview() {{
  // Stats
  const total_audit = AUDIT.total;
  const days = Object.keys(AUDIT.by_date).length;
  const mcp_calls = AUDIT.mcp_total;
  const warns = APP.by_level['WARNING'] || 0;
  const errors = APP.by_level['ERROR'] || 0;
  document.getElementById('overview-stats').innerHTML = `
    <div class="stat-card"><div class="stat-label">Tool Calls (audit)</div><div class="stat-val c-indigo">${{total_audit}}</div><div class="stat-sub">${{days}} dias com atividade</div></div>
    <div class="stat-card"><div class="stat-label">Chamadas MCP</div><div class="stat-val c-green">${{mcp_calls}}</div><div class="stat-sub">Databricks + Fabric</div></div>
    <div class="stat-card"><div class="stat-label">Agentes Registrados</div><div class="stat-val c-indigo">${{AGENTS.length}}</div><div class="stat-sub">em agents/registry/</div></div>
    <div class="stat-card"><div class="stat-label">Warnings / Errors</div><div class="stat-val ${{errors > 0 ? 'c-red' : 'c-amber'}}">${{warns}} / ${{errors}}</div><div class="stat-sub">no app.jsonl</div></div>
  `;

  // Activity chart
  const dates = Object.keys(AUDIT.by_date);
  const vals  = Object.values(AUDIT.by_date);
  const maxV  = Math.max(...vals, 1);
  document.getElementById('activity-chart').innerHTML = dates.map((d, i) => {{
    const h = Math.round((vals[i] / maxV) * 100);
    return `<div class="bar-col">
      <div class="bar-val">${{vals[i]}}</div>
      <div class="bar" style="height:${{h}}px"></div>
      <div class="bar-label">${{d.slice(5)}}</div>
    </div>`;
  }}).join('');

  // Top 8 tools
  const top = Object.entries(AUDIT.by_tool).slice(0, 8);
  const maxT = top[0] ? top[0][1] : 1;
  document.getElementById('top-tools-list').innerHTML = top.map(([t, v]) => `
    <div class="tool-row">
      <span class="tool-name">${{t}}</span>
      <div class="tool-bar-bg"><div class="tool-bar-fill" style="width:${{Math.round(v/maxT*100)}}%"></div></div>
      <span class="tool-val">${{v}}</span>
    </div>
  `).join('');

  // Log levels
  const lvColors = {{INFO:'green', WARNING:'amber', ERROR:'red', DEBUG:'slate'}};
  document.getElementById('log-levels-overview').innerHTML = Object.entries(APP.by_level)
    .filter(([l]) => l)
    .map(([l, c]) => `<div class="tool-row">
      <span class="tool-name">${{badge(l, lvColors[l]||'slate')}}</span>
      <div class="tool-bar-bg"><div class="tool-bar-fill" style="width:${{Math.min(100,Math.round(c/(APP.total||1)*100))}}%;background:${{l==='ERROR'?'#ef4444':l==='WARNING'?'#f59e0b':l==='INFO'?'#22c55e':'#64748b'}}"></div></div>
      <span class="tool-val">${{c}}</span>
    </div>`).join('');

  // MCP overview
  document.getElementById('mcp-overview').innerHTML = Object.entries(MCP).map(([k, v]) => `
    <div class="tool-row">
      <span class="tool-name" style="width:220px">${{v.label}}</span>
      ${{v.configured ? badge('Configurado', 'green') : badge('Não configurado', 'amber')}}
    </div>
  `).join('');
}}

// ═══════════════════ AGENTES ═══════════════════
const tierColors = {{T1:'indigo', T2:'blue'}};
function buildAgents() {{
  document.getElementById('agents-grid').innerHTML = AGENTS.map(a => {{
    const tools = (a.tools||[]).filter(t => !t.startsWith('mcp__') && !t.includes('_readonly') && !t.includes('_all'));
    const aliases = (a.tools||[]).filter(t => t.includes('_readonly') || t.includes('_all'));
    const mcps = (a.mcp_servers||[]);
    return `<div class="agent-card">
      <div class="agent-name">${{a.name}}</div>
      <div class="agent-meta">
        ${{badge('Tier ' + (a.tier||'?'), tierColors[a.tier]||'slate')}}
        ${{badge(a.model||'?', 'slate')}}
      </div>
      <div class="agent-desc">${{a.description||''}}</div>
      <div class="agent-meta">
        ${{tools.map(t => `<span class="badge badge-slate">${{t}}</span>`).join('')}}
        ${{aliases.map(t => `<span class="badge badge-indigo">${{t}}</span>`).join('')}}
      </div>
      ${{mcps.length > 0 ? `<div class="agent-mcps">🔌 MCPs: ${{mcps.join(', ')}}</div>` : '<div class="agent-mcps" style="color:#94a3b8">🔌 Sem MCP servers</div>'}}
    </div>`;
  }}).join('');
}}

// ═══════════════════ EXECUÇÕES ═══════════════════
function buildExecucoes() {{
  // Stats
  const uniqueTools = Object.keys(AUDIT.by_tool).length;
  const mcpCalls = AUDIT.mcp_total;
  const topTool = Object.entries(AUDIT.by_tool)[0];
  document.getElementById('exec-stats').innerHTML = `
    <div class="stat-card"><div class="stat-label">Total de Chamadas</div><div class="stat-val c-indigo">${{AUDIT.total}}</div><div class="stat-sub">no audit.jsonl</div></div>
    <div class="stat-card"><div class="stat-label">Ferramentas Distintas</div><div class="stat-val c-green">${{uniqueTools}}</div><div class="stat-sub">incluindo MCP</div></div>
    <div class="stat-card"><div class="stat-label">Ferramenta Mais Usada</div><div class="stat-val c-indigo" style="font-size:18px">${{topTool ? topTool[0] : '—'}}</div><div class="stat-sub">${{topTool ? topTool[1] + ' chamadas' : ''}}</div></div>
    <div class="stat-card"><div class="stat-label">Chamadas MCP</div><div class="stat-val c-green">${{mcpCalls}}</div><div class="stat-sub">Databricks reais</div></div>
  `;

  // All tools
  const allTools = Object.entries(AUDIT.by_tool);
  const maxT = allTools[0] ? allTools[0][1] : 1;
  document.getElementById('all-tools-list').innerHTML = allTools.map(([t, v]) => `
    <div class="tool-row">
      <span class="tool-name" style="width:220px;font-family:monospace;font-size:11px">${{t}}</span>
      <div class="tool-bar-bg"><div class="tool-bar-fill" style="width:${{Math.round(v/maxT*100)}}%"></div></div>
      <span class="tool-val">${{v}}</span>
    </div>
  `).join('');

  // MCP calls grouped
  const mcpByTool = {{}};
  (AUDIT.mcp_calls||[]).forEach(r => {{
    const t = r.tool_name;
    mcpByTool[t] = (mcpByTool[t]||0) + 1;
  }});
  if (Object.keys(mcpByTool).length === 0) {{
    document.getElementById('mcp-calls-table').innerHTML = '<p style="color:#94a3b8;font-size:13px;padding:12px 0">Nenhuma chamada MCP registrada</p>';
  }} else {{
    document.getElementById('mcp-calls-table').innerHTML = `<table>
      <thead><tr><th>Tool MCP</th><th>Chamadas</th></tr></thead>
      <tbody>${{Object.entries(mcpByTool).sort((a,b)=>b[1]-a[1]).map(([t,v])=>
        `<tr><td style="font-family:monospace;font-size:11px">${{t}}</td><td><strong>${{v}}</strong></td></tr>`
      ).join('')}}</tbody>
    </table>`;
  }}

  // Recent audit entries (last 30)
  const recent = (AUDIT.mcp_calls.length > 0 ? AUDIT.mcp_calls : []).slice(-15);
  // Use last records from by_date — we store last records in mcp_calls
  // Actually show last audit entries from app log recent
  document.getElementById('audit-recent-table').innerHTML = `<table>
    <thead><tr><th>Timestamp</th><th>Ferramenta</th><th>Inputs</th></tr></thead>
    <tbody>${{(AUDIT.mcp_calls||[]).slice(-20).reverse().map(r =>
      `<tr>
        <td style="font-family:monospace;font-size:11px;color:#64748b">${{fmtTs(r.timestamp)}}</td>
        <td style="font-family:monospace;font-weight:700">${{r.tool_name}}</td>
        <td>${{(r.input_keys||[]).map(k=>`<span class="badge badge-slate">${{k}}</span>`).join(' ')}}</td>
      </tr>`
    ).join('')}}</tbody>
  </table>`;
}}

// ═══════════════════ MCP ═══════════════════
function buildMCP() {{
  const mcpByTool = {{}};
  (AUDIT.mcp_calls||[]).forEach(r => {{
    const t = r.tool_name;
    if (!mcpByTool[t]) mcpByTool[t] = [];
    mcpByTool[t].push(r);
  }});

  document.getElementById('mcp-cards').innerHTML = Object.entries(MCP).map(([k, v]) => {{
    const relatedCalls = (AUDIT.mcp_calls||[]).filter(r => r.tool_name.includes(k.replace('_','')));
    return `<div class="mcp-card">
      <div class="mcp-header">
        <div class="mcp-name">${{v.label}}</div>
        ${{v.configured ? badge('✓ Configurado', 'green') : badge('⚠ Não configurado', 'amber')}}
      </div>
      ${{!v.configured && v.missing && v.missing.length > 0 ? `
        <div class="mcp-missing">Variáveis ausentes: ${{v.missing.map(m=>`<span>${{m}}</span>`).join('')}}</div>
      ` : ''}}
      <div class="mcp-calls">
        Chamadas registradas: <strong>${{(AUDIT.mcp_calls||[]).filter(r=>r.tool_name.includes(k==='fabric_community'?'fabric_community':k==='fabric_rti'?'fabric_rti':k)).length}}</strong>
      </div>
    </div>`;
  }}).join('');

  // History table
  const tbody = document.querySelector('#mcp-history-table tbody');
  if (AUDIT.mcp_calls && AUDIT.mcp_calls.length > 0) {{
    tbody.innerHTML = [...AUDIT.mcp_calls].reverse().map(r => `
      <tr>
        <td style="font-family:monospace;font-size:11px;color:#64748b">${{fmtTs(r.timestamp)}}</td>
        <td style="font-family:monospace;font-size:11px;font-weight:700">${{r.tool_name}}</td>
        <td>${{(r.input_keys||[]).map(k=>`<span class="badge badge-slate">${{k}}</span>`).join(' ')}}</td>
      </tr>
    `).join('');
  }} else {{
    tbody.innerHTML = '<tr><td colspan="3" style="color:#94a3b8;text-align:center;padding:20px">Nenhuma chamada MCP encontrada no audit.jsonl</td></tr>';
  }}
}}

// ═══════════════════ LOGS ═══════════════════
let appLogAll = [];
let auditLogAll = [];

function renderAppLog(filter) {{
  const filtered = filter === 'ALL' ? appLogAll : appLogAll.filter(r => r.level === filter);
  document.getElementById('app-log-count').textContent = filtered.length + ' entradas';
  const lvColors = {{INFO:'#22c55e', WARNING:'#f59e0b', ERROR:'#ef4444', DEBUG:'#475569'}};
  document.getElementById('app-log-box').innerHTML = [...filtered].reverse().map(r => `
    <div class="log-entry">
      <span class="log-ts">${{fmtTs(r.timestamp)}}</span>
      <span class="log-level lvl-${{r.level}}">${{r.level}}</span>
      <span class="log-logger">${{(r.logger||'').replace('data_agents.','').replace('data_agents','')}}</span>
      <span class="log-msg">${{r.message||''}}</span>
    </div>
  `).join('');
}}

function renderAuditLog(filter) {{
  let filtered = auditLogAll;
  if (filter === 'MCP') filtered = auditLogAll.filter(r => r.tool_name && r.tool_name.startsWith('mcp__'));
  else if (filter === 'Agent') filtered = auditLogAll.filter(r => r.tool_name === 'Agent');
  document.getElementById('audit-log-count').textContent = filtered.length + ' entradas';
  document.getElementById('audit-log-box').innerHTML = [...filtered].reverse().map(r => `
    <div class="log-entry">
      <span class="log-ts">${{fmtTs(r.timestamp)}}</span>
      <span class="log-level" style="color:#818cf8;width:52px">${{r.tool_name||'?'}}</span>
      <span class="log-logger">${{r.tool_use_id ? r.tool_use_id.slice(-8) : ''}}</span>
      <span class="log-msg" style="color:#94a3b8">${{(r.input_keys||[]).join(', ')}}</span>
    </div>
  `).join('');
}}

function filterAppLog(filter, btn) {{
  document.querySelectorAll('#page-logs .log-filter-btn').forEach((b,i) => {{ if(i<4) b.classList.remove('active'); }});
  btn.classList.add('active');
  renderAppLog(filter);
}}

function filterAuditLog(filter, btn) {{
  const allBtns = document.querySelectorAll('#page-logs .log-filter-btn');
  [allBtns[4], allBtns[5], allBtns[6]].forEach(b => b && b.classList.remove('active'));
  btn.classList.add('active');
  renderAuditLog(filter);
}}

function buildLogs() {{
  appLogAll = APP.recent || [];
  auditLogAll = AUDIT.mcp_calls || [];
  // For audit, use all entries stored in mcp_calls - augment with by_tool summary
  renderAppLog('ALL');
  renderAuditLog('ALL');
}}

// ═══════════════════ CONFIG ═══════════════════
function buildConfig() {{
  const s = SETTINGS;
  document.getElementById('settings-grid').innerHTML = `
    <div class="setting-card"><div class="setting-key">Modelo Padrão</div><div class="setting-val">${{s.model||'—'}}</div><div class="setting-desc">Supervisor + Pipeline Architect</div></div>
    <div class="setting-card"><div class="setting-key">Budget Máximo</div><div class="setting-val">${{s.budget||s['budget']||'—'}}</div><div class="setting-desc">Por sessão do agente</div></div>
    <div class="setting-card"><div class="setting-key">Max Turns</div><div class="setting-val">${{s.max_turns||'—'}}</div><div class="setting-desc">Turnos por sessão</div></div>
    <div class="setting-card"><div class="setting-key">Agentes Carregados</div><div class="setting-val">${{AGENTS.length}}</div><div class="setting-desc">Via agents/registry/*.md</div></div>
    <div class="setting-card"><div class="setting-key">Log App</div><div class="setting-val" style="font-size:13px">logs/app.jsonl</div><div class="setting-desc">INFO, WARNING, ERROR, DEBUG</div></div>
    <div class="setting-card"><div class="setting-key">Log Audit</div><div class="setting-val" style="font-size:13px">logs/audit.jsonl</div><div class="setting-desc">Todas as tool calls</div></div>
  `;

  document.getElementById('files-table').innerHTML = [
    ['config/settings.py', 'Configurações (modelo, budget, max_turns, credenciais)', '~3KB'],
    ['config/mcp_servers.py', 'Registro e build dos MCP servers por plataforma', '~1KB'],
    ['config/logging_config.py', 'Setup do logging estruturado JSONL', '~2KB'],
    ['agents/registry/*.md', `${{AGENTS.length}} agentes definidos com frontmatter YAML`, `${{AGENTS.length}} arquivos`],
    ['agents/loader.py', 'Loader dinâmico — lê o registry e instancia AgentDefinition', '~6KB'],
    ['agents/supervisor.py', 'Factory do ClaudeAgentOptions (hooks, MCPs, modelo)', '~3KB'],
    ['hooks/security_hook.py', 'Bloqueia comandos destrutivos antes da execução (PreToolUse)', '~2KB'],
    ['hooks/audit_hook.py', 'Registra toda tool call em logs/audit.jsonl (PostToolUse)', '~2KB'],
    ['hooks/cost_guard_hook.py', 'Alerta operações de alto custo MCP (PostToolUse)', '~2KB'],
    ['logs/audit.jsonl', 'Histórico completo de tool calls (audit_hook)', `${{AUDIT.total}} entradas`],
    ['logs/app.jsonl', 'Log estruturado da aplicação (JSONLFormatter)', `${{APP.total}} entradas`],
  ].map(([f, d, s]) => `<tr><td style="font-family:monospace;font-size:12px">${{f}}</td><td style="color:#64748b;font-size:13px">${{d}}</td><td style="color:#94a3b8;font-size:12px">${{s}}</td></tr>`).join('');
}}

// ═══════════════════ INIT ═══════════════════
buildOverview();
buildAgents();
buildExecucoes();
buildMCP();
buildLogs();
buildConfig();
</script>
</body>
</html>
"""


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    print("📖 Lendo logs...")
    audit_records = load_jsonl(AUDIT_LOG)
    app_records = load_jsonl(APP_LOG)

    print(f"   audit.jsonl: {len(audit_records)} entradas")
    print(f"   app.jsonl:   {len(app_records)} entradas")

    print("🔍 Analisando dados...")
    audit = parse_audit(audit_records)
    app = parse_app_log(app_records)
    mcp = infer_mcp_status(app_records)
    settings = read_settings_from_app_log(app_records)

    print("🤖 Lendo registry de agentes...")
    try:
        agents = parse_registry()
        print(f"   {len(agents)} agentes encontrados")
    except ImportError:
        print("   ⚠️  PyYAML não instalado — sem dados de agentes")
        agents = []

    print("🏗️  Gerando HTML...")
    OUTPUT.parent.mkdir(exist_ok=True)
    html = generate_html(audit, app, agents, mcp, settings)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"✅ Dashboard gerado em: {OUTPUT}")
    print(f"   Abra no navegador: file://{OUTPUT.resolve()}")


if __name__ == "__main__":
    main()
