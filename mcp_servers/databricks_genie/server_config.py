"""
Configuração do MCP Server Customizado: databricks_genie.

Expõe a Genie Conversation API e Space Management API do Databricks,
resolvendo o gap do databricks-mcp-server oficial que não inclui as tools
de Genie (ask_genie, get_genie, create_or_update_genie, migrate_genie, delete_genie).

Servidor: databricks-genie-mcp (entry point em pyproject.toml)
Protocolo: stdio
Autenticação: Bearer Token (DATABRICKS_TOKEN) via REST API
Dependências: nenhuma adicional (usa urllib da stdlib Python)

REGISTRY DE SPACES: Suporta nomes amigáveis mapeados para space_ids reais.
  DATABRICKS_GENIE_SPACES={"retail-sales": "01f117197b5319fb972e10a45735b28c",
                            "hr-analytics": "01abc123..."}
  DATABRICKS_GENIE_DEFAULT_SPACE=retail-sales

Como encontrar o Space ID:
  Databricks → AI/BI → Genie → abra o Space → copie o ID da URL
  Formato: 01f1xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
"""


def get_databricks_genie_mcp_config() -> dict:
    """Retorna a configuração MCP para o servidor databricks_genie customizado."""
    from config.settings import settings  # importação local para evitar circular import

    return {
        "databricks_genie": {
            "type": "stdio",
            "command": settings.databricks_genie_command,
            "args": [],
            "env": {
                # Credenciais Databricks (compartilhadas com databricks-mcp-server)
                "DATABRICKS_HOST": settings.databricks_host,
                "DATABRICKS_TOKEN": settings.databricks_token,
                # Registry de Genie Spaces com nomes amigáveis
                "DATABRICKS_GENIE_SPACES": settings.databricks_genie_spaces,
                "DATABRICKS_GENIE_DEFAULT_SPACE": settings.databricks_genie_default_space,
            },
        }
    }


# ─── Lista de Tools ───────────────────────────────────────────────────────────

DATABRICKS_GENIE_MCP_TOOLS = [
    # Diagnóstico — execute primeiro se houver erros de conexão
    "mcp__databricks_genie__genie_diagnostics",
    # Descoberta de spaces
    "mcp__databricks_genie__genie_list_spaces",
    "mcp__databricks_genie__genie_get",
    # Conversation API — perguntas em linguagem natural
    "mcp__databricks_genie__genie_ask",
    "mcp__databricks_genie__genie_followup",
    # Space Management
    "mcp__databricks_genie__genie_create_or_update",
    "mcp__databricks_genie__genie_delete",
    # Export / Import / Migração entre ambientes
    "mcp__databricks_genie__genie_export",
    "mcp__databricks_genie__genie_import",
]

# Subconjunto somente leitura (para agentes sem permissão de criar/alterar spaces)
DATABRICKS_GENIE_MCP_READONLY_TOOLS = [
    "mcp__databricks_genie__genie_diagnostics",
    "mcp__databricks_genie__genie_list_spaces",
    "mcp__databricks_genie__genie_get",
    "mcp__databricks_genie__genie_ask",
    "mcp__databricks_genie__genie_followup",
    "mcp__databricks_genie__genie_export",
]
