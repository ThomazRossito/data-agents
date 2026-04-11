"""
Configuração do MCP Server Customizado: fabric_sql.

Conecta ao Fabric SQL Analytics Endpoint via TDS (pyodbc + AAD Bearer Token),
resolvendo a limitação da REST API que só enxerga o schema `dbo`.

MULTI-LAKEHOUSE: Usa FABRIC_SQL_LAKEHOUSES (JSON registry) para suportar múltiplos
lakehouses sem hardcode. O agente escolhe o lakehouse em runtime via parâmetro.

Servidor: fabric-sql-mcp (entry point em pyproject.toml, instalado via pip install -e .)
Protocolo: stdio
Autenticação: Azure AD Service Principal → Bearer Token → pyodbc SQL_COPT_SS_ACCESS_TOKEN

Pré-requisitos:
  1. ODBC Driver 18 para SQL Server no sistema:
       macOS: brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
              HOMEBREW_ACCEPT_EULA=Y brew install msodbcsql18
       Linux: https://learn.microsoft.com/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server
  2. pip install -e . (inclui pyodbc via pyproject.toml)
  3. Variáveis no .env: FABRIC_SQL_LAKEHOUSES + FABRIC_SQL_DEFAULT_LAKEHOUSE

Como encontrar o SQL Endpoint de um Lakehouse:
  Portal Fabric → Lakehouse → SQL Analytics Endpoint → copiar valor de "Server"
  Formato: <workspace-name>.datawarehouse.fabric.microsoft.com
"""


def get_fabric_sql_mcp_config() -> dict:
    """Retorna a configuração MCP para o servidor fabric_sql customizado."""
    from config.settings import settings  # importação local para evitar circular import

    return {
        "fabric_sql": {
            "type": "stdio",
            "command": settings.fabric_sql_command,
            "args": [],
            "env": {
                # Credenciais Azure (compartilhadas entre todos os lakehouses)
                "AZURE_TENANT_ID": settings.azure_tenant_id,
                "AZURE_CLIENT_ID": settings.azure_client_id,
                "AZURE_CLIENT_SECRET": settings.azure_client_secret,
                # Registry multi-lakehouse (JSON)
                "FABRIC_SQL_LAKEHOUSES": settings.fabric_sql_lakehouses,
                "FABRIC_SQL_DEFAULT_LAKEHOUSE": settings.fabric_sql_default_lakehouse,
                # Backward compat: variáveis legadas para um único lakehouse
                "FABRIC_SQL_ENDPOINT": settings.fabric_sql_endpoint,
                "FABRIC_LAKEHOUSE_NAME": settings.fabric_lakehouse_name,
            },
        }
    }


# ─── Lista de Tools ───────────────────────────────────────────────────────────

FABRIC_SQL_MCP_TOOLS = [
    # Registry — lista lakehouses disponíveis no .env
    "mcp__fabric_sql__fabric_sql_list_lakehouses",
    # Diagnóstico — execute primeiro se houver erros de conexão
    "mcp__fabric_sql__fabric_sql_diagnostics",
    # Descoberta de schema — substitui mcp__fabric_community__list_tables para schemas customizados
    "mcp__fabric_sql__fabric_sql_list_schemas",
    "mcp__fabric_sql__fabric_sql_list_tables",
    "mcp__fabric_sql__fabric_sql_describe_table",
    "mcp__fabric_sql__fabric_sql_count_tables_by_schema",
    # Execução SQL — SELECT e consultas de metadados
    "mcp__fabric_sql__fabric_sql_execute",
    "mcp__fabric_sql__fabric_sql_sample_table",
]
