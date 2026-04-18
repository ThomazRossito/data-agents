"""
workflow.executor — Leitura e sumarização de eventos de workflow.

Lê `logs/workflows.jsonl` (gerado por `workflow.tracker`) e produz um dicionário
agregado consumido pelo dashboard de monitoramento.

Exportado:
  - `WORKFLOWS_LOG_PATH` (constante do caminho do log)
  - `load_workflow_history()` → `list[dict]`
  - `get_workflow_summary()`  → `dict[str, Any]` com métricas agregadas
"""

import json
import logging
from pathlib import Path
from typing import Any

from config.settings import settings

logger = logging.getLogger("data_agents.workflow.executor")

WORKFLOWS_LOG_PATH: Path = Path(settings.audit_log_path).parent / "workflows.jsonl"


def load_workflow_history() -> list[dict]:
    """Lê todos os eventos de `logs/workflows.jsonl`."""
    events: list[dict] = []
    if not WORKFLOWS_LOG_PATH.exists():
        return events
    try:
        with open(WORKFLOWS_LOG_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return events


def get_workflow_summary() -> dict[str, Any]:
    """
    Calcula resumo agregado de workflows e delegações para o dashboard.

    Returns:
        Dict com métricas de workflows, delegações por agente, Clarity Checkpoint
        e specs gerados.
    """
    events = load_workflow_history()

    summary: dict[str, Any] = {
        "total_events": len(events),
        "total_delegations": 0,
        "delegations_by_agent": {},
        "workflows_triggered": {},
        "workflow_steps": [],
        "clarity_checks": [],
        "clarity_pass_rate": 0.0,
        "specs_generated": [],
        "clarifications_requested": 0,
        "events_by_date": {},
        "prd_modifications": [],
        "specs_needing_review": [],
        "cascade_events": 0,
    }

    agent_counts: dict[str, int] = {}
    wf_counts: dict[str, int] = {}
    clarity_checks: list[dict] = []
    date_counts: dict[str, int] = {}

    for event in events:
        event_type = event.get("event", "")
        date_key = event.get("timestamp", "")[:10]
        date_counts[date_key] = date_counts.get(date_key, 0) + 1

        if event_type == "agent_delegation":
            summary["total_delegations"] += 1
            agent = event.get("agent", "unknown")
            agent_counts[agent] = agent_counts.get(agent, 0) + 1

        elif event_type == "workflow_step":
            summary["total_delegations"] += 1
            agent = event.get("agent", "unknown")
            agent_counts[agent] = agent_counts.get(agent, 0) + 1
            wf = event.get("workflow", "unknown")
            wf_counts[wf] = wf_counts.get(wf, 0) + 1
            summary["workflow_steps"].append(event)

        elif event_type == "clarity_checkpoint":
            clarity_checks.append(event)

        elif event_type == "spec_generated":
            summary["specs_generated"].append(event)

        elif event_type == "clarity_clarification_requested":
            summary["clarifications_requested"] += 1

        elif event_type == "prd_modified":
            summary["prd_modifications"].append(event)
            summary["cascade_events"] += 1

        elif event_type == "spec_needs_review":
            summary["specs_needing_review"].append(event)
            summary["cascade_events"] += 1

    summary["delegations_by_agent"] = dict(sorted(agent_counts.items(), key=lambda x: -x[1]))
    summary["workflows_triggered"] = dict(sorted(wf_counts.items(), key=lambda x: -x[1]))
    summary["clarity_checks"] = clarity_checks
    summary["events_by_date"] = dict(sorted(date_counts.items()))

    if clarity_checks:
        passed = sum(1 for c in clarity_checks if c.get("passed", False))
        summary["clarity_pass_rate"] = round(passed / len(clarity_checks) * 100, 1)

    return summary
