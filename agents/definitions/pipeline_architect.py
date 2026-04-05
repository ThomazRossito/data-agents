from claude_agent_sdk import AgentDefinition

from agents.prompts.pipeline_architect_prompt import PIPELINE_ARCHITECT_SYSTEM_PROMPT
from mcp_servers.databricks.server_config import DATABRICKS_MCP_TOOLS
from mcp_servers.fabric.server_config import ALL_FABRIC_TOOLS
from mcp_servers.fabric_rti.server_config import FABRIC_RTI_MCP_TOOLS


def create_pipeline_architect() -> AgentDefinition:
    """
    Cria o AgentDefinition do Pipeline Architect.

    Acesso amplo — opera em múltiplas plataformas simultaneamente.
    É o único agente autorizado a executar jobs, disparar pipelines e mover dados.
    """
    # Tools RTI relevantes para pipelines (sem kusto_command destrutivo)
    rti_pipeline_tools = [
        t for t in FABRIC_RTI_MCP_TOOLS
        if "kusto_command" not in t  # remove operações destrutivas
    ]

    return AgentDefinition(
        description=(
            "Arquiteto e executor de Pipelines de Dados (ETL/ELT). Use para: "
            "design e execução de pipelines cross-platform (Fabric ↔ Databricks), "
            "orquestração de Jobs Databricks e Spark Declarative Pipelines (LakeFlow), "
            "configuração e monitoramento de pipelines Data Factory no Fabric, "
            "movimentação de dados entre OneLake e Unity Catalog, "
            "monitoramento end-to-end com tratamento de falhas."
        ),
        prompt=PIPELINE_ARCHITECT_SYSTEM_PROMPT,
        tools=(
            ["Read", "Write", "Grep", "Glob", "Bash"]
            + DATABRICKS_MCP_TOOLS
            + ALL_FABRIC_TOOLS
            + rti_pipeline_tools
        ),
        model="claude-opus-4-6",
        mcpServers=["databricks", "fabric", "fabric_community", "fabric_rti"],
    )
