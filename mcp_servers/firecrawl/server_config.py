"""
Configuração do MCP Server: firecrawl.

Web scraping e crawling estruturado para LLMs. Transforma páginas web em Markdown
limpo, sem ruído de HTML. Suporta crawling de sites inteiros, extração de dados
estruturados e busca integrada.

Casos de uso no data-agents:
  - Pipeline Architect: raspar schemas de APIs externas, documentação de fontes de dados,
    especificações de endpoints REST antes de construir conectores
  - Business Analyst: coletar dados de sites públicos, relatórios anuais, catálogos
    de produtos para alimentar pipelines de ingestão

Servidor: firecrawl-mcp (via npx)
Protocolo: stdio
Autenticação: FIRECRAWL_API_KEY (obrigatório)

Plano gratuito: 500 créditos/mês
  - Scrape: 1 crédito/página
  - Crawl: 1 crédito/página rastreada
Plano pago: a partir de $16/mês (3.000 créditos)

Como obter a API Key: https://www.firecrawl.dev/app/api-keys

Referência: https://docs.firecrawl.dev/mcp
"""


def get_firecrawl_mcp_config() -> dict:
    """Retorna a configuração MCP para o Firecrawl."""
    from config.settings import settings  # importação local para evitar circular import

    return {
        "firecrawl": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "firecrawl-mcp"],
            "env": {
                "FIRECRAWL_API_KEY": settings.firecrawl_api_key,
            },
        }
    }


# ─── Lista de Tools ───────────────────────────────────────────────────────────

FIRECRAWL_MCP_TOOLS = [
    # Scrape de uma única URL → retorna Markdown limpo
    # Parâmetros: url, formats (["markdown","html"]), onlyMainContent, waitFor
    "mcp__firecrawl__firecrawl_scrape",
    # Crawl de um site inteiro (segue links) → retorna lista de páginas em Markdown
    # Parâmetros: url, maxDepth, limit, allowBackwardLinks, allowExternalLinks
    "mcp__firecrawl__firecrawl_crawl",
    # Verifica status de um crawl em andamento (crawls são assíncronos)
    # Parâmetros: id
    "mcp__firecrawl__firecrawl_check_crawl_status",
    # Cancela um crawl em andamento
    # Parâmetros: id
    "mcp__firecrawl__firecrawl_cancel_crawl",
    # Busca web + scraping dos resultados em um único passo
    # Parâmetros: query, limit, lang, country, scrapeOptions
    "mcp__firecrawl__firecrawl_search",
    # Mapeia todos os links de um site sem fazer scraping do conteúdo (mais rápido)
    # Parâmetros: url, includeSubdomains, limit
    "mcp__firecrawl__firecrawl_map",
    # Scrape em lote de múltiplas URLs em paralelo
    # Parâmetros: urls, options
    "mcp__firecrawl__firecrawl_batch_scrape",
    # Verifica status de um batch scrape em andamento
    # Parâmetros: id
    "mcp__firecrawl__firecrawl_check_batch_scrape_status",
    # Extração estruturada de dados de uma URL usando schema JSON
    # Parâmetros: urls, prompt, schema, systemPrompt
    "mcp__firecrawl__firecrawl_extract",
]
