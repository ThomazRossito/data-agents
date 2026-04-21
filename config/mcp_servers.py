"""
Registry centralizado de servidores MCP.

Cada plataforma de dados é um módulo isolado que expõe uma função
get_config() retornando um dict compatível com ClaudeAgentOptions.mcp_servers.

Comportamento padrão:
  - Se `platforms=None`, ativa apenas as plataformas com credenciais válidas
    (detectadas via settings.get_available_platforms()).
  - Se nenhuma credencial estiver configurada, registra todas as plataformas
    para evitar que o sistema fique sem MCP servers (comportamento de fallback).

Para adicionar uma nova plataforma:
  1. Copie mcp_servers/_template/server_config.py para mcp_servers/<nome>/server_config.py
  2. Implemente a função get_<nome>_mcp_config()
  3. Registre-a aqui no dicionário ALL_MCP_CONFIGS abaixo
"""

import logging

from mcp_servers.context7.server_config import get_context7_mcp_config
from mcp_servers.databricks.server_config import get_databricks_mcp_config
from mcp_servers.databricks_genie.server_config import get_databricks_genie_mcp_config
from mcp_servers.fabric.server_config import (
    get_fabric_mcp_config,
    get_fabric_official_mcp_config,
)
from mcp_servers.fabric_rti.server_config import get_fabric_rti_mcp_config
from mcp_servers.fabric_semantic.server_config import get_fabric_semantic_mcp_config
from mcp_servers.fabric_sql.server_config import get_fabric_sql_mcp_config
from mcp_servers.firecrawl.server_config import get_firecrawl_mcp_config
from mcp_servers.github.server_config import get_github_mcp_config
from mcp_servers.memory_mcp.server_config import get_memory_mcp_config
from mcp_servers.migration_source.server_config import get_migration_source_mcp_config
from mcp_servers.postgres.server_config import get_postgres_mcp_config
from mcp_servers.tavily.server_config import get_tavily_mcp_config

logger = logging.getLogger("data_agents.mcp")

# Registry completo de plataformas disponíveis
ALL_MCP_CONFIGS: dict = {
    # ── Plataformas de dados ──────────────────────────────────────────────────
    "databricks": get_databricks_mcp_config,
    # databricks_genie: MCP customizado que expõe a Genie Conversation + Space Management API.
    # Resolve o gap do databricks-mcp-server oficial que não inclui as tools de Genie.
    # Requer: DATABRICKS_HOST + DATABRICKS_TOKEN (já usados pelo databricks-mcp-server)
    #         + DATABRICKS_GENIE_SPACES (JSON registry com nomes amigáveis para space_ids)
    "databricks_genie": get_databricks_genie_mcp_config,
    "fabric": get_fabric_mcp_config,
    # fabric_official: MCP oficial Microsoft (npx @microsoft/fabric-mcp) —
    # OneLake file ops (upload/download/list/delete) + API specs.
    # Autenticação via cache `az login` local (sem env vars), mesmo tenant do
    # fabric_community. Restaura capacidade OneLake que foi perdida em 0a446c8.
    "fabric_official": get_fabric_official_mcp_config,
    # fabric_sql: MCP customizado que conecta ao SQL Analytics Endpoint via TDS (pyodbc + AAD)
    # Resolve limitação da REST API que só enxerga o schema dbo.
    # Requer: FABRIC_SQL_ENDPOINT + FABRIC_LAKEHOUSE_NAME no .env
    "fabric_sql": get_fabric_sql_mcp_config,
    "fabric_rti": get_fabric_rti_mcp_config,
    # fabric_semantic: MCP customizado para introspecção profunda de Semantic Models
    # Expõe TMDL (tabelas, colunas, medidas DAX, relacionamentos, RLS) e execução DAX.
    # Reutiliza credenciais Azure (AZURE_TENANT_ID + AZURE_CLIENT_ID + AZURE_CLIENT_SECRET).
    "fabric_semantic": get_fabric_semantic_mcp_config,
    # ── MCPs externos ─────────────────────────────────────────────────────────
    # context7: documentação atualizada de bibliotecas (free até 1k req/mês, sem credenciais)
    "context7": get_context7_mcp_config,
    # tavily: busca web otimizada para LLMs (free até 1k créditos/mês, requer TAVILY_API_KEY)
    "tavily": get_tavily_mcp_config,
    # github: gestão de repos, issues e PRs (gratuito via PAT, requer GITHUB_PERSONAL_ACCESS_TOKEN)
    "github": get_github_mcp_config,
    # firecrawl: web scraping estruturado (free até 500 créditos/mês, requer FIRECRAWL_API_KEY)
    "firecrawl": get_firecrawl_mcp_config,
    # postgres: queries somente leitura em PostgreSQL (gratuito, requer POSTGRES_URL)
    "postgres": get_postgres_mcp_config,
    # memory_mcp: knowledge graph persistente de entidades e relações (gratuito, sem credenciais)
    # Complementa o módulo memory/ existente: memory/ = memória episódica, memory_mcp = grafo de entidades
    "memory_mcp": get_memory_mcp_config,
    # migration_source: MCP customizado para conectar a bancos de origem (SQL Server, PostgreSQL)
    # Extrai DDL, views, procedures, functions e stats para assessment e planejamento de migração.
    # Requer MIGRATION_SOURCES no .env com registry JSON das fontes.
    "migration_source": get_migration_source_mcp_config,
    # Adicione novas plataformas aqui:
    # "snowflake": get_snowflake_mcp_config,
    # "bigquery":  get_bigquery_mcp_config,
}


