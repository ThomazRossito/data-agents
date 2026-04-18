"""
utils.tokenizer — Estimativas de tokens consumidos por texto.

Duas variantes com propósitos distintos:

  - `estimate_tokens_flat(text)`
      Heurística simples de 4 chars/token. Usada para estimar economia de
      tokens/custo em logs de compressão (onde precisão é secundária e o
      custo é médio ponderado).

  - `estimate_tokens_adjusted(text)`
      Ajusta a razão chars/token para textos com alta densidade de não-ASCII
      (português/acentos), usando 3.5 quando >10% dos chars são não-ASCII e
      4.0 caso contrário. Usada pelo `context_budget_hook` onde precisão
      importa para alertar em 80%/95% do budget.

Ambas retornam inteiros ≥ 1 para entradas não vazias (evita divisão por zero
em cálculos downstream).
"""

from __future__ import annotations

# Razão chars/token padrão (Claude tokenizer ≈ 4 chars/token em inglês/código)
CHARS_PER_TOKEN: float = 4.0

# Razão ajustada para textos com alta densidade de não-ASCII (~pt-BR)
CHARS_PER_TOKEN_NON_ASCII: float = 3.5

# Threshold de não-ASCII a partir do qual a razão ajustada é usada
NON_ASCII_DENSITY_THRESHOLD: float = 0.10


def estimate_tokens_flat(text: str) -> int:
    """
    Estima tokens via razão plana `CHARS_PER_TOKEN` (4 chars/token).

    Uso: logs de compressão, cálculos de custo agregado onde a média
    ponderada entre inglês e pt-BR é aceitável.
    """
    if not text:
        return 0
    return max(1, int(len(text) / CHARS_PER_TOKEN))


def estimate_tokens_adjusted(text: str) -> int:
    """
    Estima tokens ajustando a razão quando há muitos caracteres não-ASCII.

    Português e outros idiomas com acentos têm ~3.5 chars/token; inglês e
    código, ~4.0. Usado no `context_budget_hook` para reduzir desvio ao
    alertar sobre limites de contexto.
    """
    if not text:
        return 0
    non_ascii = sum(1 for c in text if ord(c) > 127)
    ratio = (
        CHARS_PER_TOKEN_NON_ASCII
        if non_ascii / len(text) > NON_ASCII_DENSITY_THRESHOLD
        else CHARS_PER_TOKEN
    )
    return max(1, int(len(text) / ratio))


__all__ = [
    "CHARS_PER_TOKEN",
    "CHARS_PER_TOKEN_NON_ASCII",
    "NON_ASCII_DENSITY_THRESHOLD",
    "estimate_tokens_flat",
    "estimate_tokens_adjusted",
]
