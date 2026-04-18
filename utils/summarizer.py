"""
Session Summarizer — Sumariza um transcript de sessão via Claude Haiku.

Motivação (T4.4): quando a sessão se aproxima do limite de contexto (>65%),
compactamos o histórico em 7 campos estruturados. O resumo é emitido por
Claude Haiku (modelo barato e rápido) via Anthropic Messages API diretamente
— sem passar pelo Claude Agent SDK nem pelo Supervisor.

O prompt segue o template GAPS G3 (Goal / Actions / Plan / State), adaptado
para 7 campos úteis em continuidade de sessão de engenharia de dados.

Uso programático:
    from utils.summarizer import summarize_session
    from hooks.transcript_hook import load_transcript

    result = await summarize_session(load_transcript(session_id))
    print(result["summary"])
    print(f"Custo: ${result['cost_usd']:.5f}")
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("data_agents.summarizer")

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_MAX_OUTPUT_TOKENS = 2048

# Preços Haiku 4.5 (USD por 1M tokens) — janeiro/2026.
_PRICE_INPUT_PER_MTOK = 1.00
_PRICE_OUTPUT_PER_MTOK = 5.00

_SYSTEM_PROMPT = """Você é o Session Summarizer do projeto data-agents. Sua tarefa: dado um
transcript (pares usuário↔assistente) de uma sessão de engenharia de dados, emitir
um resumo estruturado em 7 campos para permitir retomada ou handoff.

## Formato obrigatório (Markdown, respeite a ordem e os títulos)

## Objetivo
<uma frase com a meta principal da sessão>

## Decisões
- <decisão técnica/arquitetural tomada, ≤12 palavras>

## Artefatos
- `path/ou/tabela/tocada`

## Pendências
- **<item aberto>** — <motivo>

## Próximos passos
- <ação acionável, ≤12 palavras>

## Contexto técnico
- <catálogos, schemas, libs, APIs, credenciais, plataformas envolvidas>

## Descobertas-chave
- <aprendizado, gotcha, anti-padrão, fato surpreendente>

## Regras rígidas

- Se um campo não tiver evidência no transcript, escreva `Nenhum(a)` na linha
  seguinte ao título. **Nunca invente.**
- Bullets curtos. Priorize sinal sobre texto decorativo.
- Use paths reais que apareceram no transcript — nunca fabrique arquivos.
- Seu output é o resumo e SÓ o resumo. Não inclua preâmbulo, explicação ou
  comentários fora dos 7 campos.
"""


def _format_transcript(
    transcript: list[dict[str, Any]], max_turns: int, max_chars_per_turn: int
) -> str:
    """Converte a lista de entries do transcript em texto plano para envio ao modelo."""
    if not transcript:
        return ""

    tail = transcript[-(max_turns * 2) :]
    lines: list[str] = []
    for entry in tail:
        role = entry.get("role", "?")
        content = (entry.get("content") or "")[:max_chars_per_turn]
        label = "USER" if role == "user" else "ASSISTANT"
        lines.append(f"### {label}\n{content}")
    return "\n\n".join(lines)


def _estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    """Calcula o custo em USD com base nos preços do modelo Haiku."""
    cost_in = (input_tokens / 1_000_000) * _PRICE_INPUT_PER_MTOK
    cost_out = (output_tokens / 1_000_000) * _PRICE_OUTPUT_PER_MTOK
    return round(cost_in + cost_out, 6)


def should_summarize(context_used_ratio: float, threshold: float = 0.65) -> bool:
    """
    Decide se é hora de rodar o sumarizador.

    Args:
        context_used_ratio: Fração [0, 1] do context budget já consumida.
        threshold: Limiar para disparar o resumo (default 0.65).

    Returns:
        True quando o consumo ultrapassou o limiar.
    """
    return context_used_ratio >= threshold


async def summarize_session(
    transcript: list[dict[str, Any]],
    model: str = _DEFAULT_MODEL,
    max_turns: int = 60,
    max_chars_per_turn: int = 3000,
    api_key: str | None = None,
) -> dict[str, Any]:
    """
    Sumariza um transcript chamando Anthropic Messages API direta (Haiku).

    A função é `async` para se integrar facilmente ao event loop do `main.py`
    e ao fluxo existente em `scripts/refresh_skills.py`.

    Args:
        transcript: Lista de entries no formato do transcript_hook
            (dicts com role, content, timestamp, ...).
        model: Identificador do modelo Anthropic. Padrão: Claude Haiku 4.5.
        max_turns: Quantidade máxima de pares user/assistant a enviar.
        max_chars_per_turn: Teto de caracteres por turno.
        api_key: ANTHROPIC_API_KEY. Se None, usa `settings.anthropic_api_key`.

    Returns:
        Dict com:
          - summary (str): o Markdown estruturado nos 7 campos
          - input_tokens (int)
          - output_tokens (int)
          - cost_usd (float)
          - model (str)
          - turns_summarized (int): quantidade de entries consideradas

    Raises:
        ValueError: se o transcript estiver vazio.
        RuntimeError: se a chamada à API falhar.
    """
    if not transcript:
        raise ValueError("Transcript vazio — nada a sumarizar.")

    from anthropic import AsyncAnthropic
    from config.settings import settings

    key = api_key or settings.anthropic_api_key
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY ausente. Configure no .env ou passe via api_key=.")

    formatted = _format_transcript(
        transcript, max_turns=max_turns, max_chars_per_turn=max_chars_per_turn
    )
    user_message = (
        "Resuma o transcript abaixo nos 7 campos definidos no system prompt.\n\n"
        "===== TRANSCRIPT =====\n"
        f"{formatted}\n"
        "===== FIM =====\n"
    )

    client = AsyncAnthropic(api_key=key)

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=_MAX_OUTPUT_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
    except Exception as e:
        logger.error(f"Falha ao chamar Anthropic API para summarize: {e}")
        raise RuntimeError(f"Summarizer falhou: {e}") from e

    # Extrai o texto consolidado de todos os blocos do tipo "text".
    summary_parts: list[str] = []
    for block in response.content:
        text = getattr(block, "text", None)
        if text:
            summary_parts.append(text)
    summary = "\n".join(summary_parts).strip()

    input_tokens = int(getattr(response.usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(response.usage, "output_tokens", 0) or 0)
    cost = _estimate_cost_usd(input_tokens, output_tokens)

    turns_considered = min(len(transcript), max_turns * 2)

    logger.info(
        f"Session summarized: {turns_considered} entries → {len(summary)} chars "
        f"(${cost:.5f}, {input_tokens}/{output_tokens} tokens)"
    )

    return {
        "summary": summary,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
        "model": model,
        "turns_summarized": turns_considered,
    }
