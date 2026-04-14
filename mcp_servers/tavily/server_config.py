"""
Configuração do MCP Server: tavily.

Provê busca web otimizada para LLMs com resultados prontos para consumo pelo modelo.
Diferente de uma busca genérica, o Tavily retorna conteúdo já processado e relevante,
sem ruído de HTML/CSS/ads.

Casos de uso no data-agents:
  - Business Analyst: pesquisa de mercado, benchmarks de indústria, documentação de APIs
  - Governance Auditor: busca de normas LGPD/GDPR, frameworks de governança, regulatórios
  - Qualquer agente: troubleshooting de erros sem documentação local

Servidor: tavily-mcp (via uvx)
Protocolo: stdio
Autenticação: TAVILY_API_KEY (obrigatório)

Plano gratuito: 1.000 créditos/mês — sem cartão de crédito
  - Busca básica: 1 crédito/request
  - Busca avançada (com extração de conteúdo): mais créditos
Plano pago: $0.008/crédito ou pacotes a partir de $30/mês

Adquirida pela Nebius em fevereiro/2026.
Referência: https://docs.tavily.com/
"""


def get_tavily_mcp_config() -> dict:
    """Retorna a configuração MCP para o Tavily."""
    from config.settings import settings  # importação local para evitar circular import

    return {
        "tavily": {
            "type": "stdio",
            "command": "uvx",
            "args": ["tavily-mcp"],
            "env": {
                "TAVILY_API_KEY": settings.tavily_api_key,
            },
        }
    }


# ─── Lista de Tools ───────────────────────────────────────────────────────────

TAVILY_MCP_TOOLS = [
    # Busca web otimizada para LLMs — retorna resultados limpos sem ruído HTML
    # Parâmetros: query, search_depth ("basic"|"advanced"), max_results, include_answer
    "mcp__tavily__tavily-search",
    # Extrai conteúdo completo de uma URL específica — útil para ler docs e artigos
    # Parâmetros: urls (lista)
    "mcp__tavily__tavily-extract",
]
