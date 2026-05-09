"""
commands/analyze.py — Handler do /analyze-project.

Spawna 4 agentes especialistas em paralelo, cada um analisando o projeto
de dados a partir do seu domínio, e consolida o resultado em um relatório
salvo em output/analyze-project/.

Grupos fixos de análise:
  default  → databricks-engineer + fabric-engineer + data-quality-steward + governance-auditor
  --quality → data-quality-steward + governance-auditor + data-contracts-engineer
  --arch    → databricks-engineer + fabric-engineer + data-mesh-architect
  --databricks → databricks-engineer (foco Databricks)
  --fabric  → fabric-engineer (foco Fabric)

Uso:
    /analyze-project [--focus <area>] [descrição do projeto]
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("data_agents.analyze")

# ── Grupos de análise ─────────────────────────────────────────────────────────

ANALYZE_GROUPS: dict[str, list[str]] = {
    "default": [
        "databricks-engineer",
        "fabric-engineer",
        "data-quality-steward",
        "governance-auditor",
    ],
    "quality": ["data-quality-steward", "governance-auditor", "data-contracts-engineer"],
    "arch": ["databricks-engineer", "fabric-engineer", "data-mesh-architect"],
    "databricks": ["databricks-engineer"],
    "fabric": ["fabric-engineer"],
}

# ── Prompts de análise por agente ─────────────────────────────────────────────

_BASE_INSTRUCTION = (
    "You are conducting a professional assessment of a data project. "
    "Be concrete and actionable. Format with clear sections. "
    "If no project description is provided, give a template-based assessment "
    "with the most common issues for this domain.\n\n"
)

ANALYZE_PROMPTS: dict[str, str] = {
    "databricks-engineer": (
        _BASE_INSTRUCTION
        + "## Databricks Engineering Assessment\n\n"
        + "Analyze the Databricks engineering setup for this project. Cover:\n"
        + "1. **Pipeline Architecture** — Bronze/Silver/Gold design, DLT vs Jobs, CDC strategy\n"
        + "2. **SQL & Schema Quality** — naming conventions, partitioning, Liquid Clustering\n"
        + "3. **Spark Performance Risks** — OOM, skew, shuffle, missing OPTIMIZE/VACUUM\n"
        + "4. **Job Orchestration** — dependencies, retries, SLA alerting\n"
        + "5. **Top 3 Improvement Opportunities** — ranked by impact\n\n"
        + "Project context: {task}"
    ),
    "fabric-engineer": (
        _BASE_INSTRUCTION
        + "## Microsoft Fabric Engineering Assessment\n\n"
        + "Analyze the Microsoft Fabric setup for this project. Cover:\n"
        + "1. **Lakehouse & Workspace Design** — structure, naming, environment separation\n"
        + "2. **Semantic Model Quality** — relationships, DAX measures, Direct Lake fit\n"
        + "3. **Data Factory Pipelines** — idempotency, watermarks, error handling\n"
        + "4. **FinOps** — Capacity Unit usage, rightsizing opportunities\n"
        + "5. **Top 3 Improvement Opportunities** — ranked by impact\n\n"
        + "Project context: {task}"
    ),
    "data-quality-steward": (
        _BASE_INSTRUCTION
        + "## Data Quality Assessment\n\n"
        + "Analyze the data quality posture for this project. Cover:\n"
        + "1. **Existing Quality Gates** — expectations, profiling, schema validation\n"
        + "2. **SLA Coverage** — freshness, completeness, uniqueness, null rates\n"
        + "3. **Drift Detection** — schema drift, statistical drift monitoring\n"
        + "4. **Missing Controls** — which layers lack quality checks\n"
        + "5. **Top 3 Quality Risks** — ranked by data trust impact\n\n"
        + "Project context: {task}"
    ),
    "governance-auditor": (
        _BASE_INSTRUCTION
        + "## Governance & Compliance Assessment\n\n"
        + "Analyze the governance and compliance posture for this project. Cover:\n"
        + "1. **Access Controls** — Unity Catalog / Fabric permissions, RLS/OLS, least-privilege\n"
        + "2. **PII Classification** — identified PII columns, masking, tokenization\n"
        + "3. **Lineage Coverage** — cross-platform lineage gaps, impact analysis readiness\n"
        + "4. **Regulatory Compliance** — LGPD/GDPR, audit trail, data retention\n"
        + "5. **Top 3 Governance Risks** — ranked by compliance exposure\n\n"
        + "Project context: {task}"
    ),
    "data-contracts-engineer": (
        _BASE_INSTRUCTION
        + "## Data Contracts Assessment\n\n"
        + "Analyze the data contracts posture for this project. Cover:\n"
        + "1. **Contract Coverage** — which producers/consumers have formal contracts\n"
        + "2. **Schema Stability** — breaking change governance, evolution strategy\n"
        + "3. **SLA Formalization** — freshness, quality, availability commitments\n"
        + "4. **Missing Contracts** — highest-risk interfaces without agreements\n"
        + "5. **Top 3 Contract Gaps** — ranked by downstream impact\n\n"
        + "Project context: {task}"
    ),
    "data-mesh-architect": (
        _BASE_INSTRUCTION
        + "## Data Mesh / Architecture Assessment\n\n"
        + "Analyze the data architecture and mesh maturity for this project. Cover:\n"
        + "1. **Domain Boundaries** — clear ownership, team alignment, data product candidates\n"
        + "2. **Platform Self-Serve** — how much friction exists for new consumers\n"
        + "3. **Federated Governance** — global policies vs domain autonomy balance\n"
        + "4. **Architectural Debt** — monolithic patterns, coupling, single points of failure\n"
        + "5. **Top 3 Architectural Improvements** — ranked by scalability impact\n\n"
        + "Project context: {task}"
    ),
}

_DEFAULT_ANALYZE_PROMPT = (
    _BASE_INSTRUCTION
    + "## Data Project Assessment\n\n"
    + "Analyze the data project from your area of expertise.\n\n"
    + "Project context: {task}"
)


# ── Argument parser ───────────────────────────────────────────────────────────


def parse_analyze_args(user_input: str) -> tuple[list[str], str]:
    """
    Extrai grupo de agentes e descrição do projeto do input.

    Formatos aceitos:
      /analyze-project <descrição>
      /analyze-project --quality <descrição>
      /analyze-project --arch <descrição>
      /analyze-project --databricks <descrição>
      /analyze-project --fabric <descrição>

    Returns:
        (agent_names, project_description)
    """
    parts = user_input.split(maxsplit=1)
    rest = parts[1].strip() if len(parts) > 1 else ""

    flag_map = {
        "--quality": "quality",
        "--arch": "arch",
        "--databricks": "databricks",
        "--fabric": "fabric",
    }

    for flag, group_key in flag_map.items():
        if rest.startswith(flag):
            description = rest[len(flag) :].strip()
            return ANALYZE_GROUPS[group_key], description

    return ANALYZE_GROUPS["default"], rest


# ── Report builder ────────────────────────────────────────────────────────────


def build_report(
    results: list[tuple[str, str, float]],
    project_description: str,
    agent_names: list[str],
) -> str:
    """Monta o relatório consolidado em Markdown."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total_cost = sum(c for _, _, c in results)

    lines = [
        "# Relatório de Análise — Data Project",
        f"> Gerado em: {now}",
        f"> Agentes consultados: {', '.join(agent_names)}",
        f"> Custo total: ${total_cost:.5f}",
        "",
    ]

    if project_description:
        lines += ["## Contexto do Projeto", "", project_description, ""]

    lines += ["---", ""]

    for name, text, cost in results:
        if text.strip():
            lines += [f"## {name}", "", text.strip(), "", f"> _Custo: ${cost:.5f}_", "", "---", ""]

    return "\n".join(lines)


def save_report(report: str) -> Path:
    """Salva o relatório em output/analyze-project/ e retorna o caminho."""
    output_dir = Path("output/analyze-project")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"report_{timestamp}.md"
    path.write_text(report, encoding="utf-8")
    return path
