"""
Testes para memory/retrieval.py.

Cobre:
  - retrieve_relevant_memories(): FTS5 local sem Sonnet lateral
  - format_memories_for_injection(): formatação do contexto para o prompt
"""

from unittest.mock import MagicMock

import pytest

from memory.types import Memory, MemoryType
from memory.store import MemoryStore
from memory.retrieval import (
    retrieve_relevant_memories,
    format_memories_for_injection,
)


# ─── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(data_dir=tmp_path / "mem_data")
    return s


def _make_memory(mem_type=MemoryType.ARCHITECTURE, summary="Resumo", tags=None) -> Memory:
    return Memory(
        type=mem_type,
        content="Conteúdo completo da memória.",
        summary=summary,
        tags=tags or ["test"],
        confidence=1.0,
    )


# ─── retrieve_relevant_memories ───────────────────────────────────────
# Fase 4: FTS5 local, sem Sonnet lateral, sem patches HTTP.


class TestRetrieveRelevantMemories:
    def test_returns_list_type(self, store):
        result = retrieve_relevant_memories("qualquer query", store)
        assert isinstance(result, list)

    def test_returns_empty_when_store_empty(self, store):
        result = retrieve_relevant_memories("pipeline databricks bronze", store)
        assert result == []

    def test_finds_memory_by_summary_keywords(self, store):
        mem = _make_memory(summary="Pipeline Databricks Bronze layer ingestion")
        store.save(mem)
        result = retrieve_relevant_memories("Databricks Bronze ingestion", store)
        assert any(m.id == mem.id for m in result)

    def test_no_results_for_unrelated_query(self, store):
        mem = _make_memory(summary="Pipeline Databricks Bronze layer ingestion")
        store.save(mem)
        result = retrieve_relevant_memories("quantum physics black holes", store)
        assert result == [] or all(m.id != mem.id for m in result)

    def test_respects_max_memories_limit(self, store):
        for i in range(15):
            store.save(_make_memory(summary=f"pipeline data ingestion pattern number {i}"))
        result = retrieve_relevant_memories(
            "pipeline data ingestion pattern", store, max_memories=5
        )
        assert len(result) <= 5

    def test_long_term_param_bypasses_lazy_creation(self, store):
        from memory.long_term import LongTermMemory

        mock_lt = MagicMock(spec=LongTermMemory)
        mock_lt.search.return_value = []
        retrieve_relevant_memories("q", store, long_term=mock_lt)
        mock_lt.search.assert_called_once()

    def test_returns_memory_objects(self, store):
        from memory.types import Memory as MemType

        mem = _make_memory(summary="databricks unity catalog configuration setup")
        store.save(mem)
        result = retrieve_relevant_memories("databricks unity catalog", store)
        assert all(isinstance(m, MemType) for m in result)


# ─── format_memories_for_injection ────────────────────────────────────


class TestFormatMemoriesForInjection:
    def test_returns_empty_string_for_empty_list(self):
        result = format_memories_for_injection([])
        assert result == ""

    def test_contains_memory_summary(self):
        mem = _make_memory(summary="Pipeline usa Auto Loader na Bronze")
        result = format_memories_for_injection([mem])
        assert "Pipeline usa Auto Loader na Bronze" in result

    def test_contains_memory_content(self):
        mem = _make_memory()
        mem.content = "Conteúdo muito específico que deve aparecer."
        result = format_memories_for_injection([mem])
        assert "Conteúdo muito específico" in result

    def test_groups_by_type(self):
        user_mem = _make_memory(mem_type=MemoryType.USER, summary="Preferência do usuário")
        arch_mem = _make_memory(mem_type=MemoryType.ARCHITECTURE, summary="Decisão arch")
        result = format_memories_for_injection([user_mem, arch_mem])
        assert "Preferências do Usuário" in result
        assert "Decisões Arquiteturais" in result

    def test_includes_confidence_when_below_one(self):
        mem = _make_memory()
        mem.confidence = 0.75
        result = format_memories_for_injection([mem])
        assert "0.75" in result

    def test_no_confidence_shown_when_full(self):
        mem = _make_memory()
        mem.confidence = 1.0
        result = format_memories_for_injection([mem])
        # Confidence 1.0 não precisa ser mostrada
        assert "confidence: 1.00" not in result

    def test_content_truncated_at_500_chars(self):
        mem = _make_memory()
        mem.content = "X" * 600
        result = format_memories_for_injection([mem])
        # Não deve incluir os 600 chars completos
        assert "X" * 600 not in result
        assert "truncado" in result.lower() or "..." in result

    def test_header_section_present(self):
        mem = _make_memory()
        result = format_memories_for_injection([mem])
        assert "Contexto Injetado" in result or "Memórias Relevantes" in result

    def test_multiple_types_all_present(self):
        mems = [
            _make_memory(mem_type=MemoryType.USER),
            _make_memory(mem_type=MemoryType.FEEDBACK),
            _make_memory(mem_type=MemoryType.ARCHITECTURE),
            _make_memory(mem_type=MemoryType.PROGRESS),
        ]
        result = format_memories_for_injection(mems)
        # Todos os 4 tipos devem estar representados
        for mem in mems:
            assert mem.id in result
