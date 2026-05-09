"""
Memory Retrieval — Busca de memórias relevantes via LongTermMemory (SQLite FTS5).

Custo: ~0 (sem chamada LLM). Latência: < 5ms para qualquer volume viável.

Fluxo:
  1. LongTermMemory.search(query) → BM25 + cosine rerank opcional
  2. Retorna Memory objects com conteúdo completo diretamente
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from memory.store import MemoryStore
from memory.telemetry import record as _telemetry
from memory.types import Memory, MemoryType
from config.settings import settings

if TYPE_CHECKING:
    from memory.long_term import LongTermMemory

logger = logging.getLogger("data_agents.memory.retrieval")


def retrieve_relevant_memories(
    query: str,
    store: MemoryStore,
    max_memories: int | None = None,
    include_types: list[MemoryType] | None = None,
    long_term: LongTermMemory | None = None,
) -> list[Memory]:
    """
    Busca memórias relevantes via LongTermMemory (SQLite FTS5).

    Se `long_term` não for fornecido, cria uma instância lazy e sincroniza
    com o store antes de buscar.

    Args:
        query: A query/tarefa atual do usuário.
        store: MemoryStore com as memórias persistidas.
        max_memories: Máximo de memórias a retornar.
        include_types: Se fornecido, filtra por tipos. None = todos.
        long_term: Índice LongTermMemory (opcional — criado lazily se None).

    Returns:
        Lista de Memory objects relevantes, com conteúdo completo.
    """
    if max_memories is None:
        max_memories = settings.memory_retrieval_max

    t0 = time.time()

    lt = long_term
    if lt is None:
        try:
            from memory.long_term import LongTermMemory as _LTM
            from pathlib import Path

            lt = _LTM(db_path=Path(settings.long_term_db_path))
            synced = lt.migrate_from_store(store)
            if synced == 0:
                logger.debug("retrieve: store vazio — sem memórias para indexar.")
                return []
        except Exception as e:
            logger.warning(f"retrieve: falha ao criar LongTermMemory ({e}) — sem retrieval.")
            return []

    try:
        memories = lt.search(
            query=query,
            limit=max_memories,
            include_types=include_types,
        )
    except Exception as e:
        logger.warning(f"retrieve: LongTermMemory.search falhou ({e}).")
        return []

    logger.info(f"Retrieval (FTS5): query='{query[:60]}' → {len(memories)} memórias")
    _telemetry(
        "retrieval.query",
        reason="ok",
        selected=len(memories),
        loaded=len(memories),
        cost_usd=0.0,
        duration_ms=int((time.time() - t0) * 1000),
    )
    return memories


def format_memories_for_injection(memories: list[Memory]) -> str:
    """
    Formata memórias recuperadas para injeção no prompt do supervisor.

    Formato otimizado para contexto: compacto mas informativo.
    """
    if not memories:
        return ""

    sections: list[str] = [
        "\n\n---\n\n"
        "## [Contexto Injetado] Memórias Relevantes da Sessão\n\n"
        "As memórias abaixo foram recuperadas automaticamente como contexto "
        "relevante para a tarefa atual. Use-as para informar suas decisões.\n"
    ]

    by_type: dict[MemoryType, list[Memory]] = {}
    for mem in memories:
        by_type.setdefault(mem.type, []).append(mem)

    type_labels = {
        MemoryType.USER: "Preferências do Usuário",
        MemoryType.FEEDBACK: "Feedback & Correções",
        MemoryType.ARCHITECTURE: "Decisões Arquiteturais",
        MemoryType.PROGRESS: "Progresso & Contexto",
        MemoryType.DATA_ASSET: "Assets de Dados",
        MemoryType.PLATFORM_DECISION: "Decisões de Plataforma",
        MemoryType.PIPELINE_STATUS: "Status de Pipelines",
        MemoryType.LESSON_LEARNED: "Lições Aprendidas",
    }

    for mt, mems in by_type.items():
        label = type_labels.get(mt, mt.value.replace("_", " ").title())
        # Lessons aprendidas recebem destaque para garantir que os agentes as leiam
        if mt == MemoryType.LESSON_LEARNED:
            sections.append(f"\n### ⚠️ {label} — leia antes de executar operações de risco\n")
        else:
            sections.append(f"\n### {label}\n")
        for mem in mems:
            conf = f" (confidence: {mem.confidence:.2f})" if mem.confidence < 1.0 else ""
            sections.append(f"**[{mem.id}]** {mem.summary}{conf}\n")
            content = mem.content[:500]
            if len(mem.content) > 500:
                content += "...\n*(conteúdo truncado — leia o arquivo completo se necessário)*"
            sections.append(f"{content}\n")

    return "\n".join(sections)
