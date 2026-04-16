"""
Testes do MCP customizado migration_source.

Cobre:
  - Registry: parsing de MIGRATION_SOURCES, resolução de fonte default
  - Resolver: fonte explícita, default, não encontrada, registry vazio
  - server_config: estrutura do config dict e lista de tools
  - settings: validação de migration_source nas credenciais
"""

import json
import os
from unittest.mock import patch

import pytest

from mcp_servers.migration_source.server_config import (
    MIGRATION_SOURCE_MCP_TOOLS,
    get_migration_source_mcp_config,
)
from mcp_servers.migration_source.server import _get_registry, _resolve_source_config


# ─── Fixtures ────────────────────────────────────────────────────────────────

SAMPLE_REGISTRY = {
    "ERP_PROD": {
        "type": "sqlserver",
        "host": "10.0.0.1",
        "port": 1433,
        "database": "ERP",
        "user": "sa",
        "password": "secret",
    },
    "ANALYTICS": {
        "type": "postgresql",
        "host": "10.0.0.2",
        "port": 5432,
        "database": "analytics",
        "user": "postgres",
        "password": "secret",
    },
}


# ─── Testes do Registry ───────────────────────────────────────────────────────


class TestGetRegistry:
    """Testes para a função _get_registry()."""

    def test_valid_json_returns_dict(self):
        raw = json.dumps(SAMPLE_REGISTRY)
        with patch.dict(os.environ, {"MIGRATION_SOURCES": raw}):
            registry = _get_registry()
        assert isinstance(registry, dict)
        assert len(registry) == 2
        assert "ERP_PROD" in registry
        assert "ANALYTICS" in registry

    def test_empty_env_returns_empty_dict(self):
        with patch.dict(os.environ, {"MIGRATION_SOURCES": ""}, clear=False):
            # Remove key to simulate missing env var
            env = {k: v for k, v in os.environ.items() if k != "MIGRATION_SOURCES"}
            with patch.dict(os.environ, env, clear=True):
                registry = _get_registry()
        assert registry == {}

    def test_invalid_json_returns_empty_dict(self):
        with patch.dict(os.environ, {"MIGRATION_SOURCES": "not-valid-json"}):
            registry = _get_registry()
        assert registry == {}

    def test_non_dict_json_returns_empty_dict(self):
        with patch.dict(os.environ, {"MIGRATION_SOURCES": '["lista", "nao", "dict"]'}):
            registry = _get_registry()
        assert registry == {}

    def test_registry_preserves_source_config(self):
        raw = json.dumps(SAMPLE_REGISTRY)
        with patch.dict(os.environ, {"MIGRATION_SOURCES": raw}):
            registry = _get_registry()
        assert registry["ERP_PROD"]["type"] == "sqlserver"
        assert registry["ERP_PROD"]["host"] == "10.0.0.1"
        assert registry["ANALYTICS"]["type"] == "postgresql"


# ─── Testes do Resolver ───────────────────────────────────────────────────────


class TestResolveSourceConfig:
    """Testes para a função _resolve_source_config()."""

    def _patch_env(self, sources: dict | None = None, default: str = ""):
        raw = json.dumps(sources or SAMPLE_REGISTRY)
        return patch.dict(
            os.environ,
            {"MIGRATION_SOURCES": raw, "MIGRATION_DEFAULT_SOURCE": default},
        )

    def test_explicit_source_found(self):
        with self._patch_env():
            name, config = _resolve_source_config("ANALYTICS")
        assert name == "ANALYTICS"
        assert config["type"] == "postgresql"

    def test_explicit_source_not_found_raises(self):
        with self._patch_env():
            with pytest.raises(RuntimeError, match="não encontrada no registry"):
                _resolve_source_config("INEXISTENTE")

    def test_default_source_used_when_none(self):
        with self._patch_env(default="ERP_PROD"):
            name, config = _resolve_source_config(None)
        assert name == "ERP_PROD"
        assert config["type"] == "sqlserver"

    def test_default_not_in_registry_raises(self):
        with self._patch_env(default="NAO_EXISTE"):
            with pytest.raises(RuntimeError, match="não encontrado no registry"):
                _resolve_source_config(None)

    def test_no_registry_raises(self):
        with patch.dict(os.environ, {"MIGRATION_SOURCES": "{}", "MIGRATION_DEFAULT_SOURCE": ""}):
            with pytest.raises(RuntimeError, match="Nenhuma fonte de migração configurada"):
                _resolve_source_config(None)

    def test_first_source_used_as_fallback_when_no_default(self):
        with self._patch_env(default=""):
            name, config = _resolve_source_config(None)
        # Sem default, usa a primeira do registry
        assert name in SAMPLE_REGISTRY
        assert "type" in config


