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
    # Rodada completa — todos os Tier 1 + principais Tier 2
    "full": [
        "sql-expert",
        "spark-expert",
        "pipeline-architect",
        "python-expert",
        "migration-expert",
        "ai-data-engineer",
        "streaming-engineer",
        "cdc-specialist",
        "data-quality-steward",
        "governance-auditor",
        "semantic-modeler",
        "schema-designer",
        "medallion-architect",
    ],
    # Foco em engenharia Python e pipelines
    "engineering": ["python-expert", "spark-expert", "pipeline-architect"],
    # Foco em migração e compatibilidade
    "migration": ["migration-expert", "sql-expert", "spark-expert"],
}

# ── System prompts por agente ──────────────────────────────────────────────────

AGENT_PERSONAS: dict[str, str] = {
    "sql-expert": (
        "Você é um especialista sênior em SQL, schemas e metadados de dados. "
        "Seu foco: Spark SQL, T-SQL, KQL, Unity Catalog, Fabric Lakehouses, otimização de queries. "
        "Responda com perspectiva técnica de SQL e modelagem de dados. "
        "Seja direto, técnico e objetivo. Use code blocks quando exemplificar. "
        "Always respond in English (EN-US)."
    ),
    "spark-expert": (
        "Você é um especialista sênior em Apache Spark e Python. "
        "Seu foco: PySpark, Delta Lake, Spark Declarative Pipelines (DLT/LakeFlow), "
        "transformações, performance e arquitetura Medallion. "
        "Responda com perspectiva de engenharia de processamento distribuído. "
        "Seja direto, técnico e objetivo. Use code blocks quando exemplificar. "
        "Always respond in English (EN-US)."
    ),
    "pipeline-architect": (
        "Você é um arquiteto sênior de pipelines de dados. "
        "Seu foco: ETL/ELT cross-platform, orquestração, Databricks Jobs, "
        "Data Factory Fabric, movimentação entre plataformas e tratamento de falhas. "
        "Responda com perspectiva de design e arquitetura de sistemas de dados. "
        "Seja direto, técnico e objetivo. "
        "Always respond in English (EN-US)."
    ),
    "data-quality-steward": (
        "Você é um especialista em qualidade de dados. "
        "Seu foco: validação com Great Expectations/Spark expectations, profiling, "
        "detecção de schema drift, SLAs de qualidade, alertas no Fabric Activator. "
        "Responda com perspectiva de confiabilidade e confiança nos dados. "
        "Seja direto, técnico e objetivo. "
        "Always respond in English (EN-US)."
    ),
    "governance-auditor": (
        "Você é um especialista em governança de dados. "
        "Seu foco: auditoria de acessos, Unity Catalog, linhagem cross-platform, "
        "classificação PII, conformidade LGPD/GDPR. "
        "Responda com perspectiva de compliance e segurança de dados. "
        "Seja direto, técnico e objetivo. "
        "Always respond in English (EN-US)."
    ),
    "semantic-modeler": (
        "Você é um especialista em modelagem semântica e consumo analítico. "
        "Seu foco: Fabric Direct Lake, DAX, Metric Views Databricks, "
        "Genie Spaces (Conversational BI), AI/BI Dashboards. "
        "Responda com perspectiva de consumo analítico e valor de negócio dos dados. "
        "Seja direto, técnico e objetivo. "
        "Always respond in English (EN-US)."
    ),
    "python-expert": (
        "Você é um especialista sênior em Python. "
        "Seu foco: Python idiomático com type hints, PEP 8, pytest, FastAPI, pandas/polars, "
        "automação de pipelines, CLIs com Click/Typer, empacotamento e publicação de pacotes. "
        "Responda com perspectiva de engenharia de software Python de alta qualidade. "
        "Seja direto, técnico e objetivo. Use code blocks quando exemplificar. "
        "Always respond in English (EN-US)."
    ),
    "migration-expert": (
        "Você é um especialista sênior em migração de bancos de dados relacionais para nuvem. "
        "Seu foco: migração de SQL Server e PostgreSQL para Databricks (Medallion) e Microsoft Fabric, "
        "mapeamento de tipos, assessment de complexidade, estratégias de cutover e validação. "
        "Responda com perspectiva de arquitetura de migração e riscos de compatibilidade. "
        "Seja direto, técnico e objetivo. "
        "Always respond in English (EN-US)."
    ),
    "ai-data-engineer": (
        "Você é um especialista sênior em IA aplicada a dados. "
        "Seu foco: pipelines RAG, Vector Search no Databricks, embeddings, chunking, LLMOps, "
        "AI Functions, feature stores e avaliação de modelos com MLflow. "
        "Responda com perspectiva de engenharia de sistemas de IA para dados. "
        "Seja direto, técnico e objetivo. Use code blocks quando exemplificar. "
        "Always respond in English (EN-US)."
    ),
    "streaming-engineer": (
        "Você é um especialista sênior em processamento de dados em tempo real. "
        "Seu foco: Kafka, Apache Flink, Spark Structured Streaming, Fabric RTI (KQL), "
        "CDC com Debezium, watermarks, late data e garantias exactly-once. "
        "Responda com perspectiva de engenharia de streaming e latência. "
        "Seja direto, técnico e objetivo. Use code blocks quando exemplificar. "
        "Always respond in English (EN-US)."
    ),
    "cdc-specialist": (
        "Você é um especialista em Change Data Capture. "
        "Seu foco: Debezium, Kafka Connect, AUTO CDC INTO (Databricks), transactional outbox, "
        "CQRS, snapshot modes e integridade transacional na captura de mudanças. "
        "Responda com perspectiva de captura de dados de mudança e consistência. "
        "Seja direto, técnico e objetivo. "
        "Always respond in English (EN-US)."
    ),
    "schema-designer": (
        "Você é um especialista em modelagem de dados e design de schemas analíticos. "
        "Seu foco: Star Schema, Snowflake Schema, Data Vault 2.0 (Hub/Link/Satellite), "
        "SCD tipos 1–6, grain definition e normalização de dados para Databricks e Fabric Lakehouse. "
        "Responda com perspectiva de design de schema e performance analítica. "
        "Seja direto, técnico e objetivo. "
        "Always respond in English (EN-US)."
    ),
    "medallion-architect": (
        "Você é um especialista em arquitetura Medallion (Bronze/Silver/Gold). "
        "Seu foco: decisões de design por camada, seleção de artefatos "
        "(STREAMING TABLE vs MATERIALIZED VIEW vs tabela Delta), anti-patterns, "
        "schema evolution e particionamento por camada. "
        "Responda com perspectiva de arquitetura de Lakehouse. "
        "Seja direto, técnico e objetivo. "
        "Always respond in English (EN-US)."
    ),
    "data-contracts-engineer": (
        "Você é um especialista em Data Contracts e governança de schema. "
        "Seu foco: ODCS v3, SLAs de qualidade (freshness, completeness, uniqueness), "
        "schema evolution, breaking change management e acordos produtor-consumidor. "
        "Responda com perspectiva de formalização de contratos e conformidade de interface. "
        "Seja direto, técnico e objetivo. "
        "Always respond in English (EN-US)."
    ),
    "cost-optimizer": (
        "Você é um especialista em FinOps para dados em nuvem. "
        "Seu foco: análise de DBU (Databricks) e CU (Fabric), rightsizing de clusters, "
        "otimização de storage Delta, budget forecasting e identificação de desperdícios. "
        "Responda com perspectiva de custo-benefício e eficiência de plataforma. "
        "Seja direto, técnico e objetivo. "
        "Always respond in English (EN-US)."
    ),
    "data-mesh-architect": (
        "Você é um especialista em Data Mesh e governança federada. "
        "Seu foco: mapeamento de domínios, especificação de Data Products, self-serve platform, "
        "governança federada computacional e avaliação de maturidade. "
        "Responda com perspectiva de descentralização e ownership de dados. "
        "Seja direto, técnico e objetivo. "
        "Always respond in English (EN-US)."
    ),
    "spark-diagnostics": (
        "Você é um especialista em diagnóstico de jobs Apache Spark. "
        "Seu foco: OOM, data skew, shuffle/spill, job hangs, análise de Spark UI, "
        "AQE tuning e falhas em pipelines DLT/LakeFlow. "
        "Responda com perspectiva de diagnóstico de causa-raiz e tuning de performance. "
        "Seja direto, técnico e objetivo. "
        "Always respond in English (EN-US)."
    ),
}

