"""agents.party — Execução paralela de múltiplos agentes (Party Mode).

Uso via supervisor:
    /party qual a diferença entre Delta Lake e Iceberg?
    /party --sql como escrever SCD Type 2 em Spark SQL?
    /party --quality como garantir qualidade em dados incrementais?
    /party --engineering como processar CSV de 10 GB com eficiência?
    /party --full explique o Unity Catalog

Presets:
    --sql         → sql_expert, spark_expert, pipeline_architect
    --quality     → data_quality, governance_auditor, sql_expert
    --engineering → python_expert, spark_expert, pipeline_architect
    --dbt         → dbt_expert, sql_expert, data_quality
    --full        → spark_expert, sql_expert, pipeline_architect,
                    data_quality, governance_auditor
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.base import AgentResult, BaseAgent
from hooks.output_compressor import compress

logger = logging.getLogger("data_agents.party")

_PARTY_MAX_CHARS = 4000  # por agente, antes de consolidar

_PRESETS: dict[str, list[str]] = {
    "--sql": ["sql_expert", "spark_expert", "pipeline_architect"],
    "--quality": ["data_quality", "governance_auditor", "sql_expert"],
    "--engineering": ["python_expert", "spark_expert", "pipeline_architect"],
    "--dbt": ["dbt_expert", "sql_expert", "data_quality"],
    "--full": [
        "spark_expert", "sql_expert", "pipeline_architect",
        "data_quality", "governance_auditor",
    ],
}

_DEFAULT_PRESET = "--sql"


def parse_party_command(tail: str) -> tuple[list[str], str]:
    """
    Parseia o argumento do /party.

    Retorna (agent_names, query).

    Exemplos:
        "--sql qual join?" → (['sql_expert', 'spark_expert', ...], 'qual join?')
        "--agents sql_expert,dbt_expert ..." → (['sql_expert','dbt_expert'], '...')
        "sem flag ..." → preset default + query completa
    """
    parts = tail.strip().split(maxsplit=1)
    if not parts:
        return _PRESETS[_DEFAULT_PRESET], ""

    flag = parts[0]
    query = parts[1] if len(parts) > 1 else ""

    if flag in _PRESETS:
        return _PRESETS[flag], query

    if flag == "--agents" and query:
        names_part, _, rest = query.partition(" ")
        names = [n.strip() for n in names_part.split(",") if n.strip()]
        return names, rest

    # sem flag reconhecida — usa preset default com tail completo
    return _PRESETS[_DEFAULT_PRESET], tail


def run_party(
    query: str,
    agents: dict[str, BaseAgent],
    agent_names: list[str],
    context: str = "",
) -> AgentResult:
    """
    Executa `query` em paralelo nos agentes listados.

    Retorna AgentResult consolidado com um bloco por agente.
    """
    available = [n for n in agent_names if n in agents]
    missing = [n for n in agent_names if n not in agents]
    if missing:
        logger.warning("Party: agentes não encontrados: %s", missing)
    if not available:
        return AgentResult(
            content="❌ Nenhum agente válido encontrado para o party.",
            tool_calls_count=0,
            tokens_used=0,
        )

    logger.info(
        "Party Mode: %d agentes → %s", len(available), available
    )

    results: dict[str, AgentResult] = {}
    futures = {}

    with ThreadPoolExecutor(max_workers=min(len(available), 5)) as pool:
        for name in available:
            agent = agents[name]
            future = pool.submit(agent.run, query, context)
            futures[future] = name

        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as exc:
                logger.exception("Party: erro no agente %s", name)
                results[name] = AgentResult(
                    content=f"❌ Erro: {exc}",
                    tool_calls_count=0,
                    tokens_used=0,
                )

    # Consolida mantenendo a ordem original
    parts = [f"# 🎉 Party Mode — {len(available)} agentes\n"]
    total_tokens = 0
    total_calls = 0

    for name in available:
        result = results.get(name)
        if result is None:
            continue
        body = compress(result.content, _PARTY_MAX_CHARS)
        parts.append(f"\n---\n## 🤖 `{name}`\n\n{body}\n")
        total_tokens += result.tokens_used
        total_calls += result.tool_calls_count

    return AgentResult(
        content="\n".join(parts),
        tool_calls_count=total_calls,
        tokens_used=total_tokens,
    )
