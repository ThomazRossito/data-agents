"""
Configuração dos MCP Servers para Microsoft Fabric.

Servidor ativo por padrão:
  Fabric Community MCP (Python) — REST API wrapper:
  https://github.com/Augustab/microsoft_fabric_mcp
  Capabilities: lakehouses, schemas Delta, jobs, schedules, lineage,
  compute usage, dependências entre items.

Servidor opcional (documentação local, sem conexão ao tenant):
  Fabric MCP Server oficial (Microsoft) — local-first:
  https://github.com/microsoft/mcp/tree/main/servers/Fabric.Mcp.Server
  Não requer credenciais. Fornece: OpenAPI specs, schemas de items, best practices.
  Para ativar: adicione manualmente ao .mcp.json após build do binário.

Pré-requisitos:
  pip install -e ".[dev]"  (inclui microsoft-fabric-mcp via pyproject.toml)
  Credenciais no .env: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET,
                       FABRIC_WORKSPACE_ID, FABRIC_API_BASE_URL

Importante:
  As credenciais são lidas do .env via pydantic-settings.
  NÃO é necessário fazer export das variáveis no shell.
  NÃO configure fabric_community no .mcp.json — isso sobrescreveria
  as credenciais do .env com variáveis de shell potencialmente vazias.
"""


def get_fabric_mcp_config() -> dict:
    """Retorna a configuração MCP para Microsoft Fabric."""
    from config.settings import settings  # importação local para evitar circular import

    return {
        # Servidor community Python — Lakehouses + Jobs + Lineage
        # Comando configurável via FABRIC_COMMUNITY_COMMAND no .env
        # Padrão: "microsoft-fabric-mcp" (binário instalado pelo pip)
        "fabric_community": {
            "type": "stdio",
            "command": settings.fabric_community_command,
            "args": [],
            "env": {
                "AZURE_TENANT_ID": settings.azure_tenant_id,
                "AZURE_CLIENT_ID": settings.azure_client_id,
                "AZURE_CLIENT_SECRET": settings.azure_client_secret,
                "FABRIC_WORKSPACE_ID": settings.fabric_workspace_id,
                "FABRIC_API_BASE_URL": settings.fabric_api_base_url,
            },
        },
    }


# Tools do servidor community (ativo — credenciais via .env)
FABRIC_COMMUNITY_MCP_TOOLS = [
    # Workspaces
    "mcp__fabric_community__list_workspaces",
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

# Tools do servidor oficial Microsoft (opcional — local-first, sem conexão ao tenant)
# Ref: https://github.com/microsoft/mcp/tree/main/servers/Fabric.Mcp.Server
# Não está ativo por padrão. Para ativar, adicione ao .mcp.json após build/npx.
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
    # API Specs & Best Practices (documentação local)
    "mcp__fabric__list_workload_types",
    "mcp__fabric__get_workload_api_spec",
    "mcp__fabric__get_core_api_spec",
    "mcp__fabric__get_item_schema",
    "mcp__fabric__get_best_practices",
]

# Lista consolidada (community ativo + oficial como referência)
ALL_FABRIC_TOOLS = FABRIC_COMMUNITY_MCP_TOOLS + FABRIC_MCP_TOOLS
