"""
Registry centralizado de servidores MCP.

Cada plataforma de dados é um módulo isolado que expõe uma função
get_config() retornando um dict compatível com ClaudeAgentOptions.mcp_servers.

Para adicionar uma nova plataforma:
  1. Copie mcp_servers/_template/server_config.py para mcp_servers/<nome>/server_config.py
  2. Implemente a função get_<nome>_mcp_config()
  3. Registre-a aqui no dicionário all_configs abaixo
"""

from mcp_servers.databricks.server_config import get_databricks_mcp_config
from mcp_servers.fabric.server_config import get_fabric_mcp_config
from mcp_servers.fabric_rti.server_config import get_fabric_rti_mcp_config


def build_mcp_registry(platforms: list[str] | None = None) -> dict:
    """
    Constrói o registry de MCP servers para as plataformas solicitadas.

    Args:
        platforms: Lista de plataformas a ativar.
                   None = todas disponíveis.
                   Valores válidos: "databricks", "fabric", "fabric_rti"

    Returns:
        Dict compatível com ClaudeAgentOptions.mcp_servers
    """
    all_configs = {
        "databricks": get_databricks_mcp_config,
        "fabric":     get_fabric_mcp_config,
        "fabric_rti": get_fabric_rti_mcp_config,
        # Adicione novas plataformas aqui:
        # "snowflake": get_snowflake_mcp_config,
        # "bigquery":  get_bigquery_mcp_config,
    }

    if platforms is None:
        platforms = list(all_configs.keys())

    registry: dict = {}
    for platform in platforms:
        if platform in all_configs:
            config = all_configs[platform]()
            registry.update(config)

    return registry
