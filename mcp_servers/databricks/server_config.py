"""
Configuração do MCP Server para Databricks.

Utiliza o pacote oficial `databricks-mcp-server` do ai-dev-kit da Databricks:
  https://github.com/databricks-solutions/ai-dev-kit

Capabilities expostas (50+ tools):
  - Unity Catalog: catálogos, schemas, tabelas, volumes, funções, grants
  - SQL Execution: execute_sql, execute_sql_multi (paralelo), get_best_warehouse
  - Jobs & Workflows: listar, disparar, cancelar, monitorar, wait_for_run
  - Spark Declarative Pipelines (LakeFlow/DLT): listar, iniciar, parar
  - Compute: execute_code, manage_cluster, manage_sql_warehouse, list_compute
  - Workspace & Notebooks: navegar, exportar, upload_to_workspace
  - Files & Volumes: ler e listar arquivos em DBFS e Volumes
  - AI/BI: create_or_update_genie, create_or_update_dashboard
  - AI Agents: manage_ka (Knowledge Assistants), manage_mas (Mosaic AI Supervisor)
  - Model Serving: list/query/status de endpoints

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
                "DATABRICKS_HOST": settings.databricks_host,
                "DATABRICKS_TOKEN": settings.databricks_token,
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
    "mcp__databricks__get_table_stats_and_schema",  # stats + schema combinados (novo)
    "mcp__databricks__sample_table_data",
    # SQL
    "mcp__databricks__execute_sql",
    "mcp__databricks__execute_sql_multi",  # executa múltiplas queries em paralelo (novo)
    "mcp__databricks__list_sql_warehouses",
    "mcp__databricks__get_best_warehouse",  # seleciona warehouse ideal para a query (novo)
    "mcp__databricks__get_query_history",
    # Jobs & Workflows
    "mcp__databricks__list_jobs",
    "mcp__databricks__get_job",
    "mcp__databricks__run_job_now",
    "mcp__databricks__list_job_runs",
    "mcp__databricks__get_run",
    "mcp__databricks__cancel_run",
    "mcp__databricks__wait_for_run",  # aguarda conclusão com polling (novo)
    # Spark Declarative Pipelines (LakeFlow)
    "mcp__databricks__list_pipelines",
    "mcp__databricks__get_pipeline",
    "mcp__databricks__create_or_update_pipeline",
    "mcp__databricks__start_pipeline",
    "mcp__databricks__stop_pipeline",
    "mcp__databricks__get_pipeline_update",
    # Compute
    "mcp__databricks__list_clusters",
    "mcp__databricks__get_cluster",
    "mcp__databricks__start_cluster",
    "mcp__databricks__manage_cluster",  # create/modify/terminate clusters (novo)
    "mcp__databricks__manage_sql_warehouse",  # CRUD completo de warehouses (novo)
    "mcp__databricks__list_compute",  # node types, spark versions disponíveis (novo)
    "mcp__databricks__execute_code",  # executa código em serverless/cluster (novo)
    # Workspace & Notebooks
    "mcp__databricks__list_workspace",
    "mcp__databricks__export_notebook",
    "mcp__databricks__import_notebook",
    "mcp__databricks__upload_to_workspace",  # upload de arquivos/pastas (novo)
    # Files & Volumes
    "mcp__databricks__list_files",
    "mcp__databricks__read_file",
    "mcp__databricks__upload_to_volume",
    "mcp__databricks__list_volume_files",
    # AI/BI — Genie e Dashboards
    "mcp__databricks__create_or_update_genie",  # cria/atualiza Genie Space (novo)
    "mcp__databricks__create_or_update_dashboard",  # cria/publica AI/BI Dashboard (novo)
    # AI Agents — Knowledge Assistants e Mosaic AI Supervisor
    "mcp__databricks__manage_ka",  # Knowledge Assistants (novo)
    "mcp__databricks__manage_mas",  # Mosaic AI Supervisor Agents (novo)
    # Model Serving
    "mcp__databricks__list_serving_endpoints",  # lista endpoints disponíveis (novo)
    "mcp__databricks__get_serving_endpoint_status",  # verifica saúde do endpoint (novo)
    "mcp__databricks__query_serving_endpoint",  # invoca chat/ML model (novo)
]

# Subconjunto apenas de leitura/descoberta (para agentes sem permissão de escrita)
DATABRICKS_MCP_READONLY_TOOLS = [
    t
    for t in DATABRICKS_MCP_TOOLS
    if any(
        kw in t
        for kw in [
            "list_",
            "get_",
            "describe_",
            "sample_",
            "export_",
            "read_",
            "query_serving_endpoint",  # leitura de modelo — permitido em readonly
        ]
    )
]

# Subconjunto AI/BI — Genie, Dashboards, Knowledge Assistants, Mosaic AI Supervisor
DATABRICKS_AIBI_TOOLS = [
    "mcp__databricks__create_or_update_genie",
    "mcp__databricks__create_or_update_dashboard",
    "mcp__databricks__manage_ka",
    "mcp__databricks__manage_mas",
]

# Subconjunto Model Serving — endpoints de modelos ML/GenAI
DATABRICKS_SERVING_TOOLS = [
    "mcp__databricks__list_serving_endpoints",
    "mcp__databricks__get_serving_endpoint_status",
    "mcp__databricks__query_serving_endpoint",
]

# Subconjunto Compute avançado — criação/gestão de clusters e execução de código
DATABRICKS_COMPUTE_TOOLS = [
    "mcp__databricks__manage_cluster",
    "mcp__databricks__manage_sql_warehouse",
    "mcp__databricks__list_compute",
    "mcp__databricks__execute_code",
    "mcp__databricks__wait_for_run",
]