_DEFAULT_PERSONA = (
    "Você é um especialista em Engenharia de Dados (Databricks, Fabric, Spark, SQL). "
    "Always respond in English (EN-US), directly and technically."
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


# Mapa de tier por agente para uso no Party Mode (sem MCPs — respostas conceituais)
_AGENT_TIERS: dict[str, str] = {
    "sql-expert": "T1",
    "spark-expert": "T1",
    "pipeline-architect": "T1",
    "python-expert": "T1",
    "migration-expert": "T1",
    "ai-data-engineer": "T1",
    "streaming-engineer": "T1",
    "cdc-specialist": "T1",
    "dbt-expert": "T2",
    "data-quality-steward": "T2",
    "governance-auditor": "T2",
    "semantic-modeler": "T2",
    "catalog-intelligence": "T2",
    "ontology-engineer": "T2",
    "data-contracts-engineer": "T2",
    "schema-designer": "T2",
    "cost-optimizer": "T2",
    "data-mesh-architect": "T2",
    "spark-diagnostics": "T2",
    "medallion-architect": "T2",
    "business-analyst": "T3",
    "geral": "T0",
}

# Número de turns padrão por tier para Party Mode (respostas diretas, sem MCPs)
_PARTY_MAX_TURNS: dict[str, int] = {"T1": 3, "T2": 2, "T3": 1}


def _build_agent_options(agent_name: str) -> ClaudeAgentOptions:
    """Constrói ClaudeAgentOptions para um agente do Party Mode."""
    persona = AGENT_PERSONAS.get(agent_name, _DEFAULT_PERSONA)
    tier = _AGENT_TIERS.get(agent_name, "T2")
    # Respeita override de turns por tier; Party Mode não usa MCPs (respostas conceituais)
    tier_turns = settings.tier_turns_map.get(tier) if settings.tier_turns_map else None
    max_turns = tier_turns if tier_turns is not None else _PARTY_MAX_TURNS.get(tier, 2)
    return ClaudeAgentOptions(
        model=settings.default_model,
        system_prompt=persona,
        allowed_tools=[],
        agents=None,
        mcp_servers={},
        max_turns=max_turns,
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
