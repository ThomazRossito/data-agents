"""
Context Budget Hook — Monitoramento e compactação autônoma do context window.

Estratégia em 3 limiares:
  70%  → WARNING: avisa o usuário preventivamente.
  80%  → COMPACTAR: gera summary via Haiku, seta flag de compactação.
         O entry point (main.py / chainlit_app.py) detecta o flag após a resposta,
         injeta o summary no base system_prompt e reconecta o cliente — transparente.
  95%  → ERROR: se a compactação falhou por algum motivo, loga critical.

Relação com outros hooks:
  - cost_guard_hook.py: bloqueia por custo em USD. Este hook monitora tokens brutos.
  - output_compressor_hook.py: comprime output de tools (camada 1 de compressão).
  - Este hook: monitora o contexto acumulado e dispara compactação autônoma.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import settings
from utils.tokenizer import estimate_tokens_adjusted as _estimate_tokens

logger = logging.getLogger("data_agents.hooks.context_budget")


# Rastreia se a compactação já foi disparada na sessão atual (evita duplo disparo).
_compaction_fired_for_session: bool = False

# Flag consumível: True quando uma compactação foi concluída e aguarda ser aplicada.
_compaction_pending: bool = False

# Summary gerado pela compactação — consumido pelo entry point.
_compaction_summary: str = ""

# Session ID da sessão corrente — configurado por reset_context_budget(session_id=...).
_active_session_id: str | None = None

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

    Rastreia tokens acumulados e:
      - 70%: emite WARNING proativo.
      - 80%: dispara _schedule_compaction() uma única vez por sessão.
      - 95%: emite ERROR (safety net caso a compactação não tenha ocorrido).

    Returns:
        {} (hook não modifica o output).
    """
    global _session_input_tokens, _session_output_tokens
    global _compaction_fired_for_session

    if not input_data or not isinstance(input_data, dict):
        return {}

    input_token_limit = settings.context_budget_input_limit
    warn_threshold = settings.context_budget_warn_threshold
    critical_threshold = settings.context_budget_critical_threshold
    summarize_threshold = settings.context_budget_summarize_threshold

    tool_input = input_data.get("tool_input")
    tool_output = input_data.get("tool_output")
    if isinstance(tool_output, dict):
        tool_output = str(tool_output)

    input_tokens, output_tokens = _extract_token_counts(tool_input, tool_output, context)

    _session_input_tokens += input_tokens
    _session_output_tokens += output_tokens

    usage_ratio = _session_input_tokens / input_token_limit

    # Compactação autônoma: dispara uma única vez por sessão ao cruzar o limiar.
    # A flag é definida ANTES do await para evitar duplo disparo em chamadas concorrentes.
    if usage_ratio >= summarize_threshold and not _compaction_fired_for_session:
        _compaction_fired_for_session = True
        await _schedule_compaction(usage_ratio)

    if usage_ratio >= critical_threshold:
        logger.error(
            f"🚨 CONTEXT CRÍTICO: {_session_input_tokens:,}/{input_token_limit:,} tokens "
            f"({usage_ratio:.0%}) — sessão próxima ao limite. "
            f"Compactação autônoma pode ter falhado; considere reiniciar a sessão."
        )
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


async def _schedule_compaction(usage_ratio: float) -> None:
    """Gera summary via Haiku, persiste em disco e seta o flag de compactação.

    O entry point (main.py / chainlit_app.py) chama check_and_consume_compaction()
    após cada resposta do Supervisor e, se o flag estiver ativo, injeta o summary
    no base system_prompt e reconecta o cliente — nova janela de contexto limpa.

    Falhas são best-effort: logadas mas não propagadas.
    """
    global _compaction_pending, _compaction_summary

    session_id = _active_session_id
    if not session_id:
        logger.info(
            f"📋 Compactação não disparada: session_id desconhecido "
            f"(usage={usage_ratio:.0%}). Chame reset_context_budget(session_id=...)."
        )
        return
    try:
        from hooks.transcript_hook import load_transcript
        from utils.summarizer import summarize_session

        transcript = load_transcript(session_id)
        if not transcript:
            logger.info(f"📋 Compactação: transcript vazio para {session_id}; skip.")
            return

        result = await summarize_session(transcript)
        _persist_summary(session_id, result, usage_ratio)

        _compaction_summary = result.get("summary", "")
        _compaction_pending = True

        logger.info(
            f"📋 Compactação agendada a {usage_ratio:.0%}: {session_id} "
            f"({result['turns_summarized']} turns, ${result['cost_usd']:.5f})"
        )
    except Exception as e:
        logger.warning(f"Compactação auto falhou (session={session_id}): {e}")


def check_and_consume_compaction() -> str | None:
    """Retorna o summary de compactação se pendente e limpa o flag.

    Deve ser chamado pelo entry point (main.py / chainlit_app.py) após cada
    resposta do Supervisor. Se retornar uma string não-vazia, o caller deve:
      1. Injetar o summary no base system_prompt.
      2. Reconectar o cliente SDK para iniciar nova janela de contexto.

    Returns:
        Summary Markdown se compactação está pendente; None caso contrário.
    """
    global _compaction_pending, _compaction_summary

    if not _compaction_pending:
        return None

    summary = _compaction_summary
    _compaction_pending = False
    _compaction_summary = ""
    return summary or None


def _persist_summary(session_id: str, result: dict[str, Any], usage_ratio: float) -> None:
    """Grava o resumo estruturado em `logs/summaries/<session_id>.md`."""
    summaries_dir = Path(settings.audit_log_path).parent / "summaries"
    path = summaries_dir / f"{session_id}.md"
    ts = datetime.now(timezone.utc).isoformat()
    header = (
        f"# Session Summary — {session_id}\n\n"
        f"_Disparado em {ts} ao atingir {usage_ratio:.0%} do context budget._\n"
        f"_Modelo: {result['model']} | Turns: {result['turns_summarized']} | "
        f"Custo: ${result['cost_usd']:.5f}_\n\n---\n\n"
    )
    try:
        summaries_dir.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(header + result.get("summary", "") + "\n")
    except OSError as e:
        logger.warning(f"Falha ao gravar summary em {path}: {e}")


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
        estimated_input = _estimate_tokens(input_text)

    if tool_output:
        estimated_output = _estimate_tokens(tool_output)

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


def reset_context_budget(session_id: str | None = None) -> None:
    """
    Reseta os contadores de tokens e o estado de compactação da sessão.

    Chamado no início de cada nova sessão ou após reconexão do cliente.
    Quando `session_id` é fornecido, registra-o como sessão ativa para que
    _schedule_compaction() possa localizar o transcript correto.
    """
    global _session_input_tokens, _session_output_tokens
    global _compaction_fired_for_session, _compaction_pending, _compaction_summary
    global _active_session_id
    _session_input_tokens = 0
    _session_output_tokens = 0
    _compaction_fired_for_session = False
    _compaction_pending = False
    _compaction_summary = ""
    _active_session_id = session_id
    logger.debug(f"Context budget resetado (session_id={session_id}).")
