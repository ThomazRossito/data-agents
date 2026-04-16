"""
Configuração do MCP Server Customizado: migration_source.

Conecta diretamente a bancos relacionais de origem (SQL Server e PostgreSQL)
para extração de metadados, DDL, procedures, views e functions — viabilizando
o assessment e planejamento de migrações para Databricks ou Microsoft Fabric.

MULTI-SOURCE: Usa MIGRATION_SOURCES (JSON registry) para suportar múltiplos bancos
sem hardcode. O agente escolhe a fonte em runtime via parâmetro.

Configuração no .env:

  # Registry de fontes de migração (JSON)
  # type: "sqlserver" | "postgresql"
  MIGRATION_SOURCES={
    "ERP_PROD":  {"type": "sqlserver",  "host": "10.0.0.1", "port": 1433, "database": "ERP",      "user": "sa",       "password": "..."},
    "CRM_DEV":   {"type": "sqlserver",  "host": "10.0.0.2", "port": 1433, "database": "CRM",      "user": "readonly", "password": "..."},
    "ANALYTICS": {"type": "postgresql", "host": "10.0.0.3", "port": 5432, "database": "analytics", "user": "postgres", "password": "..."}
  }
  MIGRATION_DEFAULT_SOURCE=ERP_PROD

Servidor: migration-source-mcp (entry point em pyproject.toml, instalado via pip install -e .)
Protocolo: stdio

Pré-requisitos:
  SQL Server:  ODBC Driver 17 ou 18 (pyodbc já incluído via pyproject.toml)
    macOS: brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
           HOMEBREW_ACCEPT_EULA=Y brew install msodbcsql18
    Linux: https://learn.microsoft.com/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server

  PostgreSQL:  psycopg2-binary (incluído via pyproject.toml)
    macOS: brew install libpq  (se compilar psycopg2 em vez de binary)
"""


def get_migration_source_mcp_config() -> dict:
    """Retorna a configuração MCP para o servidor migration_source customizado."""
    from config.settings import settings  # importação local para evitar circular import

    return {
        "migration_source": {
            "type": "stdio",
            "command": settings.migration_source_command,
            "args": [],
            "env": {
                "MIGRATION_SOURCES": settings.migration_sources,
                "MIGRATION_DEFAULT_SOURCE": settings.migration_default_source,
            },
        }
    }


# ─── Lista de Tools ───────────────────────────────────────────────────────────

MIGRATION_SOURCE_MCP_TOOLS = [
    # Registry e diagnóstico
    "mcp__migration_source__migration_source_list_sources",
    "mcp__migration_source__migration_source_diagnostics",
    # Schema discovery
    "mcp__migration_source__migration_source_list_schemas",
    "mcp__migration_source__migration_source_list_tables",
    "mcp__migration_source__migration_source_describe_table",
    "mcp__migration_source__migration_source_get_table_ddl",
    "mcp__migration_source__migration_source_count_tables_by_schema",
    # Objetos programáticos
    "mcp__migration_source__migration_source_list_views",
    "mcp__migration_source__migration_source_get_view_definition",
    "mcp__migration_source__migration_source_list_procedures",
    "mcp__migration_source__migration_source_get_procedure_definition",
    "mcp__migration_source__migration_source_list_functions",
    "mcp__migration_source__migration_source_get_function_definition",
    # Assessment
    "mcp__migration_source__migration_source_get_schema_summary",
    "mcp__migration_source__migration_source_sample_table",
]
