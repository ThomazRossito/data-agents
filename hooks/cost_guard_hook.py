"""Hook de controle de custo — classificação por operação e alerta de tokens."""

import logging

from config.settings import settings

logger = logging.getLogger(__name__)

_HIGH_COST_PATTERNS = [
    "execute_job", "start_cluster", "start_pipeline",
    "create_pipeline", "create_job",
]
_MEDIUM_COST_PATTERNS = ["execute_sql", "run_query", "submit_run"]

_session_high_count = 0
_session_total_tokens = 0


def classify_operation(tool_name: str) -> str:
    tl = tool_name.lower()
    if any(p in tl for p in _HIGH_COST_PATTERNS):
        return "HIGH"
    if any(p in tl for p in _MEDIUM_COST_PATTERNS):
        return "MEDIUM"
    return "LOW"


def track(tool_name: str, tokens_used: int) -> None:
    global _session_high_count, _session_total_tokens

    level = classify_operation(tool_name)
    _session_total_tokens += tokens_used

    if level == "HIGH":
        _session_high_count += 1
        if _session_high_count > 5:
            logger.warning(
                "ALERTA: %d operações HIGH nesta sessão. Verifique o custo.",
                _session_high_count,
            )

    budget = settings.max_budget_tokens
    pct = _session_total_tokens / budget if budget else 0
    if pct >= 0.95:
        logger.error(
            "CRÍTICO: 95%% do budget de tokens atingido (%d/%d).",
            _session_total_tokens, budget,
        )
    elif pct >= 0.80:
        logger.warning(
            "AVISO: 80%% do budget de tokens atingido (%d/%d).",
            _session_total_tokens, budget,
        )


def session_summary() -> dict:
    return {
        "total_tokens": _session_total_tokens,
        "high_ops": _session_high_count,
        "budget": settings.max_budget_tokens,
        "budget_pct": round(_session_total_tokens / settings.max_budget_tokens * 100, 1)
        if settings.max_budget_tokens
        else 0,
    }


def reset() -> None:
    """Reseta contadores de sessão. Útil em testes e ao iniciar nova sessão."""
    global _session_high_count, _session_total_tokens
    _session_high_count = 0
    _session_total_tokens = 0
