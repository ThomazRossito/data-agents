"""
Memory Types — Definição dos tipos de memória e dataclass Memory.

Taxonomia fechada com 4 tipos, cada um com regras de decay diferentes:
  - USER: nunca decai (confidence fixa em 1.0)
  - FEEDBACK: decay lento (90 dias para chegar a 0.1)
  - ARCHITECTURE: nunca decai (confidence fixa em 1.0)
  - PROGRESS: decay rápido (7 dias para chegar a 0.1)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MemoryType(str, Enum):
    """
    Tipos de memória com taxonomia fechada.

    A taxonomia fechada (closed taxonomy) supera tagging aberto porque:
    1. Cada tipo tem regras de decay bem definidas
    2. O retrieval pode filtrar por tipo antes da busca semântica
    3. Evita proliferação de categorias ambíguas
    """

    USER = "user"
    """Preferências do usuário, papel, expertise, estilo de comunicação."""

    FEEDBACK = "feedback"
    """Correções e orientações dadas pelo usuário ao sistema."""

    ARCHITECTURE = "architecture"
    """Decisões arquiteturais, padrões, gotchas, regras de negócio descobertas."""

    PROGRESS = "progress"
    """Estado atual de tarefas, contexto de sessão, progresso de workflows."""


# Configuração de decay por tipo (em dias para atingir confidence 0.1)
DECAY_CONFIG: dict[MemoryType, float | None] = {
    MemoryType.USER: None,  # Nunca decai
    MemoryType.FEEDBACK: 90.0,  # 90 dias
    MemoryType.ARCHITECTURE: None,  # Nunca decai
    MemoryType.PROGRESS: 7.0,  # 7 dias
}


@dataclass
class Memory:
    """
    Uma unidade de memória persistente.

    Cada memória é armazenada como um arquivo Markdown individual com
    frontmatter YAML contendo metadados.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    """Identificador único da memória (12 chars hex)."""

    type: MemoryType = MemoryType.PROGRESS
    """Tipo da memória (determina regras de decay)."""

    content: str = ""
    """Conteúdo principal da memória em texto livre."""

    summary: str = ""
    """Resumo de uma linha para o index.md (usado pelo retrieval)."""

    tags: list[str] = field(default_factory=list)
    """Tags para filtragem rápida (ex: ['databricks', 'pipeline', 'bronze'])."""

    confidence: float = 1.0
    """Score de confiança (0.0 a 1.0). Decai conforme o tipo."""

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    """Timestamp de criação (UTC)."""

    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    """Timestamp da última atualização (UTC)."""

    source_session: str = ""
    """ID ou label da sessão que originou esta memória."""

    related_ids: list[str] = field(default_factory=list)
    """IDs de memórias relacionadas (cross-references)."""

    superseded_by: str | None = None
    """Se esta memória foi substituída, ID da memória substituta."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Metadados adicionais livres."""

    def is_active(self, threshold: float = 0.1) -> bool:
        """Retorna True se a memória ainda está ativa (confidence acima do threshold)."""
        return self.confidence >= threshold and self.superseded_by is None

    def to_frontmatter(self) -> str:
        """Serializa para frontmatter YAML (para salvar em arquivo .md)."""
        lines = [
            "---",
            f'id: "{self.id}"',
            f"type: {self.type.value}",
            f'summary: "{self.summary}"',
            f"tags: [{', '.join(self.tags)}]",
            f"confidence: {self.confidence:.3f}",
            f"created_at: {self.created_at.isoformat()}",
            f"updated_at: {self.updated_at.isoformat()}",
            f'source_session: "{self.source_session}"',
        ]
        if self.related_ids:
            lines.append(f"related_ids: [{', '.join(self.related_ids)}]")
        if self.superseded_by:
            lines.append(f'superseded_by: "{self.superseded_by}"')
        lines.append("---")
        return "\n".join(lines)

    def to_markdown(self) -> str:
        """Serializa completo para Markdown (frontmatter + conteúdo)."""
        return f"{self.to_frontmatter()}\n\n{self.content}"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        """Cria uma Memory a partir de um dicionário (parse de frontmatter)."""
        mem_type = data.get("type", "progress")
        if isinstance(mem_type, str):
            mem_type = MemoryType(mem_type)

        created = data.get("created_at", "")
        updated = data.get("updated_at", "")

        return cls(
            id=data.get("id", uuid.uuid4().hex[:12]),
            type=mem_type,
            content=data.get("content", ""),
            summary=data.get("summary", ""),
            tags=data.get("tags", []),
            confidence=float(data.get("confidence", 1.0)),
            created_at=datetime.fromisoformat(created) if created else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(updated) if updated else datetime.now(timezone.utc),
            source_session=data.get("source_session", ""),
            related_ids=data.get("related_ids", []),
            superseded_by=data.get("superseded_by"),
            metadata=data.get("metadata", {}),
        )
