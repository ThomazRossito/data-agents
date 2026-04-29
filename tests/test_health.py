"""Testes para agents/health.py."""
from __future__ import annotations

import urllib.error
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# _check helper
# ---------------------------------------------------------------------------

def test_check_success():
    from agents.health import _check

    label, status = _check("teste", lambda: "tudo ok")
    assert label == "teste"
    assert status.startswith("✅")
    assert "tudo ok" in status


def test_check_health_warning():
    from agents.health import _check, _HealthWarning

    def raise_warning():
        raise _HealthWarning("credencial ausente")

    label, status = _check("teste", raise_warning)
    assert label == "teste"
    assert status.startswith("⚠️")
    assert "credencial ausente" in status


def test_check_generic_exception():
    from agents.health import _check

    def raise_error():
        raise ConnectionError("timeout")

    label, status = _check("teste", raise_error)
    assert label == "teste"
    assert status.startswith("❌")
    assert "timeout" in status


# ---------------------------------------------------------------------------
# _check_copilot
# ---------------------------------------------------------------------------

def test_check_copilot_no_token():
    from agents.health import _check_copilot, _HealthWarning

    settings = MagicMock()
    settings.github_token = None

    with pytest.raises(_HealthWarning, match="GITHUB_TOKEN"):
        _check_copilot(settings)


def test_check_copilot_reachable():
    from agents.health import _check_copilot

    settings = MagicMock()
    settings.github_token = "test_token"

    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_cm)
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_cm):
        result = _check_copilot(settings)
    assert "GitHub API" in result


# ---------------------------------------------------------------------------
# _check_databricks
# ---------------------------------------------------------------------------

def test_check_databricks_no_credentials():
    from agents.health import _check_databricks, _HealthWarning

    settings = MagicMock()
    settings.has_databricks.return_value = False

    with pytest.raises(_HealthWarning, match="DATABRICKS_HOST"):
        _check_databricks(settings)


def test_check_databricks_reachable():
    from agents.health import _check_databricks

    settings = MagicMock()
    settings.has_databricks.return_value = True
    settings.databricks_host = "https://adb-1234.azuredatabricks.net"
    settings.databricks_token = "dapi123"

    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_cm)
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_cm):
        result = _check_databricks(settings)
    assert "Databricks" in result


def test_check_databricks_http_401():
    from agents.health import _check_databricks

    settings = MagicMock()
    settings.has_databricks.return_value = True
    settings.databricks_host = "https://adb-1234.azuredatabricks.net"
    settings.databricks_token = "dapi_invalid"

    err = urllib.error.HTTPError(
        url="", code=401, msg="Unauthorized", hdrs={}, fp=None  # type: ignore[arg-type]
    )
    with patch("urllib.request.urlopen", side_effect=err):
        result = _check_databricks(settings)
    assert "401" in result


def test_check_databricks_http_500_raises():
    from agents.health import _check_databricks

    settings = MagicMock()
    settings.has_databricks.return_value = True
    settings.databricks_host = "https://adb-1234.azuredatabricks.net"
    settings.databricks_token = "dapi123"

    err = urllib.error.HTTPError(
        url="", code=500, msg="Internal", hdrs={}, fp=None  # type: ignore[arg-type]
    )
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(urllib.error.HTTPError):
            _check_databricks(settings)


# ---------------------------------------------------------------------------
# _check_fabric
# ---------------------------------------------------------------------------

def test_check_fabric_no_credentials():
    from agents.health import _check_fabric, _HealthWarning

    settings = MagicMock()
    settings.has_fabric.return_value = False

    with pytest.raises(_HealthWarning, match="AZURE_TENANT_ID"):
        _check_fabric(settings)


def test_check_fabric_http_401():
    from agents.health import _check_fabric

    settings = MagicMock()
    settings.has_fabric.return_value = True

    err = urllib.error.HTTPError(
        url="", code=401, msg="Unauthorized", hdrs={}, fp=None  # type: ignore[arg-type]
    )
    with patch("urllib.request.urlopen", side_effect=err):
        result = _check_fabric(settings)
    assert "401" in result


def test_check_fabric_reachable():
    from agents.health import _check_fabric

    settings = MagicMock()
    settings.has_fabric.return_value = True

    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_cm)
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_cm):
        result = _check_fabric(settings)
    assert "Fabric" in result


# ---------------------------------------------------------------------------
# run_health_check
# ---------------------------------------------------------------------------

def test_run_health_check_returns_agent_result():
    from agents.health import run_health_check

    # Mocka todos os checks individuais via _check para retornar status fixo
    def fake_check(label, fn):
        return label, "✅  ok"

    with patch("agents.health._check", side_effect=fake_check):
        result = run_health_check()

    assert "Health Check" in result.content
    assert result.tool_calls_count == 0
    assert result.tokens_used == 0


def test_run_health_check_contains_components():
    from agents.health import run_health_check

    def fake_check(label, fn):
        return label, "✅  ok"

    with patch("agents.health._check", side_effect=fake_check):
        result = run_health_check()

    assert "GitHub" in result.content or "Databricks" in result.content
    assert "|" in result.content  # tabela markdown
