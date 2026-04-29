"""agents.health — Health check das plataformas configuradas.

Verifica conectividade sem chamar o LLM. Acionado via /health.

Retorna AgentResult com tabela de status:
    ✅ GitHub API — reachable
    ⚠️  Databricks  — credencial ausente
    ❌ Fabric       — connection refused
    ✅ Memory       — 3 memórias ativas
    ✅ KG           — 12 entidades, 8 relações
"""
from __future__ import annotations

import logging
import urllib.error
import urllib.request
from typing import Any

from agents.base import AgentResult

logger = logging.getLogger("data_agents.health")

_TIMEOUT = 5


def _check(label: str, fn) -> tuple[str, str]:
    """Executa `fn()`, retorna (label, status_line)."""
    try:
        detail = fn()
        return label, f"✅  {detail}"
    except _HealthWarning as w:
        return label, f"⚠️   {w}"
    except Exception as e:
        return label, f"❌  {e}"


class _HealthWarning(Exception):
    pass


# ── Checks individuais ───────────────────────────────────────────────────────

def _check_copilot(settings: Any) -> str:
    if not settings.github_token:
        raise _HealthWarning("GITHUB_TOKEN não configurado")
    url = "https://api.github.com"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"token {settings.github_token}"},
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT):
        pass
    return "GitHub API reachable"


def _check_databricks(settings: Any) -> str:
    if not settings.has_databricks():
        raise _HealthWarning("DATABRICKS_HOST / DATABRICKS_TOKEN ausentes")
    url = f"{settings.databricks_host}/api/2.0/clusters/list"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {settings.databricks_token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT):
            pass
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return f"Databricks reachable (HTTP {e.code} — token inválido)"
        raise
    return f"Databricks reachable ({settings.databricks_host})"


def _check_fabric(settings: Any) -> str:
    if not settings.has_fabric():
        raise _HealthWarning(
            "AZURE_TENANT_ID / FABRIC_WORKSPACE_ID ausentes"
        )
    url = "https://api.fabric.microsoft.com/v1/workspaces"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT):
            pass
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return "Fabric API reachable (HTTP 401 — auth required, OK)"
        raise
    return "Fabric API reachable"


def _check_memory() -> str:
    from memory.store import MemoryStore

    store = MemoryStore()
    mems = store.list_all(active_only=True)
    return f"Memory OK — {len(mems)} memória(s) ativa(s)"


def _check_kg() -> str:
    from memory.kg import KnowledgeGraph

    kg = KnowledgeGraph()
    return f"KG OK — {kg.summary()}"


# ── Runner ───────────────────────────────────────────────────────────────────

def run_health_check() -> AgentResult:
    """Executa todos os checks e retorna AgentResult com tabela de status."""
    from config.settings import settings

    checks = [
        ("GitHub / Copilot API", lambda: _check_copilot(settings)),
        ("Databricks", lambda: _check_databricks(settings)),
        ("Microsoft Fabric", lambda: _check_fabric(settings)),
        ("Memory (episódica)", _check_memory),
        ("Knowledge Graph", _check_kg),
    ]

    rows = []
    for label, fn in checks:
        _, status = _check(label, fn)
        rows.append(f"| {label} | {status} |")

    table = (
        "## 🏥 Health Check\n\n"
        "| Componente | Status |\n"
        "|------------|--------|\n"
        + "\n".join(rows)
    )
    return AgentResult(content=table, tool_calls_count=0, tokens_used=0)
