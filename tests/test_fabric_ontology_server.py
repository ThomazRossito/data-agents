"""
Testes do MCP customizado fabric_ontology.

Cobre:
  - server_config: estrutura do config dict
  - MCP_TOOLS: lista não vazia, sem duplicatas
  - MCP_READONLY_TOOLS: subconjunto de MCP_TOOLS, apenas list_/get_/discover_/preview_/profile_
  - Aliases em MCP_TOOL_SETS (agents/loader.py)
  - fabric_ontology em ALWAYS_ACTIVE_MCPS (config/mcp_servers.py)
  - fabric_ontology em CREDENTIAL_FREE_MCPS (test_settings.py compatível)
"""

# ─── server_config ────────────────────────────────────────────────────────────


class TestFabricOntologyServerConfig:
    def test_config_returns_dict_with_fabric_ontology_key(self):
        from mcp_servers.fabric_ontology.server_config import (
            get_fabric_ontology_mcp_config,
        )

        config = get_fabric_ontology_mcp_config()
        assert isinstance(config, dict)
        assert "fabric_ontology" in config

    def test_config_type_is_stdio(self):
        from mcp_servers.fabric_ontology.server_config import (
            get_fabric_ontology_mcp_config,
        )

        config = get_fabric_ontology_mcp_config()
        assert config["fabric_ontology"]["type"] == "stdio"

    def test_config_command_is_string(self):
        from mcp_servers.fabric_ontology.server_config import (
            get_fabric_ontology_mcp_config,
        )

        config = get_fabric_ontology_mcp_config()
        assert isinstance(config["fabric_ontology"]["command"], str)
        assert config["fabric_ontology"]["command"]  # not empty

    def test_config_env_is_empty(self):
        """Auth via Azure CLI — nenhuma env var obrigatória."""
        from mcp_servers.fabric_ontology.server_config import (
            get_fabric_ontology_mcp_config,
        )

        config = get_fabric_ontology_mcp_config()
        assert config["fabric_ontology"]["env"] == {}


# ─── MCP_TOOLS ────────────────────────────────────────────────────────────────


class TestFabricOntologyMcpTools:
    def test_mcp_tools_not_empty(self):
        from mcp_servers.fabric_ontology.server_config import MCP_TOOLS

        assert MCP_TOOLS
        assert len(MCP_TOOLS) > 0

    def test_mcp_tools_no_duplicates(self):
        from mcp_servers.fabric_ontology.server_config import MCP_TOOLS

        assert len(MCP_TOOLS) == len(set(MCP_TOOLS))

    def test_mcp_tools_correct_prefix(self):
        from mcp_servers.fabric_ontology.server_config import MCP_TOOLS

        for tool in MCP_TOOLS:
            assert tool.startswith("mcp__fabric_ontology__"), (
                f"Tool incorrectamente prefixado: {tool}"
            )

    def test_mcp_tools_includes_core_tools(self):
        from mcp_servers.fabric_ontology.server_config import MCP_TOOLS

        required = [
            "mcp__fabric_ontology__list_ontologies",
            "mcp__fabric_ontology__get_ontology",
            "mcp__fabric_ontology__create_ontology",
            "mcp__fabric_ontology__list_entity_types",
            "mcp__fabric_ontology__add_entity_type",
            "mcp__fabric_ontology__list_relationship_types",
            "mcp__fabric_ontology__add_relationship_type",
            "mcp__fabric_ontology__list_contextualizations",
            "mcp__fabric_ontology__add_contextualization",
        ]
        for tool in required:
            assert tool in MCP_TOOLS, f"Tool obrigatória ausente: {tool}"


# ─── MCP_READONLY_TOOLS ────────────────────────────────────────────────────────


class TestFabricOntologyReadonlyTools:
    def test_readonly_is_subset_of_all(self):
        from mcp_servers.fabric_ontology.server_config import (
            MCP_READONLY_TOOLS,
            MCP_TOOLS,
        )

        for tool in MCP_READONLY_TOOLS:
            assert tool in MCP_TOOLS, f"Readonly tool não está em MCP_TOOLS: {tool}"

    def test_readonly_tools_not_empty(self):
        from mcp_servers.fabric_ontology.server_config import MCP_READONLY_TOOLS

        assert MCP_READONLY_TOOLS

    def test_readonly_tools_only_safe_prefixes(self):
        from mcp_servers.fabric_ontology.server_config import MCP_READONLY_TOOLS

        safe = ("list_", "get_", "discover_", "preview_", "profile_")
        for tool in MCP_READONLY_TOOLS:
            suffix = tool.removeprefix("mcp__fabric_ontology__")
            assert any(suffix.startswith(p) for p in safe), (
                f"Readonly tool com operação mutante: {tool}"
            )

    def test_write_tools_not_in_readonly(self):
        from mcp_servers.fabric_ontology.server_config import MCP_READONLY_TOOLS

        mutating_prefixes = ("add_", "create_", "update_", "remove_", "delete_", "set_")
        for tool in MCP_READONLY_TOOLS:
            suffix = tool.removeprefix("mcp__fabric_ontology__")
            assert not any(suffix.startswith(p) for p in mutating_prefixes), (
                f"Operação mutante encontrada em readonly: {tool}"
            )


# ─── Integração com loader.py ─────────────────────────────────────────────────


class TestFabricOntologyAliases:
    def test_fabric_ontology_all_alias_exists(self):
        from agents.loader import MCP_TOOL_SETS

        assert "fabric_ontology_all" in MCP_TOOL_SETS
        assert MCP_TOOL_SETS["fabric_ontology_all"]

    def test_fabric_ontology_readonly_alias_exists(self):
        from agents.loader import MCP_TOOL_SETS

        assert "fabric_ontology_readonly" in MCP_TOOL_SETS
        assert MCP_TOOL_SETS["fabric_ontology_readonly"]

    def test_readonly_alias_is_subset_of_all_alias(self):
        from agents.loader import MCP_TOOL_SETS

        all_tools = set(MCP_TOOL_SETS["fabric_ontology_all"])
        readonly_tools = set(MCP_TOOL_SETS["fabric_ontology_readonly"])
        assert readonly_tools.issubset(all_tools)


# ─── Integração com ALWAYS_ACTIVE_MCPS ────────────────────────────────────────


class TestFabricOntologyAlwaysActive:
    def test_fabric_ontology_in_always_active_mcps(self):
        from config.mcp_servers import ALWAYS_ACTIVE_MCPS

        assert "fabric_ontology" in ALWAYS_ACTIVE_MCPS

    def test_fabric_ontology_in_all_mcp_configs(self):
        from config.mcp_servers import ALL_MCP_CONFIGS

        assert "fabric_ontology" in ALL_MCP_CONFIGS

    def test_fabric_ontology_config_callable(self):
        from config.mcp_servers import ALL_MCP_CONFIGS

        config_fn = ALL_MCP_CONFIGS["fabric_ontology"]
        assert callable(config_fn)
        result = config_fn()
        assert isinstance(result, dict)
        assert "fabric_ontology" in result
