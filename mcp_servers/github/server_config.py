"""
Configuração do MCP Server: github.

Integração com GitHub para gestão de repositórios, issues e pull requests.
Permite que agentes criem PRs com código gerado, abram issues, naveguem em
repositórios e façam buscas em código — diretamente do fluxo de trabalho.

Casos de uso no data-agents:
  - Pipeline Architect: abrir PR com pipeline gerado, criar branch de feature,
    buscar exemplos de código em repositórios do time, commitar arquivos

Servidor: @modelcontextprotocol/server-github (via npx)
Protocolo: stdio
Autenticação: GITHUB_PERSONAL_ACCESS_TOKEN (obrigatório)

Como criar o token:
  GitHub → Settings → Developer Settings → Personal Access Tokens → Tokens (classic)
  Escopos necessários: repo, read:org (para repos privados)

Custo: gratuito para repositórios públicos e privados (via PAT)

Referência: https://github.com/modelcontextprotocol/servers/tree/main/src/github
"""


def get_github_mcp_config() -> dict:
    """Retorna a configuração MCP para o GitHub."""
    from config.settings import settings  # importação local para evitar circular import

    return {
        "github": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {
                "GITHUB_PERSONAL_ACCESS_TOKEN": settings.github_personal_access_token,
            },
        }
    }


# ─── Lista de Tools ───────────────────────────────────────────────────────────

GITHUB_MCP_TOOLS = [
    # Conteúdo de arquivos e repositórios
    "mcp__github__get_file_contents",
    "mcp__github__create_or_update_file",
    "mcp__github__push_files",
    # Repositórios e branches
    "mcp__github__search_repositories",
    "mcp__github__create_repository",
    "mcp__github__fork_repository",
    "mcp__github__create_branch",
    "mcp__github__list_branches",
    "mcp__github__delete_branch",
    # Commits
    "mcp__github__list_commits",
    "mcp__github__get_commit",
    # Issues
    "mcp__github__create_issue",
    "mcp__github__list_issues",
    "mcp__github__get_issue",
    "mcp__github__update_issue",
    "mcp__github__add_issue_comment",
    # Pull Requests
    "mcp__github__create_pull_request",
    "mcp__github__list_pull_requests",
    "mcp__github__get_pull_request",
    "mcp__github__get_pull_request_diff",
    "mcp__github__merge_pull_request",
    # Busca de código
    "mcp__github__search_code",
    "mcp__github__search_issues",
]

# Subconjunto somente leitura (navegação sem escrita)
GITHUB_MCP_READONLY_TOOLS = [
    "mcp__github__get_file_contents",
    "mcp__github__search_repositories",
    "mcp__github__list_branches",
    "mcp__github__list_commits",
    "mcp__github__get_commit",
    "mcp__github__list_issues",
    "mcp__github__get_issue",
    "mcp__github__list_pull_requests",
    "mcp__github__get_pull_request",
    "mcp__github__get_pull_request_diff",
    "mcp__github__search_code",
    "mcp__github__search_issues",
]
