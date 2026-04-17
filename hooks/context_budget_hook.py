"""
Context Budget Hook — Monitoramento de uso do context window (Ch. 5 — Agent Loop).

Inspirado na 4ª camada de compressão descrita em Ch. 5 do livro
"Claude Code from Source": monitoramento do context window com avisos proativos
antes de atingir limites que causariam truncagem silenciosa ou falha da sessão.

Estratégia:
  - Rastreia tokens de input (prompt) e output (completion) acumulados na sessão.
  - Emite WARNING quando o uso atinge o limiar de alerta (padrão: 80% do budget).
  - Emite ERROR quando atinge o limiar crítico (padrão: 95% do budget).
  - Não bloqueia a execução — apenas registra. O cost_guard_hook bloqueia por custo.

Relação com outros hooks:
  - cost_guard_hook.py: bloqueia por custo em USD. Este hook monitora tokens brutos.
  - output_compressor_hook.py: comprime output de tools (camada 1 de compressão).
  - Este hook: monitora o contexto acumulado (camada 4 de compressão — watchdog).
"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import settings

logger = logging.getLogger("data_agents.hooks.context_budget")

# Tokens aproximados: estimativa grosseira se os metadados não estiverem disponíveis
# 1 token ≈ 4 chars em inglês / ~3.5 chars em português
_CHARS_PER_TOKEN = 4

# Rastreia se o checkpoint crítico já foi salvo na sessão atual (evita saves repetidos)
_critical_checkpoint_saved: bool = False

# Contadores por sessão — isolados por reset explícito (reset_context_budget)
_session_input_tokens: int = 0
_session_output_tokens: int = 0

# Aliases de módulo para compatibilidade com testes e importações externas
_INPUT_TOKEN_LIMIT: int = settings.context_budget_input_limit
_WARN_THRESHOLD: float = settings.context_budget_warn_threshold
_CRITICAL_THRESHOLD: float = settings.context_budget_critical_threshold


async def track_context_budget(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    """
    Hook PostToolUse que monitora o consumo de tokens da sessão.

    Rastreia tokens acumulados e emite alertas quando o uso se aproxima
    dos limites do context window. Não bloqueia a execução.

    Assinatura alinhada com o SDK: (input_data, tool_use_id, context).
    input_data contém: tool_name, tool_input, tool_output.

    Returns:
        {} (hook não modifica o output).
    """
    global _session_input_tokens, _session_output_tokens, _critical_checkpoint_saved

    if not input_data or not isinstance(input_data, dict):
        return {}

    input_token_limit = settings.context_budget_input_limit
    warn_threshold = settings.context_budget_warn_threshold
    critical_threshold = settings.context_budget_critical_threshold

    tool_input = input_data.get("tool_input")
    tool_output = input_data.get("tool_output")
    if isinstance(tool_output, dict):
        tool_output = str(tool_output)

    # Extrai contagem de tokens do context (se o SDK fornecer) ou de tool_input/output
    input_tokens, output_tokens = _extract_token_counts(tool_input, tool_output, context)

    _session_input_tokens += input_tokens
    _session_output_tokens += output_tokens

    usage_ratio = _session_input_tokens / input_token_limit

    if usage_ratio >= critical_threshold:
        logger.error(
            f"🚨 CONTEXT CRÍTICO: {_session_input_tokens:,}/{input_token_limit:,} tokens "
            f"({usage_ratio:.0%}) — sessão próxima ao limite. "
            f"Considere iniciar nova sessão ou usar /memory flush para compactar contexto."
        )
        # Salva checkpoint uma única vez ao atingir o limiar crítico
        if not _critical_checkpoint_saved:
            _critical_checkpoint_saved = True
            _save_emergency_checkpoint()
    elif usage_ratio >= warn_threshold:
        logger.warning(
            f"⚠️  CONTEXT ALTO: {_session_input_tokens:,}/{input_token_limit:,} tokens "
            f"({usage_ratio:.0%}) — {input_token_limit - _session_input_tokens:,} tokens restantes."
        )
    else:
        logger.debug(
            f"Context budget: {_session_input_tokens:,} input + "
            f"{_session_output_tokens:,} output tokens acumulados "
            f"({usage_ratio:.1%} do limite de {input_token_limit:,})"
        )

    return {}


def _save_emergency_checkpoint() -> None:
    """Tenta salvar um checkpoint de emergência ao atingir 95% do context budget."""
    try:
        from hooks.checkpoint import save_checkpoint

        save_checkpoint(reason="context_budget_critical")
        logger.warning("💾 Checkpoint de emergência salvo (context budget crítico).")
    except Exception as e:
        logger.warning(f"Checkpoint de emergência não disponível: {e}")


def _extract_token_counts(
    tool_input: dict[str, Any] | None,
    tool_output: str | None,
    hook_context: dict[str, Any] | None,
) -> tuple[int, int]:
    """
    Extrai contagens de tokens dos metadados disponíveis.

    Tenta múltiplas fontes em ordem de precisão:
    1. hook_context["usage"] — metadados do SDK (mais preciso)
    2. Estimativa por contagem de caracteres (fallback)

    Returns:
        Tupla (input_tokens, output_tokens)
    """
    # Fonte 1: metadados do SDK no hook_context
    if hook_context:
        usage = hook_context.get("usage") or hook_context.get("token_usage") or {}
        if isinstance(usage, dict):
            sdk_input = usage.get("input_tokens") or usage.get("prompt_tokens", 0)
            sdk_output = usage.get("output_tokens") or usage.get("completion_tokens", 0)
            if sdk_input or sdk_output:
                return int(sdk_input), int(sdk_output)

    # Fonte 2: estimativa por caracteres (fallback quando SDK não fornece metadados)
    estimated_input = 0
    estimated_output = 0

    if tool_input:
        input_text = str(tool_input)
        estimated_input = max(1, len(input_text) // _CHARS_PER_TOKEN)

    if tool_output:
        estimated_output = max(1, len(tool_output) // _CHARS_PER_TOKEN)

    return estimated_input, estimated_output


def get_context_usage() -> dict[str, Any]:
    """
    Retorna estatísticas do uso de contexto da sessão atual.

    Útil para o painel de memória da UI e para diagnóstico.

    Returns:
        Dict com tokens usados, limite, razão de uso e status.
    """
    input_token_limit = settings.context_budget_input_limit
    ratio = _session_input_tokens / input_token_limit
    if ratio >= settings.context_budget_critical_threshold:
        status = "critical"
    elif ratio >= settings.context_budget_warn_threshold:
        status = "warning"
    else:
        status = "ok"

    return {
        "input_tokens": _session_input_tokens,
        "output_tokens": _session_output_tokens,
        "total_tokens": _session_input_tokens + _session_output_tokens,
        "limit": input_token_limit,
        "usage_ratio": ratio,
        "remaining_tokens": max(0, input_token_limit - _session_input_tokens),
        "status": status,
    }


def reset_context_budget() -> None:
    """
    Reseta os contadores de tokens da sessão.

    Chamado no início de cada nova sessão ou após /memory flush.
    """
    global _session_input_tokens, _session_output_tokens, _critical_checkpoint_saved
    _session_input_tokens = 0
    _session_output_tokens = 0
    _critical_checkpoint_saved = False
    logger.debug("Context budget resetado.")
