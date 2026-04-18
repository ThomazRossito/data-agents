"""
Testes do hook de compressão de output (output_compressor_hook).

Cobre:
  - Compressão de resultados SQL (JSON lista, JSON dict, texto tabular)
  - Compressão de listagens (JSON lista, JSON dict, texto linha a linha)
  - Compressão de output de Bash/Read por número de linhas
  - Fallback de segurança por número de caracteres
  - Casos de borda: output pequeno (sem compressão), input inválido, exceções
  - Interface do hook principal (compress_tool_output)
  - Estrutura da resposta de compressão (hookSpecificOutput)
  - Logging de eventos de compressão
"""

import json

import pytest

from hooks.output_compressor_hook import (
    MAX_BASH_LINES,
    MAX_FILE_LINES,
    MAX_LIST_ITEMS,
    MAX_OUTPUT_CHARS,
    MAX_SQL_ROWS,
    _build_response,
    _compress_by_chars,
    _compress_by_lines,
    _compress_list_result,
    _compress_sql_result,
    _extract_output,
    compress_tool_output,
)


# ─── Helpers de fixture ───────────────────────────────────────────


def _make_sql_rows(n: int) -> str:
    """Gera JSON de lista com n rows simulando retorno de execute_sql."""
    return json.dumps([{"id": i, "valor": f"item_{i}", "data": "2024-01-01"} for i in range(n)])


def _make_list_items(n: int, key: str = "tables") -> str:
    """Gera JSON de dict com n itens simulando retorno de list_tables."""
    items = [{"name": f"table_{i}", "type": "MANAGED"} for i in range(n)]
    return json.dumps({key: items, "total": n})


def _make_text_lines(n: int, prefix: str = "linha") -> str:
    """Gera string com n linhas de texto simples."""
    return "\n".join(f"{prefix} {i}: conteúdo de exemplo aqui" for i in range(n))


def _make_hook_input(tool_name: str, output: str) -> dict:
    """Monta o input_data de um PostToolUse hook com tool_response."""
    return {
        "tool_name": tool_name,
        "tool_input": {"statement": "SELECT 1"},
        "tool_response": output,
    }


# ─── _extract_output ─────────────────────────────────────────────


class TestExtractOutput:
    def test_reads_tool_response_key(self):
        result = _extract_output({"tool_name": "Bash", "tool_response": "hello"})
        assert result == "hello"

    def test_reads_tool_output_key_as_fallback(self):
        result = _extract_output({"tool_name": "Bash", "tool_output": "world"})
        assert result == "world"

    def test_reads_output_key_as_last_resort(self):
        result = _extract_output({"output": "fallback"})
        assert result == "fallback"

    def test_returns_none_when_no_output_key(self):
        result = _extract_output({"tool_name": "Bash", "tool_input": {}})
        assert result is None

    def test_returns_none_on_empty_dict(self):
        assert _extract_output({}) is None

    def test_coerces_non_string_to_str(self):
        result = _extract_output({"tool_response": 42})
        assert result == "42"


# ─── _build_response ─────────────────────────────────────────────


