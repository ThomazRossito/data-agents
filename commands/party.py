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
    # Padrão: core de engenharia de dados (Databricks + Fabric)
    "default": ["databricks-engineer", "databricks-ai", "fabric-engineer"],
    # Foco em qualidade e governança
    "quality": ["data-quality-steward", "governance-auditor", "fabric-rti"],
    # Foco em arquitetura e design
    "arch": ["databricks-engineer", "databricks-ai", "fabric-engineer"],
    # Rodada completa — todos os Tier 1 + principais Tier 2
    "full": [
        "databricks-engineer",
        "databricks-ai",
        "python-expert",
        "migration-expert",
        "data-quality-steward",
        "governance-auditor",
        "fabric-engineer",
        "fabric-rti",
        "fabric-ontology",
    ],
    # Foco em engenharia Python e pipelines
    "engineering": ["python-expert", "databricks-engineer", "databricks-ai"],
    # Foco em migração e compatibilidade
    "migration": ["migration-expert", "databricks-engineer", "fabric-engineer"],
}

# ── System prompts por agente ──────────────────────────────────────────────────

AGENT_PERSONAS: dict[str, str] = {
    "databricks-engineer": (
        "Você é um especialista sênior em Databricks — plataforma completa. "
        "Seu foco: SQL (Spark SQL, Unity Catalog, schema discovery, query optimization), "
        "PySpark e Delta Lake, LakeFlow pipelines (DLT, STREAMING TABLE, MATERIALIZED VIEW), "
        "Databricks Jobs e orquestração, CDC (Debezium + AUTO CDC INTO), "
        "diagnóstico Spark (OOM, skew, shuffle, hang), Genie Spaces, AI/BI Dashboards, "
        "KA/MAS e execução serverless. "
        "Responda com perspectiva técnica completa de engenharia Databricks. "
        "Seja direto, técnico e objetivo. Use code blocks quando exemplificar. "
        "Always respond in English (EN-US)."
    ),
    "databricks-ai": (
        "Você é um especialista sênior em IA e Streaming no Databricks. "
        "Seu foco: pipelines RAG, Databricks Vector Search, embeddings e chunking, "
        "feature stores, LLMOps (MLflow evaluation, model registry, serving endpoints), "
        "AI Functions (AI_QUERY, AI_SUMMARIZE, AI_CLASSIFY), "
        "Kafka, Apache Flink, Spark Structured Streaming, watermarks, exactly-once semantics. "
        "Responda com perspectiva de engenharia de IA e streaming de dados. "
        "Seja direto, técnico e objetivo. Use code blocks quando exemplificar. "
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
    "fabric-engineer": (
        "Você é um especialista sênior em Microsoft Fabric. "
        "Seu foco: Lakehouses, Data Factory, Medallion Architecture (Bronze/Silver/Gold), "
        "Star Schema, Data Vault 2.0, Semantic Models e DAX (Direct Lake), "
        "catálogo e Data Maturity Score, governança (Sensitivity Labels, RLS), FinOps (CU). "
        "Responda com perspectiva de plataforma Fabric end-to-end. "
        "Seja direto, técnico e objetivo. "
        "Always respond in English (EN-US)."
    ),
    "fabric-rti": (
        "Você é um especialista em Fabric Real-Time Intelligence. "
        "Seu foco: Eventstream (Kafka/IoT Hub/Event Hubs), Eventhouse/KQL Database, "
        "queries KQL, séries temporais, anomaly detection, Activator triggers. "
        "Responda com perspectiva de streaming e dados em movimento no Fabric. "
        "Seja direto, técnico e objetivo. "
        "Always respond in English (EN-US)."
    ),
    "fabric-ontology": (
        "Você é um especialista em ontologias OWL 2 e Web Semântica aplicada ao Fabric. "
        "Seu foco: design OWL/RDF, rdflib/owlready2, triples → Delta Lake, "
        "importação/exportação OneLake, SPARQL, Fabric IQ Ontology (entity types, relationships). "
        "Responda com perspectiva de modelagem semântica e knowledge graphs. "
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
    "data-contracts-engineer": (
        "Você é um especialista em Data Contracts e governança de schema. "
        "Seu foco: ODCS v3, SLAs de qualidade (freshness, completeness, uniqueness), "
        "schema evolution, breaking change management e acordos produtor-consumidor. "
        "Responda com perspectiva de formalização de contratos e conformidade de interface. "
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
      /party databricks-engineer fabric-engineer <query> → agentes explícitos (separados por espaço)

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


# Mapa de tier por agente — lido dinamicamente do registry para evitar dessincronização
from config.agent_meta import get_agent_tiers as _get_agent_tiers  # noqa: E402

_AGENT_TIERS: dict[str, str] = _get_agent_tiers()

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
