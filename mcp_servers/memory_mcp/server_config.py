"""
Configuração do MCP Server: memory_mcp.

Knowledge Graph persistente baseado em entidades e relações.
Complementa (não substitui) o módulo memory/ existente do projeto.

DIFERENÇA EM RELAÇÃO AO MÓDULO memory/ DO PROJETO:
  - memory/ (existente): memória episódica e contextual — captura fatos da sessão,
    aplica decay temporal, faz retrieval semântico por query. Foco em "o que aconteceu".
  - memory_mcp (este): knowledge graph de entidades — armazena entidades nomeadas
    (tabelas, schemas, projetos, times) e suas relações de forma estruturada e
    persistente. Foco em "o que existe e como se relaciona".

Casos de uso no data-agents:
  - Pipeline Architect: memorizar arquitetura de pipelines existentes, relações entre
    tabelas, decisões de design recorrentes, padrões aprovados pelo time
  - Governance Auditor: construir grafo de linhagem manual, registrar classificações
    de dados sensíveis, manter registro de decisões de conformidade

Servidor: @modelcontextprotocol/server-memory (via npx)
Protocolo: stdio
Autenticação: não requerida
Persistência: arquivo JSON local (memory.json no diretório de execução)

Custo: gratuito (open source oficial da Anthropic)

Referência: https://github.com/modelcontextprotocol/servers/tree/main/src/memory
"""


def get_memory_mcp_config() -> dict:
    """Retorna a configuração MCP para o Memory MCP (knowledge graph)."""
    return {
        "memory_mcp": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-memory"],
            "env": {},
        }
    }


# ─── Lista de Tools ───────────────────────────────────────────────────────────

MEMORY_MCP_TOOLS = [
    # Leitura do grafo — sempre use primeiro para ver o que já está memorizado
    "mcp__memory_mcp__read_graph",
    # Busca entidades por query de texto
    # Parâmetros: query (string)
    "mcp__memory_mcp__search_nodes",
    # Abre entidades específicas por nome
    # Parâmetros: names (lista de strings)
    "mcp__memory_mcp__open_nodes",
    # Cria novas entidades no grafo
    # Parâmetros: entities [{name, entityType, observations}]
    "mcp__memory_mcp__create_entities",
    # Cria relações entre entidades existentes
    # Parâmetros: relations [{from, to, relationType}]
    "mcp__memory_mcp__create_relations",
    # Adiciona observações a entidades existentes
    # Parâmetros: observations [{entityName, contents}]
    "mcp__memory_mcp__add_observations",
    # Remove entidades do grafo (use com cuidado)
    # Parâmetros: entityNames (lista de strings)
    "mcp__memory_mcp__delete_entities",
    # Remove observações específicas de uma entidade
    # Parâmetros: deletions [{entityName, observations}]
    "mcp__memory_mcp__delete_observations",
    # Remove relações do grafo
    # Parâmetros: relations [{from, to, relationType}]
    "mcp__memory_mcp__delete_relations",
]

# Subconjunto somente leitura do knowledge graph
MEMORY_MCP_READONLY_TOOLS = [
    "mcp__memory_mcp__read_graph",
    "mcp__memory_mcp__search_nodes",
    "mcp__memory_mcp__open_nodes",
]
