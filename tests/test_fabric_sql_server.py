"""
Testes do MCP customizado fabric_sql.

Cobre:
  - Registry: parsing de FABRIC_SQL_LAKEHOUSES (valid, empty, malformed)
  - Resolver: nome → (endpoint, database), default, legacy fallback, erros
  - Serialização: datetime, bytes, NaN, strings
  - _error_response: formato da resposta em caso de exceção
  - server_config: estrutura do config dict e lista de tools
"""

import json
import math
import os
from datetime import datetime
from unittest.mock import patch

import pytest

from mcp_servers.fabric_sql.server import (
    _error_response,
    _get_registry,
    _resolve_connection_params,
    _serialize_row,
)
from mcp_servers.fabric_sql.server_config import (
    FABRIC_SQL_MCP_TOOLS,
    get_fabric_sql_mcp_config,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

SAMPLE_REGISTRY = {
    "TARN_LH_DEV": "tarn-dev.datawarehouse.fabric.microsoft.com",
    "TARN_LH_PROD": "tarn-prod.datawarehouse.fabric.microsoft.com",
}


@pytest.fixture
def clean_env():
    """Remove variáveis de ambiente relevantes antes de cada teste."""
    keys = (
        "FABRIC_SQL_LAKEHOUSES",
        "FABRIC_SQL_DEFAULT_LAKEHOUSE",
        "FABRIC_SQL_ENDPOINT",
        "FABRIC_LAKEHOUSE_NAME",
        "AZURE_TENANT_ID",
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET",
    )
    preserved = {k: os.environ.pop(k, None) for k in keys}
    yield
    for k, v in preserved.items():
        if v is not None:
            os.environ[k] = v


# ─── Registry parsing ────────────────────────────────────────────────────────


class TestGetRegistry:
    def test_valid_json_returns_dict(self, clean_env):
        raw = json.dumps(SAMPLE_REGISTRY)
        with patch.dict(os.environ, {"FABRIC_SQL_LAKEHOUSES": raw}):
            registry = _get_registry()
        assert registry == SAMPLE_REGISTRY

    def test_empty_env_returns_empty_dict(self, clean_env):
        assert _get_registry() == {}

    def test_malformed_json_returns_empty_dict(self, clean_env):
        with patch.dict(os.environ, {"FABRIC_SQL_LAKEHOUSES": "not-valid-json"}):
            assert _get_registry() == {}

    def test_non_object_json_raises(self, clean_env):
        # Array é JSON válido mas não é dict — deve erguer ValueError
        with patch.dict(os.environ, {"FABRIC_SQL_LAKEHOUSES": '["a", "b"]'}):
            with pytest.raises(ValueError, match="objeto JSON"):
                _get_registry()

    def test_whitespace_only_env_returns_empty(self, clean_env):
        with patch.dict(os.environ, {"FABRIC_SQL_LAKEHOUSES": "   \n\t   "}):
            assert _get_registry() == {}


# ─── Resolver de conexão ─────────────────────────────────────────────────────


class TestResolveConnectionParams:
    def test_explicit_lakehouse_in_registry(self, clean_env):
        raw = json.dumps(SAMPLE_REGISTRY)
        with patch.dict(os.environ, {"FABRIC_SQL_LAKEHOUSES": raw}):
            endpoint, db = _resolve_connection_params("TARN_LH_DEV")
        assert endpoint == SAMPLE_REGISTRY["TARN_LH_DEV"]
        assert db == "TARN_LH_DEV"

    def test_explicit_lakehouse_not_in_registry_raises(self, clean_env):
        raw = json.dumps(SAMPLE_REGISTRY)
        with patch.dict(os.environ, {"FABRIC_SQL_LAKEHOUSES": raw}):
            with pytest.raises(RuntimeError, match="não encontrado no registry"):
                _resolve_connection_params("LAKEHOUSE_INEXISTENTE")

    def test_default_from_registry(self, clean_env):
        raw = json.dumps(SAMPLE_REGISTRY)
        env = {
            "FABRIC_SQL_LAKEHOUSES": raw,
            "FABRIC_SQL_DEFAULT_LAKEHOUSE": "TARN_LH_PROD",
        }
        with patch.dict(os.environ, env):
            endpoint, db = _resolve_connection_params(None)
        assert endpoint == SAMPLE_REGISTRY["TARN_LH_PROD"]
        assert db == "TARN_LH_PROD"

    def test_default_not_in_registry_raises(self, clean_env):
        raw = json.dumps(SAMPLE_REGISTRY)
        env = {
            "FABRIC_SQL_LAKEHOUSES": raw,
            "FABRIC_SQL_DEFAULT_LAKEHOUSE": "NAO_EXISTE",
        }
        with patch.dict(os.environ, env):
            with pytest.raises(RuntimeError, match="não encontrado no registry"):
                _resolve_connection_params(None)

    def test_legacy_fallback(self, clean_env):
        env = {
            "FABRIC_SQL_ENDPOINT": "legacy-ws.datawarehouse.fabric.microsoft.com",
            "FABRIC_LAKEHOUSE_NAME": "LEGACY_LH",
        }
        with patch.dict(os.environ, env):
            endpoint, db = _resolve_connection_params(None)
        assert endpoint == "legacy-ws.datawarehouse.fabric.microsoft.com"
        assert db == "LEGACY_LH"

    def test_no_config_raises_helpful_error(self, clean_env):
        with pytest.raises(RuntimeError, match="Nenhum lakehouse configurado"):
            _resolve_connection_params(None)


# ─── Serialização de linhas ──────────────────────────────────────────────────


class TestSerializeRow:
    def test_none_passthrough(self):
        assert _serialize_row([None, None]) == [None, None]

    def test_datetime_isoformat(self):
        dt = datetime(2026, 4, 17, 12, 30, 45)
        result = _serialize_row([dt])
        assert result == ["2026-04-17T12:30:45"]

    def test_bytes_to_hex(self):
        assert _serialize_row([b"\x01\x02\xff"]) == ["0102ff"]

    def test_bytearray_to_hex(self):
        assert _serialize_row([bytearray(b"\xab\xcd")]) == ["abcd"]

    def test_nan_becomes_none(self):
        result = _serialize_row([math.nan])
        assert result == [None]

    def test_strings_and_ints_passthrough(self):
        assert _serialize_row(["hello", 42, 3.14]) == ["hello", 42, 3.14]


# ─── _error_response ─────────────────────────────────────────────────────────


class TestErrorResponse:
    def test_returns_valid_json(self):
        err = RuntimeError("boom")
        resp = _error_response(err)
        data = json.loads(resp)
        assert data["error"] == "boom"
        assert data["type"] == "RuntimeError"
        assert "traceback" in data


# ─── server_config ───────────────────────────────────────────────────────────


class TestServerConfig:
    def test_config_has_correct_structure(self):
        config = get_fabric_sql_mcp_config()
        assert "fabric_sql" in config
        entry = config["fabric_sql"]
        assert entry["type"] == "stdio"
        assert "command" in entry
        assert isinstance(entry["args"], list)
        # Env deve conter credenciais Azure + registry + fallback legado
        expected_keys = {
            "AZURE_TENANT_ID",
            "AZURE_CLIENT_ID",
            "AZURE_CLIENT_SECRET",
            "FABRIC_SQL_LAKEHOUSES",
            "FABRIC_SQL_DEFAULT_LAKEHOUSE",
            "FABRIC_SQL_ENDPOINT",
            "FABRIC_LAKEHOUSE_NAME",
        }
        assert set(entry["env"].keys()) >= expected_keys

    def test_mcp_tools_list_has_expected_tools(self):
        # Sanity check: lista não deve regredir silenciosamente
        assert "mcp__fabric_sql__fabric_sql_list_lakehouses" in FABRIC_SQL_MCP_TOOLS
        assert "mcp__fabric_sql__fabric_sql_execute" in FABRIC_SQL_MCP_TOOLS
        assert "mcp__fabric_sql__fabric_sql_diagnostics" in FABRIC_SQL_MCP_TOOLS

    def test_all_tools_use_correct_namespace(self):
        for tool in FABRIC_SQL_MCP_TOOLS:
            assert tool.startswith("mcp__fabric_sql__"), (
                f"Tool {tool} não está no namespace mcp__fabric_sql__"
            )
