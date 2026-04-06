"""
Testes para agents/supervisor.py.

Cobre:
  - build_supervisor_options(): construção com mocks do SDK
  - Parâmetros: platforms, enable_thinking
  - Configuração de hooks, MCP servers, modelo e permissões
"""

from unittest.mock import MagicMock, patch


class TestBuildSupervisorOptions:
    """Testes para a factory build_supervisor_options."""

    def _make_mock_options_class(self):
        """Retorna um mock de ClaudeAgentOptions que captura os kwargs."""
        mock_instance = MagicMock()
        mock_class = MagicMock(return_value=mock_instance)
        return mock_class, mock_instance

    def test_build_returns_agent_options(self):
        """Verifica que build_supervisor_options retorna um objeto (ClaudeAgentOptions)."""
        mock_class, mock_instance = self._make_mock_options_class()
        with patch("agents.supervisor.ClaudeAgentOptions", mock_class):
            from agents.supervisor import build_supervisor_options
            result = build_supervisor_options()
            assert result is mock_instance
            mock_class.assert_called_once()

    def test_build_calls_load_all_agents(self):
        """Verifica que os agentes do registry são carregados."""
        mock_class, _ = self._make_mock_options_class()
        with patch("agents.supervisor.ClaudeAgentOptions", mock_class):
            with patch("agents.supervisor.load_all_agents") as mock_load:
                mock_load.return_value = {"sql-expert": MagicMock()}
                from agents.supervisor import build_supervisor_options
                build_supervisor_options()
                mock_load.assert_called_once()

    def test_build_calls_build_mcp_registry_with_platforms(self):
        """Verifica que build_mcp_registry recebe as plataformas corretas."""
        mock_class, _ = self._make_mock_options_class()
        with patch("agents.supervisor.ClaudeAgentOptions", mock_class):
            with patch("agents.supervisor.build_mcp_registry") as mock_mcp:
                mock_mcp.return_value = []
                from agents.supervisor import build_supervisor_options
                build_supervisor_options(platforms=["databricks"])
                mock_mcp.assert_called_once_with(["databricks"])

    def test_build_with_no_platforms_passes_none(self):
        """Verifica que None é passado para build_mcp_registry quando platforms=None."""
        mock_class, _ = self._make_mock_options_class()
        with patch("agents.supervisor.ClaudeAgentOptions", mock_class):
            with patch("agents.supervisor.build_mcp_registry") as mock_mcp:
                mock_mcp.return_value = []
                from agents.supervisor import build_supervisor_options
                build_supervisor_options()
                mock_mcp.assert_called_once_with(None)

    def test_build_thinking_disabled_by_default(self):
        """Verifica que thinking está desabilitado por padrão."""
        mock_class, _ = self._make_mock_options_class()
        captured_kwargs = {}

        def capture(**kwargs):
            captured_kwargs.update(kwargs)
            return MagicMock()

        mock_class.side_effect = capture
        with patch("agents.supervisor.ClaudeAgentOptions", mock_class):
            with patch("agents.supervisor.build_mcp_registry", return_value=[]):
                from agents.supervisor import build_supervisor_options
                build_supervisor_options(enable_thinking=False)
                assert captured_kwargs.get("thinking") == {"type": "disabled"}

    def test_build_thinking_enabled(self):
        """Verifica que thinking com budget é configurado quando enable_thinking=True."""
        mock_class, _ = self._make_mock_options_class()
        captured_kwargs = {}

        def capture(**kwargs):
            captured_kwargs.update(kwargs)
            return MagicMock()

        mock_class.side_effect = capture
        with patch("agents.supervisor.ClaudeAgentOptions", mock_class):
            with patch("agents.supervisor.build_mcp_registry", return_value=[]):
                from agents.supervisor import build_supervisor_options
                build_supervisor_options(enable_thinking=True)
                thinking = captured_kwargs.get("thinking")
                assert thinking is not None
                assert thinking["type"] == "enabled"
                assert thinking["budget_tokens"] == 8000

    def test_build_uses_bypass_permissions(self):
        """Verifica que permission_mode é bypassPermissions."""
        mock_class, _ = self._make_mock_options_class()
        captured_kwargs = {}

        def capture(**kwargs):
            captured_kwargs.update(kwargs)
            return MagicMock()

        mock_class.side_effect = capture
        with patch("agents.supervisor.ClaudeAgentOptions", mock_class):
            with patch("agents.supervisor.build_mcp_registry", return_value=[]):
                from agents.supervisor import build_supervisor_options
                build_supervisor_options()
                assert captured_kwargs.get("permission_mode") == "bypassPermissions"

    def test_build_has_hooks_configured(self):
        """Verifica que os três hooks são configurados."""
        mock_class, _ = self._make_mock_options_class()
        captured_kwargs = {}

        def capture(**kwargs):
            captured_kwargs.update(kwargs)
            return MagicMock()

        mock_class.side_effect = capture
        with patch("agents.supervisor.ClaudeAgentOptions", mock_class):
            with patch("agents.supervisor.build_mcp_registry", return_value=[]):
                from agents.supervisor import build_supervisor_options
                build_supervisor_options()
                hooks = captured_kwargs.get("hooks", {})
                assert "PostToolUse" in hooks
                assert "PreToolUse" in hooks
                assert len(hooks["PostToolUse"]) == 2  # audit + cost guard
                assert len(hooks["PreToolUse"]) == 1   # security

    def test_build_includes_partial_messages(self):
        """Verifica que include_partial_messages está ativo para feedback visual."""
        mock_class, _ = self._make_mock_options_class()
        captured_kwargs = {}

        def capture(**kwargs):
            captured_kwargs.update(kwargs)
            return MagicMock()

        mock_class.side_effect = capture
        with patch("agents.supervisor.ClaudeAgentOptions", mock_class):
            with patch("agents.supervisor.build_mcp_registry", return_value=[]):
                from agents.supervisor import build_supervisor_options
                build_supervisor_options()
                assert captured_kwargs.get("include_partial_messages") is True
