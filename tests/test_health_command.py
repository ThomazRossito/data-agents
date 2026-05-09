"""Testes para commands/health.py — handler direto sem LLM."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from commands.health import (
    _build_platform_rows,
    _check_url,
    _tcp_reachable,
    handle_health_command,
    handle_health_command_chainlit,
)


# ── _tcp_reachable ──────────────────────────────────────────────────────────


class TestTcpReachable:
    def test_returns_true_on_successful_connect(self):
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        with patch("socket.create_connection", return_value=mock_conn):
            assert _tcp_reachable("example.com", 443) is True

    def test_returns_false_on_os_error(self):
        with patch("socket.create_connection", side_effect=OSError("timeout")):
            assert _tcp_reachable("unreachable.invalid", 443) is False


# ── _check_url ───────────────────────────────────────────────────────────────


class TestCheckUrl:
    def test_empty_url_returns_false(self):
        ok, detail = _check_url("")
        assert ok is False
        assert "URL" in detail

    def test_reachable_url(self):
        with patch("commands.health._tcp_reachable", return_value=True):
            ok, detail = _check_url("https://example.com")
        assert ok is True
        assert "TCP OK" in detail

    def test_unreachable_url(self):
        with patch("commands.health._tcp_reachable", return_value=False):
            ok, detail = _check_url("https://unreachable.invalid")
        assert ok is False
        assert "timeout" in detail.lower() or "recusada" in detail.lower()

    def test_http_defaults_to_port_80(self):
        with patch("commands.health._tcp_reachable", return_value=True) as mock_tcp:
            _check_url("http://example.com")
        mock_tcp.assert_called_once_with("example.com", 80, 3.0)

    def test_https_defaults_to_port_443(self):
        with patch("commands.health._tcp_reachable", return_value=True) as mock_tcp:
            _check_url("https://example.com")
        mock_tcp.assert_called_once_with("example.com", 443, 3.0)


# ── _build_platform_rows ─────────────────────────────────────────────────────


def _make_mock_settings(
    cred_status: dict, databricks_host: str = "", fabric_sql: str = "", kusto: str = ""
) -> MagicMock:
    """Build a mock settings object for _build_platform_rows tests."""
    s = MagicMock()
    s.validate_platform_credentials.return_value = cred_status
    s.databricks_host = databricks_host
    s.fabric_sql_endpoint = fabric_sql
    s.kusto_service_uri = kusto
    return s


class TestBuildPlatformRows:
    def test_skips_anthropic(self):
        creds = {
            "anthropic": {"ready": True, "missing": []},
            "databricks": {"ready": True, "missing": []},
        }
        mock_settings = _make_mock_settings(
            creds, databricks_host="https://adb.azuredatabricks.net"
        )
        with (
            patch("config.settings.settings", mock_settings),
            patch("config.mcp_servers.ALWAYS_ACTIVE_MCPS", []),
            patch("commands.health._check_url", return_value=(True, "TCP OK")),
        ):
            rows, ok, warn, err = _build_platform_rows()

        names = [r["name"] for r in rows]
        assert "anthropic" not in names

    def test_missing_creds_counted_as_err(self):
        creds = {"databricks": {"ready": False, "missing": ["DATABRICKS_TOKEN"]}}
        mock_settings = _make_mock_settings(creds)
        with (
            patch("config.settings.settings", mock_settings),
            patch("config.mcp_servers.ALWAYS_ACTIVE_MCPS", []),
        ):
            rows, ok, warn, err = _build_platform_rows()

        assert err == 1
        assert ok == 0
        assert warn == 0
        assert rows[0]["cred_ok"] is False
        assert "DATABRICKS_TOKEN" in rows[0]["detail"]

    def test_reachable_endpoint_counted_as_ok(self):
        creds = {"databricks": {"ready": True, "missing": []}}
        mock_settings = _make_mock_settings(
            creds, databricks_host="https://adb.azuredatabricks.net"
        )
        with (
            patch("config.settings.settings", mock_settings),
            patch("config.mcp_servers.ALWAYS_ACTIVE_MCPS", []),
            patch("commands.health._check_url", return_value=(True, "TCP OK")),
        ):
            rows, ok, warn, err = _build_platform_rows()

        assert ok == 1
        assert warn == 0
        assert err == 0
        assert rows[0]["reachable"] is True

    def test_unreachable_endpoint_counted_as_warn(self):
        creds = {"databricks": {"ready": True, "missing": []}}
        mock_settings = _make_mock_settings(
            creds, databricks_host="https://adb.azuredatabricks.net"
        )
        with (
            patch("config.settings.settings", mock_settings),
            patch("config.mcp_servers.ALWAYS_ACTIVE_MCPS", []),
            patch("commands.health._check_url", return_value=(False, "Conexão recusada / timeout")),
        ):
            rows, ok, warn, err = _build_platform_rows()

        assert warn == 1
        assert ok == 0
        assert rows[0]["reachable"] is False

    def test_always_active_with_no_endpoint_counted_as_ok(self):
        creds = {"context7": {"ready": False, "missing": []}}
        mock_settings = _make_mock_settings(creds)
        with (
            patch("config.settings.settings", mock_settings),
            patch("config.mcp_servers.ALWAYS_ACTIVE_MCPS", ["context7"]),
        ):
            rows, ok, warn, err = _build_platform_rows()

        assert ok == 1
        assert rows[0]["cred_ok"] is True


# ── handle_health_command ────────────────────────────────────────────────────


class TestHandleHealthCommand:
    def test_prints_table_to_console(self):
        fake_rows = [
            {
                "name": "databricks",
                "cred_ok": True,
                "reachable": True,
                "detail": "Endpoint alcançável",
                "missing": [],
            }
        ]
        with patch("commands.health._build_platform_rows", return_value=(fake_rows, 1, 0, 0)):
            console = MagicMock()
            handle_health_command(console)

        assert console.print.called

    def test_handles_empty_rows(self):
        with patch("commands.health._build_platform_rows", return_value=([], 0, 0, 0)):
            console = MagicMock()
            handle_health_command(console)

        assert console.print.called


# ── handle_health_command_chainlit ───────────────────────────────────────────


class TestHandleHealthCommandChainlit:
    def test_returns_markdown_string(self):
        fake_rows = [
            {
                "name": "databricks",
                "cred_ok": True,
                "reachable": True,
                "detail": "Endpoint alcançável",
                "missing": [],
            }
        ]
        with patch("commands.health._build_platform_rows", return_value=(fake_rows, 1, 0, 0)):
            result = handle_health_command_chainlit()

        assert isinstance(result, str)
        assert "databricks" in result
        assert "Health Check" in result

    def test_contains_summary_counts(self):
        fake_rows = [
            {
                "name": "databricks",
                "cred_ok": True,
                "reachable": True,
                "detail": "Endpoint alcançável",
                "missing": [],
            },
            {
                "name": "fabric_sql",
                "cred_ok": False,
                "reachable": None,
                "detail": "FABRIC_SQL_ENDPOINT",
                "missing": ["FABRIC_SQL_ENDPOINT"],
            },
        ]
        with patch("commands.health._build_platform_rows", return_value=(fake_rows, 1, 0, 1)):
            result = handle_health_command_chainlit()

        assert "1 OK" in result
        assert "1 inativos" in result

    def test_missing_creds_show_x_emoji(self):
        fake_rows = [
            {
                "name": "fabric",
                "cred_ok": False,
                "reachable": None,
                "detail": "AZURE_TENANT_ID",
                "missing": ["AZURE_TENANT_ID"],
            }
        ]
        with patch("commands.health._build_platform_rows", return_value=(fake_rows, 0, 0, 1)):
            result = handle_health_command_chainlit()

        assert "❌" in result

    def test_warning_shows_warning_emoji(self):
        fake_rows = [
            {
                "name": "databricks",
                "cred_ok": True,
                "reachable": False,
                "detail": "Conexão recusada / timeout",
                "missing": [],
            }
        ]
        with patch("commands.health._build_platform_rows", return_value=(fake_rows, 0, 1, 0)):
            result = handle_health_command_chainlit()

        assert "⚠️" in result

    def test_empty_rows_returns_valid_markdown(self):
        with patch("commands.health._build_platform_rows", return_value=([], 0, 0, 0)):
            result = handle_health_command_chainlit()

        assert isinstance(result, str)
        assert "0 OK" in result
