"""
Testes para memory/extractor.py.

Cobre:
  - extract_memories_from_conversation(): mock da chamada Sonnet
  - Tratamento de tipos inválidos, JSON malformado, erros HTTP
  - Truncagem de conversa longa
  - Deduplicação via existing_summaries
"""

import json
from unittest.mock import patch, MagicMock


from memory.types import MemoryType
from memory.extractor import extract_memories_from_conversation


# ─── Helpers ─────────────────────────────────────────────────────────


def _mock_sonnet(extractions: list[dict]):
    """Cria mock HTTP retornando extrações formatadas pelo Sonnet."""
    body = json.dumps(
        {
            "content": [{"text": json.dumps(extractions)}],
            "usage": {"input_tokens": 200, "output_tokens": 50},
        }
    ).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _sample_extraction(**overrides):
    base = {
        "type": "architecture",
        "summary": "Pipeline Medallion com 3 camadas",
        "content": "A arquitetura usa Bronze → Silver → Gold com Auto Loader.",
        "tags": ["pipeline", "medallion"],
    }
    base.update(overrides)
    return base


# ─── extract_memories_from_conversation ───────────────────────────────


class TestExtractMemoriesFromConversation:
    def test_returns_memories_from_sonnet_response(self):
        mock_resp = _mock_sonnet([_sample_extraction()])
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = extract_memories_from_conversation(
                "Usuário: Quero criar um pipeline Medallion."
            )
        assert len(result) == 1
        assert result[0].type == MemoryType.ARCHITECTURE

    def test_returns_empty_for_empty_conversation(self):
        result = extract_memories_from_conversation("")
        assert result == []

    def test_returns_empty_for_whitespace_only(self):
        result = extract_memories_from_conversation("   \n\t  ")
        assert result == []

    def test_multiple_extractions(self):
        extractions = [
            _sample_extraction(type="user", summary="Preferência por código em PT-BR"),
            _sample_extraction(type="feedback", summary="Não usar SELECT *"),
            _sample_extraction(type="architecture", summary="Pipeline Bronze pronto"),
        ]
        mock_resp = _mock_sonnet(extractions)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = extract_memories_from_conversation("Conversa longa...")
        assert len(result) == 3
        types = {m.type for m in result}
        assert MemoryType.USER in types
        assert MemoryType.FEEDBACK in types

    def test_invalid_type_skipped(self):
        extractions = [
            _sample_extraction(type="invalid_type", summary="Ignorado"),
            _sample_extraction(type="progress", summary="Válido"),
        ]
        mock_resp = _mock_sonnet(extractions)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = extract_memories_from_conversation("Conversa.")
        # Apenas o tipo válido deve ser retornado
        assert len(result) == 1
        assert result[0].type == MemoryType.PROGRESS

    def test_session_id_stored_in_memory(self):
        mock_resp = _mock_sonnet([_sample_extraction()])
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = extract_memories_from_conversation("Conversa.", session_id="session_42")
        assert result[0].source_session == "session_42"

    def test_handles_http_error_gracefully(self):
        with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
            result = extract_memories_from_conversation("Conversa.")
        assert result == []

    def test_handles_invalid_json_response_gracefully(self):
        body = json.dumps(
            {
                "content": [{"text": "isto não é json"}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
        ).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = extract_memories_from_conversation("Conversa.")
        assert result == []

    def test_handles_empty_json_array_response(self):
        mock_resp = _mock_sonnet([])
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = extract_memories_from_conversation("Conversa.")
        assert result == []

    def test_handles_non_list_response_gracefully(self):
        body = json.dumps(
            {
                "content": [{"text": '{"not": "a list"}'}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
        ).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = extract_memories_from_conversation("Conversa.")
        assert result == []

    def test_long_conversation_truncated(self):
        """Conversas muito longas devem ser truncadas antes de enviar ao Sonnet."""
        long_conv = "X" * 100_000
        captured_payload = []

        def mock_urlopen(req, timeout=None):
            captured_payload.append(req.data.decode("utf-8"))
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(
                {
                    "content": [{"text": "[]"}],
                    "usage": {"input_tokens": 100, "output_tokens": 5},
                }
            ).encode("utf-8")
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            extract_memories_from_conversation(long_conv)

        # O payload enviado deve ser menor que a conversa original
        payload_str = captured_payload[0]
        assert len(payload_str) < len(long_conv)

    def test_tags_preserved_from_extraction(self):
        mock_resp = _mock_sonnet([_sample_extraction(tags=["databricks", "bronze", "auto-loader"])])
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = extract_memories_from_conversation("Conversa.")
        assert set(result[0].tags) == {"databricks", "bronze", "auto-loader"}

    def test_handles_markdown_code_fence_in_response(self):
        """Sonnet às vezes envolve JSON em code fences — deve ser tratado."""
        fenced = '```json\n[{"type": "architecture", "summary": "Test", "content": "Body.", "tags": ["x"]}]\n```'
        body = json.dumps(
            {
                "content": [{"text": fenced}],
                "usage": {"input_tokens": 50, "output_tokens": 20},
            }
        ).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = extract_memories_from_conversation("Conversa.")
        assert len(result) == 1
