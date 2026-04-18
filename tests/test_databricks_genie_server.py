"""
Testes do MCP customizado databricks_genie.

Cobre:
  - Registry: parsing de DATABRICKS_GENIE_SPACES (valid, empty, malformed)
  - Resolver: nome amigável → space_id, space_id direto, default, erros
  - Credenciais: validação de DATABRICKS_HOST e DATABRICKS_TOKEN
  - server_config: estrutura do config dict e lista de tools
  - _error_response: formato da resposta em caso de exceção
"""

import json
import os
from unittest.mock import patch

import pytest

from mcp_servers.databricks_genie.server import (
    _error_response,
    _get_credentials,
    _get_spaces_registry,
    _resolve_friendly_name,
    _resolve_space_id,
)
from mcp_servers.databricks_genie.server_config import (
    DATABRICKS_GENIE_MCP_READONLY_TOOLS,
    DATABRICKS_GENIE_MCP_TOOLS,
    get_databricks_genie_mcp_config,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

SAMPLE_REGISTRY = {
    "retail-sales": "01f117197b5319fb972e10a45735b28c",
    "hr-analytics": "01abc123def456789000000000000000",
}


@pytest.fixture
def clean_env():
    """Remove variáveis de ambiente relevantes antes de cada teste."""
    keys = (
        "DATABRICKS_GENIE_SPACES",
        "DATABRICKS_GENIE_DEFAULT_SPACE",
        "DATABRICKS_HOST",
        "DATABRICKS_TOKEN",
    )
    preserved = {k: os.environ.pop(k, None) for k in keys}
    yield
    for k, v in preserved.items():
        if v is not None:
            os.environ[k] = v


# ─── Registry parsing ────────────────────────────────────────────────────────


class TestGetSpacesRegistry:
    def test_valid_json_returns_dict(self, clean_env):
        raw = json.dumps(SAMPLE_REGISTRY)
        with patch.dict(os.environ, {"DATABRICKS_GENIE_SPACES": raw}):
            registry = _get_spaces_registry()
        assert registry == SAMPLE_REGISTRY

    def test_empty_env_returns_empty_dict(self, clean_env):
        assert _get_spaces_registry() == {}

    def test_malformed_json_returns_empty_dict(self, clean_env):
        with patch.dict(os.environ, {"DATABRICKS_GENIE_SPACES": "not-valid-json"}):
            registry = _get_spaces_registry()
        assert registry == {}

    def test_non_object_json_raises(self, clean_env):
        # Array é JSON válido mas não é dict — deve erguer ValueError explicativo
        with patch.dict(os.environ, {"DATABRICKS_GENIE_SPACES": "[1, 2, 3]"}):
            with pytest.raises(ValueError, match="objeto JSON"):
                _get_spaces_registry()

    def test_whitespace_only_env_returns_empty(self, clean_env):
        with patch.dict(os.environ, {"DATABRICKS_GENIE_SPACES": "   \n\t   "}):
            assert _get_spaces_registry() == {}


# ─── Resolver de space_id ────────────────────────────────────────────────────


class TestResolveSpaceId:
    def test_friendly_name_in_registry(self, clean_env):
        raw = json.dumps(SAMPLE_REGISTRY)
        with patch.dict(os.environ, {"DATABRICKS_GENIE_SPACES": raw}):
            assert _resolve_space_id("retail-sales") == SAMPLE_REGISTRY["retail-sales"]

    def test_direct_space_id_passthrough(self, clean_env):
        # Se o space não está no registry, é assumido como space_id direto
        raw = json.dumps(SAMPLE_REGISTRY)
        with patch.dict(os.environ, {"DATABRICKS_GENIE_SPACES": raw}):
            sid = "01xyz999888777666555444333222111"
            assert _resolve_space_id(sid) == sid

    def test_default_from_registry(self, clean_env):
        raw = json.dumps(SAMPLE_REGISTRY)
        env = {
            "DATABRICKS_GENIE_SPACES": raw,
            "DATABRICKS_GENIE_DEFAULT_SPACE": "hr-analytics",
        }
        with patch.dict(os.environ, env):
            assert _resolve_space_id(None) == SAMPLE_REGISTRY["hr-analytics"]

    def test_default_as_direct_id_when_no_registry(self, clean_env):
        direct_id = "01f117197b5319fb972e10a45735b28c"
        with patch.dict(os.environ, {"DATABRICKS_GENIE_DEFAULT_SPACE": direct_id}):
            assert _resolve_space_id(None) == direct_id

    def test_default_not_in_registry_raises(self, clean_env):
        raw = json.dumps(SAMPLE_REGISTRY)
        env = {
            "DATABRICKS_GENIE_SPACES": raw,
            "DATABRICKS_GENIE_DEFAULT_SPACE": "nao-existe",
        }
        with patch.dict(os.environ, env):
            with pytest.raises(RuntimeError, match="não encontrado no registry"):
                _resolve_space_id(None)

    def test_no_config_raises_helpful_error(self, clean_env):
        with pytest.raises(RuntimeError, match="Nenhum Genie Space configurado"):
            _resolve_space_id(None)


# ─── Resolver reverso (space_id → friendly name) ─────────────────────────────


class TestResolveFriendlyName:
    def test_returns_friendly_name_when_found(self, clean_env):
        raw = json.dumps(SAMPLE_REGISTRY)
        with patch.dict(os.environ, {"DATABRICKS_GENIE_SPACES": raw}):
            assert _resolve_friendly_name(SAMPLE_REGISTRY["retail-sales"]) == "retail-sales"

    def test_returns_none_when_not_found(self, clean_env):
        raw = json.dumps(SAMPLE_REGISTRY)
        with patch.dict(os.environ, {"DATABRICKS_GENIE_SPACES": raw}):
            assert _resolve_friendly_name("01unknown0000000000000000000000") is None

    def test_returns_none_when_registry_empty(self, clean_env):
        assert _resolve_friendly_name("01anything") is None


# ─── Credenciais ─────────────────────────────────────────────────────────────


class TestGetCredentials:
    def test_both_set_returns_tuple(self, clean_env):
        env = {
            "DATABRICKS_HOST": "https://adb-123.azuredatabricks.net/",
            "DATABRICKS_TOKEN": "dapi-xxxxx",
        }
        with patch.dict(os.environ, env):
            host, token = _get_credentials()
        # Host deve vir sem trailing slash
        assert host == "https://adb-123.azuredatabricks.net"
        assert token == "dapi-xxxxx"

    def test_missing_host_raises(self, clean_env):
        with patch.dict(os.environ, {"DATABRICKS_TOKEN": "dapi-x"}):
            with pytest.raises(RuntimeError, match="DATABRICKS_HOST"):
                _get_credentials()

    def test_missing_token_raises(self, clean_env):
        with patch.dict(os.environ, {"DATABRICKS_HOST": "https://example"}):
            with pytest.raises(RuntimeError, match="DATABRICKS_TOKEN"):
                _get_credentials()


# ─── _error_response ─────────────────────────────────────────────────────────


class TestErrorResponse:
    def test_returns_valid_json(self):
        err = ValueError("boom")
        resp = _error_response(err)
        data = json.loads(resp)
        assert data["error"] == "boom"
        assert data["type"] == "ValueError"
        assert "traceback" in data


# ─── server_config ───────────────────────────────────────────────────────────


class TestServerConfig:
    def test_config_has_correct_structure(self):
        config = get_databricks_genie_mcp_config()
        assert "databricks_genie" in config
        entry = config["databricks_genie"]
        assert entry["type"] == "stdio"
        assert "command" in entry
        assert isinstance(entry["args"], list)
        assert set(entry["env"].keys()) >= {
            "DATABRICKS_HOST",
            "DATABRICKS_TOKEN",
            "DATABRICKS_GENIE_SPACES",
            "DATABRICKS_GENIE_DEFAULT_SPACE",
        }

    def test_mcp_tools_list_has_expected_tools(self):
        # Sanity check: lista não deve regredir silenciosamente
        assert "mcp__databricks_genie__genie_diagnostics" in DATABRICKS_GENIE_MCP_TOOLS
        assert "mcp__databricks_genie__genie_ask" in DATABRICKS_GENIE_MCP_TOOLS
        assert "mcp__databricks_genie__genie_create_or_update" in DATABRICKS_GENIE_MCP_TOOLS

    def test_readonly_subset_excludes_mutating_tools(self):
        mutating = {
            "mcp__databricks_genie__genie_create_or_update",
            "mcp__databricks_genie__genie_delete",
            "mcp__databricks_genie__genie_import",
        }
        readonly_set = set(DATABRICKS_GENIE_MCP_READONLY_TOOLS)
        assert readonly_set.isdisjoint(mutating)

    def test_all_tools_use_correct_namespace(self):
        for tool in DATABRICKS_GENIE_MCP_TOOLS:
            assert tool.startswith("mcp__databricks_genie__"), (
                f"Tool {tool} não está no namespace mcp__databricks_genie__"
            )
