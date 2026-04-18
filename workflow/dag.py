"""
workflow.dag — Constantes e padrões de reconhecimento de eventos de workflow.

Fonte de verdade para: agentes conhecidos, regex de detecção, display names.
Alterações aqui propagam para `tracker` (reconhece eventos) e `executor` (agrega
e apresenta no dashboard).
"""

import re

# ─── Padrões de detecção ────────────────────────────────────────────────────

# Detecta referências a workflows no prompt de delegação (WF-01 a WF-05)
WORKFLOW_PATTERN = re.compile(r"WF-0([1-5])", re.IGNORECASE)

# Detecta referências ao Clarity Checkpoint
CLARITY_PATTERN = re.compile(
    r"(?:clarity|clareza|checkpoint).*?(\d)\s*/\s*5",
    re.IGNORECASE,
)

# Detecta geração de specs
SPEC_PATTERN = re.compile(
    r"(?:spec|especificação).*?(pipeline|star.?schema|cross.?platform)",
    re.IGNORECASE,
)

# Detecta modificações em arquivos PRD (output/*/prd/*.md)
PRD_PATTERN = re.compile(r"output/(?:\w+/)?prd/.*\.md$", re.IGNORECASE)

# Detecta arquivos de spec (output/*/specs/*.md)
SPEC_FILE_PATTERN = re.compile(r"output/(?:(\w+)/)?specs/(.*\.md)$", re.IGNORECASE)


# ─── Agentes conhecidos ─────────────────────────────────────────────────────

KNOWN_AGENTS: frozenset[str] = frozenset(
    {
        "sql-expert",
        "spark-expert",
        "pipeline-architect",
        "python-expert",
        "migration-expert",
        "data-quality-steward",
        "governance-auditor",
        "semantic-modeler",
        "business-analyst",
        "dbt-expert",
        "business-monitor",
        "geral",
    }
)

_DISPLAY_NAMES: dict[str, str] = {
    "sql-expert": "SQL Expert",
    "spark-expert": "Spark Expert",
    "pipeline-architect": "Pipeline Architect",
    "python-expert": "Python Expert",
    "migration-expert": "Migration Expert",
    "data-quality-steward": "Data Quality Steward",
    "governance-auditor": "Governance Auditor",
    "semantic-modeler": "Semantic Modeler",
    "business-analyst": "Business Analyst",
    "dbt-expert": "dbt Expert",
    "business-monitor": "Business Monitor",
    "geral": "Geral",
}


def display_name_for(raw: str) -> str:
    """Retorna o nome legível para exibição no dashboard."""
    return _DISPLAY_NAMES.get(raw, raw)
