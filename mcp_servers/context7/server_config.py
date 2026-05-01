"""
Configuração do MCP Server: context7.

Provê documentação atualizada de bibliotecas diretamente no contexto do agente,
resolvendo o problema de docs desatualizadas no treinamento do modelo.

Ao invés de usar conhecimento estático do treinamento, o agente busca a referência
real e atual de qualquer biblioteca — Databricks SDK, Fabric API, Claude Agent SDK,
PySpark, Delta Lake, etc.

Servidor: @upstash/context7-mcp (via npx)
Protocolo: stdio
Autenticação: não requerida no plano gratuito (repos públicos)

Plano gratuito: 1.000 requests/mês
Plano Pro: $7/seat/mês — incluí repos privados e limites maiores

Referência: https://context7.com/docs
"""


def get_context7_mcp_config() -> dict:
    """Retorna a configuração MCP para o Context7."""
    from config.settings import settings  # importação local para evitar circular import

    env: dict = {}
    if settings.context7_api_key:
        env["CONTEXT7_API_KEY"] = settings.context7_api_key

    return {
        "context7": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@upstash/context7-mcp@latest"],
            "env": env,
        }
    }


# ─── Lista de Tools ───────────────────────────────────────────────────────────

CONTEXT7_MCP_TOOLS = [
    # Resolve o ID de uma biblioteca para uso com get-library-docs
    # Ex: "databricks-sdk-python" → resolve para o ID correto no Context7
    "mcp__context7__resolve-library-id",
    # Busca documentação atualizada de uma biblioteca pelo ID resolvido
    # Parâmetros: context7CompatibleLibraryID, topic (opcional), tokens (opcional)
    "mcp__context7__get-library-docs",
]