def build_mcp_registry(platforms: list[str] | None = None) -> dict:
    """
    Constrói o registry de MCP servers para as plataformas solicitadas.

    Se `platforms=None`, detecta automaticamente quais plataformas têm
    credenciais válidas via settings.get_available_platforms(). Isso evita
    tentar inicializar servidores MCP sem credenciais, que causariam erros
    de conexão silenciosos no startup.

    Args:
        platforms: Lista explícita de plataformas a ativar.
                   None = detecção automática por credenciais disponíveis.
                   Valores válidos: "databricks", "fabric", "fabric_rti"

    Returns:
        Dict compatível com ClaudeAgentOptions.mcp_servers
    """
    if platforms is None:
        # Importação local para evitar dependência circular no startup
        from config.settings import settings

        available = settings.get_available_platforms()

        # MCPs sem credenciais obrigatórias — sempre ativos independente do .env
        ALWAYS_ACTIVE_MCPS = ["context7", "memory_mcp"]

        if available:
            # Ativa plataformas com credenciais + MCPs que não precisam de credenciais
            platforms = list(dict.fromkeys(available + ALWAYS_ACTIVE_MCPS))
            logger.info(f"MCP servers ativos (por credenciais + sem credenciais): {platforms}")
        else:
            platforms = list(ALL_MCP_CONFIGS.keys())
            logger.warning(
                "Nenhuma credencial de plataforma configurada. "
                "Registrando todos os MCP servers como fallback."
            )

    registry: dict = {}
    for platform in platforms:
        if platform in ALL_MCP_CONFIGS:
            config = ALL_MCP_CONFIGS[platform]()
            registry.update(config)
        else:
            logger.warning(f"Plataforma desconhecida ignorada: '{platform}'")

    # ── Aliases: garante que os agentes possam referenciar mcp_servers
    # pelo nome da plataforma OU pelo nome do server concreto.
    # Ex: plataforma "fabric" registra server "fabric_community" —
    # mas agentes podem declarar mcp_servers: [fabric] e precisam encontrá-lo.
    PLATFORM_TO_SERVER_ALIASES: dict[str, str] = {
        "fabric": "fabric_community",
        "fabric_rti": "fabric_rti",
        "fabric_semantic": "fabric_semantic",
    }
    for alias, server_name in PLATFORM_TO_SERVER_ALIASES.items():
        if server_name in registry and alias not in registry:
            registry[alias] = registry[server_name]
            logger.debug(f"Alias MCP registrado: '{alias}' → '{server_name}'")

    return registry
