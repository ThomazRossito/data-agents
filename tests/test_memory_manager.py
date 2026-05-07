"""
Testes de contrato para memory/manager.py.

IMPORTANTE: estes testes verificam o CONTRATO público do MemoryManager —
o que é garantido para os chamadores. NÃO testam implementação interna.

Nas Fases 1–4 do roadmap, a implementação muda (Ledger, SQLite, ChromaDB),
mas estes testes devem permanecer verdes sem modificação.

Contratos verificados:
  - start_session: inicializa estado, reseta flags
  - inject_context: enriquece prompt; respeita feature flags; decay apenas 1x/sessão
  - flush_session: retorna contagem; respeita feature flags; passa session_id
  - end_session: chama flush; reseta estado; respeita feature flags
  - apply_decay: delega; marca flag; noop em store vazio
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from memory.manager import MemoryManager
from memory.types import Memory, MemoryType


# ─── Fixtures ─────────────────────────────────────────────────────────────────


def _make_settings(enabled: bool = True) -> MagicMock:
    s = MagicMock()
    s.memory_enabled = enabled
    s.memory_retrieval_enabled = enabled
    s.memory_capture_enabled = enabled
    return s


@pytest.fixture
def manager():
    return MemoryManager(settings=_make_settings(enabled=True))


@pytest.fixture
def manager_off():
    return MemoryManager(settings=_make_settings(enabled=False))


def _mem(summary: str = "test") -> Memory:
    return Memory(type=MemoryType.ARCHITECTURE, content="c", summary=summary)


# ─── start_session ────────────────────────────────────────────────────────────


class TestStartSession:
    def test_stores_session_id(self, manager):
        manager.start_session("sess-abc")
        assert manager._session_id == "sess-abc"

    def test_resets_decay_flag(self, manager):
        manager._decay_applied = True
        manager.start_session("sess-new")
        assert manager._decay_applied is False

    def test_successive_calls_overwrite(self, manager):
        manager.start_session("s1")
        manager.start_session("s2")
        assert manager._session_id == "s2"


# ─── inject_context ───────────────────────────────────────────────────────────


def _setup_inject(manager, memories: list | None = None):
    """Helper: injeta mocks de LongTermMemory + decay no manager."""
    mock_lt = MagicMock()
    mock_lt.search.return_value = memories or []
    mock_lt.migrate_from_store.return_value = len(memories or [])
    manager._long_term = mock_lt
    manager._long_term_synced = True  # skip sync I/O em testes de contrato
    manager._decay_applied = True  # skip decay I/O em testes de contrato
    return mock_lt


class TestInjectContext:
    def test_returns_enriched_prompt(self, manager):
        _setup_inject(manager, [_mem("databricks pipeline memory")])
        result = manager.inject_context("databricks", "original")
        assert result != "original"  # foi enriquecido
        assert "databricks pipeline memory" in result

    def test_returns_original_when_no_memories(self, manager):
        _setup_inject(manager, [])
        result = manager.inject_context("q", "original prompt")
        assert result == "original prompt"

    def test_returns_original_when_disabled(self, manager_off):
        mock_lt = _setup_inject(manager_off, [_mem("x")])
        result = manager_off.inject_context("q", "original prompt")
        mock_lt.search.assert_not_called()
        assert result == "original prompt"

    def test_returns_original_on_exception(self, manager):
        mock_lt = MagicMock()
        mock_lt.search.side_effect = RuntimeError("boom")
        manager._long_term = mock_lt
        manager._decay_applied = True
        manager._long_term_synced = True
        result = manager.inject_context("q", "safe prompt")
        assert result == "safe prompt"

    def test_decay_applied_once_per_session(self, manager):
        _setup_inject(manager, [])
        manager._decay_applied = False

        def _set_decay_flag():
            manager._decay_applied = True

        with patch.object(manager, "apply_decay", side_effect=_set_decay_flag) as mock_decay:
            manager.inject_context("q1", "p")
            manager.inject_context("q2", "p")
        mock_decay.assert_called_once()

    def test_decay_reset_on_new_session(self, manager):
        _setup_inject(manager, [])
        manager._decay_applied = False
        with patch.object(manager, "apply_decay") as mock_decay:
            manager.inject_context("q1", "p")
            manager.start_session("new-session")
            manager._long_term = MagicMock()
            manager._long_term.search.return_value = []
            manager._long_term_synced = True
            manager.inject_context("q2", "p")
        assert mock_decay.call_count == 2

    def test_cache_hit_skips_search(self, manager):
        mock_lt = _setup_inject(manager, [_mem("cached content")])
        manager.inject_context("same query", "prompt")  # populates cache
        manager.inject_context("same query", "prompt")  # should hit cache
        assert mock_lt.search.call_count == 1


# ─── flush_session ────────────────────────────────────────────────────────────


class TestFlushSession:
    def test_returns_count(self, manager):
        manager.start_session("s1")
        with patch("hooks.memory_hook.flush_session_memories", return_value=7):
            with patch.object(manager, "sync_long_term", return_value=0):
                assert manager.flush_session() == 7

    def test_passes_session_id(self, manager):
        manager.start_session("sess-xyz")
        with patch("hooks.memory_hook.flush_session_memories", return_value=0) as mock:
            manager.flush_session()
        mock.assert_called_once_with(session_id="sess-xyz")

    def test_returns_zero_when_disabled(self, manager_off):
        with patch("hooks.memory_hook.flush_session_memories") as mock:
            count = manager_off.flush_session()
        mock.assert_not_called()
        assert count == 0

    def test_returns_zero_on_exception(self, manager):
        manager.start_session("s1")
        with patch("hooks.memory_hook.flush_session_memories", side_effect=OSError("disk full")):
            assert manager.flush_session() == 0


# ─── end_session ──────────────────────────────────────────────────────────────


class TestEndSession:
    def test_calls_flush(self, manager):
        manager.start_session("s1")
        with patch.object(manager, "flush_session", return_value=2) as mock:
            manager.end_session()
        mock.assert_called_once()

    def test_resets_session_id(self, manager):
        manager.start_session("s1")
        with patch.object(manager, "flush_session", return_value=0):
            manager.end_session()
        assert manager._session_id == ""

    def test_resets_decay_flag(self, manager):
        manager._decay_applied = True
        with patch.object(manager, "flush_session", return_value=0):
            manager.end_session()
        assert manager._decay_applied is False

    def test_skips_flush_when_disabled(self, manager_off):
        with patch.object(manager_off, "flush_session") as mock:
            manager_off.end_session()
        mock.assert_not_called()


# ─── apply_decay ──────────────────────────────────────────────────────────────


class TestApplyDecay:
    def _mock_store(self, manager: MemoryManager, memories: list) -> MagicMock:
        """Injeta um store mockado diretamente na instância (bypassa a property)."""
        mock_store = MagicMock()
        mock_store.list_all.return_value = memories
        manager._store = mock_store
        return mock_store

    def test_marks_decay_applied(self, manager):
        self._mock_store(manager, [])
        manager.apply_decay()
        assert manager._decay_applied is True

    def test_delegates_to_decay_module(self, manager):
        mem = _mem()
        mock_store = self._mock_store(manager, [mem])
        with patch("memory.decay.apply_decay") as mock_decay:
            manager.apply_decay()
        mock_decay.assert_called_once_with([mem], save_fn=mock_store.save)

    def test_noop_on_empty_store(self, manager):
        self._mock_store(manager, [])
        with patch("memory.decay.apply_decay") as mock_decay:
            manager.apply_decay()
        mock_decay.assert_not_called()

    def test_does_not_raise_on_exception(self, manager):
        mock_store = MagicMock()
        mock_store.list_all.side_effect = OSError("io error")
        manager._store = mock_store
        manager.apply_decay()  # não deve lançar


# ─── End-to-end session flow ──────────────────────────────────────────────────


class TestSessionFlow:
    """
    Contrato end-to-end: start → inject → flush → end.

    Verifica que a sequência completa de uma sessão funciona sem erros
    e que o estado é corretamente propagado entre as etapas.
    """

    def _setup(self, manager: MemoryManager) -> MagicMock:
        """Injeta LongTermMemory mockado e desabilita I/O de decay."""
        mock_lt = MagicMock()
        mock_lt.search.return_value = [_mem("pipeline memory for test")]
        mock_lt.migrate_from_store.return_value = 1
        manager._long_term = mock_lt
        manager._decay_applied = True
        manager._long_term_synced = True
        return mock_lt

    def test_start_then_inject_returns_enriched(self, manager):
        self._setup(manager)
        manager.start_session("flow-01")
        result = manager.inject_context("pipeline query", "base prompt")
        assert result != "base prompt"
        assert "pipeline memory for test" in result

    def test_start_then_flush_then_end_resets_state(self, manager):
        self._setup(manager)
        manager.start_session("flow-02")
        with patch("hooks.memory_hook.flush_session_memories", return_value=3):
            with patch.object(manager, "sync_long_term", return_value=3):
                count = manager.flush_session()
        assert count == 3
        with patch.object(manager, "flush_session", return_value=0):
            manager.end_session()
        assert manager._session_id == ""
        assert manager._decay_applied is False

    def test_inject_cache_cleared_on_new_session(self, manager):
        self._setup(manager)
        manager.start_session("flow-03")
        manager.inject_context("repeat query", "p")  # popula cache
        assert len(manager._retrieval_cache) == 1
        manager.start_session("flow-04")  # novo session deve limpar cache
        assert len(manager._retrieval_cache) == 0

    def test_sync_long_term_called_once_per_session(self, manager):
        self._setup(manager)
        manager.start_session("flow-05")  # reseta _long_term_synced=False

        def _set_synced():
            manager._long_term_synced = True

        with patch.object(manager, "sync_long_term", side_effect=_set_synced) as mock_sync:
            manager.inject_context("q1", "p")
            manager.inject_context("q2", "p")  # diferente query, diferente hash
        mock_sync.assert_called_once()

    def test_full_lifecycle_no_exceptions(self, manager):
        self._setup(manager)
        manager.start_session("flow-06")
        manager.inject_context("query a", "base")
        manager.inject_context("query a", "base")  # cache hit
        with patch("hooks.memory_hook.flush_session_memories", return_value=2):
            with patch.object(manager, "sync_long_term", return_value=2):
                manager.flush_session()
        with patch.object(manager, "flush_session", return_value=0):
            manager.end_session()
