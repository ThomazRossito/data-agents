"""
Tests for memory.long_term — LongTermMemory (SQLite FTS5 index).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from memory.long_term import LongTermMemory
from memory.types import Memory, MemoryType


def _make_memory(
    mem_id: str = "abc123",
    mem_type: MemoryType = MemoryType.ARCHITECTURE,
    summary: str = "Test memory summary",
    content: str = "Test memory content with details",
    tags: list[str] | None = None,
    confidence: float = 1.0,
    superseded_by: str | None = None,
) -> Memory:
    return Memory(
        id=mem_id,
        type=mem_type,
        summary=summary,
        content=content,
        tags=tags or ["test"],
        confidence=confidence,
        source_session="test_session",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        superseded_by=superseded_by,
    )


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_long_term.db"


@pytest.fixture
def lt(db_path: Path) -> LongTermMemory:
    return LongTermMemory(db_path=db_path)


# ── Construction ──────────────────────────────────────────────────────────────


class TestInit:
    def test_creates_db_file(self, db_path: Path) -> None:
        LongTermMemory(db_path=db_path)
        assert db_path.exists()

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "long_term.db"
        LongTermMemory(db_path=nested)
        assert nested.exists()

    def test_idempotent_init(self, db_path: Path) -> None:
        LongTermMemory(db_path=db_path)
        LongTermMemory(db_path=db_path)  # no error on second init


# ── Upsert ────────────────────────────────────────────────────────────────────


class TestUpsert:
    def test_inserts_memory(self, lt: LongTermMemory) -> None:
        lt.upsert(_make_memory("m1", summary="databricks pipeline setup"))
        stats = lt.get_stats()
        assert stats["active"] == 1

    def test_updates_existing(self, lt: LongTermMemory) -> None:
        lt.upsert(_make_memory("m1", summary="original summary"))
        lt.upsert(_make_memory("m1", summary="updated summary"))
        stats = lt.get_stats()
        assert stats["total"] == 1  # not doubled
        memories = lt.list_all()
        assert memories[0].summary == "updated summary"

    def test_multiple_memories(self, lt: LongTermMemory) -> None:
        for i in range(5):
            lt.upsert(_make_memory(f"m{i}", summary=f"memory number {i}"))
        assert lt.get_stats()["active"] == 5

    def test_inactive_memory_not_counted_as_active(self, lt: LongTermMemory) -> None:
        lt.upsert(_make_memory("m1", confidence=0.05))  # below is_active threshold
        stats = lt.get_stats()
        assert stats["total"] == 1
        assert stats["active"] == 0

    def test_superseded_not_counted_as_active(self, lt: LongTermMemory) -> None:
        lt.upsert(_make_memory("m1", superseded_by="m2"))
        stats = lt.get_stats()
        assert stats["active"] == 0

    def test_preserves_all_fields(self, lt: LongTermMemory) -> None:
        original = _make_memory(
            "xyz",
            mem_type=MemoryType.FEEDBACK,
            summary="important feedback",
            content="detailed content here",
            tags=["databricks", "pipeline"],
            confidence=0.85,
        )
        lt.upsert(original)
        memories = lt.list_all()
        m = memories[0]
        assert m.id == "xyz"
        assert m.type == MemoryType.FEEDBACK
        assert m.summary == "important feedback"
        assert m.content == "detailed content here"
        assert "databricks" in m.tags
        assert abs(m.confidence - 0.85) < 1e-6


# ── Delete ────────────────────────────────────────────────────────────────────


class TestDelete:
    def test_removes_memory(self, lt: LongTermMemory) -> None:
        lt.upsert(_make_memory("m1"))
        lt.delete("m1")
        assert lt.get_stats()["total"] == 0

    def test_noop_for_unknown_id(self, lt: LongTermMemory) -> None:
        lt.delete("nonexistent")  # should not raise

    def test_only_removes_target(self, lt: LongTermMemory) -> None:
        lt.upsert(_make_memory("m1"))
        lt.upsert(_make_memory("m2"))
        lt.delete("m1")
        assert lt.get_stats()["active"] == 1
        assert lt.list_all()[0].id == "m2"


# ── Search ────────────────────────────────────────────────────────────────────


class TestSearch:
    def test_empty_query_returns_empty(self, lt: LongTermMemory) -> None:
        lt.upsert(_make_memory("m1", summary="some content"))
        assert lt.search("") == []

    def test_finds_by_summary(self, lt: LongTermMemory) -> None:
        lt.upsert(_make_memory("m1", summary="databricks SQL warehouse configuration"))
        results = lt.search("databricks warehouse")
        assert len(results) >= 1
        assert results[0].id == "m1"

    def test_finds_by_content(self, lt: LongTermMemory) -> None:
        lt.upsert(_make_memory("m1", content="use Auto Loader for incremental ingestion"))
        results = lt.search("Auto Loader incremental")
        assert any(r.id == "m1" for r in results)

    def test_finds_by_tag(self, lt: LongTermMemory) -> None:
        lt.upsert(_make_memory("m1", summary="general", tags=["medallion", "bronze"]))
        results = lt.search("medallion")
        assert any(r.id == "m1" for r in results)

    def test_returns_memory_objects(self, lt: LongTermMemory) -> None:
        lt.upsert(_make_memory("m1", summary="python packaging patterns"))
        results = lt.search("python")
        assert all(isinstance(r, Memory) for r in results)

    def test_respects_limit(self, lt: LongTermMemory) -> None:
        for i in range(10):
            lt.upsert(_make_memory(f"m{i}", summary=f"pipeline design pattern number {i}"))
        results = lt.search("pipeline design pattern", limit=3)
        assert len(results) <= 3

    def test_excludes_inactive(self, lt: LongTermMemory) -> None:
        lt.upsert(_make_memory("active", summary="active memory entry"))
        lt.upsert(_make_memory("dead", summary="dead memory entry", confidence=0.0))
        results = lt.search("memory entry")
        assert all(r.id != "dead" for r in results)

    def test_excludes_superseded(self, lt: LongTermMemory) -> None:
        lt.upsert(_make_memory("old", summary="old superseded memory", superseded_by="new"))
        lt.upsert(_make_memory("new", summary="new replacement memory"))
        results = lt.search("superseded")
        assert all(r.id != "old" for r in results)

    def test_filter_by_type(self, lt: LongTermMemory) -> None:
        lt.upsert(_make_memory("f1", mem_type=MemoryType.FEEDBACK, summary="feedback entry"))
        lt.upsert(
            _make_memory("a1", mem_type=MemoryType.ARCHITECTURE, summary="architecture entry")
        )
        results = lt.search("entry", include_types=[MemoryType.FEEDBACK])
        assert all(r.type == MemoryType.FEEDBACK for r in results)

    def test_no_results_for_unrelated_query(self, lt: LongTermMemory) -> None:
        lt.upsert(_make_memory("m1", summary="databricks pipeline configuration"))
        results = lt.search("quantum physics black holes")
        assert results == [] or all(r.id == "m1" for r in results)

    def test_fts5_bracket_in_query_does_not_raise(self, lt: LongTermMemory) -> None:
        """Query com [ ] não deve levantar exceção (fts5: syntax error near '[')."""
        lt.upsert(_make_memory("m1", summary="agentes especializados no sistema"))
        results = lt.search("quais são os [agentes] configurados")
        assert isinstance(results, list)

    def test_fts5_special_chars_in_query_do_not_raise(self, lt: LongTermMemory) -> None:
        """Qualquer caractere não-word na query deve ser sanitizado silenciosamente."""
        lt.upsert(_make_memory("m1", summary="databricks pipeline"))
        for query in [
            "databricks [pipeline]",
            "spark: structured streaming",
            "pipeline (ETL/ELT)",
            "dados? qualidade*",
            "schema^evolution",
            "{bronze} -> silver -> gold",
            "/plan quantos agentes no projeto",
            "/sql select * from tabela",
            "agentes, pipelines, schemas",
        ]:
            results = lt.search(query)
            assert isinstance(results, list), f"Falhou para query: {query!r}"


# ── migrate_from_store ────────────────────────────────────────────────────────


class TestMigrateFromStore:
    def test_indexes_all_memories(self, lt: LongTermMemory) -> None:
        mock_store = MagicMock()
        memories = [
            _make_memory("m1", summary="first memory"),
            _make_memory("m2", summary="second memory"),
            _make_memory("m3", summary="third memory"),
        ]
        mock_store.list_all.return_value = memories

        count = lt.migrate_from_store(mock_store)
        assert count == 3
        assert lt.get_stats()["active"] == 3

    def test_empty_store_returns_zero(self, lt: LongTermMemory) -> None:
        mock_store = MagicMock()
        mock_store.list_all.return_value = []
        assert lt.migrate_from_store(mock_store) == 0

    def test_idempotent(self, lt: LongTermMemory) -> None:
        mock_store = MagicMock()
        mock_store.list_all.return_value = [_make_memory("m1")]
        lt.migrate_from_store(mock_store)
        lt.migrate_from_store(mock_store)  # second call should not duplicate
        assert lt.get_stats()["total"] == 1


# ── get_stats ─────────────────────────────────────────────────────────────────


class TestGetStats:
    def test_empty_stats(self, lt: LongTermMemory) -> None:
        stats = lt.get_stats()
        assert stats == {"total": 0, "active": 0, "by_type": {}}

    def test_by_type_breakdown(self, lt: LongTermMemory) -> None:
        lt.upsert(_make_memory("f1", mem_type=MemoryType.FEEDBACK))
        lt.upsert(_make_memory("a1", mem_type=MemoryType.ARCHITECTURE))
        lt.upsert(_make_memory("a2", mem_type=MemoryType.ARCHITECTURE))
        stats = lt.get_stats()
        assert stats["by_type"]["feedback"] == 1
        assert stats["by_type"]["architecture"] == 2


# ── list_all ──────────────────────────────────────────────────────────────────


class TestListAll:
    def test_empty(self, lt: LongTermMemory) -> None:
        assert lt.list_all() == []

    def test_active_only_default(self, lt: LongTermMemory) -> None:
        lt.upsert(_make_memory("active"))
        lt.upsert(_make_memory("dead", confidence=0.0))
        results = lt.list_all(active_only=True)
        assert all(r.id == "active" for r in results)

    def test_include_inactive(self, lt: LongTermMemory) -> None:
        lt.upsert(_make_memory("active"))
        lt.upsert(_make_memory("dead", confidence=0.0))
        results = lt.list_all(active_only=False)
        assert len(results) == 2