class TestBuildResponse:
    def test_structure_is_correct(self):
        result = _build_response("compressed content")
        assert "hookSpecificOutput" in result
        assert result["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
        assert result["hookSpecificOutput"]["toolResponse"] == "compressed content"

    def test_handles_empty_string(self):
        result = _build_response("")
        assert result["hookSpecificOutput"]["toolResponse"] == ""


# ─── _compress_sql_result ────────────────────────────────────────


class TestCompressSqlResultJsonList:
    """Output como lista JSON direta: [{"col": "val"}, ...]"""

    def test_no_compression_when_under_limit(self):
        output = _make_sql_rows(MAX_SQL_ROWS - 1)
        assert _compress_sql_result(output, "mcp__databricks__execute_sql") is None

    def test_no_compression_when_exactly_at_limit(self):
        output = _make_sql_rows(MAX_SQL_ROWS)
        assert _compress_sql_result(output, "mcp__databricks__execute_sql") is None

    def test_compresses_when_over_limit(self):
        output = _make_sql_rows(MAX_SQL_ROWS + 10)
        result = _compress_sql_result(output, "mcp__databricks__execute_sql")
        assert result is not None
        rows = json.loads(result.split("\n\n", 1)[1])
        assert len(rows) == MAX_SQL_ROWS

    def test_header_contains_total_and_limit(self):
        total = MAX_SQL_ROWS + 50
        output = _make_sql_rows(total)
        result = _compress_sql_result(output, "mcp__databricks__execute_sql")
        assert str(total) in result
        assert str(MAX_SQL_ROWS) in result

    def test_header_contains_guidance(self):
        output = _make_sql_rows(MAX_SQL_ROWS + 5)
        result = _compress_sql_result(output, "mcp__databricks__execute_sql")
        assert "WHERE" in result or "LIMIT" in result


class TestCompressSqlResultJsonDict:
    """Output como dict com chave de lista: {"rows": [...], "schema": {...}}"""

    def test_no_compression_when_under_limit(self):
        data = {"rows": [{"id": i} for i in range(MAX_SQL_ROWS)], "schema": {"cols": ["id"]}}
        assert _compress_sql_result(json.dumps(data), "mcp__databricks__execute_sql") is None

    def test_compresses_dict_with_rows_key(self):
        data = {"rows": [{"id": i} for i in range(MAX_SQL_ROWS + 20)], "schema": {}}
        result = _compress_sql_result(json.dumps(data), "mcp__databricks__execute_sql")
        assert result is not None
        parsed = json.loads(result.split("\n\n", 1)[1])
        assert len(parsed["rows"]) == MAX_SQL_ROWS

    def test_preserves_other_dict_fields(self):
        data = {
            "rows": [{"id": i} for i in range(MAX_SQL_ROWS + 5)],
            "schema": {"column_names": ["id"]},
            "query_id": "abc123",
        }
        result = _compress_sql_result(json.dumps(data), "mcp__databricks__execute_sql")
        parsed = json.loads(result.split("\n\n", 1)[1])
        assert "schema" in parsed
        assert "query_id" in parsed
        assert parsed["query_id"] == "abc123"


class TestCompressSqlResultTextFallback:
    """Output como texto tabular (markdown table, CSV, plain text)."""

    def test_no_compression_when_under_limit(self):
        output = _make_text_lines(MAX_SQL_ROWS)
        assert _compress_sql_result(output, "mcp__databricks__execute_sql") is None

    def test_compresses_text_lines(self):
        total = MAX_SQL_ROWS + 30
        output = _make_text_lines(total)
        result = _compress_sql_result(output, "mcp__databricks__execute_sql")
        assert result is not None
        assert len(result.splitlines()) <= MAX_SQL_ROWS + 1  # +1 para aviso de truncamento

    def test_footer_mentions_omitted_lines(self):
        output = _make_text_lines(MAX_SQL_ROWS + 20)
        result = _compress_sql_result(output, "mcp__databricks__execute_sql")
        assert "omitidas" in result or "omitidos" in result


# ─── _compress_list_result ───────────────────────────────────────


class TestCompressListResult:
    def test_no_compression_when_under_limit(self):
        items = [{"name": f"t{i}"} for i in range(MAX_LIST_ITEMS)]
        assert _compress_list_result(json.dumps(items), "mcp__databricks__list_tables") is None

    def test_compresses_json_list(self):
        items = [{"name": f"t{i}"} for i in range(MAX_LIST_ITEMS + 20)]
        result = _compress_list_result(json.dumps(items), "mcp__databricks__list_tables")
        assert result is not None
        parsed = json.loads(result.split("\n\n", 1)[1])
        assert len(parsed) == MAX_LIST_ITEMS

    def test_compresses_json_dict_with_inner_list(self):
        output = _make_list_items(MAX_LIST_ITEMS + 15, key="tables")
        result = _compress_list_result(output, "mcp__databricks__list_tables")
        assert result is not None
        parsed = json.loads(result.split("\n\n", 1)[1])
        assert len(parsed["tables"]) == MAX_LIST_ITEMS

    def test_header_contains_total(self):
        total = MAX_LIST_ITEMS + 50
        items = [{"name": f"t{i}"} for i in range(total)]
        result = _compress_list_result(json.dumps(items), "mcp__databricks__list_tables")
        assert str(total) in result

    def test_header_contains_tool_label(self):
        items = [{"name": f"t{i}"} for i in range(MAX_LIST_ITEMS + 5)]
        result = _compress_list_result(json.dumps(items), "mcp__databricks__list_tables")
        # Deve mencionar o nome da tool de alguma forma
        assert result is not None
        assert "[OUTPUT COMPRIMIDO" in result

    def test_compresses_text_fallback(self):
        output = _make_text_lines(MAX_LIST_ITEMS + 10, prefix="table_")
        result = _compress_list_result(output, "mcp__databricks__list_tables")
        assert result is not None

    def test_no_compression_for_empty_json_list(self):
        result = _compress_list_result("[]", "mcp__databricks__list_tables")
        assert result is None

    def test_no_compression_for_empty_json_dict(self):
        result = _compress_list_result('{"tables": []}', "mcp__databricks__list_tables")
        assert result is None


# ─── _compress_by_lines ──────────────────────────────────────────


class TestCompressByLines:
    def test_no_compression_under_limit(self):
        output = _make_text_lines(MAX_BASH_LINES)
        assert _compress_by_lines(output, MAX_BASH_LINES, "Bash") is None

    def test_compresses_over_limit(self):
        output = _make_text_lines(MAX_BASH_LINES + 50)
        result = _compress_by_lines(output, MAX_BASH_LINES, "Bash")
        assert result is not None
        lines = result.splitlines()
        # Linhas truncadas + 1 linha de rodapé
        assert len(lines) == MAX_BASH_LINES + 1

    def test_footer_mentions_omitted_count(self):
        omitted = 30
        output = _make_text_lines(MAX_BASH_LINES + omitted)
        result = _compress_by_lines(output, MAX_BASH_LINES, "Bash")
        assert str(omitted) in result

    def test_label_appears_in_footer(self):
        output = _make_text_lines(MAX_FILE_LINES + 5)
        result = _compress_by_lines(output, MAX_FILE_LINES, "Read/Grep")
        assert "Read/Grep" in result

    def test_single_line_no_compression(self):
        assert _compress_by_lines("apenas uma linha", 5, "Test") is None


# ─── _compress_by_chars ──────────────────────────────────────────


class TestCompressByChars:
    def test_no_compression_under_limit(self):
        output = "a" * MAX_OUTPUT_CHARS
        assert _compress_by_chars(output) is None

    def test_compresses_over_limit(self):
        output = "a" * (MAX_OUTPUT_CHARS + 1000)
        result = _compress_by_chars(output)
        assert result is not None
        assert len(result) < len(output)

    def test_truncated_content_starts_with_original(self):
        output = "abcdef" * 2000  # > MAX_OUTPUT_CHARS
        result = _compress_by_chars(output)
        assert result.startswith("abcdef")

    def test_footer_mentions_omitted_chars(self):
        extra = 500
        output = "x" * (MAX_OUTPUT_CHARS + extra)
        result = _compress_by_chars(output)
        assert str(extra) in result

    def test_exactly_at_limit_no_compression(self):
        output = "a" * MAX_OUTPUT_CHARS
        assert _compress_by_chars(output) is None


# ─── compress_tool_output (hook principal) ────────────────────────


class TestCompressToolOutputSqlTool:
    @pytest.mark.asyncio
    async def test_compresses_large_sql_result(self):
        output = _make_sql_rows(MAX_SQL_ROWS + 100)
        input_data = _make_hook_input("mcp__databricks__execute_sql", output)
        result = await compress_tool_output(input_data, tool_use_id="sql-1", context=None)
        assert "hookSpecificOutput" in result
        assert result["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
        compressed = result["hookSpecificOutput"]["toolResponse"]
        rows = json.loads(compressed.split("\n\n", 1)[1])
        assert len(rows) == MAX_SQL_ROWS

    @pytest.mark.asyncio
    async def test_no_compression_for_small_sql_result(self):
        output = _make_sql_rows(MAX_SQL_ROWS - 5)
        input_data = _make_hook_input("mcp__databricks__execute_sql", output)
        result = await compress_tool_output(input_data, tool_use_id="sql-2", context=None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_works_with_kusto_query_tool(self):
        output = _make_sql_rows(MAX_SQL_ROWS + 10)
        input_data = _make_hook_input("mcp__fabric_rti__kusto_query", output)
        result = await compress_tool_output(input_data, tool_use_id="kql-1", context=None)
        assert "hookSpecificOutput" in result


class TestCompressToolOutputListTool:
    @pytest.mark.asyncio
    async def test_compresses_large_list(self):
        output = _make_list_items(MAX_LIST_ITEMS + 20)
        input_data = _make_hook_input("mcp__databricks__list_tables", output)
        result = await compress_tool_output(input_data, tool_use_id="list-1", context=None)
        assert "hookSpecificOutput" in result

    @pytest.mark.asyncio
    async def test_no_compression_for_small_list(self):
        output = _make_list_items(MAX_LIST_ITEMS - 2)
        input_data = _make_hook_input("mcp__databricks__list_tables", output)
        result = await compress_tool_output(input_data, tool_use_id="list-2", context=None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_works_with_fabric_list_tools(self):
        output = _make_list_items(MAX_LIST_ITEMS + 5)
        for tool in ("mcp__fabric__list_workspaces", "mcp__fabric__list_lakehouses"):
            input_data = _make_hook_input(tool, output)
            result = await compress_tool_output(input_data, tool_use_id="list-3", context=None)
            assert "hookSpecificOutput" in result, f"{tool} não comprimiu"


class TestCompressToolOutputBashTool:
    @pytest.mark.asyncio
    async def test_compresses_large_bash_output(self):
        output = _make_text_lines(MAX_BASH_LINES + 50)
        input_data = _make_hook_input("Bash", output)
        result = await compress_tool_output(input_data, tool_use_id="bash-1", context=None)
        assert "hookSpecificOutput" in result
        lines = result["hookSpecificOutput"]["toolResponse"].splitlines()
        assert len(lines) <= MAX_BASH_LINES + 1

    @pytest.mark.asyncio
    async def test_no_compression_for_small_bash_output(self):
        output = _make_text_lines(MAX_BASH_LINES - 10)
        input_data = _make_hook_input("Bash", output)
        result = await compress_tool_output(input_data, tool_use_id="bash-2", context=None)
        assert result == {}


class TestCompressToolOutputReadTool:
    @pytest.mark.asyncio
    async def test_compresses_large_file(self):
        output = _make_text_lines(MAX_FILE_LINES + 100)
        input_data = _make_hook_input("Read", output)
        result = await compress_tool_output(input_data, tool_use_id="read-1", context=None)
        assert "hookSpecificOutput" in result

    @pytest.mark.asyncio
    async def test_no_compression_for_small_file(self):
        output = _make_text_lines(MAX_FILE_LINES - 20)
        input_data = _make_hook_input("Read", output)
        result = await compress_tool_output(input_data, tool_use_id="read-2", context=None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_grep_tool_also_compressed(self):
        output = _make_text_lines(MAX_FILE_LINES + 10)
        input_data = _make_hook_input("Grep", output)
        result = await compress_tool_output(input_data, tool_use_id="grep-1", context=None)
        assert "hookSpecificOutput" in result


class TestCompressToolOutputFallback:
    @pytest.mark.asyncio
    async def test_unknown_tool_uses_char_fallback(self):
        output = "x" * (MAX_OUTPUT_CHARS + 2000)
        input_data = _make_hook_input("mcp__unknown__some_tool", output)
        result = await compress_tool_output(input_data, tool_use_id="unk-1", context=None)
        assert "hookSpecificOutput" in result
        assert len(result["hookSpecificOutput"]["toolResponse"]) < len(output)

    @pytest.mark.asyncio
    async def test_unknown_tool_small_output_no_compression(self):
        output = "hello world"
        input_data = _make_hook_input("mcp__unknown__tool", output)
        result = await compress_tool_output(input_data, tool_use_id="unk-2", context=None)
        assert result == {}


class TestCompressToolOutputEdgeCases:
    @pytest.mark.asyncio
    async def test_returns_empty_dict_on_none_input(self):
        result = await compress_tool_output(None, tool_use_id=None, context=None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_on_empty_dict_input(self):
        result = await compress_tool_output({}, tool_use_id=None, context=None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_tool_name(self):
        result = await compress_tool_output(
            {"tool_response": "some output"}, tool_use_id=None, context=None
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_output(self):
        input_data = {"tool_name": "mcp__databricks__execute_sql", "tool_input": {}}
        result = await compress_tool_output(input_data, tool_use_id=None, context=None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_output_is_blank(self):
        input_data = _make_hook_input("mcp__databricks__execute_sql", "   ")
        result = await compress_tool_output(input_data, tool_use_id=None, context=None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_is_fail_safe_on_internal_exception(self, monkeypatch):
        """Hook nunca deve propagar exceções — retorna {} em caso de falha."""

        def raise_error(output, tool_name):
            raise RuntimeError("erro simulado na compressão")

        monkeypatch.setattr("compression.hook._compress_sql_result", raise_error)
        output = _make_sql_rows(MAX_SQL_ROWS + 10)
        input_data = _make_hook_input("mcp__databricks__execute_sql", output)
        result = await compress_tool_output(input_data, tool_use_id="err-1", context=None)
        assert result == {}


class TestCompressToolOutputLogging:
    @pytest.mark.asyncio
    async def test_logs_compression_event(self, caplog):
        import logging

        output = _make_sql_rows(MAX_SQL_ROWS + 50)
        input_data = _make_hook_input("mcp__databricks__execute_sql", output)

        with caplog.at_level(logging.INFO, logger="data_agents.output_compressor"):
            await compress_tool_output(input_data, tool_use_id="log-1", context=None)

        assert any("OUTPUT COMPRIMIDO" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_logs_reduction_percentage(self, caplog):
        import logging

        output = _make_sql_rows(MAX_SQL_ROWS + 100)
        input_data = _make_hook_input("mcp__databricks__execute_sql", output)

        with caplog.at_level(logging.INFO, logger="data_agents.output_compressor"):
            await compress_tool_output(input_data, tool_use_id="log-2", context=None)

        messages = " ".join(r.message for r in caplog.records)
        assert "redução" in messages or "%" in messages

    @pytest.mark.asyncio
    async def test_no_log_when_no_compression(self, caplog):
        import logging

        output = _make_sql_rows(MAX_SQL_ROWS - 5)
        input_data = _make_hook_input("mcp__databricks__execute_sql", output)

        with caplog.at_level(logging.INFO, logger="data_agents.output_compressor"):
            await compress_tool_output(input_data, tool_use_id="log-3", context=None)

        assert not any("OUTPUT COMPRIMIDO" in r.message for r in caplog.records)
