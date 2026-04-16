"""
Hook de controle de custos — loga e alerta sobre execuções que podem gerar custo elevado.
Aplicado como PostToolUse para monitoramento.

Implementa:
  - Classificação de custo por tier (HIGH, MEDIUM, LOW)
  - Logging estruturado via módulo logging
  - Contagem de operações por sessão para alertas acumulados
"""

import logging
from typing import Any

logger = logging.getLogger("data_agents.cost")

# ─── Classificação de custo por tool ──────────────────────────────

COST_TIERS: dict[str, dict] = {
    # HIGH: Operações que iniciam compute ou executam jobs
    "mcp__databricks__run_job_now": {"tier": "HIGH", "description": "Execução de Job Databricks"},
    "mcp__databricks__start_cluster": {"tier": "HIGH", "description": "Inicialização de Cluster"},
    "mcp__databricks__start_pipeline": {
        "tier": "HIGH",
        "description": "Inicialização de Pipeline SDP",
    },
    "mcp__databricks__cancel_run": {"tier": "HIGH", "description": "Cancelamento de Job Run"},
    # MEDIUM: Operações que consomem SQL Warehouse (DBUs)
    "mcp__databricks__execute_sql": {"tier": "MEDIUM", "description": "Execução SQL no Warehouse"},
    # LOW: Operações de leitura que podem ter custo marginal
    "mcp__databricks__get_query_history": {
        "tier": "LOW",
        "description": "Consulta de histórico SQL",
    },
    "mcp__fabric_rti__kusto_query": {"tier": "LOW", "description": "Query KQL no Eventhouse"},
}

# Contadores de sessão (resetados a cada restart)
_session_counters: dict[str, int] = {}


async def log_cost_generating_operations(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    """
    Registra operações de custo elevado com classificação por tier.

    Emite warnings para operações HIGH e alertas quando o acumulado
    de operações HIGH ultrapassa 100 na mesma sessão.
    """
    # Proteção contra eventos de teardown do SDK
    if not input_data or not isinstance(input_data, dict):
        return {}

    tool_name = input_data.get("tool_name", "")

    if tool_name not in COST_TIERS:
        return {}

    info = COST_TIERS[tool_name]
    tier = info["tier"]
    description = info["description"]

    # Incrementar contador de sessão
    _session_counters[tool_name] = _session_counters.get(tool_name, 0) + 1
    count = _session_counters[tool_name]

    # Total de operações HIGH na sessão
    total_high = sum(
        _session_counters.get(t, 0) for t, i in COST_TIERS.items() if i["tier"] == "HIGH"
    )

    if tier == "HIGH":
        logger.warning(
            f"[COST:HIGH] {description}: {tool_name} "
            f"(uso #{count} nesta sessão, total HIGH={total_high}) "
            f"tool_use_id={tool_use_id}"
        )
        if total_high >= 100:
            logger.warning(
                f"[COST:ALERT] {total_high} operações de custo elevado nesta sessão. "
                f"Considere revisar se todas são necessárias."
            )
    elif tier == "MEDIUM":
        logger.info(
            f"[COST:MEDIUM] {description}: {tool_name} (uso #{count}) tool_use_id={tool_use_id}"
        )
    else:
        logger.debug(
            f"[COST:LOW] {description}: {tool_name} (uso #{count}) tool_use_id={tool_use_id}"
        )

    return {}


def get_session_cost_summary() -> dict[str, Any]:
    """
    Retorna resumo de custos da sessão atual.
    Útil para o comando /status ou para o template de síntese do DOMA.
    """
    summary: dict[str, Any] = {"total_operations": 0, "by_tier": {}, "by_tool": {}}

    for tool_name, count in _session_counters.items():
        tier = COST_TIERS.get(tool_name, {}).get("tier", "UNKNOWN")
        summary["total_operations"] += count
        summary["by_tier"][tier] = summary["by_tier"].get(tier, 0) + count
        summary["by_tool"][tool_name] = count

    return summary


def reset_session_counters() -> None:
    """Reseta os contadores de sessão. Chamado no início de cada nova sessão."""
    _session_counters.clear()
