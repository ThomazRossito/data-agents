"""
commands/party.py — Lógica do DOMA Party Mode (/party).

Spawna múltiplos agentes especialistas em paralelo, cada um respondendo
de forma independente à mesma query. Produz perspectivas genuinamente
distintas sem o viés de convergência de um único LLM roleplaying personagens.

Importado por:
  - main.py  (CLI interativo)

Uso típico:
    from commands.party import run_party_query, PARTY_GROUPS, parse_party_args

    agent_names, query = parse_party_args("/party --quality analise os dados")
    results = await run_party_query(query, agent_names)
    for name, text, cost in results:
        print(f"{name}: {text}")
"""

from __future__ import annotations

import asyncio
import logging

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query as sdk_query,
)

from config.settings import settings

logger = logging.getLogger("data_agents.party")

# ── Grupos temáticos de agentes ────────────────────────────────────────────────

PARTY_GROUPS: dict[str, list[str]] = {
    # Padrão: core de engenharia de dados
    "default": ["sql-expert", "spark-expert", "pipeline-architect"],
    # Foco em qualidade e governança
    "quality": ["data-quality-steward", "governance-auditor", "semantic-modeler"],
    # Foco em arquitetura e design
    "arch": ["pipeline-architect", "spark-expert", "sql-expert"],
    # Rodada completa — Tier 1 + principais Tier 2
    "full": [
        "sql-expert",
        "spark-expert",
        "pipeline-architect",
        "data-quality-steward",
        "governance-auditor",
        "semantic-modeler",
    ],
}

# ── System prompts por agente ──────────────────────────────────────────────────

AGENT_PERSONAS: dict[str, str] = {
    "sql-expert": (
        "Você é um especialista sênior em SQL, schemas e metadados de dados. "
        "Seu foco: Spark SQL, T-SQL, KQL, Unity Catalog, Fabric Lakehouses, otimização de queries. "
        "Responda com perspectiva técnica de SQL e modelagem de dados. "
        "Seja direto, técnico e objetivo. Use code blocks quando exemplificar. "
        "Responda em português brasileiro."
    ),
    "spark-expert": (
        "Você é um especialista sênior em Apache Spark e Python. "
        "Seu foco: PySpark, Delta Lake, Spark Declarative Pipelines (DLT/LakeFlow), "
        "transformações, performance e arquitetura Medallion. "
        "Responda com perspectiva de engenharia de processamento distribuído. "
        "Seja direto, técnico e objetivo. Use code blocks quando exemplificar. "
        "Responda em português brasileiro."
    ),
    "pipeline-architect": (
        "Você é um arquiteto sênior de pipelines de dados. "
        "Seu foco: ETL/ELT cross-platform, orquestração, Databricks Jobs, "
        "Data Factory Fabric, movimentação entre plataformas e tratamento de falhas. "
        "Responda com perspectiva de design e arquitetura de sistemas de dados. "
        "Seja direto, técnico e objetivo. "
        "Responda em português brasileiro."
    ),
    "data-quality-steward": (
        "Você é um especialista em qualidade de dados. "
        "Seu foco: validação com Great Expectations/Spark expectations, profiling, "
        "detecção de schema drift, SLAs de qualidade, alertas no Fabric Activator. "
        "Responda com perspectiva de confiabilidade e confiança nos dados. "
        "Seja direto, técnico e objetivo. "
        "Responda em português brasileiro."
    ),
    "governance-auditor": (
        "Você é um especialista em governança de dados. "
        "Seu foco: auditoria de acessos, Unity Catalog, linhagem cross-platform, "
        "classificação PII, conformidade LGPD/GDPR. "
        "Responda com perspectiva de compliance e segurança de dados. "
        "Seja direto, técnico e objetivo. "
        "Responda em português brasileiro."
    ),
    "semantic-modeler": (
        "Você é um especialista em modelagem semântica e consumo analítico. "
        "Seu foco: Fabric Direct Lake, DAX, Metric Views Databricks, "
        "Genie Spaces (Conversational BI), AI/BI Dashboards. "
        "Responda com perspectiva de consumo analítico e valor de negócio dos dados. "
        "Seja direto, técnico e objetivo. "
        "Responda em português brasileiro."
    ),
}

