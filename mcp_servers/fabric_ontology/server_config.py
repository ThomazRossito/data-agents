"""
Configuração do MCP Server Customizado: fabric_ontology.

Operações cirúrgicas de CRUD no Microsoft Fabric IQ Ontology:
entity types, relationship types, data bindings, contextualizations,
documentos e descoberta de tabelas em Lakehouses/KQL.

Autenticação via Azure CLI (az login) — sem credenciais no .env.
"""


def get_fabric_ontology_mcp_config() -> dict:
    """Retorna a configuração MCP para o servidor fabric_ontology customizado."""
    from config.settings import settings  # importação local para evitar circular import

    command = settings.fabric_ontology_command or "fabric-ontology-mcp"
    return {
        "fabric_ontology": {
            "type": "stdio",
            "command": command,
            "args": [],
            "env": {},  # auth via Azure CLI (az login) — sem credentials no .env
        }
    }


# ─── Lista completa de Tools ──────────────────────────────────────────────────

MCP_TOOLS: list[str] = [
    # Workspace discovery
    "mcp__fabric_ontology__list_workspaces",
    "mcp__fabric_ontology__list_workspace_items",
    # KQL / Eventhouse
    "mcp__fabric_ontology__get_kql_database_details",
    "mcp__fabric_ontology__list_kql_tables",
    "mcp__fabric_ontology__get_kql_table_schema",
    "mcp__fabric_ontology__preview_kql_table",
    "mcp__fabric_ontology__profile_kql_table",
    # Ontology CRUD
    "mcp__fabric_ontology__list_ontologies",
    "mcp__fabric_ontology__get_ontology",
    "mcp__fabric_ontology__create_ontology",
    "mcp__fabric_ontology__update_ontology",
    "mcp__fabric_ontology__delete_ontology",
    "mcp__fabric_ontology__get_ontology_definition",
    "mcp__fabric_ontology__update_ontology_definition_raw",
    # Entity Types
    "mcp__fabric_ontology__list_entity_types",
    "mcp__fabric_ontology__get_entity_type",
    "mcp__fabric_ontology__add_entity_type",
    "mcp__fabric_ontology__remove_entity_type",
    "mcp__fabric_ontology__update_entity_type",
    # Properties
    "mcp__fabric_ontology__add_property",
    "mcp__fabric_ontology__remove_property",
    "mcp__fabric_ontology__update_property",
    # Relationship Types
    "mcp__fabric_ontology__list_relationship_types",
    "mcp__fabric_ontology__get_relationship_type",
    "mcp__fabric_ontology__add_relationship_type",
    "mcp__fabric_ontology__remove_relationship_type",
    "mcp__fabric_ontology__update_relationship_type",
    # Data Bindings
    "mcp__fabric_ontology__list_data_bindings",
    "mcp__fabric_ontology__add_data_binding",
    "mcp__fabric_ontology__remove_data_binding",
    # Documents
    "mcp__fabric_ontology__list_documents",
    "mcp__fabric_ontology__add_document",
    "mcp__fabric_ontology__remove_document",
    # Overviews & Resource Links
    "mcp__fabric_ontology__get_overview",
    "mcp__fabric_ontology__set_overview",
    "mcp__fabric_ontology__get_resource_links",
    "mcp__fabric_ontology__set_resource_links",
    # Contextualizations
    "mcp__fabric_ontology__list_contextualizations",
    "mcp__fabric_ontology__add_contextualization",
    "mcp__fabric_ontology__remove_contextualization",
    # Lakehouse discovery & preview
    "mcp__fabric_ontology__discover_lakehouse_tables",
    "mcp__fabric_ontology__get_lakehouse_table_schema",
    "mcp__fabric_ontology__discover_workspace_data",
    "mcp__fabric_ontology__preview_lakehouse_table",
    "mcp__fabric_ontology__profile_lakehouse_table",
]

# Subconjunto somente leitura: list_, get_, discover_, preview_, profile_
MCP_READONLY_TOOLS: list[str] = [
    t
    for t in MCP_TOOLS
    if any(
        t.startswith(f"mcp__fabric_ontology__{prefix}")
        for prefix in ("list_", "get_", "discover_", "preview_", "profile_")
    )
]
