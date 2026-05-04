"""Testes para commands/mcp.py — display de status dos MCP servers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

_FAKE_STATUS = {
    "anthropic": {"ready": True, "missing": []},
    "databricks": {"ready": True, "missing": []},
    "fabric": {"ready": False, "missing": ["AZURE_TENANT_ID", "FABRIC_WORKSPACE_ID"]},
    "context7": {"ready": True, "missing": []},
    "memory_mcp": {"ready": True, "missing": []},
    "tavily": {"ready": False, "missing": ["TAVILY_API_KEY"]},
}


@pytest.fixture()
def mock_settings():
    # Pydantic v2 proíbe setattr em instâncias; patchamos na classe.
    with patch(
        "config.settings.Settings.validate_platform_credentials",
        return_value=_FAKE_STATUS,
    ):
        yield


# ── handle_mcp_command_chainlit ───────────────────────────────────────────────


class TestHandleMcpCommandChainlit:
    def test_returns_markdown_string(self, mock_settings):
        from commands.mcp import handle_mcp_command_chainlit

        result = handle_mcp_command_chainlit("/mcp")
        assert isinstance(result, str)
        assert "Status dos MCP Servers" in result
        assert "|" in result  # é uma tabela Markdown

    def test_active_mcps_shown_as_green(self, mock_settings):
        from commands.mcp import handle_mcp_command_chainlit

        result = handle_mcp_command_chainlit("/mcp")
        assert "🟢 ATIVO" in result

    def test_inactive_mcps_show_missing_keys(self, mock_settings):
        from commands.mcp import handle_mcp_command_chainlit

        result = handle_mcp_command_chainlit("/mcp")
        assert "🔴 INATIVO" in result
        assert "TAVILY_API_KEY" in result

    def test_always_active_mcps_no_credential_message(self, mock_settings):
        from commands.mcp import handle_mcp_command_chainlit

        result = handle_mcp_command_chainlit("/mcp")
        assert "Sem credenciais" in result

    def test_filter_by_name(self, mock_settings):
        from commands.mcp import handle_mcp_command_chainlit

        result = handle_mcp_command_chainlit("/mcp tavily")
        assert "tavily" in result
        assert "databricks" not in result

    def test_filter_no_match_returns_header_only(self, mock_settings):
        from commands.mcp import handle_mcp_command_chainlit

        result = handle_mcp_command_chainlit("/mcp nonexistent_xyz")
        assert "Status dos MCP Servers" in result
        assert "databricks" not in result

    def test_anthropic_entry_excluded(self, mock_settings):
        from commands.mcp import handle_mcp_command_chainlit

        result = handle_mcp_command_chainlit("/mcp")
        # anthropic não deve aparecer na tabela de MCPs
        lines = [line for line in result.splitlines() if "anthropic" in line.lower()]
        assert len(lines) == 0

    def test_summary_line_with_counts(self, mock_settings):
        from commands.mcp import handle_mcp_command_chainlit

        result = handle_mcp_command_chainlit("/mcp")
        # Deve conter contagens de ativos e inativos
        assert "ativos" in result
        assert "inativos" in result


# ── handle_mcp_command (CLI / Rich) ──────────────────────────────────────────


class TestHandleMcpCommandCli:
    def test_prints_table_to_console(self, mock_settings):
        from commands.mcp import handle_mcp_command

        console = MagicMock()
        handle_mcp_command("/mcp", console)
        assert console.print.called

    def test_filter_restricts_output(self, mock_settings):
        from commands.mcp import handle_mcp_command

        console = MagicMock()
        handle_mcp_command("/mcp context7", console)
        # Deve ter impresso a tabela
        assert console.print.called

    def test_no_summary_line_when_filter_active(self, mock_settings):
        from commands.mcp import handle_mcp_command

        console = MagicMock()
        handle_mcp_command("/mcp context7", console)
        # Quando há filtro, o summary de totais não é impresso
        # (apenas a tabela e nada mais)
        call_texts = [str(c) for c in console.print.call_args_list]
        has_summary = any("total" in t.lower() for t in call_texts)
        assert not has_summary