_DEFAULT_PERSONA = (
    "Você é um especialista em Engenharia de Dados (Databricks, Fabric, Spark, SQL). "
    "Responda em português brasileiro, de forma direta e técnica."
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def parse_party_args(user_input: str) -> tuple[list[str], str]:
    """
    Extrai lista de agentes e query limpa do input do usuário.

    Formatos aceitos:
      /party <query>                        → grupo "default"
      /party --quality <query>              → grupo "quality"
      /party --arch <query>                 → grupo "arch"
      /party --full <query>                 → grupo "full"
      /party sql-expert spark-expert <query> → agentes explícitos (separados por espaço)

    Returns:
        (agent_names, clean_query)
    """
    # Remove o prefixo /party
    parts = user_input.split(maxsplit=1)
    rest = parts[1].strip() if len(parts) > 1 else ""

    if not rest:
        return PARTY_GROUPS["default"], ""

    # Flag de grupo
    for flag, group_key in [("--quality", "quality"), ("--arch", "arch"), ("--full", "full")]:
        if rest.startswith(flag):
            query = rest[len(flag) :].strip()
            return PARTY_GROUPS[group_key], query

    # Agentes explícitos: cada token que bate com um agente conhecido
    known_agents = set(AGENT_PERSONAS.keys())
    tokens = rest.split()
    explicit_agents: list[str] = []
    query_start = 0
    for i, token in enumerate(tokens):
        if token in known_agents:
            explicit_agents.append(token)
            query_start = i + 1
        else:
            break  # primeiro token não-agente → começo da query

    if explicit_agents:
        query = " ".join(tokens[query_start:]).strip()
        return explicit_agents, query

    # Nenhuma flag nem agentes explícitos → grupo default com toda a string como query
    return PARTY_GROUPS["default"], rest


def _build_agent_options(agent_name: str) -> ClaudeAgentOptions:
    """Constrói ClaudeAgentOptions mínimo para um agente do Party Mode."""
    persona = AGENT_PERSONAS.get(agent_name, _DEFAULT_PERSONA)
    return ClaudeAgentOptions(
        model=settings.default_model,
        system_prompt=persona,
        allowed_tools=[],
        agents=None,
        mcp_servers={},
        max_turns=1,
        permission_mode="bypassPermissions",
    )


# ── Core async ────────────────────────────────────────────────────────────────


async def _query_single_agent(  # pragma: no cover
    agent_name: str,
    query: str,
) -> tuple[str, str, float]:
    """
    Executa query em um único agente do Party Mode.

    Returns:
        (agent_name, response_text, cost_usd)
    """
    options = _build_agent_options(agent_name)
    response_text = ""
    cost = 0.0

    try:
        async for message in sdk_query(prompt=query, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock) and block.text.strip():
                        response_text += block.text
            elif isinstance(message, ResultMessage):
                cost = float(message.total_cost_usd or 0)
    except Exception as e:
        logger.error("Party Mode — erro no agente %s: %s", agent_name, e, exc_info=True)
        response_text = f"_Erro ao consultar agente: {e}_"

    return agent_name, response_text, cost


async def run_party_query(  # pragma: no cover
    query: str,
    agent_names: list[str],
) -> list[tuple[str, str, float]]:
    """
    Spawna todos os agentes em paralelo via asyncio.gather.

    Returns:
        Lista de (agent_name, response_text, cost_usd) na ordem dos agent_names.
    """
    if not query.strip():
        return [(name, "_Nenhuma query fornecida._", 0.0) for name in agent_names]

    tasks = [_query_single_agent(name, query) for name in agent_names]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output: list[tuple[str, str, float]] = []
    for i, result in enumerate(results):
        name = agent_names[i]
        if isinstance(result, Exception):
            logger.error("Party Mode — gather exception para %s: %s", name, result)
            output.append((name, f"_Erro inesperado: {result}_", 0.0))
        else:
            output.append(result)  # type: ignore[arg-type]

    return output
