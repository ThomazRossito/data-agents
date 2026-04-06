"""
Configuração dos MCP Servers para Microsoft Fabric.

Combina dois servidores MCP complementares:

1. Fabric MCP Server oficial (Microsoft) — dotnet:
   https://github.com/microsoft/mcp/tree/main/servers/Fabric.Mcp.Server
   Capabilities: OneLake (upload/download/delete), workspaces, items,
   API specs OpenAPI completas, best practices.

2. Fabric Community MCP (Python) — REST API wrapper:
   https://github.com/Augustab/microsoft_fabric_mcp
   Capabilities: lakehouses, schemas Delta, jobs, schedules, lineage,
   compute usage, dependências entre items.

Pré-requisitos:
  dotnet SDK 8.0+ (para servidor oficial)
  pip install microsoft-fabric-mcp (para community)
  az login  (ou configurar AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID)
"""


def get_fabric_mcp_config() -> dict:
    """Retorna a configuração MCP para Microsoft Fabric."""
    from config.settings import settings  # importação local para evitar circular import

    return {
        # Servidor oficial Microsoft (dotnet) — OneLake + Workspaces + API Specs
        "fabric": {
            "type": "stdio",
            "command": "dotnet",
            "args": [
                "run",
                "--project",
                settings.fabric_mcp_server_path,
            ],
            "env": {
                "FABRIC_API_BASE_URL": settings.fabric_api_base_url,
                "AZURE_TENANT_ID": settings.azure_tenant_id,
                "AZURE_CLIENT_ID": settings.azure_client_id,
                "AZURE_CLIENT_SECRET": settings.azure_client_secret,
            },
        },
        # Servidor community Python — Lakehouses + Jobs + Lineage
        "fabric_community": {
            "type": "stdio",
            "command": "python",
            "args": ["-m", "microsoft_fabric_mcp"],
            "env": {
                "AZURE_TENANT_ID": settings.azure_tenant_id,
                "AZURE_CLIENT_ID": settings.azure_client_id,
                "AZURE_CLIENT_SECRET": settings.azure_client_secret,
                "FABRIC_WORKSPACE_ID": settings.fabric_workspace_id,
                "FABRIC_API_BASE_URL": settings.fabric_api_base_url,
            },
        },
    }


# Tools do servidor oficial Microsoft
FABRIC_MCP_TOOLS = [
    # OneLake — Operações de arquivo
    "mcp__fabric__onelake_download_file",
    "mcp__fabric__onelake_upload_file",
    "mcp__fabric__onelake_delete_file",
    "mcp__fabric__onelake_create_directory",
    "mcp__fabric__onelake_list_files",
    # Workspaces & Items
    "mcp__fabric__list_workspaces",
    "mcp__fabric__get_workspace",
    "mcp__fabric__list_items",
    "mcp__fabric__get_item",
    # API Specs & Best Practices
    "mcp__fabric__list_workload_types",
    "mcp__fabric__get_workload_api_spec",
    "mcp__fabric__get_core_api_spec",
    "mcp__fabric__get_item_schema",
    "mcp__fabric__get_best_practices",
]

# Tools do servidor community
FABRIC_COMMUNITY_MCP_TOOLS = [
    # Lakehouse — Schema e tabelas
    "mcp__fabric_community__list_tables",
    "mcp__fabric_community__get_table_schema",
    "mcp__fabric_community__list_shortcuts",
    "mcp__fabric_community__get_shortcut",
    # Jobs & Schedules
    "mcp__fabric_community__list_job_instances",
    "mcp__fabric_community__get_job_details",
    "mcp__fabric_community__list_schedules",
    "mcp__fabric_community__get_schedule",
    # Lineage & Dependências
    "mcp__fabric_community__get_lineage",
    "mcp__fabric_community__get_dependencies",
    "mcp__fabric_community__get_compute_usage",
]

# Lista consolidada de todas as tools Fabric
ALL_FABRIC_TOOLS = FABRIC_MCP_TOOLS + FABRIC_COMMUNITY_MCP_TOOLS
