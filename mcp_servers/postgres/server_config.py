"""
Configuração do MCP Server: postgres.

Conexão direta a banco PostgreSQL para execução de queries SQL.
Expõe o banco como recurso navegável e permite execução de queries
somente leitura (SELECT) — sem risco de mutação de dados.

Casos de uso no data-agents:
  - SQL Expert: consultas a bancos PostgreSQL externos (metastore, catálogos,
    sistemas operacionais), comparação de dados entre Postgres e Databricks/Fabric
  - Data Quality Steward: inspeção de schemas e dados em fontes PostgreSQL
    antes de ingestão nos Data Lakes
  - Governance Auditor: auditoria de dados em sistemas transacionais Postgres

Servidor: @modelcontextprotocol/server-postgres (via npx)
Protocolo: stdio
Autenticação: POSTGRES_URL (connection string completa, obrigatório)

Formato da connection string:
  postgresql://usuario:senha@host:5432/banco
  postgresql://usuario:senha@host:5432/banco?sslmode=require  (para ambientes cloud)

Custo: gratuito (open source oficial da Anthropic)

ATENÇÃO: O servidor executa apenas queries somente leitura (SELECT).
Tentativas de INSERT/UPDATE/DELETE/DROP são bloqueadas pelo servidor.

Referência: https://github.com/modelcontextprotocol/servers/tree/main/src/postgres
"""


def get_postgres_mcp_config() -> dict:
    """Retorna a configuração MCP para o PostgreSQL."""
    from config.settings import settings  # importação local para evitar circular import

    return {
        "postgres": {
            "type": "stdio",
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-postgres",
                settings.postgres_url,
            ],
            "env": {},
        }
    }


# ─── Lista de Tools ───────────────────────────────────────────────────────────
# O servidor postgres expõe schemas e tabelas como Resources (não Tools).
# A única Tool é query — use os Resources para descoberta de schema.

POSTGRES_MCP_TOOLS = [
    # Executa uma query SQL somente leitura no banco configurado
    # Parâmetros: sql (string com a query SELECT)
    # ATENÇÃO: apenas SELECT é permitido — INSERT/UPDATE/DELETE são bloqueados
    "mcp__postgres__query",
]
