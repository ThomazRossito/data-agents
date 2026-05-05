"""
Configuração dos MCP Servers para Microsoft Fabric.

Servidores registrados aqui:

1. Fabric Community MCP (Python) — REST API wrapper
   https://github.com/Augustab/microsoft_fabric_mcp
   Capabilities: lakehouses, schemas Delta, jobs, schedules, lineage,
   compute usage, dependências entre items. 28 tools (metadata-heavy).

2. Fabric Official MCP (Microsoft, Node.js) — OneLake file ops + API specs
   https://github.com/microsoft/mcp  (pacote npm `@microsoft/fabric-mcp`)
   Capabilities exclusivas: `onelake_upload_file`, `onelake_download_file`,
   `onelake_list_files`, `onelake_delete_file`, `onelake_create_directory` —
   não existem no community MCP. Autenticação via cache `az login` ou
   credencial Azure default chain; não recebe env vars do `.env`.
   14 tools.

Pré-requisitos:
  pip install -e ".[dev]"  (inclui microsoft-fabric-mcp via pyproject.toml)
  npm / npx disponível no PATH (para o official via `npx @microsoft/fabric-mcp`)
  `az login` ativo no host para acesso ao OneLake

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


def get_fabric_official_mcp_config() -> dict:
    """Retorna a configuração MCP para o servidor oficial Microsoft Fabric (OneLake).

    Usa `npx @microsoft/fabric-mcp@latest` em modo `all`, que habilita OneLake
    file ops + API specs + best practices. Autenticação via cache `az login` —
    não recebemos env vars para evitar conflito com a DefaultAzureCredential chain.
    """
    return {
        "fabric_official": {
            "type": "stdio",
            "command": "npx",
            "args": [
                "-y",
                "@microsoft/fabric-mcp@latest",
                "server",
                "start",
                "--mode",
                "all",
            ],
        }
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

# Tools do servidor oficial Microsoft (@microsoft/fabric-mcp, modo `all`).
# Registrado como server `fabric_official` em ALL_MCP_CONFIGS; injeção nos
# agentes via aliases `fabric_official_all` / `fabric_official_readonly`.
FABRIC_OFFICIAL_MCP_TOOLS = [
    # OneLake — Operações de arquivo
    "mcp__fabric_official__onelake_download_file",
    "mcp__fabric_official__onelake_upload_file",
    "mcp__fabric_official__onelake_delete_file",
    "mcp__fabric_official__onelake_create_directory",
    "mcp__fabric_official__onelake_list_files",
    # Workspaces & Items
    "mcp__fabric_official__list_workspaces",
    "mcp__fabric_official__get_workspace",
    "mcp__fabric_official__list_items",
    "mcp__fabric_official__get_item",
    "mcp__fabric_official__core_create-item",
    # API Specs & Best Practices (documentação local)
    "mcp__fabric_official__list_workload_types",
    "mcp__fabric_official__get_workload_api_spec",
    "mcp__fabric_official__get_core_api_spec",
    "mcp__fabric_official__get_item_schema",
    "mcp__fabric_official__get_best_practices",
]

# Subset readonly do oficial — exclui operações de escrita/criação.
# Usado pelo alias `fabric_official_readonly` em agents/loader.py para agentes
# com escopo de leitura (sql-expert, governance-auditor, data-quality-steward).
_DESTRUCTIVE_OFFICIAL_SUFFIXES = (
    "onelake_upload_file",
    "onelake_delete_file",
    "onelake_create_directory",
    "core_create-item",
)
FABRIC_OFFICIAL_MCP_READONLY_TOOLS = [
    t for t in FABRIC_OFFICIAL_MCP_TOOLS if not t.endswith(_DESTRUCTIVE_OFFICIAL_SUFFIXES)
]

# Alias legado — preservado para imports existentes. Aponta para o mesmo set ativo.
FABRIC_COMMUNITY_MCP_TOOLS = FABRIC_MCP_TOOLS

# Lista consolidada (community ativo + oficial como referência documental)
ALL_FABRIC_TOOLS = FABRIC_MCP_TOOLS + FABRIC_OFFICIAL_MCP_TOOLS
