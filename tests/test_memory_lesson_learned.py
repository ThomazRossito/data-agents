"""
Tests for LESSON_LEARNED memory type — Phase 1-4 coverage.

Tests:
  - MemoryType enum has LESSON_LEARNED
  - DECAY_CONFIG has 30-day entry for LESSON_LEARNED
  - Settings has memory_decay_lesson_learned_days and memory_lesson_max_per_agent
  - Memory can be created, saved, and loaded from MemoryStore
  - decay._get_decay_days returns settings value for LESSON_LEARNED
  - store.prune_lessons_by_agent removes excess entries
  - compiler.deduplicate_lessons merges similar lessons
  - retrieval.format_memories_for_injection includes LESSON_LEARNED section
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from pathlib import Path


# ── Phase 1: Type + DECAY_CONFIG ──────────────────────────────────────────────


def test_lesson_learned_in_memory_type_enum() -> None:
    from memory.types import MemoryType

    assert hasattr(MemoryType, "LESSON_LEARNED")
    assert MemoryType.LESSON_LEARNED.value == "lesson_learned"


def test_lesson_learned_in_decay_config() -> None:
    from memory.types import DECAY_CONFIG, MemoryType

    assert MemoryType.LESSON_LEARNED in DECAY_CONFIG
    assert DECAY_CONFIG[MemoryType.LESSON_LEARNED] == 30.0


def test_settings_has_lesson_learned_fields() -> None:
    from config.settings import Settings

    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert hasattr(s, "memory_decay_lesson_learned_days")
    assert s.memory_decay_lesson_learned_days == 30.0
    assert hasattr(s, "memory_lesson_max_per_agent")
    assert s.memory_lesson_max_per_agent == 50


def test_settings_has_s4_fields() -> None:
    from config.settings import Settings

    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert hasattr(s, "s4_autonomous_mode")
    assert s.s4_autonomous_mode is False
    assert hasattr(s, "s4_auto_approval_min_clarity_score")
    assert s.s4_auto_approval_min_clarity_score == 4
    assert hasattr(s, "s4_auto_approval_max_cost_usd")
    assert s.s4_auto_approval_max_cost_usd == 0.10


def test_decay_get_decay_days_lesson_learned() -> None:
    from memory.decay import _get_decay_days
    from memory.types import MemoryType

    days = _get_decay_days(MemoryType.LESSON_LEARNED)
    assert days == 30.0


def test_error_trigger_matches_combined_text() -> None:
    """tool_error sem keyword + tool_output com 'exception' deve disparar o trigger."""
    from hooks.memory_hook import _detect_lesson_triggers, reset_lesson_state

    reset_lesson_state()
    triggers = _detect_lesson_triggers(
        tool_name="mcp__databricks__execute_sql",
        tool_output="AnalysisException: Table or view not found: silver.tbl",
        tool_error="Table or view not found: silver.tbl",  # sem keyword sozinho
        tool_use_id="test_combined_001",
    )
    assert "error" in triggers


def test_error_trigger_fires_on_tool_error_keyword() -> None:
    """tool_error com 'failed' deve disparar o trigger mesmo sem tool_output."""
    from hooks.memory_hook import _detect_lesson_triggers, reset_lesson_state

    reset_lesson_state()
    triggers = _detect_lesson_triggers(
        tool_name="mcp__databricks__run_job_now",
        tool_output="",
        tool_error="Job failed: OOM after 120s",
        tool_use_id="test_error_kw_001",
    )
    assert "error" in triggers


# ── Phase 1: Memory CRUD ──────────────────────────────────────────────────────


@pytest.fixture
def tmp_store(tmp_path: Path):
    from memory.store import MemoryStore

    return MemoryStore(data_dir=tmp_path / "memory_data")


def _make_lesson(agent: str = "databricks-engineer", trigger: str = "error"):  # type: ignore[return]
    from memory.types import Memory, MemoryType

    return Memory(
        type=MemoryType.LESSON_LEARNED,
        summary=f"{agent}: {trigger} — mcp__databricks__execute_sql",
        content="## O que aconteceu\nQuery falhou.\n\n## Causa raiz\nTable not found.\n\n## Padrão para evitar\nVerificar catálogo antes de query.",
        tags=[agent, trigger, "execute_sql", "lesson_learned"],
        confidence=1.0,
        metadata={"agent": agent, "trigger": trigger, "task_type": "execute_sql"},
    )


def test_lesson_save_and_load(tmp_store) -> None:
    from memory.types import MemoryType

    lesson = _make_lesson()
    path = tmp_store.save(lesson)
    assert path.exists()

    loaded = tmp_store.load(lesson.id, MemoryType.LESSON_LEARNED)
    assert loaded is not None
    assert loaded.type == MemoryType.LESSON_LEARNED
    assert loaded.summary == lesson.summary
    assert loaded.metadata["agent"] == "databricks-engineer"
    assert loaded.metadata["trigger"] == "error"


def test_lesson_list_all_by_type(tmp_store) -> None:
    from memory.types import MemoryType

    lesson1 = _make_lesson("databricks-engineer", "error")
    lesson2 = _make_lesson("fabric-engineer", "slow_op")
    tmp_store.save(lesson1)
    tmp_store.save(lesson2)

    lessons = tmp_store.list_all(memory_type=MemoryType.LESSON_LEARNED)
    assert len(lessons) == 2
    types = {m.type for m in lessons}
    assert types == {MemoryType.LESSON_LEARNED}


def test_lesson_decay_reduces_confidence(tmp_store) -> None:
    from memory.decay import compute_decayed_confidence
    from datetime import timedelta

    lesson = _make_lesson()
    # Simulate 15 days ago
    lesson.created_at = datetime.now(timezone.utc) - timedelta(days=15)

    decayed = compute_decayed_confidence(lesson)
    # 15 days out of 30 days should be significantly decayed
    assert decayed < 0.8
    assert decayed > 0.0


# ── Phase 3: prune_lessons_by_agent ──────────────────────────────────────────


def test_prune_lessons_keeps_max_entries(tmp_store) -> None:
    from memory.types import MemoryType

    agent = "databricks-engineer"
    # Create 55 lessons for the same agent
    for i in range(55):
        from memory.types import Memory

        lesson = Memory(
            type=MemoryType.LESSON_LEARNED,
            summary=f"{agent}: error — tool_{i}",
            content=f"Content {i}",
            tags=[agent, "error", f"tool_{i}"],
            confidence=1.0 - (i * 0.01),  # decreasing confidence
            metadata={"agent": agent, "trigger": "error", "task_type": f"tool_{i}"},
        )
        tmp_store.save(lesson)

    # Verify we have 55
    lessons_before = tmp_store.list_all(memory_type=MemoryType.LESSON_LEARNED)
    agent_lessons = [m for m in lessons_before if m.metadata.get("agent") == agent]
    assert len(agent_lessons) == 55

    # Prune to max 50
    removed = tmp_store.prune_lessons_by_agent(agent_name=agent, max_entries=50)
    assert removed == 5

    lessons_after = [
        m
        for m in tmp_store.list_all(memory_type=MemoryType.LESSON_LEARNED)
        if m.metadata.get("agent") == agent
    ]
    assert len(lessons_after) == 50


def test_prune_lessons_under_limit_does_nothing(tmp_store) -> None:
    agent = "fabric-engineer"
    for i in range(3):
        tmp_store.save(_make_lesson(agent=agent, trigger="slow_op"))

    removed = tmp_store.prune_lessons_by_agent(agent_name=agent, max_entries=50)
    assert removed == 0


# ── Phase 3: deduplicate_lessons ─────────────────────────────────────────────


def test_deduplicate_lessons_merges_similar(tmp_store) -> None:
    from memory.compiler import deduplicate_lessons
    from memory.types import Memory, MemoryType

    agent = "databricks-engineer"
    # Two very similar lessons (same agent + task_type, similar summary)
    lesson1 = Memory(
        type=MemoryType.LESSON_LEARNED,
        summary=f"{agent}: error — mcp__databricks__run_job_now",
        content="## O que aconteceu\nJob falhou OOM.\n\n## Causa raiz\nSem partition filter.\n\n## Padrão para evitar\nSempre usar WHERE.",
        tags=[agent, "error", "run_job_now"],
        confidence=0.9,
        metadata={"agent": agent, "trigger": "error", "task_type": "run_job_now"},
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    lesson2 = Memory(
        type=MemoryType.LESSON_LEARNED,
        summary=f"{agent}: error — mcp__databricks__run_job_now",  # identical summary
        content="## O que aconteceu\nJob OOM novamente.\n\n## Causa raiz\nFiltro ausente.\n\n## Padrão para evitar\nUsar WHERE obrigatório.",
        tags=[agent, "error", "run_job_now"],
        confidence=1.0,
        metadata={"agent": agent, "trigger": "error", "task_type": "run_job_now"},
        created_at=datetime(2026, 1, 15, tzinfo=timezone.utc),  # mais recente
    )
    tmp_store.save(lesson1)
    tmp_store.save(lesson2)

    metrics = deduplicate_lessons(tmp_store)
    assert metrics["merged"] >= 1


def test_deduplicate_lessons_keeps_different(tmp_store) -> None:
    from memory.compiler import deduplicate_lessons
    from memory.types import Memory, MemoryType

    lesson1 = Memory(
        type=MemoryType.LESSON_LEARNED,
        summary="databricks-engineer: error — mcp__databricks__execute_sql",
        content="SQL error content",
        tags=["databricks-engineer", "error", "execute_sql"],
        confidence=1.0,
        metadata={"agent": "databricks-engineer", "trigger": "error", "task_type": "execute_sql"},
    )
    lesson2 = Memory(
        type=MemoryType.LESSON_LEARNED,
        summary="fabric-engineer: slow_op — mcp__fabric_sql__run_query",
        content="Slow query content",
        tags=["fabric-engineer", "slow_op", "run_query"],
        confidence=1.0,
        metadata={"agent": "fabric-engineer", "trigger": "slow_op", "task_type": "run_query"},
    )
    tmp_store.save(lesson1)
    tmp_store.save(lesson2)

    metrics = deduplicate_lessons(tmp_store)
    # Different agents — should not merge
    assert metrics["merged"] == 0


# ── Phase 4: format_memories_for_injection ───────────────────────────────────


def test_format_memories_includes_lesson_learned_section(tmp_store) -> None:
    from memory.retrieval import format_memories_for_injection
    from memory.types import Memory, MemoryType

    lesson = Memory(
        type=MemoryType.LESSON_LEARNED,
        summary="databricks-engineer: error — mcp__databricks__execute_sql",
        content="## O que aconteceu\nQuery falhou.\n\n## Causa raiz\nTabela inexistente.\n\n## Padrão para evitar\nVerificar schema.",
        tags=["databricks-engineer", "error"],
        confidence=1.0,
        metadata={"agent": "databricks-engineer", "trigger": "error"},
    )

    result = format_memories_for_injection([lesson])
    assert "Lições Aprendidas" in result
    assert "⚠️" in result
    assert lesson.summary in result


def test_format_memories_empty_returns_empty() -> None:
    from memory.retrieval import format_memories_for_injection

    result = format_memories_for_injection([])
    assert result == ""
