"""workflow — Motor de workflows colaborativos multi-agente."""
from workflow.dag import WorkflowDef, detect_workflow
from workflow.executor import execute_workflow

__all__ = ["WorkflowDef", "detect_workflow", "execute_workflow"]
