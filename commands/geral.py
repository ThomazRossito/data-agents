"""
commands/geral.py — Lógica compartilhada do comando /geral.

Módulo único importado por múltiplos entry points:
  - main.py              (CLI interativo / terminal)
  - ui/chainlit_app.py   (interface Chainlit)

Garante implementação única — sem duplicação entre os entry points.
O caller é responsável por gerenciar o histórico e exibir a resposta.

Uso típico:
    from commands.geral import run_geral_query, build_prompt_with_history

    history.append({"role": "user", "content": user_message})
    text, metrics = await run_geral_query(user_message, history)
    if text:
        history.append({"role": "assistant", "content": text})
"""

from __future__ import annotations

import logging
import time

import anthropic

from config.settings import settings

logger = logging.getLogger("data_agents.geral")

# ── System prompt ─────────────────────────────────────────────────────────────
GERAL_SYSTEM = (
    "Você é um assistente técnico especializado em Engenharia de Dados: "
    "Databricks, Microsoft Fabric, Apache Spark, Delta Lake, SQL, arquitetura Medallion "
    "e boas práticas. "
    "Always respond in English (EN-US), directly and objectively. "
    "Use exemplos e code blocks quando enriquecer a resposta. "
    "Não peça aprovação, não crie documentos, não acesse arquivos externos."
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _geral_model() -> str:
    """
    Modelo para /geral — sempre Haiku (T0).

    T0 é intencionalmente excluído do TIER_MODEL_MAP para que o Haiku
    não seja sobrescrito acidentalmente por um override global de T1/T2/T3.
    """
    tier_map: dict = getattr(settings, "tier_model_map", {}) or {}
    return tier_map.get("T0") or "claude-haiku-4-5"


def build_prompt_with_history(user_message: str, history: list[dict]) -> str:
    """
    Embute histórico recente no prompt para suporte a follow-ups.

    O sdk_query() é stateless (não há API de multi-turn), então o histórico
    é prefixado como texto estruturado antes da mensagem atual.

    Args:
        user_message: Mensagem atual do usuário (deve já estar em history).
        history:      Lista completa [{role, content}] incluindo a mensagem atual.

    Returns:
        Prompt final com histórico prefixado (se houver turnos anteriores).
    """
    history_prefix = ""
    if len(history) > 1:
        lines: list[str] = []
        for msg in history[-21:-1]:  # até 10 turnos anteriores (excluindo atual)
            role = "Usuário" if msg["role"] == "user" else "Assistente"
            lines.append(f"{role}: {msg['content']}")
        if lines:
            history_prefix = "Histórico:\n" + "\n".join(lines) + "\n\n"
    return history_prefix + user_message


# ── Core async ────────────────────────────────────────────────────────────────


async def run_geral_query(
    user_message: str,
    history: list[dict],
    session_type: str = "geral",
) -> tuple[str, dict[str, float]]:
    """
    Executa consulta /geral via API Anthropic direta (sem SDK de agentes).

    Usa anthropic.AsyncAnthropic em vez de sdk_query porque /geral é uma
    query single-turn simples sem ferramentas ou sub-agentes. O SDK de agentes
    não é adequado para chamadas stateless diretas sem orchestration.

    O caller é responsável por:
      1. Adicionar user_message ao history ANTES de chamar esta função.
      2. Adicionar response_text ao history APÓS retorno bem-sucedido.
      3. Exibir o response_text (CLI com Rich ou UI com Streamlit).

    Args:
        user_message: Mensagem atual do usuário (sem histórico embutido).
        history:      Lista [{role, content}] incluindo a mensagem atual.
        session_type: Tipo de sessão para logging (default "geral").

    Returns:
        Tuple (response_text, metrics) onde:
          - response_text: Texto da resposta (vazio se erro).
          - metrics: {"cost": float, "turns": float, "duration": float}

    Raises:
        Propaga exceções da API Anthropic — o caller deve tratar e reverter histórico.
    """
    prompt = build_prompt_with_history(user_message, history)
    model = _geral_model()

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    t0 = time.monotonic()
    message = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=GERAL_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    duration = time.monotonic() - t0

    # Extrai texto da resposta
    response_text = ""
    for block in message.content:
        if hasattr(block, "text") and block.text.strip():
            response_text += block.text

    # Calcula custo estimado (Haiku: $0.80/MTok input, $4.00/MTok output)
    input_tokens = message.usage.input_tokens if message.usage else 0
    output_tokens = message.usage.output_tokens if message.usage else 0
    cost = (input_tokens * 0.80 + output_tokens * 4.00) / 1_000_000

    metrics: dict[str, float] = {
        "cost": cost,
        "turns": 1.0,
        "duration": duration,
        "input_tokens": float(input_tokens),
        "output_tokens": float(output_tokens),
    }

    logger.debug(
        "geral query: model=%s cost=%.5f in=%d out=%d duration=%.1fs",
        model,
        cost,
        input_tokens,
        output_tokens,
        duration,
    )

    return response_text, metrics