# ─── Testes do server_config ─────────────────────────────────────────────────


class TestMigrationSourceMcpConfig:
    """Testes para get_migration_source_mcp_config() e lista de tools."""

    def test_config_returns_migration_source_key(self):
        from config.settings import Settings

        s = Settings(
            migration_sources='{"TEST": {"type": "sqlserver", "host": "x", "port": 1433, "database": "db", "user": "u", "password": "p"}}',
            migration_default_source="TEST",
            migration_source_command="migration-source-mcp",
        )
        with patch("config.settings.settings", s):
            config = get_migration_source_mcp_config()
        assert "migration_source" in config
        assert config["migration_source"]["type"] == "stdio"
        assert "command" in config["migration_source"]

    def test_tool_list_has_expected_count(self):
        assert len(MIGRATION_SOURCE_MCP_TOOLS) == 15

    def test_tool_list_all_prefixed_correctly(self):
        for tool in MIGRATION_SOURCE_MCP_TOOLS:
            assert tool.startswith("mcp__migration_source__"), (
                f"Tool '{tool}' não segue convenção mcp__migration_source__*"
            )

    def test_tool_list_contains_diagnostics(self):
        assert "mcp__migration_source__migration_source_diagnostics" in MIGRATION_SOURCE_MCP_TOOLS

    def test_tool_list_contains_list_sources(self):
        assert "mcp__migration_source__migration_source_list_sources" in MIGRATION_SOURCE_MCP_TOOLS

    def test_tool_list_contains_ddl_tool(self):
        assert "mcp__migration_source__migration_source_get_table_ddl" in MIGRATION_SOURCE_MCP_TOOLS

    def test_tool_list_contains_procedures(self):
        assert (
            "mcp__migration_source__migration_source_get_procedure_definition"
            in MIGRATION_SOURCE_MCP_TOOLS
        )

    def test_tool_list_contains_schema_summary(self):
        assert (
            "mcp__migration_source__migration_source_get_schema_summary"
            in MIGRATION_SOURCE_MCP_TOOLS
        )


# ─── Testes de Integração com Settings ───────────────────────────────────────


class TestMigrationSourceSettings:
    """Testes para validação de migration_source no settings."""

    def test_migration_source_not_ready_without_sources(self):
        from config.settings import Settings

        s = Settings(migration_sources="{}", migration_default_source="")
        status = s.validate_platform_credentials()
        assert "migration_source" in status
        assert not status["migration_source"]["ready"]
        assert "MIGRATION_SOURCES" in status["migration_source"]["missing"]

    def test_migration_source_ready_with_sources(self):
        from config.settings import Settings

        raw = json.dumps(SAMPLE_REGISTRY)
        s = Settings(migration_sources=raw, migration_default_source="ERP_PROD")
        status = s.validate_platform_credentials()
        assert status["migration_source"]["ready"]
        assert status["migration_source"]["missing"] == []

    def test_migration_source_not_in_credential_free_mcps(self):
        """migration_source requer credenciais — não deve ser tratado como free MCP."""
        from config.settings import Settings

        s = Settings(migration_sources="{}")
        status = s.validate_platform_credentials()
        # Não deve estar ready quando sem configuração
        assert not status["migration_source"]["ready"]
