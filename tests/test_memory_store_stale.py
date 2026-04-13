"""
Testes para as novas funções de staleness em memory/store.py (Ch. 11).

Cobre:
  - get_stale_memories(): retorna memórias com confidence decaída abaixo do threshold
  - prune_stale_memories(): remove memórias stale, suporta dry_run
"""

from datetime import datetime, timedelta, timezone

import pytest

from memory.store import MemoryStore
from memory.types import Memory, MemoryType


@pytest.fixture
def store(tmp_path):
    return MemoryStore(data_dir=tmp_path / "stale_test")


def _progress_memory(days_old: int, confidence: float = 1.0, **kwargs) -> Memory:
    """Cria memória PROGRESS com a idade especificada."""
    created = datetime.now(timezone.utc) - timedelta(days=days_old)
    return Memory(
        type=MemoryType.PROGRESS,
        content="Progresso de tarefa com texto suficiente.",
        summary=f"Progresso {days_old}d",
        tags=["task"],
        confidence=confidence,
        created_at=created,
        **kwargs,
    )


def _feedback_memory(days_old: int, confidence: float = 1.0, **kwargs) -> Memory:
    """Cria memória FEEDBACK com a idade especificada."""
    created = datetime.now(timezone.utc) - timedelta(days=days_old)
    return Memory(
        type=MemoryType.FEEDBACK,
        content="Feedback do usuário com texto suficiente.",
        summary=f"Feedback {days_old}d",
        tags=["feedback"],
        confidence=confidence,
        created_at=created,
        **kwargs,
    )


def _arch_memory(**kwargs) -> Memory:
    """Cria memória ARCHITECTURE (nunca decai)."""
    return Memory(
        type=MemoryType.ARCHITECTURE,
        content="Decisão arquitetural permanente com texto suficiente.",
        summary="Decisão arq",
        tags=["arch"],
        confidence=1.0,
        **kwargs,
    )


# ─── get_stale_memories ──────────────────────────────────────────────────────


class TestGetStaleMemories:
    def test_returns_empty_for_fresh_store(self, store):
        """Store vazio não tem memórias stale."""
        assert store.get_stale_memories() == []

    def test_fresh_progress_is_not_stale(self, store):
        """PROGRESS recém criado (0 dias) tem confidence ~1.0 — não é stale."""
        mem = _progress_memory(days_old=0)
        store.save(mem)
        assert store.get_stale_memories(threshold=0.1) == []

    def test_old_progress_is_stale(self, store):
        """PROGRESS com 20 dias tem confidence << 0.1 — é stale."""
        mem = _progress_memory(days_old=20)
        store.save(mem)
        stale = store.get_stale_memories(threshold=0.1)
        assert len(stale) == 1
        assert stale[0].id == mem.id

    def test_old_feedback_is_stale_at_90_days(self, store):
        """FEEDBACK com 100 dias tem confidence < 0.1 — é stale."""
        mem = _feedback_memory(days_old=100)
        store.save(mem)
        stale = store.get_stale_memories(threshold=0.1)
        assert len(stale) == 1
        assert stale[0].id == mem.id

    def test_architecture_never_stale_regardless_of_age(self, store):
        """ARCHITECTURE não tem decay — nunca aparece como stale."""
        old_arch = _arch_memory(created_at=datetime.now(timezone.utc) - timedelta(days=365))
        store.save(old_arch)
        stale = store.get_stale_memories(threshold=0.1)
        assert stale == []

    def test_user_memory_never_stale(self, store):
        """USER não tem decay — nunca aparece como stale."""
        old_user = Memory(
            type=MemoryType.USER,
            content="Preferência do usuário com texto suficiente.",
            summary="Preferência user",
            tags=["user"],
            confidence=1.0,
            created_at=datetime.now(timezone.utc) - timedelta(days=500),
        )
        store.save(old_user)
        assert store.get_stale_memories(threshold=0.1) == []

    def test_superseded_memory_excluded(self, store):
        """Memórias superseded não são incluídas no resultado stale."""
        mem = _progress_memory(days_old=20, superseded_by="some_newer_id")
        store.save(mem)
        assert store.get_stale_memories(threshold=0.1) == []

    def test_filters_by_memory_type(self, store):
        """Filtra por memory_type quando especificado."""
        progress_mem = _progress_memory(days_old=20)
        feedback_mem = _feedback_memory(days_old=100)
        store.save(progress_mem)
        store.save(feedback_mem)

        # Filtra apenas PROGRESS
        stale_progress = store.get_stale_memories(threshold=0.1, memory_type=MemoryType.PROGRESS)
        assert all(m.type == MemoryType.PROGRESS for m in stale_progress)

    def test_higher_threshold_finds_more_stale(self, store):
        """Threshold mais alto encontra mais memórias como stale."""
        mem_3d = _progress_memory(days_old=3)  # confidence ~0.37
        mem_10d = _progress_memory(days_old=10)  # confidence << 0.1
        store.save(mem_3d)
        store.save(mem_10d)

        stale_strict = store.get_stale_memories(threshold=0.1)
        stale_lenient = store.get_stale_memories(threshold=0.5)

        assert len(stale_strict) <= len(stale_lenient)

    def test_multiple_stale_memories_returned(self, store):
        """Múltiplas memórias stale são todas retornadas."""
        mem1 = _progress_memory(days_old=20)
        mem2 = _progress_memory(days_old=30)
        mem3 = _progress_memory(days_old=0)  # não é stale
        store.save(mem1)
        store.save(mem2)
        store.save(mem3)

        stale = store.get_stale_memories(threshold=0.1)
        stale_ids = {m.id for m in stale}
        assert mem1.id in stale_ids
        assert mem2.id in stale_ids
        assert mem3.id not in stale_ids


