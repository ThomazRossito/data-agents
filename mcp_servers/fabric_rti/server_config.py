"""
Configuração do MCP Server para Fabric Real-Time Intelligence (RTI).

Servidor dedicado a operações em tempo real:
  Eventhouse (Kusto/KQL), Eventstreams, Activator.

Referência:
  https://github.com/microsoft/fabric-rti-mcp

Capabilities:
  Eventhouse / Kusto (13 tools):
    - kusto_query: Executar queries KQL
    - kusto_command: Operações de management
    - kusto_list_databases, kusto_list_tables: Descoberta
    - kusto_get_table_schema, kusto_get_entities_schema: Introspecção
    - kusto_sample_table_data: Amostragem
    - kusto_ingest_inline_into_table: Ingestão inline
    - kusto_get_shots: Busca semântica (requer OpenAI embedding)
    - kusto_deeplink_from_query: Gerar URL de query

  Eventstreams (17 tools):
    - CRUD de eventstreams
    - Configuração de sources, streams, destinations

  Activator (2 tools):
    - Listar e criar triggers KQL com notificação

Pré-requisitos:
  pip install microsoft-fabric-rti-mcp
  az login  (ou configurar variáveis AZURE_*)
  KUSTO_SERVICE_URI e KUSTO_SERVICE_DEFAULT_DB no .env
"""


def get_fabric_rti_mcp_config() -> dict:
    """Retorna a configuração MCP para Fabric Real-Time Intelligence."""
    from config.settings import settings  # importação local para evitar circular import

    return {
        "fabric_rti": {
            "type": "stdio",
            "command": "uvx",
            "args": ["microsoft-fabric-rti-mcp"],
            "env": {
                "KUSTO_SERVICE_URI": settings.kusto_service_uri,
                "KUSTO_SERVICE_DEFAULT_DB": settings.kusto_service_default_db,
                "FABRIC_API_BASE_URL": settings.fabric_api_base_url,
                "AZURE_TENANT_ID": settings.azure_tenant_id,
                "AZURE_CLIENT_ID": settings.azure_client_id,
                "AZURE_CLIENT_SECRET": settings.azure_client_secret,
            },
        }
    }


FABRIC_RTI_MCP_TOOLS = [
    # Eventhouse / Kusto — Queries e Descoberta
    "mcp__fabric_rti__kusto_query",
    "mcp__fabric_rti__kusto_command",
    "mcp__fabric_rti__kusto_list_databases",
    "mcp__fabric_rti__kusto_list_tables",
    "mcp__fabric_rti__kusto_get_table_schema",
    "mcp__fabric_rti__kusto_get_entities_schema",
    "mcp__fabric_rti__kusto_get_function_schema",
    "mcp__fabric_rti__kusto_sample_table_data",
    "mcp__fabric_rti__kusto_sample_function_data",
    "mcp__fabric_rti__kusto_ingest_inline_into_table",
    "mcp__fabric_rti__kusto_deeplink_from_query",
    # Eventstreams — CRUD
    "mcp__fabric_rti__eventstream_list",
    "mcp__fabric_rti__eventstream_get",
    "mcp__fabric_rti__eventstream_create",
    "mcp__fabric_rti__eventstream_update",
    "mcp__fabric_rti__eventstream_delete",
    # Activator — Alertas
    "mcp__fabric_rti__activator_list_artifacts",
    "mcp__fabric_rti__activator_create_trigger",
]

# Subconjunto apenas de leitura (para SQL Expert)
FABRIC_RTI_READONLY_TOOLS = [
    "mcp__fabric_rti__kusto_query",
    "mcp__fabric_rti__kusto_list_databases",
    "mcp__fabric_rti__kusto_list_tables",
    "mcp__fabric_rti__kusto_get_table_schema",
    "mcp__fabric_rti__kusto_get_entities_schema",
    "mcp__fabric_rti__kusto_sample_table_data",
]
