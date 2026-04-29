"""hooks.output_compressor — Trunca respostas verbosas.

Garante que respostas longas de MCP ou agentes não desperdicem
janela de contexto em chamadas subsequentes.

    compress("texto longo...", max_chars=8000)
    → head + [...N chars truncados...] + tail
"""
from __future__ import annotations

_HEAD_CHARS = 3000
_TAIL_CHARS = 2000


def compress(text: str, max_chars: int = 8000) -> str:
    """
    Trunca `text` para no máximo `max_chars` caracteres.

    Preserva os primeiros `_HEAD_CHARS` e últimos `_TAIL_CHARS` chars,
    inserindo uma linha de indicação do truncamento no meio.
    Se o texto já couber em `max_chars`, retorna inalterado.
    """
    if len(text) <= max_chars:
        return text

    head_limit = min(_HEAD_CHARS, max_chars // 2)
    tail_limit = min(_TAIL_CHARS, max_chars // 2)
    removed = len(text) - head_limit - tail_limit
    marker = f"\n\n[...{removed} caracteres truncados...]\n\n"
    return text[:head_limit] + marker + text[-tail_limit:]
