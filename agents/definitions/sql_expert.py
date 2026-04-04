from claude_agent_sdk import AgentDefinition

from agents.prompts.sql_expert_prompt import SQL_EXPERT_SYSTEM_PROMPT
from mcp_servers.databricks.server_config import DATABRICKS_MCP_READONLY_TOOLS
from mcp_servers.fabric.server_config import FABRIC_MCP_TOOLS, FABRIC_COMMUNITY_MCP_TOOLS
from mcp_servers.fabric_rti.server_config import FABRIC_RTI_READONLY_TOOLS


def create_sql_expert() -> AgentDefinition:
    """
    Cria o AgentDefinition do SQL Expert.

    Tools: apenas leitura e descoberta de metadados — sem escrita ou execução de jobs.
    MCP: acesso a Databricks, Fabric e Fabric RTI para introspecção e queries.
    """
    # Tools Fabric filtradas: apenas descoberta (sem upload/delete)
    fabric_readonly = [
        t for t in FABRIC_MCP_TOOLS + FABRIC_COMMUNITY_MCP_TOOLS
        if any(kw in t for kw in [
            "list_", "get_", "download_", "sample_",
        ])
    ]

    return AgentDefinition(
        description=(
            "Especialista em SQL e metadados de dados. Use para: "
            "descoberta de schemas e tabelas em Databricks ou Fabric, "
            "geração e otimização de queries SQL (Spark SQL, T-SQL, KQL), "
            "análise exploratória via SQL, "
            "introspecção de catálogos Unity Catalog e Fabric Lakehouses, "
            "queries KQL em Fabric Real-Time Intelligence (Eventhouse)."
        ),
        prompt=SQL_EXPERT_SYSTEM_PROMPT,
        tools=(
            ["Read", "Grep", "Glob"]
            + DATABRICKS_MCP_READONLY_TOOLS
            + fabric_readonly
            + FABRIC_RTI_READONLY_TOOLS
        ),
        model="sonnet",
        mcpServers=["databricks", "fabric", "fabric_community", "fabric_rti"],
    )