# ─── prune_stale_memories ────────────────────────────────────────────────────


class TestPruneStaleMemories:
    def test_dry_run_does_not_delete(self, store):
        """dry_run=True identifica mas não remove memórias."""
        mem = _progress_memory(days_old=20)
        store.save(mem)

        pruned = store.prune_stale_memories(threshold=0.1, dry_run=True)
        assert len(pruned) == 1

        # Memória ainda existe
        remaining = store.list_all(active_only=False, min_confidence=0.0)
        assert any(m.id == mem.id for m in remaining)

    def test_prune_removes_stale_memories(self, store):
        """Sem dry_run, remove efetivamente as memórias stale."""
        mem = _progress_memory(days_old=20)
        store.save(mem)

        pruned = store.prune_stale_memories(threshold=0.1, dry_run=False)
        assert len(pruned) == 1

        # Memória foi removida
        remaining = store.list_all(active_only=False, min_confidence=0.0)
        assert not any(m.id == mem.id for m in remaining)

    def test_prune_returns_empty_for_fresh_store(self, store):
        """Store sem memórias stale retorna lista vazia."""
        assert store.prune_stale_memories() == []

    def test_prune_preserves_fresh_memories(self, store):
        """Memórias recentes não são afetadas pela poda."""
        fresh = _progress_memory(days_old=0)
        old = _progress_memory(days_old=20)
        store.save(fresh)
        store.save(old)

        store.prune_stale_memories(threshold=0.1, dry_run=False)

        remaining = store.list_all(active_only=False, min_confidence=0.0)
        remaining_ids = {m.id for m in remaining}
        assert fresh.id in remaining_ids
        assert old.id not in remaining_ids

    def test_prune_returns_pruned_list(self, store):
        """Retorna lista das memórias removidas (mesmo com dry_run)."""
        mem1 = _progress_memory(days_old=20)
        mem2 = _progress_memory(days_old=30)
        store.save(mem1)
        store.save(mem2)

        pruned = store.prune_stale_memories(threshold=0.1)
        assert len(pruned) == 2
        pruned_ids = {m.id for m in pruned}
        assert mem1.id in pruned_ids
        assert mem2.id in pruned_ids

    def test_prune_does_not_touch_architecture(self, store):
        """ARCHITECTURE não é incluída na poda."""
        arch = _arch_memory(created_at=datetime.now(timezone.utc) - timedelta(days=365))
        store.save(arch)

        pruned = store.prune_stale_memories(threshold=0.1)
        assert pruned == []

        remaining = store.list_all(active_only=False, min_confidence=0.0)
        assert any(m.id == arch.id for m in remaining)
