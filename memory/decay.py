"""memory.decay — Cálculo de confidence com decaimento temporal."""
from __future__ import annotations

from datetime import UTC, datetime

from memory.types import DECAY_CONFIG, Memory


def compute_decayed_confidence(memory: Memory, now: datetime | None = None) -> float:
    """
    Calcula a confidence decaída de uma memória.

    Tipos sem entrada em DECAY_CONFIG nunca decaem (retornam confidence original).
    Tipos com decay perdem `rate * days_since_update` de confidence (mínimo 0.0).
    """
    if now is None:
        now = datetime.now(UTC)

    decay_rate = DECAY_CONFIG.get(memory.type)
    if decay_rate is None:
        return memory.confidence

    delta = now - memory.updated_at.replace(tzinfo=UTC)
    days = delta.total_seconds() / 86_400
    decayed = memory.confidence - decay_rate * days
    return max(0.0, decayed)
