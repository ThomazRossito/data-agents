"""
Memory Telemetry — instrumentação leve para medir uso real do subsistema de memória.

Grava eventos estruturados em logs/memory_usage.jsonl (uma linha por evento) e mantém
contadores em memória agregados por sessão. Usado para responder: "a memória paga o custo?"

Eventos registrados:
  - store.save / store.load / store.delete
  - store.list_all / store.build_index / store.append_daily_log
  - retrieval.query  (hits, misses, duração, custo estimado)
  - compiler.contradiction_check (custo Sonnet estimado, resultado)

Decisão de Sprint 0 (T0.5): estes dados alimentam T1.7 — decidir entre
remover memory/ (Caminho A) ou fazer enxugamento cirúrgico (Caminho B).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("data_agents.memory.telemetry")

_LOG_PATH = Path(__file__).parent.parent / "logs" / "memory_usage.jsonl"
_LOCK = threading.Lock()

_counters: dict[str, int] = defaultdict(int)
_cost_usd: float = 0.0


def record(event: str, **fields: Any) -> None:
    """
    Registra um evento de telemetria.

    Append-only em logs/memory_usage.jsonl. Incrementa contador em memória.
    Cost fields (cost_usd) são acumulados no total da sessão.
    """
    global _cost_usd

    entry: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }

    _counters[event] += 1
    if "cost_usd" in fields:
        try:
            _cost_usd += float(fields["cost_usd"])
        except (TypeError, ValueError):
            pass

    try:
        with _LOCK:
            os.makedirs(_LOG_PATH.parent, exist_ok=True)
            with open(_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.debug(f"Falha ao gravar telemetria ({event}): {e}")


def snapshot() -> dict[str, Any]:
    """Retorna o snapshot dos contadores acumulados na sessão atual."""
    return {
        "counters": dict(_counters),
        "cost_usd_session": round(_cost_usd, 6),
    }
