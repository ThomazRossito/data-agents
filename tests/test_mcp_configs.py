"""Testes de configuração dos servidores MCP."""

from mcp_servers.databricks.server_config import get_databricks_mcp_config, DATABRICKS_MCP_TOOLS
from mcp_servers.fabric.server_config import get_fabric_mcp_config, ALL_FABRIC_TOOLS
from mcp_servers.fabric_rti.server_config import get_fabric_rti_mcp_config, FABRIC_RTI_MCP_TOOLS
from config.mcp_servers import build_mcp_registry


def test_databricks_config_has_required_keys():
    config = get_databricks_mcp_config()
    assert "databricks" in config
    server = config["databricks"]
    assert server["type"] == "stdio"
    assert "command" in server
    assert "env" in server


def test_fabric_config_has_community_server():
    """Fabric config deve expor o servidor community (credenciais via .env/pydantic)."""
    config = get_fabric_mcp_config()
    assert "fabric_community" in config
    server = config["fabric_community"]
    assert server["type"] == "stdio"
    assert "command" in server
    assert "env" in server
    # Servidor oficial Microsoft foi removido do config Python —
    # é local-first (sem credenciais) e configurável separadamente via .mcp.json
    assert "fabric" not in config


def test_fabric_rti_config_has_required_keys():
    config = get_fabric_rti_mcp_config()
    assert "fabric_rti" in config
    assert config["fabric_rti"]["type"] == "stdio"


def test_registry_all_platforms():
    # Passa plataformas explícitas para não depender de credenciais do ambiente
    registry = build_mcp_registry(platforms=["databricks", "fabric", "fabric_rti"])
    assert "databricks" in registry
    # "fabric" plataforma → registra "fabric_community" (servidor community Python)
    assert "fabric_community" in registry
    # servidor oficial Microsoft não é registrado via Python (é local-first, sem credenciais)
    assert "fabric" not in registry
    assert "fabric_rti" in registry


def test_registry_single_platform():
    registry = build_mcp_registry(platforms=["databricks"])
    assert "databricks" in registry
    assert "fabric" not in registry
    assert "fabric_rti" not in registry


def test_databricks_tools_format():
    for tool in DATABRICKS_MCP_TOOLS:
        assert tool.startswith("mcp__databricks__"), f"Tool com prefixo errado: {tool}"


def test_fabric_tools_format():
    for tool in ALL_FABRIC_TOOLS:
        assert tool.startswith("mcp__fabric"), f"Tool com prefixo errado: {tool}"


def test_rti_tools_format():
    for tool in FABRIC_RTI_MCP_TOOLS:
        assert tool.startswith("mcp__fabric_rti__"), f"Tool com prefixo errado: {tool}"
