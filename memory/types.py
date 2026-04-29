"""memory.types — Tipos e estruturas de memória persistente."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class MemoryType(StrEnum):
    USER = "user"
    FEEDBACK = "feedback"
    ARCHITECTURE = "architecture"
    PROGRESS = "progress"


# Tipos que decaem com o tempo (perdem relevância)
DECAY_CONFIG: dict[MemoryType, float] = {
    MemoryType.FEEDBACK: 0.05,    # decai 5% por dia
    MemoryType.PROGRESS: 0.10,    # decai 10% por dia
}


@dataclass
class Memory:
    id: str
    type: MemoryType
    summary: str
    content: str
    confidence: float = 1.0
    tags: list[str] = field(default_factory=list)
    related_ids: list[str] = field(default_factory=list)
    superseded_by: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_active(self, min_confidence: float = 0.1) -> bool:
        return self.superseded_by is None and self.confidence >= min_confidence

    def to_markdown(self) -> str:
        tags_str = ", ".join(self.tags) if self.tags else ""
        related_str = ", ".join(self.related_ids) if self.related_ids else ""
        lines = [
            "---",
            f"id: {self.id}",
            f"type: {self.type.value}",
            f"summary: {self.summary}",
            f"confidence: {self.confidence}",
            f"tags: [{tags_str}]",
            f"related_ids: [{related_str}]",
            f"superseded_by: {self.superseded_by or ''}",
            f"created_at: {self.created_at.isoformat()}",
            f"updated_at: {self.updated_at.isoformat()}",
            "---",
            "",
            self.content,
        ]
        return "\n".join(lines)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        def parse_list(val: Any) -> list[str]:
            if isinstance(val, list):
                return [str(x) for x in val if x]
            if isinstance(val, str):
                val = val.strip("[]")
                return [x.strip() for x in val.split(",") if x.strip()]
            return []

        def parse_dt(val: Any) -> datetime:
            if isinstance(val, datetime):
                return val
            try:
                return datetime.fromisoformat(str(val))
            except (ValueError, TypeError):
                return datetime.now(UTC)

        return cls(
            id=str(data.get("id", "")),
            type=MemoryType(data.get("type", "user")),
            summary=str(data.get("summary", "")),
            content=str(data.get("content", "")),
            confidence=float(data.get("confidence", 1.0)),
            tags=parse_list(data.get("tags", [])),
            related_ids=parse_list(data.get("related_ids", [])),
            superseded_by=data.get("superseded_by") or None,
            created_at=parse_dt(data.get("created_at")),
            updated_at=parse_dt(data.get("updated_at")),
        )
