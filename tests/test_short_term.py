"""
Tests for memory.short_term — ShortTermMemory (SQLite TTL buffer).
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from memory.short_term import ShortTermMemory, ShortTermEntry


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_short_term.db"


@pytest.fixture
def stm(db_path: Path) -> ShortTermMemory:
    return ShortTermMemory(db_path=db_path, ttl_days=1.0)


# ── Construction ──────────────────────────────────────────────────────────────


class TestInit:
    def test_creates_db_file(self, db_path: Path) -> None:
        ShortTermMemory(db_path=db_path, ttl_days=1.0)
        assert db_path.exists()

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "c" / "test.db"
        ShortTermMemory(db_path=nested, ttl_days=1.0)
        assert nested.exists()

    def test_idempotent_init(self, db_path: Path) -> None:
        ShortTermMemory(db_path=db_path, ttl_days=1.0)
        ShortTermMemory(db_path=db_path, ttl_days=1.0)  # no error on second init


# ── Append ────────────────────────────────────────────────────────────────────


class TestAppend:
    def test_returns_entry_id(self, stm: ShortTermMemory) -> None:
        entry_id = stm.append("hello world", session_id="s1")
        assert isinstance(entry_id, str)
        assert len(entry_id) == 12  # uuid hex[:12]

    def test_empty_content_returns_empty_string(self, stm: ShortTermMemory) -> None:
        entry_id = stm.append("", session_id="s1")
        assert entry_id == ""

    def test_whitespace_only_returns_empty_string(self, stm: ShortTermMemory) -> None:
        entry_id = stm.append("   \n", session_id="s1")
        assert entry_id == ""

    def test_stores_tool_name(self, stm: ShortTermMemory) -> None:
        stm.append("content", session_id="s1", tool_name="Write")
        stats = stm.get_stats("s1")
        assert stats["active"] == 1

    def test_multiple_entries_accumulate(self, stm: ShortTermMemory) -> None:
        for i in range(5):
            stm.append(f"entry {i}", session_id="s1")
        stats = stm.get_stats("s1")
        assert stats["active"] == 5

    def test_different_sessions_isolated(self, stm: ShortTermMemory) -> None:
        stm.append("session A content", session_id="sA")
        stm.append("session B content", session_id="sB")
        assert stm.get_stats("sA")["active"] == 1
        assert stm.get_stats("sB")["active"] == 1


# ── Stats ─────────────────────────────────────────────────────────────────────


class TestStats:
    def test_empty_stats(self, stm: ShortTermMemory) -> None:
        stats = stm.get_stats("s1")
        assert stats == {"total": 0, "active": 0, "expired": 0}

    def test_global_stats_aggregates_sessions(self, stm: ShortTermMemory) -> None:
        stm.append("a", session_id="s1")
        stm.append("b", session_id="s2")
        stats = stm.get_stats()
        assert stats["active"] == 2

    def test_expired_counted_correctly(self, db_path: Path) -> None:
        stm_short = ShortTermMemory(db_path=db_path, ttl_days=0.0)
        stm_short.append("will expire immediately", session_id="s1")
        time.sleep(0.01)
        stm_short.expire_old_entries()
        stats = stm_short.get_stats("s1")
        assert stats["total"] == 0  # deleted on expire


# ── get_session_buffer ────────────────────────────────────────────────────────


class TestGetSessionBuffer:
    def test_empty_buffer(self, stm: ShortTermMemory) -> None:
        assert stm.get_session_buffer("s1") == ""

    def test_returns_content_in_order(self, stm: ShortTermMemory) -> None:
        stm.append("first", session_id="s1")
        stm.append("second", session_id="s1")
        buf = stm.get_session_buffer("s1")
        assert "first" in buf
        assert "second" in buf
        assert buf.index("first") < buf.index("second")

    def test_separator_between_entries(self, stm: ShortTermMemory) -> None:
        stm.append("alpha", session_id="s1")
        stm.append("beta", session_id="s1")
        buf = stm.get_session_buffer("s1")
        assert "---" in buf

    def test_filters_by_session(self, stm: ShortTermMemory) -> None:
        stm.append("session A", session_id="sA")
        stm.append("session B", session_id="sB")
        buf = stm.get_session_buffer("sA")
        assert "session A" in buf
        assert "session B" not in buf


# ── expire_old_entries ────────────────────────────────────────────────────────


class TestExpireOldEntries:
    def test_removes_expired(self, db_path: Path) -> None:
        stm = ShortTermMemory(db_path=db_path, ttl_days=0.0)
        stm.append("expired", session_id="s1")
        time.sleep(0.02)
        removed = stm.expire_old_entries()
        assert removed == 1

    def test_keeps_active(self, stm: ShortTermMemory) -> None:
        stm.append("active", session_id="s1")
        removed = stm.expire_old_entries()
        assert removed == 0
        assert stm.get_stats("s1")["active"] == 1

    def test_returns_count(self, db_path: Path) -> None:
        stm = ShortTermMemory(db_path=db_path, ttl_days=0.0)
        for _ in range(3):
            stm.append("x", session_id="s1")
        time.sleep(0.02)
        removed = stm.expire_old_entries()
        assert removed == 3


# ── search ────────────────────────────────────────────────────────────────────


class TestSearch:
    def test_empty_query_returns_empty(self, stm: ShortTermMemory) -> None:
        stm.append("some content", session_id="s1")
        results = stm.search("")
        assert results == []

    def test_finds_matching_entry(self, stm: ShortTermMemory) -> None:
        stm.append("databricks SQL execution pipeline", session_id="s1")
        stm.append("unrelated content about weather", session_id="s1")
        results = stm.search("databricks", session_id="s1")
        assert len(results) >= 1
        assert any("databricks" in r.content.lower() for r in results)

    def test_returns_short_term_entries(self, stm: ShortTermMemory) -> None:
        stm.append("python testing patterns", session_id="s1")
        results = stm.search("python", session_id="s1")
        assert all(isinstance(r, ShortTermEntry) for r in results)

    def test_respects_limit(self, stm: ShortTermMemory) -> None:
        for i in range(10):
            stm.append(f"python entry number {i} with extra text", session_id="s1")
        results = stm.search("python entry", session_id="s1", limit=3)
        assert len(results) <= 3

    def test_session_filter(self, stm: ShortTermMemory) -> None:
        stm.append("shared keyword content alpha", session_id="sA")
        stm.append("shared keyword content beta", session_id="sB")
        results = stm.search("keyword", session_id="sA")
        assert all(r.session_id == "sA" for r in results)


# ── mark_promoted ─────────────────────────────────────────────────────────────


class TestMarkPromoted:
    def test_marks_entry_promoted(self, stm: ShortTermMemory) -> None:
        entry_id = stm.append("promote me", session_id="s1")
        stm.mark_promoted(entry_id)
        # Verify via direct query that promoted=1
        import sqlite3

        with sqlite3.connect(str(stm._db_path)) as conn:
            row = conn.execute(
                "SELECT promoted FROM short_term_entries WHERE id=?", (entry_id,)
            ).fetchone()
        assert row[0] == 1

    def test_noop_for_unknown_id(self, stm: ShortTermMemory) -> None:
        stm.mark_promoted("nonexistent")  # should not raise
