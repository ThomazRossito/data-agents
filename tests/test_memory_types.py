"""
Testes para memory/types.py.

Cobre:
  - MemoryType: enum values e iteração
  - DECAY_CONFIG: configuração correta por tipo
  - Memory: criação, defaults, is_active(), to_frontmatter(), to_markdown(), from_dict()
"""

from datetime import datetime, timezone

import pytest

from memory.types import Memory, MemoryType, DECAY_CONFIG


# ─── MemoryType ──────────────────────────────────────────────────────


class TestMemoryType:
    def test_four_types_exist(self):
        types = list(MemoryType)
        assert len(types) == 4

    def test_type_values(self):
        assert MemoryType.USER.value == "user"
        assert MemoryType.FEEDBACK.value == "feedback"
        assert MemoryType.ARCHITECTURE.value == "architecture"
        assert MemoryType.PROGRESS.value == "progress"

    def test_from_string(self):
        assert MemoryType("user") == MemoryType.USER
        assert MemoryType("progress") == MemoryType.PROGRESS

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            MemoryType("invalid_type")


# ─── DECAY_CONFIG ─────────────────────────────────────────────────────


class TestDecayConfig:
    def test_user_never_decays(self):
        assert DECAY_CONFIG[MemoryType.USER] is None

    def test_architecture_never_decays(self):
        assert DECAY_CONFIG[MemoryType.ARCHITECTURE] is None

    def test_feedback_decays_at_90_days(self):
        assert DECAY_CONFIG[MemoryType.FEEDBACK] == 90.0

    def test_progress_decays_at_7_days(self):
        assert DECAY_CONFIG[MemoryType.PROGRESS] == 7.0

    def test_all_types_in_config(self):
        for mt in MemoryType:
            assert mt in DECAY_CONFIG


# ─── Memory defaults ─────────────────────────────────────────────────


class TestMemoryDefaults:
    def test_default_type_is_progress(self):
        mem = Memory()
        assert mem.type == MemoryType.PROGRESS

    def test_default_confidence_is_one(self):
        mem = Memory()
        assert mem.confidence == 1.0

    def test_id_is_generated(self):
        mem = Memory()
        assert mem.id and len(mem.id) == 12

    def test_two_memories_have_different_ids(self):
        a = Memory()
        b = Memory()
        assert a.id != b.id

    def test_created_at_is_utc(self):
        mem = Memory()
        assert mem.created_at.tzinfo is not None

    def test_default_tags_empty_list(self):
        mem = Memory()
        assert mem.tags == []

    def test_default_related_ids_empty(self):
        mem = Memory()
        assert mem.related_ids == []

    def test_default_superseded_by_none(self):
        mem = Memory()
        assert mem.superseded_by is None


# ─── Memory.is_active ────────────────────────────────────────────────


class TestMemoryIsActive:
    def test_active_when_confidence_above_threshold(self):
        mem = Memory(confidence=0.5)
        assert mem.is_active() is True

    def test_inactive_when_confidence_below_threshold(self):
        mem = Memory(confidence=0.05)
        assert mem.is_active() is False

    def test_inactive_when_superseded(self):
        mem = Memory(confidence=1.0, superseded_by="other_id")
        assert mem.is_active() is False

    def test_active_at_exact_threshold(self):
        # 0.1 é o threshold padrão (inclusive)
        mem = Memory(confidence=0.1)
        assert mem.is_active() is True

    def test_custom_threshold(self):
        mem = Memory(confidence=0.3)
        assert mem.is_active(threshold=0.4) is False
        assert mem.is_active(threshold=0.2) is True


# ─── Memory.to_frontmatter ───────────────────────────────────────────


