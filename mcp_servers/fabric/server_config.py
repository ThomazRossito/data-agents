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


# Tools do servidor community (ativo — credenciais via .env).
# Nome canônico do set ativo de tools Fabric neste projeto.
# `FABRIC_COMMUNITY_MCP_TOOLS` é alias legado preservado abaixo para backward compat.
# Ref: microsoft-fabric-mcp v0.1.4 — 28 ferramentas disponíveis
# Fonte: /opt/anaconda3/envs/multi_agents/lib/python3.12/site-packages/fabric_mcp.py
FABRIC_MCP_TOOLS = [
    # Workspaces
    "mcp__fabric_community__list_workspaces",
    "mcp__fabric_community__list_workspaces_with_identity",
    "mcp__fabric_community__get_workspace",
    "mcp__fabric_community__get_workspace_identity",
    # Items — Descoberta e introspecção de artefatos (Semantic Models, Reports, etc.)
    "mcp__fabric_community__list_items",
    "mcp__fabric_community__get_item",
    # Lakehouses
    "mcp__fabric_community__list_lakehouses",
    # Lakehouse — Schema e tabelas Delta
    "mcp__fabric_community__list_tables",
    "mcp__fabric_community__get_table_schema",
    "mcp__fabric_community__get_all_schemas",
    # Shortcuts (OneLake)
    "mcp__fabric_community__list_shortcuts",
    "mcp__fabric_community__get_shortcut",
    "mcp__fabric_community__list_workspace_shortcuts",
    # Jobs & Schedules
    "mcp__fabric_community__list_job_instances",
    "mcp__fabric_community__get_job_instance",
    "mcp__fabric_community__list_item_schedules",
    "mcp__fabric_community__list_workspace_schedules",
    # Lineage & Dependências
    "mcp__fabric_community__get_item_lineage",
    "mcp__fabric_community__list_item_dependencies",
    # Compute & Capacidades
    "mcp__fabric_community__list_compute_usage",
    "mcp__fabric_community__list_capacities",
    # Connections & Data Sources
    "mcp__fabric_community__list_connections",
    "mcp__fabric_community__get_data_source_usage",
    # Environments
    "mcp__fabric_community__list_environments",
    "mcp__fabric_community__get_environment_details",
    # Cache Management
    "mcp__fabric_community__clear_fabric_data_cache",
    "mcp__fabric_community__clear_name_resolution_cache",
]

# Tools do servidor oficial Microsoft (opcional — local-first, sem conexão ao tenant)
# Ref: https://github.com/microsoft/mcp/tree/main/servers/Fabric.Mcp.Server
# Não está ativo por padrão. Para ativar, adicione ao .mcp.json após build/npx.
# Listado aqui como referência; não é injetado nos agentes via aliases padrão.
FABRIC_OFFICIAL_MCP_TOOLS = [
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

# Alias legado — preservado para imports existentes. Aponta para o mesmo set ativo.
FABRIC_COMMUNITY_MCP_TOOLS = FABRIC_MCP_TOOLS

# Lista consolidada (community ativo + oficial como referência documental)
ALL_FABRIC_TOOLS = FABRIC_MCP_TOOLS + FABRIC_OFFICIAL_MCP_TOOLS
