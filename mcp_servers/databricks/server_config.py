"""
Configuração do MCP Server para Databricks.

Utiliza o pacote oficial `databricks-mcp-server` do ai-dev-kit da Databricks:
  https://github.com/databricks-solutions/ai-dev-kit

Capabilities expostas (50+ tools):
  - Unity Catalog: catálogos, schemas, tabelas, volumes, funções, grants
  - SQL Execution: execute_sql via SQL Warehouse
  - Jobs & Workflows: listar, disparar, cancelar, monitorar
  - Spark Declarative Pipelines (LakeFlow/DLT): listar, iniciar, parar
  - Clusters: listar, iniciar, inspecionar
  - Workspace & Notebooks: navegar, exportar
  - Files & Volumes: ler e listar arquivos em DBFS e Volumes

Pré-requisitos:
  pip install databricks-mcp-server
  Configurar: DATABRICKS_HOST e DATABRICKS_TOKEN no .env
"""

def get_databricks_mcp_config() -> dict:
    """Retorna a configuração MCP para o Databricks."""
    from config.settings import settings  # importação local para evitar circular import
    return {
        "databricks": {
            "type": "stdio",
            "command": "databricks-mcp-server",
            "args": [],
            "env": {
                "DATABRICKS_HOST":             settings.databricks_host,
                "DATABRICKS_TOKEN":            settings.databricks_token,
                "DATABRICKS_SQL_WAREHOUSE_ID": settings.databricks_sql_warehouse_id,
            },
        }
    }


# Subconjunto principal das tools expostas pelo servidor
# (lista completa disponível em: databricks-mcp-server --list-tools)
DATABRICKS_MCP_TOOLS = [
    # Unity Catalog — Descoberta de metadados
    "mcp__databricks__list_catalogs",
    "mcp__databricks__list_schemas",
    "mcp__databricks__list_tables",
    "mcp__databricks__describe_table",
    "mcp__databricks__get_table_schema",
    "mcp__databricks__sample_table_data",
    # SQL
    "mcp__databricks__execute_sql",
    "mcp__databricks__list_sql_warehouses",
    "mcp__databricks__get_query_history",
    # Jobs & Workflows
    "mcp__databricks__list_jobs",
    "mcp__databricks__get_job",
    "mcp__databricks__run_job_now",
    "mcp__databricks__list_job_runs",
    "mcp__databricks__get_run",
    "mcp__databricks__cancel_run",
    # Spark Declarative Pipelines (LakeFlow)
    "mcp__databricks__list_pipelines",
    "mcp__databricks__get_pipeline",
    "mcp__databricks__create_or_update_pipeline",
    "mcp__databricks__start_pipeline",
    "mcp__databricks__stop_pipeline",
    "mcp__databricks__get_pipeline_update",
    # Clusters
    "mcp__databricks__list_clusters",
    "mcp__databricks__get_cluster",
    "mcp__databricks__start_cluster",
    # Workspace & Notebooks
    "mcp__databricks__list_workspace",
    "mcp__databricks__export_notebook",
    "mcp__databricks__import_notebook",
    # Files & Volumes
    "mcp__databricks__list_files",
    "mcp__databricks__read_file",
    "mcp__databricks__upload_to_volume",
    "mcp__databricks__list_volume_files",
]

# Subconjunto apenas de leitura/descoberta (para agentes sem permissão de escrita)
DATABRICKS_MCP_READONLY_TOOLS = [
    t for t in DATABRICKS_MCP_TOOLS
    if any(kw in t for kw in [
        "list_", "get_", "describe_", "sample_", "export_", "read_"
    ])
]
