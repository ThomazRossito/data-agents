"""
compression.metrics — Persistência de métricas de compressão em JSONL.

Grava em `logs/compression.jsonl` uma linha por compressão aplicada, com:
  - chars original / comprimido / economizados
  - percentual de redução
  - tokens estimados economizados e custo em USD
  - `tool_use_id` para correlação com audit log

Nunca propaga exceções — o hook é fail-safe.
"""

import json
import os
from datetime import datetime, timezone

from compression.constants import (
    AVG_INPUT_PRICE_PER_TOKEN,
    CHARS_PER_TOKEN,
    COMPRESSION_LOG_PATH,
)


def _log_compression_metrics(
    tool_name: str,
    original_chars: int,
    compressed_chars: int,
    tool_use_id: str | None,
) -> None:
    """Persiste métricas de compressão em logs/compression.jsonl."""
    try:
        saved_chars = original_chars - compressed_chars
        reduction_pct = (
            round((1 - compressed_chars / original_chars) * 100, 1) if original_chars > 0 else 0.0
        )
        saved_tokens_est = round(saved_chars / CHARS_PER_TOKEN)
        saved_cost_est = round(saved_tokens_est * AVG_INPUT_PRICE_PER_TOKEN, 6)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_name": tool_name,
            "original_chars": original_chars,
            "compressed_chars": compressed_chars,
            "saved_chars": saved_chars,
            "reduction_pct": reduction_pct,
            "saved_tokens_est": saved_tokens_est,
            "saved_cost_est_usd": saved_cost_est,
            "tool_use_id": tool_use_id or "",
        }

        os.makedirs(os.path.dirname(COMPRESSION_LOG_PATH), exist_ok=True)
        with open(COMPRESSION_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Nunca bloqueia a execução