class TestMemoryToFrontmatter:
    def test_contains_delimiter(self):
        mem = Memory()
        fm = mem.to_frontmatter()
        assert fm.startswith("---")
        assert fm.strip().endswith("---")

    def test_contains_id(self):
        mem = Memory()
        fm = mem.to_frontmatter()
        assert f"id: {mem.id}" in fm

    def test_contains_type(self):
        mem = Memory(type=MemoryType.ARCHITECTURE)
        fm = mem.to_frontmatter()
        assert "type: architecture" in fm

    def test_contains_confidence(self):
        mem = Memory(confidence=0.75)
        fm = mem.to_frontmatter()
        assert "confidence: 0.750" in fm

    def test_contains_tags(self):
        mem = Memory(tags=["databricks", "pipeline"])
        fm = mem.to_frontmatter()
        assert "databricks" in fm
        assert "pipeline" in fm

    def test_contains_related_ids_when_present(self):
        mem = Memory(related_ids=["abc123", "def456"])
        fm = mem.to_frontmatter()
        assert "related_ids" in fm
        assert "abc123" in fm

    def test_no_related_ids_when_empty(self):
        mem = Memory(related_ids=[])
        fm = mem.to_frontmatter()
        assert "related_ids" not in fm

    def test_contains_superseded_by_when_set(self):
        mem = Memory(superseded_by="newer_id")
        fm = mem.to_frontmatter()
        assert "superseded_by: newer_id" in fm

    def test_no_superseded_by_when_none(self):
        mem = Memory(superseded_by=None)
        fm = mem.to_frontmatter()
        assert "superseded_by" not in fm


# ─── Memory.to_markdown ──────────────────────────────────────────────


class TestMemoryToMarkdown:
    def test_markdown_contains_frontmatter(self):
        mem = Memory(content="Conteúdo da memória.")
        md = mem.to_markdown()
        assert md.startswith("---")

    def test_markdown_contains_content(self):
        mem = Memory(content="Decisão importante sobre pipeline.")
        md = mem.to_markdown()
        assert "Decisão importante sobre pipeline." in md

    def test_markdown_structure(self):
        mem = Memory(content="Corpo do texto.")
        md = mem.to_markdown()
        # Frontmatter + quebra + conteúdo
        parts = md.split("---\n\n")
        assert len(parts) >= 2


# ─── Memory.from_dict ────────────────────────────────────────────────


class TestMemoryFromDict:
    def _base_dict(self, **overrides):
        now = datetime.now(timezone.utc).isoformat()
        base = {
            "id": "abc123456789",
            "type": "architecture",
            "summary": "Pipeline usa Medallion",
            "content": "Bronze → Silver → Gold com Auto Loader.",
            "tags": ["pipeline", "bronze"],
            "confidence": 0.9,
            "created_at": now,
            "updated_at": now,
            "source_session": "session_01",
        }
        base.update(overrides)
        return base

    def test_creates_memory_from_dict(self):
        mem = Memory.from_dict(self._base_dict())
        assert mem.id == "abc123456789"
        assert mem.type == MemoryType.ARCHITECTURE
        assert mem.confidence == 0.9

    def test_type_converted_from_string(self):
        mem = Memory.from_dict(self._base_dict(type="feedback"))
        assert mem.type == MemoryType.FEEDBACK

    def test_tags_preserved(self):
        mem = Memory.from_dict(self._base_dict(tags=["databricks", "delta"]))
        assert "databricks" in mem.tags

    def test_missing_optional_fields_use_defaults(self):
        minimal = {
            "id": "abc123456789",
            "type": "progress",
            "content": "Em progresso.",
        }
        mem = Memory.from_dict(minimal)
        assert mem.related_ids == []
        assert mem.superseded_by is None

    def test_superseded_by_preserved(self):
        mem = Memory.from_dict(self._base_dict(superseded_by="newer_id"))
        assert mem.superseded_by == "newer_id"

    def test_related_ids_preserved(self):
        mem = Memory.from_dict(self._base_dict(related_ids=["ref1", "ref2"]))
        assert "ref1" in mem.related_ids

    def test_datetime_parsed_correctly(self):
        fixed_dt = "2026-01-15T10:30:00+00:00"
        mem = Memory.from_dict(self._base_dict(created_at=fixed_dt, updated_at=fixed_dt))
        assert mem.created_at.year == 2026
        assert mem.created_at.month == 1

    def test_missing_datetime_uses_now(self):
        data = {"id": "x", "type": "progress", "content": "test"}
        before = datetime.now(timezone.utc)
        mem = Memory.from_dict(data)
        after = datetime.now(timezone.utc)
        assert before <= mem.created_at <= after
