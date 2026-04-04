from claude_agent_sdk import AgentDefinition

from agents.prompts.spark_expert_prompt import SPARK_EXPERT_SYSTEM_PROMPT


def create_spark_expert() -> AgentDefinition:
    """
    Cria o AgentDefinition do Python/Spark Expert.

    O Spark Expert APENAS GERA CÓDIGO — não acessa MCP diretamente.
    Recebe schemas e contexto do Supervisor e devolve código PySpark pronto.
    """
    return AgentDefinition(
        description=(
            "Especialista em Python e Apache Spark. Use para: "
            "geração de código PySpark, Spark SQL e Spark Declarative Pipelines (DLT/LakeFlow), "
            "transformações de dados com DataFrames, "
            "operações Delta Lake (MERGE, OPTIMIZE, VACUUM, Z-ORDER, SCD1/SCD2), "
            "debug e otimização de código Python/Spark existente, "
            "conversão de pandas para PySpark, "
            "implementação de padrões ETL Bronze→Silver→Gold."
        ),
        prompt=SPARK_EXPERT_SYSTEM_PROMPT,
        # Sem MCP — apenas gera código para ser executado pelo pipeline-architect
        tools=["Read", "Grep", "Glob", "Write"],
        model="sonnet",
    )
