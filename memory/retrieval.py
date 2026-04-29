"""memory.retrieval — Busca de memórias relevantes."""
from __future__ import annotations

import logging
import re

from memory.store import MemoryStore
from memory.types import Memory, MemoryType

logger = logging.getLogger("data_agents.memory.retrieval")

_MAX_MEMORIES = 8


def retrieve_relevant_memories(
    query: str,
    store: MemoryStore,
    max_memories: int = _MAX_MEMORIES,
    include_types: list[MemoryType] | None = None,
) -> list[Memory]:
    """
    Busca memórias relevantes usando keyword matching no index.

    Estratégia local (sem chamada LLM extra): extrai tokens da query e
    cruza com summary + tags de cada memória ativa.
    """
    index_path = store.data_dir / "index.md"
    if not index_path.exists():
        store.build_index()

    all_memories = store.list_all(
        memory_type=None,
        active_only=True,
    )

    if include_types:
        all_memories = [m for m in all_memories if m.type in include_types]

    if not all_memories:
        return []

    # Extrai tokens relevantes da query (ignora stop words de 1-2 chars)
    tokens = {
        t.lower()
        for t in re.findall(r"\b\w{3,}\b", query)
    }

    scored: list[tuple[float, Memory]] = []
    for mem in all_memories:
        searchable = (mem.summary + " " + " ".join(mem.tags)).lower()
        hits = sum(1 for t in tokens if t in searchable)
        if hits > 0:
            scored.append((hits / max(len(tokens), 1), mem))

    scored.sort(key=lambda x: -x[0])
    selected = [m for _, m in scored[:max_memories]]

    logger.debug(
        "Retrieval: query='%s' → %d candidatas, %d selecionadas",
        query[:60],
        len(scored),
        len(selected),
    )
    return selected


def format_memories_for_injection(memories: list[Memory]) -> str:
    """Formata memórias para injeção no prompt do supervisor."""
    if not memories:
        return ""

    type_labels = {
        MemoryType.USER: "Preferências do Usuário",
        MemoryType.FEEDBACK: "Feedback & Correções",
        MemoryType.ARCHITECTURE: "Decisões Arquiteturais",
        MemoryType.PROGRESS: "Progresso & Contexto",
    }

    sections: list[str] = [
        "\n\n---\n\n"
        "## [Contexto] Memórias Relevantes\n\n"
        "Recuperadas automaticamente como contexto para a tarefa atual.\n"
    ]

    by_type: dict[MemoryType, list[Memory]] = {}
    for mem in memories:
        by_type.setdefault(mem.type, []).append(mem)

    for mt, mems in by_type.items():
        sections.append(f"\n### {type_labels.get(mt, mt.value)}\n")
        for mem in mems:
            conf = (
                f" (confidence: {mem.confidence:.2f})"
                if mem.confidence < 1.0
                else ""
            )
            sections.append(f"**[{mem.id}]** {mem.summary}{conf}\n")
            content = mem.content[:500]
            if len(mem.content) > 500:
                content += "...\n*(truncado)*"
            sections.append(f"{content}\n")

    return "\n".join(sections)
