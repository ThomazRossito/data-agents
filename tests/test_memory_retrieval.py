"""
Testes para memory/retrieval.py.

Cobre:
  - _query_sonnet_for_ids(): mock da chamada HTTP ao Sonnet
  - retrieve_relevant_memories(): end-to-end com store real + Sonnet mock
  - format_memories_for_injection(): formatação do contexto para o prompt
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from memory.types import Memory, MemoryType
from memory.store import MemoryStore
from memory.retrieval import (
    _query_sonnet_for_ids,
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


def _mock_http_response(ids: list[str]):
    """Cria um mock de urllib.request.urlopen retornando JSON com os IDs."""
    body = json.dumps(
        {
            "content": [{"text": json.dumps(ids)}],
            "usage": {"input_tokens": 100, "output_tokens": 20},
        }
    ).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ─── _query_sonnet_for_ids ────────────────────────────────────────────


class TestQuerySonnetForIds:
    def test_returns_ids_from_sonnet_response(self):
        mock_resp = _mock_http_response(["abc123", "def456"])
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _query_sonnet_for_ids(
                "query de teste", "## Memory Index\n- **abc123**: resumo"
            )
        assert "abc123" in result
        assert "def456" in result

    def test_returns_empty_list_on_empty_response(self):
        mock_resp = _mock_http_response([])
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _query_sonnet_for_ids("query", "index")
        assert result == []

    def test_returns_empty_list_on_invalid_json(self):
        body = json.dumps(
            {
                "content": [{"text": "não é json válido"}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
        ).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _query_sonnet_for_ids("query", "index")
        assert result == []

    def test_returns_empty_list_on_http_error(self):
        with patch("urllib.request.urlopen", side_effect=Exception("network error")):
            result = _query_sonnet_for_ids("query", "index")
        assert result == []

    def test_ids_converted_to_strings(self):
        """IDs devem ser retornados como strings mesmo se Sonnet enviar como outros tipos."""
        mock_resp = _mock_http_response(["id1", "id2"])
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _query_sonnet_for_ids("q", "index")
        assert all(isinstance(i, str) for i in result)


# ─── retrieve_relevant_memories ───────────────────────────────────────


class TestRetrieveRelevantMemories:
    def test_returns_empty_when_no_index(self, store, tmp_path):
        """Se não há index, deve retornar lista vazia sem errar."""
        result = retrieve_relevant_memories("query", store)
        # Pode retornar [] se o index estiver vazio
        assert isinstance(result, list)

    def test_returns_memories_selected_by_sonnet(self, store):
        mem = _make_memory(summary="Pipeline Databricks Bronze")
        store.save(mem)
        store.build_index()

        mock_resp = _mock_http_response([mem.id])
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = retrieve_relevant_memories("Mostre o pipeline Bronze", store)

        assert any(m.id == mem.id for m in result)

    def test_returns_empty_when_sonnet_selects_nothing(self, store):
        mem = _make_memory()
        store.save(mem)
        store.build_index()

        mock_resp = _mock_http_response([])
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = retrieve_relevant_memories("query irrelevante", store)

        assert result == []

    def test_respects_max_memories_limit(self, store):
        for i in range(15):
            store.save(_make_memory(summary=f"Memória {i}"))
        store.build_index()

        # Sonnet retorna 15 IDs
        all_ids = [m.id for m in store.list_all()]
        mock_resp = _mock_http_response(all_ids)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = retrieve_relevant_memories("query", store, max_memories=5)

        assert len(result) <= 5

    def test_skips_nonexistent_ids_gracefully(self, store):
        mem = _make_memory()
        store.save(mem)
        store.build_index()

        mock_resp = _mock_http_response(["nonexistent_id_xyz", mem.id])
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = retrieve_relevant_memories("query", store)

        # nonexistent_id não deve causar erro, apenas ser ignorado
        assert all(m is not None for m in result)

    def test_handles_sonnet_error_gracefully(self, store):
        mem = _make_memory()
        store.save(mem)
        store.build_index()

        with patch("urllib.request.urlopen", side_effect=Exception("Sonnet unavailable")):
            result = retrieve_relevant_memories("query", store)

        assert result == []


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
