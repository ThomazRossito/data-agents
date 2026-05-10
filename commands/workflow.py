"""
commands/workflow.py — WorkflowRunner inspirado no CrewAI.

Implementa três melhorias sobre o sistema de delegação simples do Supervisor:

1. Context Chain (CrewAI: context=[tarefa_anterior])
   O output de cada agente é passado como contexto estruturado para o próximo.
   O próximo agente sabe exatamente o que foi produzido antes — sem depender de
   o Supervisor resumir manualmente.

2. Parallel Tasks (CrewAI: async_execution=True por task)
   Tasks independentes dentro do mesmo workflow rodam em asyncio.gather.
   Ex: no WF-01, data-quality-steward e governance-auditor podem rodar em paralelo
   depois que o spark-expert terminar.

3. Human Pause (CrewAI: human_input=True)
   Workflows com impacto em produção pausam antes de fases destrutivas e aguardam
   confirmação explícita. Implementado como callback injetável — o CLI exibe prompt
   interativo, a UI exibe botão de aprovação.

Uso pelo Supervisor (via Agent tool):
    Não é chamado diretamente. O WorkflowRunner é invocado pelo comando /workflow
    ou pode ser instanciado pelo Supervisor em sessões com DOMA Full.

Uso standalone (CLI):
    from commands.workflow import WorkflowRunner, WorkflowStep, WorkflowResult
    runner = WorkflowRunner(wf_id="WF-01", steps=[...])
    result = await runner.run(query="Crie pipeline Bronze→Gold para vendas")
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query as sdk_query,
)

from config.settings import settings

logger = logging.getLogger("data_agents.workflow")

# Tipo do callback de pausa humana:
# recebe (wf_id, phase_name, context_so_far) → True para continuar, False para abortar
HumanPauseCallback = Callable[[str, str, str], Awaitable[bool]]


# ── Definições de dados ───────────────────────────────────────────────────────


@dataclass
class WorkflowStep:
    """Define uma etapa do workflow."""

    agent: str
    """Nome do agente a invocar (ex: 'spark-expert')."""

    task: str
    """Descrição da tarefa para esta etapa. Suporta {context} como placeholder
    que será preenchido com o output acumulado das etapas anteriores."""

    phase: str = ""
    """Nome da fase para exibição e logging (ex: 'Bronze Ingestion')."""

    parallel_with: list[str] = field(default_factory=list)
    """Nomes de outros steps que podem rodar em paralelo com este.
    Use o nome do campo `phase` dos steps irmãos."""

    require_human_approval: bool = False
    """Se True, pausa antes desta etapa e aguarda aprovação humana."""

    output_key: str = ""
    """Chave para armazenar o output no WorkflowState.context_chain.
    Default: nome do agente."""


@dataclass
class StepResult:
    """Resultado de uma etapa concluída."""

    step: WorkflowStep
    output: str
    cost_usd: float
    duration_seconds: float
    success: bool
    error: str = ""


@dataclass
class WorkflowResult:
    """Resultado completo do workflow."""

    wf_id: str
    query: str
    steps_completed: list[StepResult]
    steps_failed: list[StepResult]
    total_cost_usd: float
    total_duration_seconds: float
    aborted: bool = False
    abort_reason: str = ""

    @property
    def success(self) -> bool:
        return not self.aborted and len(self.steps_failed) == 0

    def summary(self) -> str:
        lines = [
            f"## {self.wf_id} — Resultado do Workflow",
            f"- **Query:** {self.query[:120]}",
            f"- **Status:** {'✅ Concluído' if self.success else '❌ Falhou/Abortado'}",
            f"- **Etapas:** {len(self.steps_completed)} concluídas, {len(self.steps_failed)} falhas",
            f"- **Custo total:** ${self.total_cost_usd:.4f}",
            f"- **Duração total:** {self.total_duration_seconds:.1f}s",
        ]
        if self.aborted:
            lines.append(f"- **Abortado em:** {self.abort_reason}")
        for r in self.steps_completed:
            lines.append(f"\n### {r.step.phase or r.step.agent}")
            lines.append(r.output[:800] + ("..." if len(r.output) > 800 else ""))
        return "\n".join(lines)


# ── Estado acumulado do workflow ──────────────────────────────────────────────


class WorkflowState:
    """
    Acumula contexto entre etapas — equivalente ao context= do CrewAI.

    context_chain: dict agent_key → output_text
    Permite que cada etapa receba apenas o contexto relevante (não o workflow inteiro).
    """

    def __init__(self, wf_id: str, query: str):
        self.wf_id = wf_id
        self.query = query
        self.context_chain: dict[str, str] = {}
        self.started_at = datetime.now(timezone.utc)

    def add(self, key: str, output: str) -> None:
        self.context_chain[key] = output
        self._persist_context()

    def _persist_context(self) -> None:
        """Persiste o contexto acumulado em disco para sobreviver a crashes e human pauses."""
        from pathlib import Path

        ctx_dir = Path(__file__).parent.parent / "output" / "workflow-context"
        ctx_dir.mkdir(parents=True, exist_ok=True)
        ctx_path = ctx_dir / f"{self.wf_id}-context.md"
        ctx_path.write_text(self.build_context_for(None), encoding="utf-8")

    def build_context_for(self, step: WorkflowStep | None) -> str:
        """
        Compila o contexto acumulado para injetar no prompt do próximo agente.
        Inclui apenas outputs de etapas anteriores relevantes.
        Quando step=None, retorna snapshot completo (usado para persistência em disco).
        """
        if not self.context_chain:
            return ""

        lines = [
            "\n\n---",
            f"## 📋 Contexto do Workflow {self.wf_id}",
            f"**Query original:** {self.query}",
            "",
            "**Outputs das etapas anteriores** (use como insumo para sua tarefa):",
        ]
        for key, output in self.context_chain.items():
            preview = output[:600] + (
                "...\n*(truncado — output completo disponível em output/)*"
                if len(output) > 600
                else ""
            )
            lines.append(f"\n### ↳ {key}\n{preview}")
        lines.append("---\n")
        return "\n".join(lines)

    def inject_context(self, task: str, step: WorkflowStep) -> str:
        """Substitui {context} no template da task pelo contexto acumulado."""
        ctx = self.build_context_for(step)
        if "{context}" in task:
            return task.replace("{context}", ctx)
        if ctx:
            return task + ctx
        return task


# ── Runner principal ──────────────────────────────────────────────────────────


class WorkflowRunner:
    """
    Executa um workflow multi-agente com context chain, paralelismo e human pause.

    Parâmetros
    ----------
    wf_id : str
        Identificador do workflow (ex: "WF-01").
    steps : list[WorkflowStep]
        Lista de etapas em ordem de execução.
        Steps com o mesmo `parallel_with` rodam em asyncio.gather.
    human_pause_callback : HumanPauseCallback | None
        Chamado quando require_human_approval=True.
        Se None, usa aprovação automática (útil em testes).
    """

    def __init__(
        self,
        wf_id: str,
        steps: list[WorkflowStep],
        human_pause_callback: HumanPauseCallback | None = None,
    ):
        self.wf_id = wf_id
        self.steps = steps
        self._human_pause = human_pause_callback or _default_human_pause

    async def run(self, query: str) -> WorkflowResult:
        """Executa o workflow completo."""
        state = WorkflowState(wf_id=self.wf_id, query=query)
        completed: list[StepResult] = []
        failed: list[StepResult] = []
        total_cost = 0.0

        # Agrupa steps em grupos de execução (paralelos vs sequenciais)
        execution_groups = _group_steps(self.steps)

        for group in execution_groups:
            # Human pause antes de qualquer step no grupo que o exige
            for step in group:
                if step.require_human_approval:
                    ctx_preview = state.build_context_for(step)[:500]
                    approved = await self._human_pause(
                        self.wf_id, step.phase or step.agent, ctx_preview
                    )
                    if not approved:
                        abort_reason = step.phase or step.agent
                        logger.warning(
                            f"[{self.wf_id}] Workflow abortado pelo usuário antes de '{abort_reason}'"
                        )
                        elapsed = (datetime.now(timezone.utc) - state.started_at).total_seconds()
                        return WorkflowResult(
                            wf_id=self.wf_id,
                            query=query,
                            steps_completed=completed,
                            steps_failed=failed,
                            total_cost_usd=total_cost,
                            total_duration_seconds=elapsed,
                            aborted=True,
                            abort_reason=abort_reason,
                        )

            # Executa o grupo (paralelo se > 1 step)
            if len(group) == 1:
                result = await self._run_step(group[0], state)
                _register_result(result, state, completed, failed)
                total_cost += result.cost_usd
            else:
                tasks = [self._run_step(s, state) for s in group]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, res in enumerate(results):
                    if isinstance(res, Exception):
                        step = group[i]
                        result = StepResult(
                            step=step,
                            output="",
                            cost_usd=0.0,
                            duration_seconds=0.0,
                            success=False,
                            error=str(res),
                        )
                    else:
                        result = res  # type: ignore[assignment]
                    _register_result(result, state, completed, failed)
                    total_cost += result.cost_usd

            # Se alguma etapa falhou, aborta o workflow
            if failed and not _all_optional(group):
                elapsed = (datetime.now(timezone.utc) - state.started_at).total_seconds()
                return WorkflowResult(
                    wf_id=self.wf_id,
                    query=query,
                    steps_completed=completed,
                    steps_failed=failed,
                    total_cost_usd=total_cost,
                    total_duration_seconds=elapsed,
                    aborted=True,
                    abort_reason=f"Falha em {failed[-1].step.agent}",
                )

        elapsed = (datetime.now(timezone.utc) - state.started_at).total_seconds()
        return WorkflowResult(
            wf_id=self.wf_id,
            query=query,
            steps_completed=completed,
            steps_failed=failed,
            total_cost_usd=total_cost,
            total_duration_seconds=elapsed,
        )

    async def _run_step(self, step: WorkflowStep, state: WorkflowState) -> StepResult:
        """Executa uma única etapa, injetando contexto acumulado."""
        import time

        phase_label = step.phase or step.agent
        logger.info(f"[{self.wf_id}] Iniciando etapa: {phase_label}")

        # Injeta contexto acumulado no prompt da task
        enriched_task = state.inject_context(step.task, step)

        options = _build_step_options(step.agent)
        output_text = ""
        cost = 0.0
        t0 = time.monotonic()

        try:
            async for message in sdk_query(prompt=enriched_task, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock) and block.text.strip():
                            output_text += block.text
                elif isinstance(message, ResultMessage):
                    cost = float(message.total_cost_usd or 0)

            duration = time.monotonic() - t0
            logger.info(
                f"[{self.wf_id}] Etapa '{phase_label}' concluída em {duration:.1f}s (${cost:.4f})"
            )
            return StepResult(
                step=step,
                output=output_text,
                cost_usd=cost,
                duration_seconds=duration,
                success=True,
            )
        except Exception as e:
            duration = time.monotonic() - t0
            logger.error(f"[{self.wf_id}] Etapa '{phase_label}' falhou: {e}", exc_info=True)
            return StepResult(
                step=step,
                output="",
                cost_usd=cost,
                duration_seconds=duration,
                success=False,
                error=str(e),
            )


# ── Workflows pré-definidos (WF-01 a WF-05) ──────────────────────────────────


def build_wf01_pipeline_end_to_end(target_platform: str = "databricks") -> list[WorkflowStep]:
    """WF-01: Pipeline End-to-End Bronze→Gold."""
    return [
        WorkflowStep(
            agent="spark-expert",
            phase="Bronze Ingestion",
            task=(
                "Crie a camada Bronze do pipeline Medallion para o seguinte projeto:\n\n{context}\n\n"
                "Gere o código PySpark/DLT para ingestão incremental com Auto Loader. "
                "Salve os artefatos em output/wf01/bronze/."
            ),
        ),
        WorkflowStep(
            agent="spark-expert",
            phase="Silver Transformation",
            task=(
                "Com base na camada Bronze já criada, crie a camada Silver:\n\n{context}\n\n"
                "Aplique limpeza, tipagem, deduplicação e particionamento adequado. "
                "Salve em output/wf01/silver/."
            ),
        ),
        WorkflowStep(
            agent="spark-expert",
            phase="Gold Layer",
            task=(
                "Com base nas camadas Bronze e Silver, crie a camada Gold:\n\n{context}\n\n"
                "Aplique agregações, Star Schema se necessário. Salve em output/wf01/gold/."
            ),
            require_human_approval=True,
        ),
        # Qualidade e Governança rodam em paralelo após o Gold
        WorkflowStep(
            agent="data-quality-steward",
            phase="Data Quality",
            task=(
                "Valide a qualidade dos dados do pipeline gerado:\n\n{context}\n\n"
                "Crie expectations para todas as camadas. Foco em Bronze→Silver→Gold."
            ),
            parallel_with=["Governance Audit"],
        ),
        WorkflowStep(
            agent="governance-auditor",
            phase="Governance Audit",
            task=(
                "Audite o pipeline gerado para conformidade LGPD/GDPR e governança:\n\n{context}\n\n"
                "Verifique PII, linhagem e permissões de acesso."
            ),
            parallel_with=["Data Quality"],
        ),
        WorkflowStep(
            agent="semantic-modeler",
            phase="Semantic Layer",
            task=(
                "Com base na camada Gold criada, crie o modelo semântico:\n\n{context}\n\n"
                f"Plataforma alvo: {target_platform}. "
                "Crie medidas DAX ou Metric Views conforme a plataforma."
            ),
        ),
    ]


def build_wf02_star_schema() -> list[WorkflowStep]:
    """WF-02: Star Schema na camada Gold."""
    return [
        WorkflowStep(
            agent="sql-expert",
            phase="Schema Discovery",
            task=(
                "Explore os schemas disponíveis e identifique as tabelas Silver para o Star Schema:\n\n{context}\n\n"
                "Liste tabelas, tipos, cardinalidades e proponha o modelo dimensional (fatos + dimensões)."
            ),
        ),
        WorkflowStep(
            agent="spark-expert",
            phase="Star Schema Implementation",
            task=(
                "Com base na descoberta de schema, implemente o Star Schema em PySpark:\n\n{context}\n\n"
                "Crie dim_* e fact_* seguindo as regras SS1-SS5 da Constituição. "
                "dim_data via SEQUENCE, INNER JOIN em todas as fact_*."
            ),
            require_human_approval=True,
        ),
        WorkflowStep(
            agent="data-quality-steward",
            phase="Star Schema Quality",
            task=(
                "Valide o Star Schema implementado:\n\n{context}\n\n"
                "Verifique integridade referencial, contagens fact vs silver, valores nulos em chaves."
            ),
            parallel_with=["Semantic Modeling"],
        ),
        WorkflowStep(
            agent="semantic-modeler",
            phase="Semantic Modeling",
            task=(
                "Com base no Star Schema, crie o modelo semântico:\n\n{context}\n\n"
                "Gere medidas DAX/Metric Views sobre as fact_* e dim_*."
            ),
            parallel_with=["Star Schema Quality"],
        ),
    ]


def build_wf03_cross_platform() -> list[WorkflowStep]:
    """WF-03: Migração Cross-Platform Databricks ↔ Fabric."""
    return [
        WorkflowStep(
            agent="pipeline-architect",
            phase="Architecture Design",
            task=(
                "Projete a arquitetura de migração cross-platform:\n\n{context}\n\n"
                "Mapeie objetos de origem para destino. Identifique incompatibilidades."
            ),
        ),
        WorkflowStep(
            agent="sql-expert",
            phase="SQL Transpilation",
            task=(
                "Transcreva os objetos SQL para o dialeto do destino:\n\n{context}\n\n"
                "Converta DDL, views e queries de Spark SQL ↔ T-SQL conforme necessário."
            ),
            parallel_with=["Spark Migration"],
        ),
        WorkflowStep(
            agent="spark-expert",
            phase="Spark Migration",
            task=(
                "Migre o código PySpark/DLT para a plataforma destino:\n\n{context}\n\n"
                "Adapte Auto Loader, Delta Lake e jobs para o equivalente no destino."
            ),
            parallel_with=["SQL Transpilation"],
        ),
        WorkflowStep(
            agent="data-quality-steward",
            phase="Reconciliation",
            task=(
                "Valide a migração com reconciliação de contagens:\n\n{context}\n\n"
                "Compare linha a linha origem vs destino. Identifique divergências."
            ),
            require_human_approval=True,
        ),
        WorkflowStep(
            agent="governance-auditor",
            phase="Governance Validation",
            task=(
                "Valide governança e conformidade pós-migração:\n\n{context}\n\n"
                "Verifique permissões, linhagem e PII no destino."
            ),
        ),
    ]


def build_wf04_governance_audit() -> list[WorkflowStep]:
    """WF-04: Auditoria de Governança."""
    return [
        WorkflowStep(
            agent="governance-auditor",
            phase="Access Audit",
            task=(
                "Execute auditoria completa de acessos e permissões:\n\n{context}\n\n"
                "Verifique Unity Catalog, Fabric workspaces, acessos privilegiados."
            ),
        ),
        WorkflowStep(
            agent="data-quality-steward",
            phase="Data Quality Audit",
            task=(
                "Audite a qualidade dos dados nas tabelas críticas:\n\n{context}\n\n"
                "Verifique SLAs, expectations existentes e data drift."
            ),
        ),
        WorkflowStep(
            agent="governance-auditor",
            phase="Compliance Report",
            task=(
                "Gere relatório de compliance com base na auditoria:\n\n{context}\n\n"
                "Formato: sumário executivo + achados + recomendações P0/P1/P2."
            ),
        ),
    ]


def build_wf05_relational_migration(
    source_type: str = "sql-server", target: str = "databricks"
) -> list[WorkflowStep]:
    """WF-05: Migração de Banco Relacional → Databricks ou Fabric."""
    return [
        WorkflowStep(
            agent="migration-expert",
            phase="Assessment",
            task=(
                f"Execute o assessment completo do banco de origem ({source_type}):\n\n{{context}}\n\n"
                "Fase ASSESS: inventário de tabelas, views, procedures, functions. "
                "Fase ANALYZE: classifique complexidade por objeto (LOW/MEDIUM/HIGH). "
                "Salve em output/wf05/assessment.md."
            ),
        ),
        WorkflowStep(
            agent="migration-expert",
            phase="Architecture Design",
            task=(
                f"Com base no assessment, projete a arquitetura Medallion no {target}:\n\n{{context}}\n\n"
                "Fase DESIGN: mapeie tabelas fonte → Bronze/Silver/Gold. "
                "Defina estratégia de ingestão incremental. Salve em output/wf05/design.md."
            ),
            require_human_approval=True,
        ),
        # DDL transpilation e pipeline rodam em paralelo
        WorkflowStep(
            agent="sql-expert",
            phase="DDL Transpilation",
            task=(
                "Transcreva o DDL do banco de origem para o dialeto do destino:\n\n{context}\n\n"
                f"Converta tipos de dados {source_type} → {'Spark SQL' if target == 'databricks' else 'T-SQL Fabric'}. "
                "Salve scripts em output/wf05/ddl/."
            ),
            parallel_with=["Pipeline Generation"],
        ),
        WorkflowStep(
            agent="spark-expert",
            phase="Pipeline Generation",
            task=(
                "Gere os jobs de ingestão para mover dados da fonte ao destino:\n\n{context}\n\n"
                "Use Auto Loader (Databricks) ou Data Factory (Fabric) conforme o destino. "
                "Salve em output/wf05/pipelines/."
            ),
            parallel_with=["DDL Transpilation"],
        ),
        WorkflowStep(
            agent="data-quality-steward",
            phase="Reconciliation",
            task=(
                "Valide a migração com reconciliação de contagens e integridade:\n\n{context}\n\n"
                "Compare tabela a tabela: contagem de linhas, valores nulos em PKs, "
                "amostras de dados críticos. Salve em output/wf05/reconciliation.md."
            ),
            require_human_approval=True,
        ),
        WorkflowStep(
            agent="governance-auditor",
            phase="PII & Compliance",
            task=(
                "Classifique dados PII e valide conformidade LGPD/GDPR pós-migração:\n\n{context}\n\n"
                "Identifique colunas sensíveis. Recomende mascaramento e controles de acesso."
            ),
        ),
    ]


# ── Helpers internos ──────────────────────────────────────────────────────────


def _group_steps(steps: list[WorkflowStep]) -> list[list[WorkflowStep]]:
    """
    Agrupa steps em grupos de execução. Steps com parallel_with compatíveis
    formam um grupo e rodam via asyncio.gather.
    """
    groups: list[list[WorkflowStep]] = []
    used: set[int] = set()

    for i, step in enumerate(steps):
        if i in used:
            continue
        if not step.parallel_with:
            groups.append([step])
            used.add(i)
        else:
            # Encontra os steps irmãos que referenciam esta fase mutuamente
            group = [step]
            used.add(i)
            for j, other in enumerate(steps):
                if j in used:
                    continue
                if step.phase in other.parallel_with or other.phase in step.parallel_with:
                    group.append(other)
                    used.add(j)
            groups.append(group)

    return groups


def _register_result(
    result: StepResult,
    state: WorkflowState,
    completed: list[StepResult],
    failed: list[StepResult],
) -> None:
    if result.success:
        key = result.step.output_key or result.step.agent
        state.add(key, result.output)
        completed.append(result)
    else:
        failed.append(result)


def _all_optional(group: list[WorkflowStep]) -> bool:
    """Por ora nenhum step é opcional — reservado para extensão futura."""
    return False


def _build_step_options(agent_name: str) -> ClaudeAgentOptions:
    """
    Constrói opções completas para um agente de workflow usando o registry.

    Usa load_agent() para obter system prompt, tools, model e effort reais do agente.
    MCPs são filtrados para os disponíveis com credenciais (mesma lógica do supervisor).
    """
    from agents.loader import AGENTS_REGISTRY_DIR, load_agent
    from config.mcp_servers import build_mcp_registry
    from utils.frontmatter import parse_yaml_frontmatter

    mcp_registry = build_mcp_registry()
    agent_path = AGENTS_REGISTRY_DIR / f"{agent_name}.md"

    if agent_path.exists():
        _, agent_def = load_agent(
            path=agent_path,
            tier_model_map=settings.tier_model_map if settings.tier_model_map else None,
            tier_turns_map=settings.tier_turns_map if settings.tier_turns_map else None,
            tier_effort_map=settings.tier_effort_map if settings.tier_effort_map else None,
            inject_kb_index=settings.inject_kb_index,
            inject_cache_prefix=True,
        )
        # Filtra MCPs para os que o agente declara no frontmatter e têm credenciais
        raw = agent_path.read_text(encoding="utf-8")
        meta, _ = parse_yaml_frontmatter(raw)
        agent_mcp_names: list[str] = meta.get("mcp_servers", [])
        filtered_mcps = {k: v for k, v in mcp_registry.items() if k in agent_mcp_names}

        return ClaudeAgentOptions(
            model=agent_def.model or settings.default_model,
            system_prompt=agent_def.prompt,
            allowed_tools=list(agent_def.tools or []),
            agents=None,
            mcp_servers=filtered_mcps,
            max_turns=agent_def.maxTurns,
            permission_mode="bypassPermissions",
            effort=agent_def.effort if isinstance(agent_def.effort, str) else None,
        )

    # Fallback: partido persona sem MCPs (agente não encontrado no registry)
    from commands.party import AGENT_PERSONAS, _DEFAULT_PERSONA, _AGENT_TIERS, _PARTY_MAX_TURNS

    logger.warning(f"Agente '{agent_name}' não encontrado no registry — usando persona fallback")
    persona = AGENT_PERSONAS.get(agent_name, _DEFAULT_PERSONA)
    tier = _AGENT_TIERS.get(agent_name, "T2")
    tier_turns = settings.tier_turns_map.get(tier) if settings.tier_turns_map else None
    max_turns = tier_turns if tier_turns is not None else _PARTY_MAX_TURNS.get(tier, 3)

    return ClaudeAgentOptions(
        model=settings.default_model,
        system_prompt=persona,
        allowed_tools=[],
        agents=None,
        mcp_servers={},
        max_turns=max_turns,
        permission_mode="bypassPermissions",
    )


async def _default_human_pause(wf_id: str, phase: str, context_preview: str) -> bool:
    """
    Callback padrão de pausa humana — aprovação automática (para testes e automação).
    Em produção, o CLI ou UI injeta seu próprio callback interativo.
    """
    logger.info(
        f"[{wf_id}] Human pause em '{phase}' — aprovação automática (sem callback configurado)."
    )
    return True


# ── Registry de workflows pré-definidos ──────────────────────────────────────

WORKFLOW_REGISTRY: dict[str, dict[str, Any]] = {
    "WF-01": {
        "name": "Pipeline End-to-End",
        "description": "Bronze→Silver→Gold + Data Quality + Governance + Semantic Layer",
        "builder": build_wf01_pipeline_end_to_end,
        "when": "Criar pipeline Medallion completo do zero",
    },
    "WF-02": {
        "name": "Star Schema",
        "description": "Schema Discovery → Star Schema → Quality → Semantic Modeling",
        "builder": build_wf02_star_schema,
        "when": "Criar camada Gold em Star Schema a partir de tabelas Silver",
    },
    "WF-03": {
        "name": "Migração Cross-Platform",
        "description": "Design → SQL Transpilation ∥ Spark Migration → Reconciliation → Governance",
        "builder": build_wf03_cross_platform,
        "when": "Migrar pipelines entre Databricks e Fabric",
    },
    "WF-04": {
        "name": "Auditoria de Governança",
        "description": "Access Audit → Data Quality Audit → Compliance Report",
        "builder": build_wf04_governance_audit,
        "when": "Gerar relatório de compliance e governança",
    },
    "WF-05": {
        "name": "Migração Relacional → Nuvem",
        "description": "Assessment → Design → DDL Transpilation ∥ Pipeline Generation → Reconciliation → PII",
        "builder": build_wf05_relational_migration,
        "when": "Migrar SQL Server ou PostgreSQL para Databricks/Fabric",
    },
}
