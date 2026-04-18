"""
Pacote `workflow` — rastreamento e agregação de eventos de workflows DOMA.

Módulos:
  - `workflow.dag`       — constantes: agentes conhecidos, padrões regex, display names
  - `workflow.tracker`   — hooks PreToolUse / PostToolUse + callbacks de progresso
  - `workflow.executor`  — leitura e sumarização de `logs/workflows.jsonl`

Re-export de símbolos estáveis para compatibilidade com `hooks.workflow_tracker`.
"""

from workflow.dag import (
    CLARITY_PATTERN,
    KNOWN_AGENTS,
    PRD_PATTERN,
    SPEC_FILE_PATTERN,
    SPEC_PATTERN,
    WORKFLOW_PATTERN,
    display_name_for,
)
from workflow.executor import (
    WORKFLOWS_LOG_PATH,
    get_workflow_summary,
    load_workflow_history,
)
from workflow.tracker import (
    clear_progress_callbacks,
    pre_track_workflow_events,
    register_progress_callback,
    track_workflow_events,
    unregister_progress_callback,
)

__all__ = [
    "CLARITY_PATTERN",
    "KNOWN_AGENTS",
    "PRD_PATTERN",
    "SPEC_FILE_PATTERN",
    "SPEC_PATTERN",
    "WORKFLOW_PATTERN",
    "WORKFLOWS_LOG_PATH",
    "clear_progress_callbacks",
    "display_name_for",
    "get_workflow_summary",
    "load_workflow_history",
    "pre_track_workflow_events",
    "register_progress_callback",
    "track_workflow_events",
    "unregister_progress_callback",
]
