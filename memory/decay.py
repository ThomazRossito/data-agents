"""
Confidence Decay — Obsolescência automática de memórias.

Cada tipo de memória tem uma taxa de decay diferente:
  - USER: nunca decai (confidence permanece 1.0)
  - FEEDBACK: decay lento (90 dias para chegar a 0.1)
  - ARCHITECTURE: nunca decai (confidence permanece 1.0)
  - PROGRESS: decay rápido (7 dias para chegar a 0.1)

A função de decay é exponencial:
  confidence = initial * exp(-λ * days_elapsed)
  onde λ = -ln(target) / half_life_days

Memórias abaixo do threshold (0.1) são marcadas como inativas
e excluídas do retrieval (mas não deletadas — preserva histórico).
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from datetime import datetime, timezone

from memory.types import Memory, DECAY_CONFIG

logger = logging.getLogger("data_agents.memory.decay")


def _compute_decay_rate(days_to_threshold: float, threshold: float = 0.1) -> float:
    """
    Calcula a taxa de decay (λ) para que confidence atinja threshold em N dias.

    λ = -ln(threshold) / days_to_threshold
    """
    if days_to_threshold <= 0:
        return 0.0
    return -math.log(threshold) / days_to_threshold


def compute_decayed_confidence(
    memory: Memory,
    now: datetime | None = None,
) -> float:
    """
    Calcula a confidence atual de uma memória após aplicar o decay.

    Args:
        memory: Memória para calcular o decay.
        now: Timestamp atual (UTC). Default: agora.

    Returns:
        Novo valor de confidence (0.0 a 1.0).
    """
    decay_days = DECAY_CONFIG.get(memory.type)

    # Tipos sem decay mantêm confidence original
    if decay_days is None:
        return memory.confidence

    now = now or datetime.now(timezone.utc)
    elapsed = (now - memory.created_at).total_seconds() / 86400  # dias

    if elapsed <= 0:
        return memory.confidence

    rate = _compute_decay_rate(decay_days)
    decayed = memory.confidence * math.exp(-rate * elapsed)

    return max(0.0, min(1.0, decayed))


def apply_decay(
    memories: list[Memory],
    now: datetime | None = None,
    save_fn: Callable[[Memory], object] | None = None,
) -> tuple[list[Memory], list[Memory]]:
    """
    Aplica decay a uma lista de memórias e retorna as ativas e expiradas.

    Args:
        memories: Lista de memórias para processar.
        now: Timestamp atual (UTC). Default: agora.
        save_fn: Função opcional para persistir memórias atualizadas.
            Assinatura: save_fn(memory: Memory) -> None

    Returns:
        Tupla (ativas, expiradas) — memórias atualizadas.
    """
    now = now or datetime.now(timezone.utc)
    active: list[Memory] = []
    expired: list[Memory] = []

    for mem in memories:
        new_confidence = compute_decayed_confidence(mem, now)

        # Só atualiza se mudou significativamente (evita rewrites desnecessários)
        if abs(new_confidence - mem.confidence) > 0.01:
            mem.confidence = round(new_confidence, 3)
            mem.updated_at = now
            if save_fn:
                try:
                    save_fn(mem)
                except Exception as e:
                    logger.warning(f"Erro ao salvar decay de {mem.id}: {e}")

        if mem.is_active():
            active.append(mem)
        else:
            expired.append(mem)

    if expired:
        logger.info(
            f"Decay aplicado: {len(active)} ativas, {len(expired)} expiradas "
            f"(tipos: {[m.type.value for m in expired]})"
        )

    return active, expired
