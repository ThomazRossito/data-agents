"""
Hook de controle de custos — loga e alerta sobre execuções que podem gerar custo elevado.
Aplicado como PostToolUse para monitoramento.
"""

from typing import Any


# Tools que geram custo ao serem executadas (clusters, warehouses, jobs)
HIGH_COST_TOOLS = [
    "mcp__databricks__run_job_now",
    "mcp__databricks__start_cluster",
    "mcp__databricks__start_pipeline",
    "mcp__databricks__execute_sql",
]


async def log_cost_generating_operations(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    """
    Registra no stdout quando uma operação de custo elevado é executada.
    Pode ser expandido para integrar com sistema de billing/alertas.
    """
    tool_name = input_data.get("tool_name", "")

    if tool_name in HIGH_COST_TOOLS:
        print(
            f"[COST ALERT] Tool de custo elevado executada: {tool_name} "
            f"(tool_use_id={tool_use_id})"
        )

    return {}
