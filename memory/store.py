"""memory.store — CRUD de memórias em arquivos Markdown."""
from __future__ import annotations

import logging
import os
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from memory.types import DECAY_CONFIG, Memory, MemoryType

logger = logging.getLogger("data_agents.memory.store")

_DEFAULT_DATA_DIR = Path(__file__).parent / "data"


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


class MemoryStore:
    """Gerencia persistência de memórias em arquivos Markdown."""

    def __init__(self, data_dir: Path | str | None = None) -> None:
        self.data_dir = (
            Path(data_dir) if data_dir is not None else _DEFAULT_DATA_DIR
        )
        self._lock = threading.Lock()
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        for mem_type in MemoryType:
            (self.data_dir / mem_type.value).mkdir(parents=True, exist_ok=True)
        (self.data_dir / "daily").mkdir(parents=True, exist_ok=True)

    def _memory_path(self, memory: Memory) -> Path:
        return self.data_dir / memory.type.value / f"{memory.id}.md"

    # ── CRUD ────────────────────────────────────────────────────

    def save(self, memory: Memory) -> Path:
        memory.updated_at = datetime.now(UTC)
        path = self._memory_path(memory)
        with self._lock:
            _atomic_write(path, memory.to_markdown())
        logger.debug("Memória salva: %s (%s)", memory.id, memory.type.value)
        return path

    def load(self, memory_id: str, memory_type: MemoryType) -> Memory | None:
        path = self.data_dir / memory_type.value / f"{memory_id}.md"
        if not path.exists():
            return None
        return self._parse_memory_file(path)

    def delete(self, memory_id: str, memory_type: MemoryType) -> bool:
        path = self.data_dir / memory_type.value / f"{memory_id}.md"
        if path.exists():
            os.remove(path)
            return True
        return False

    def list_all(
        self,
        memory_type: MemoryType | None = None,
        active_only: bool = True,
        min_confidence: float = 0.1,
    ) -> list[Memory]:
        memories: list[Memory] = []
        types = [memory_type] if memory_type else list(MemoryType)
        for mt in types:
            type_dir = self.data_dir / mt.value
            if not type_dir.exists():
                continue
            for path in sorted(type_dir.glob("*.md")):
                mem = self._parse_memory_file(path)
                if mem is None:
                    continue
                if active_only and not mem.is_active(min_confidence):
                    continue
                memories.append(mem)
        return memories

    def list_by_tags(
        self, tags: list[str], match_all: bool = False
    ) -> list[Memory]:
        all_memories = self.list_all(active_only=True)
        search_tags = set(tags)
        results = []
        for mem in all_memories:
            mem_tags = set(mem.tags)
            if match_all and search_tags.issubset(mem_tags):
                results.append(mem)
            elif not match_all and search_tags & mem_tags:
                results.append(mem)
        return results

    def get_stale_memories(
        self,
        threshold: float = 0.1,
        memory_type: MemoryType | None = None,
    ) -> list[Memory]:
        from memory.decay import compute_decayed_confidence

        now = datetime.now(UTC)
        all_memories = self.list_all(
            memory_type=memory_type,
            active_only=False,
            min_confidence=0.0,
        )
        stale = []
        for mem in all_memories:
            if mem.superseded_by is not None:
                continue
            if DECAY_CONFIG.get(mem.type) is None:
                continue
            if compute_decayed_confidence(mem, now) < threshold:
                stale.append(mem)
        return stale

    def build_index(self) -> str:
        lines: list[str] = [
            "# Memory Index",
            "",
            "*Gerado em: "
            + datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
            + "*",
            "",
        ]
        for mt in MemoryType:
            memories = self.list_all(memory_type=mt, active_only=True)
            if not memories:
                continue
            lines.append(f"## {mt.value.upper()} ({len(memories)})")
            lines.append("")
            for mem in sorted(
                memories, key=lambda m: m.confidence, reverse=True
            ):
                tags_str = f" [{', '.join(mem.tags)}]" if mem.tags else ""
                conf_str = (
                    f" (conf={mem.confidence:.2f})"
                    if mem.confidence < 1.0
                    else ""
                )
                lines.append(
                    f"- **{mem.id}**: {mem.summary}{tags_str}{conf_str}"
                )
            lines.append("")

        index_content = "\n".join(lines)
        index_path = self.data_dir / "index.md"
        with self._lock:
            _atomic_write(index_path, index_content)
        return index_content

    def append_daily_log(
        self, content: str, date: datetime | None = None
    ) -> Path:
        dt = date or datetime.now(UTC)
        date_str = dt.strftime("%Y-%m-%d")
        path = self.data_dir / "daily" / f"{date_str}.md"
        header = f"# Daily Log — {date_str}\n\n" if not path.exists() else ""
        with self._lock:
            if path.exists():
                existing = path.read_text(encoding="utf-8")
                if "<!-- COMPILED" in existing:
                    existing = re.sub(
                        r"\s*<!--\s*COMPILED[^>]*-->\s*$", "", existing
                    )
                    _atomic_write(path, existing)
            with open(path, "a", encoding="utf-8") as f:
                if header:
                    f.write(header)
                f.write(f"\n---\n\n{content}\n")
        return path

    # ── Internal ────────────────────────────────────────────────

    def _parse_memory_file(self, path: Path) -> Memory | None:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            metadata, body = _parse_yaml_frontmatter(content)
        except ValueError:
            return None
        metadata["content"] = body
        try:
            return Memory.from_dict(metadata)
        except (KeyError, ValueError):
            return None

    def get_stats(self) -> dict[str, Any]:
        stats: dict[str, Any] = {
            "total": 0,
            "by_type": {},
            "active": 0,
            "superseded": 0,
        }
        for mt in MemoryType:
            all_of_type = self.list_all(memory_type=mt, active_only=False)
            active = [m for m in all_of_type if m.is_active()]
            stats["by_type"][mt.value] = {
                "total": len(all_of_type),
                "active": len(active),
            }
            stats["total"] += len(all_of_type)
            stats["active"] += len(active)
            stats["superseded"] += len(all_of_type) - len(active)
        return stats


def _parse_yaml_frontmatter(content: str) -> tuple[dict, str]:
    """Parse de frontmatter YAML delimitado por ---."""
    if not content.startswith("---"):
        raise ValueError("Sem frontmatter")
    end = content.find("\n---", 3)
    if end == -1:
        raise ValueError("Frontmatter não fechado")
    fm_block = content[3:end].strip()
    body = content[end + 4:].strip()
    metadata: dict = {}
    for line in fm_block.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            metadata[key.strip()] = val.strip()
    return metadata, body
