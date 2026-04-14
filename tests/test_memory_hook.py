"""
Testes para hooks/memory_hook.py.

Cobre:
  - capture_session_context: skip tools, acumulação de buffer, padrões instantâneos
  - _format_context_entry: formatação por tipo de tool
  - _check_instant_patterns: detecção de correções e decisões
  - get_session_buffer / get_buffer_stats / clear_session_buffer
  - flush_session_memories: buffer vazio e flush com memórias (mocked)
"""

from unittest.mock import MagicMock, patch

import pytest

from hooks.memory_hook import (
    _check_instant_patterns,
    _format_context_entry,
    capture_session_context,
    clear_session_buffer,
    flush_session_memories,
    get_buffer_stats,
    get_session_buffer,
)


# ── Helper: monta input_data no formato SDK ────────────────────────────────────


def _input(tool_name: str, tool_input=None, tool_output=None) -> dict:
    return {"tool_name": tool_name, "tool_input": tool_input or {}, "tool_output": tool_output}


@pytest.fixture(autouse=True)
def reset_buffer():
    """Limpa o buffer antes e depois de cada teste para evitar poluição."""
    clear_session_buffer()
    yield
    clear_session_buffer()


# ─── capture_session_context ─────────────────────────────────────────────────


class TestCaptureSessionContext:
    """Testes para a função principal do hook."""

    @pytest.mark.asyncio
    async def test_skip_tools_return_empty(self):
        """Tools de infra (Read, Glob, Grep, Bash) devem ser ignoradas."""
        for tool in ("Read", "Glob", "Grep", "Bash"):
            result = await capture_session_context(_input(tool, {}, "some output"), None, None)
            assert result == {}
        # Buffer deve permanecer vazio
        assert get_session_buffer() == ""

    @pytest.mark.asyncio
    async def test_non_skip_tool_adds_to_buffer(self):
        """Tool não listada em skip deve adicionar entrada ao buffer."""
        await capture_session_context(_input("Write", {"file_path": "foo.py"}, "ok"), None, None)
        buf = get_session_buffer()
        assert "Write" in buf

    @pytest.mark.asyncio
    async def test_returns_empty_dict_always(self):
        """O hook não deve modificar o output — sempre retorna {}."""
        result = await capture_session_context(
            _input("Agent", {"agent_name": "sql"}, "resp"), None, None
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_buffer_accumulates_multiple_entries(self):
        """Múltiplas chamadas acumulam entradas separadas no buffer."""
        await capture_session_context(_input("Write", {"file_path": "a.py"}, "ok"), None, None)
        await capture_session_context(_input("Write", {"file_path": "b.py"}, "ok"), None, None)
        stats = get_buffer_stats()
        assert stats["entries"] == 2

    @pytest.mark.asyncio
    async def test_none_output_does_not_crash(self):
        """Output None não deve causar erro."""
        result = await capture_session_context(
            _input("Write", {"file_path": "x.py"}, None), None, None
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_none_input_does_not_crash(self):
        """Input None não deve causar erro."""
        result = await capture_session_context(_input("Write", None, "some output"), None, None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_instant_pattern_detected_in_output(self):
        """Padrões instantâneos no output devem ser detectados e adicionados ao buffer."""
        await capture_session_context(
            _input("Write", {}, "prefiro sempre usar snake_case nos arquivos"), None, None
        )
        stats = get_buffer_stats()
        assert stats["instant_captures"] >= 1

    @pytest.mark.asyncio
    async def test_buffer_threshold_log(self, caplog):
        """Quando buffer excede threshold, uma mensagem de log deve ser emitida."""
        import logging

        with caplog.at_level(logging.INFO, logger="data_agents.memory.hook"):
            big_output = "x" * 50_001
            await capture_session_context(
                _input("Write", {"file_path": "big.py"}, big_output), None, None
            )
        assert get_buffer_stats()["total_chars"] > 0


# ─── _format_context_entry ───────────────────────────────────────────────────


class TestFormatContextEntry:
    """Testes para a função de formatação de entradas do buffer."""

    def test_agent_tool_includes_agent_name(self):
        result = _format_context_entry(
            "Agent", {"agent_name": "sql-expert", "prompt": "consulta tabela X"}, "resp"
        )
        assert "sql-expert" in result
        assert "consulta tabela X" in result

    def test_agent_tool_fallback_name_key(self):
        """Suporte ao campo 'name' como fallback de 'agent_name'."""
        result = _format_context_entry("Agent", {"name": "spark-expert", "prompt": "teste"}, None)
        assert "spark-expert" in result

    def test_agent_tool_prompt_truncated_at_200(self):
        """Prompt do Agent deve ser truncado em 200 caracteres."""
        long_prompt = "a" * 300
        result = _format_context_entry("Agent", {"agent_name": "x", "prompt": long_prompt}, None)
        assert "a" * 200 in result
        assert "a" * 201 not in result

    def test_write_tool_includes_file_path(self):
        result = _format_context_entry("Write", {"file_path": "output/report.md"}, "ok")
        assert "output/report.md" in result

    def test_ask_user_question_includes_question(self):
        result = _format_context_entry("AskUserQuestion", {"question": "Qual o prazo?"}, "resposta")
        assert "Qual o prazo?" in result

    def test_output_preview_truncated_at_300(self):
        """Output deve ser truncado em 300 chars no preview."""
        big_output = "y" * 400
        result = _format_context_entry("SomeTool", {}, big_output)
        assert "y" * 300 in result
        assert "y" * 301 not in result

    def test_empty_input_and_output(self):
        """Input e output vazios não devem causar erro."""
        result = _format_context_entry("SomeTool", {}, "")
        assert "SomeTool" in result

    def test_timestamp_present_in_entry(self):
        """Cada entrada deve conter um timestamp."""
        result = _format_context_entry("Write", {"file_path": "f.py"}, "ok")
        import re

        assert re.search(r"\[\d{2}:\d{2}:\d{2}\]", result)


# ─── _check_instant_patterns ─────────────────────────────────────────────────


class TestCheckInstantPatterns:
    """Testes para detecção de padrões de captura instantânea."""

    def test_feedback_nao_faca(self):
        """'não faça X' deve ser capturado como feedback."""
        _check_instant_patterns("não faça queries sem LIMIT")
        stats = get_buffer_stats()
        assert stats["instant_captures"] >= 1

    def test_feedback_prefiro(self):
        """'prefiro Y' deve ser capturado como feedback."""
        _check_instant_patterns("prefiro sempre usar CTEs em vez de subqueries")
        assert get_buffer_stats()["instant_captures"] >= 1

    def test_architecture_decision_tag(self):
        """'#decision:' deve gerar captura de arquitetura."""
        _check_instant_patterns("#decision: usar Delta Lake para camada Gold")
        assert get_buffer_stats()["instant_captures"] >= 1

    def test_architecture_pattern_tag(self):
        """'#pattern' deve gerar captura de arquitetura."""
        _check_instant_patterns("#pattern - SCD2 para dimensão cliente")
        assert get_buffer_stats()["instant_captures"] >= 1

    def test_architecture_gotcha_tag(self):
        """'#gotcha' deve gerar captura de arquitetura."""
        _check_instant_patterns(
            "#gotcha: VACUUM remove arquivos Delta necessários para time travel"
        )
        assert get_buffer_stats()["instant_captures"] >= 1

    def test_no_pattern_no_capture(self):
        """Texto sem padrão não deve gerar capturas."""
        _check_instant_patterns("Aqui está o resultado da query.")
        assert get_buffer_stats()["instant_captures"] == 0

    def test_instant_capture_marker_in_buffer(self):
        """Buffer deve conter o marcador [INSTANT_CAPTURE]."""
        _check_instant_patterns("#decision: usar Parquet")
        buf = get_session_buffer()
        assert "[INSTANT_CAPTURE]" in buf


# ─── get_session_buffer / get_buffer_stats / clear_session_buffer ────────────


class TestBufferAccessors:
    """Testes para os accessors e clear do buffer."""

    def test_get_session_buffer_empty_initially(self):
        assert get_session_buffer() == ""

    @pytest.mark.asyncio
    async def test_get_session_buffer_returns_joined_entries(self):
        await capture_session_context(_input("Write", {"file_path": "a.py"}, "ok"), None, None)
        await capture_session_context(_input("Write", {"file_path": "b.py"}, "ok"), None, None)
        buf = get_session_buffer()
        assert "---" in buf  # separador entre entradas

    def test_get_buffer_stats_structure(self):
        stats = get_buffer_stats()
        assert "entries" in stats
        assert "total_chars" in stats
        assert "instant_captures" in stats

    @pytest.mark.asyncio
    async def test_get_buffer_stats_counts_correctly(self):
        await capture_session_context(_input("Write", {"file_path": "x.py"}, "ok"), None, None)
        _check_instant_patterns("#decision: usar Delta")
        stats = get_buffer_stats()
        assert stats["entries"] == 2  # 1 write + 1 instant capture
        assert stats["instant_captures"] == 1

    @pytest.mark.asyncio
    async def test_clear_session_buffer_resets_all(self):
        await capture_session_context(
            _input("Write", {"file_path": "x.py"}, "conteúdo"), None, None
        )
        assert get_buffer_stats()["entries"] > 0
        clear_session_buffer()
        assert get_session_buffer() == ""
        stats = get_buffer_stats()
        assert stats["entries"] == 0
        assert stats["total_chars"] == 0

    def test_clear_idempotent(self):
        """Chamar clear duas vezes não deve causar erro."""
        clear_session_buffer()
        clear_session_buffer()
        assert get_buffer_stats()["entries"] == 0


# ─── flush_session_memories ──────────────────────────────────────────────────


class TestFlushSessionMemories:
    """Testes para flush_session_memories."""

    def test_flush_empty_buffer_returns_zero(self):
        """Buffer vazio → flush retorna 0 e não chama extractor."""
        result = flush_session_memories(session_id="test-session")
        assert result == 0

    @pytest.mark.asyncio
    async def test_flush_calls_extractor_and_saves(self):
        """Com buffer preenchido, deve chamar extractor e salvar memórias."""
        from memory.types import Memory, MemoryType

        fake_memory = Memory(
            type=MemoryType.USER,
            summary="Prefere CTEs",
            content="O usuário prefere CTEs a subqueries.",
            tags=["sql", "style"],
            confidence=0.9,
        )

        await capture_session_context(
            _input("Write", {"file_path": "test.py"}, "resultado da execução"), None, None
        )

        with (
            patch("memory.store.MemoryStore") as mock_store_cls,
            patch(
                "memory.extractor.extract_memories_from_conversation",
                return_value=[fake_memory],
            ) as mock_extract,
        ):
            mock_store = MagicMock()
            mock_store.list_all.return_value = []
            mock_store_cls.return_value = mock_store

            result = flush_session_memories(session_id="sess-001")

        assert result == 1
        mock_extract.assert_called_once()

    @pytest.mark.asyncio
    async def test_flush_clears_buffer_after_processing(self):
        """Após flush, o buffer deve estar limpo."""
        await capture_session_context(_input("Write", {"file_path": "x.py"}, "ok"), None, None)

        with (
            patch("memory.store.MemoryStore") as mock_store_cls,
            patch(
                "memory.extractor.extract_memories_from_conversation",
                return_value=[],
            ),
        ):
            mock_store = MagicMock()
            mock_store.list_all.return_value = []
            mock_store_cls.return_value = mock_store
            flush_session_memories(session_id="sess-002")

        assert get_session_buffer() == ""
        assert get_buffer_stats()["entries"] == 0

    @pytest.mark.asyncio
    async def test_flush_returns_zero_when_extractor_returns_empty(self):
        """Extractor sem memórias → retorna 0."""
        await capture_session_context(_input("Write", {"file_path": "y.py"}, "content"), None, None)

        with (
            patch("memory.store.MemoryStore") as mock_store_cls,
            patch(
                "memory.extractor.extract_memories_from_conversation",
                return_value=[],
            ),
        ):
            mock_store = MagicMock()
            mock_store.list_all.return_value = []
            mock_store_cls.return_value = mock_store
            result = flush_session_memories()

        assert result == 0

    @pytest.mark.asyncio
    async def test_flush_passes_session_id_to_extractor(self):
        """session_id deve ser repassado ao extractor."""
        await capture_session_context(_input("Write", {"file_path": "z.py"}, "info"), None, None)

        with (
            patch("memory.store.MemoryStore") as mock_store_cls,
            patch(
                "memory.extractor.extract_memories_from_conversation",
                return_value=[],
            ) as mock_extract,
        ):
            mock_store = MagicMock()
            mock_store.list_all.return_value = []
            mock_store_cls.return_value = mock_store
            flush_session_memories(session_id="sess-xyz")

        call_kwargs = mock_extract.call_args
        assert call_kwargs is not None
        assert "sess-xyz" in str(call_kwargs)
