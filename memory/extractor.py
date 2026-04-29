"""memory.extractor — Extrai e salva memórias a partir de resultados de agente."""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime

from memory.store import MemoryStore
from memory.types import Memory, MemoryType

logger = logging.getLogger("data_agents.memory.extractor")


def extract_and_save(
    task: str,
    result_content: str,
    store: MemoryStore,
) -> list[Memory]:
    """
    Analisa o resultado de um agente e salva memórias relevantes.

    Detecta:
    - Decisões arquiteturais (palavras-chave: decidimos, escolhemos, padrão)
    - Feedback do usuário (palavras-chave: prefiro, correto, errado, não faça)
    - Progresso de tarefas (palavras-chave: criado, implementado, concluído)
    """
    saved: list[Memory] = []

    # Decisões arquiteturais
    arch_patterns = re.compile(
        r"\b(decid|escolh|padrão adotado|definimos usar|arquitetura|"
        r"abordagem escolhida)\b",
        re.IGNORECASE,
    )
    if arch_patterns.search(result_content):
        mem = Memory(
            id=_make_id(task, MemoryType.ARCHITECTURE),
            type=MemoryType.ARCHITECTURE,
            summary=task[:120],
            content=result_content[:800],
            confidence=1.0,
            tags=_extract_tags(task + " " + result_content),
        )
        store.save(mem)
        saved.append(mem)
        logger.debug("Memória ARCHITECTURE salva: %s", mem.id)

    # Progresso
    progress_patterns = re.compile(
        r"\b(criado|implementado|concluído|finalizado|gerado|"
        r"pipeline criado|tabela criada)\b",
        re.IGNORECASE,
    )
    if progress_patterns.search(result_content):
        mem = Memory(
            id=_make_id(task, MemoryType.PROGRESS),
            type=MemoryType.PROGRESS,
            summary=f"Tarefa concluída: {task[:100]}",
            content=result_content[:600],
            confidence=1.0,
            tags=_extract_tags(task),
        )
        store.save(mem)
        saved.append(mem)
        logger.debug("Memória PROGRESS salva: %s", mem.id)

    return saved


def save_user_preference(
    preference: str,
    store: MemoryStore,
    tags: list[str] | None = None,
) -> Memory:
    """Salva uma preferência explícita do usuário."""
    mem = Memory(
        id=_make_id(preference, MemoryType.USER),
        type=MemoryType.USER,
        summary=preference[:120],
        content=preference,
        confidence=1.0,
        tags=tags or [],
    )
    store.save(mem)
    logger.info("Preferência salva: %s", mem.summary)
    return mem


def _make_id(text: str, mem_type: MemoryType) -> str:
    h = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()[:8]  # noqa: S324
    ts = datetime.now(UTC).strftime("%Y%m%d")
    return f"{mem_type.value}-{ts}-{h}"


def _extract_tags(text: str) -> list[str]:
    """Extrai tags simples baseado em domínios conhecidos."""
    domain_keywords = {
        "spark": ["spark", "pyspark", "dataframe", "delta", "streaming"],
        "sql": ["sql", "query", "select", "cte", "window"],
        "pipeline": ["pipeline", "bronze", "silver", "gold", "ingestão", "etl", "elt"],
        "quality": ["qualidade", "expectation", "validação", "null", "schema"],
        "governance": ["governança", "pii", "lgpd", "gdpr", "acesso", "naming"],
        "databricks": ["databricks", "unity catalog", "cluster", "job"],
        "fabric": ["fabric", "lakehouse", "warehouse", "onelake"],
    }
    text_lower = text.lower()
    tags = []
    for domain, keywords in domain_keywords.items():
        if any(kw in text_lower for kw in keywords):
            tags.append(domain)
    return tags
