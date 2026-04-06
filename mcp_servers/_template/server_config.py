"""
TEMPLATE — Configuração MCP para [NOME DA PLATAFORMA].

Instruções para adicionar uma nova plataforma:

1. Copie este diretório:
   cp -r mcp_servers/_template mcp_servers/snowflake

2. Renomeie e implemente a função get_config:
   mv mcp_servers/snowflake/server_config.py  (já copiado)
   → Implemente get_snowflake_mcp_config()

3. Registre em config/mcp_servers.py:
   from mcp_servers.snowflake.server_config import get_snowflake_mcp_config
   all_configs = { ..., "snowflake": get_snowflake_mcp_config }

4. (Opcional) Crie um AgentDefinition especialista:
   agents/definitions/snowflake_expert.py

5. (Opcional) Registre o agente em agents/supervisor.py
"""

import os


def get_template_mcp_config() -> dict:
    """
    Retorna a configuração MCP para [NOME DA PLATAFORMA].

    Tipos de servidor:
      - "stdio": processo local via stdin/stdout (mais comum)
      - "sse":   Server-Sent Events via HTTP
      - "http":  HTTP REST endpoint
    """
    return {
        "platform_name": {
            "type": "stdio",  # ou "sse" / "http"
            "command": "your-mcp-server-command",  # ex: "uvx", "python", "node"
            "args": [],  # argumentos do comando
            "env": {
                "PLATFORM_HOST": os.environ.get("PLATFORM_HOST", ""),
                "PLATFORM_TOKEN": os.environ.get("PLATFORM_TOKEN", ""),
            },
        }
    }


TEMPLATE_MCP_TOOLS = [
    # Liste aqui as tools expostas pelo servidor
    # Formato: "mcp__<server_name>__<tool_name>"
    "mcp__platform_name__list_something",
    "mcp__platform_name__execute_query",
]
