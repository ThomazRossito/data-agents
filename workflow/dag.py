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
# Lidos dinamicamente do registry para evitar dessincronização com novos agentes.

from config.agent_meta import get_known_agents as _get_known_agents  # noqa: E402
from ui.ui_config import AGENT_DISPLAY_NAMES as _DISPLAY_NAMES  # noqa: E402

KNOWN_AGENTS: frozenset[str] = _get_known_agents()


def display_name_for(raw: str) -> str:
    """Retorna o nome legível para exibição no dashboard."""
    return _DISPLAY_NAMES.get(raw, raw.replace("-", " ").title())
