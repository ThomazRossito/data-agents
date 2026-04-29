"""workflow.executor — Executa workflows colaborativos multi-agente."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from agents.base import AgentResult, BaseAgent
from workflow.dag import WorkflowDef, WorkflowStep

logger = logging.getLogger("data_agents.workflow.executor")

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "workflows"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def execute_workflow(
    workflow: WorkflowDef,
    task: str,
    agents: dict[str, BaseAgent],
    fallback_agent: BaseAgent,
    *,
    fail_fast: bool = True,
) -> AgentResult:
    """
    Executa um workflow multi-agente com handoff automático.

    fail_fast=True (padrão): para na primeira etapa que falhar e retorna o
    resultado parcial acumulado até então.
    fail_fast=False: continua nas etapas seguintes, registrando o erro da etapa
    no contexto como placeholder.
    """
    logger.info(
        "Iniciando workflow %s (%s) | %d etapas",
        workflow.id,
        workflow.name,
        len(workflow.steps),
    )

    total_tokens = 0
    total_tool_calls = 0
    step_results: dict[str, str] = {}
    step_log: list[str] = []

    step_log.append(f"# Workflow {workflow.id}: {workflow.name}")
    step_log.append(f"\n**Tarefa original:** {task}\n")

    for i, step in enumerate(workflow.steps, start=1):
        agent = agents.get(step.agent_name, fallback_agent)
        context = _build_step_context(
            workflow, step, i, len(workflow.steps), step_results
        )

        logger.info(
            "[%d/%d] Delegando para %s: %s",
            i,
            len(workflow.steps),
            step.agent_name,
            step.description[:60],
        )

        full_prompt = step.description + f"\n\nTarefa original: {task}"
        try:
            result = agent.run(full_prompt, context=context)
        except Exception as exc:  # noqa: BLE001
            err_msg = f"[ERRO na etapa {i}/{len(workflow.steps)} — {step.agent_name}]: {exc}"
            logger.error(err_msg)
            if fail_fast:
                step_log.append(f"\n## ⛔ Etapa {i} falhou (fail_fast=True)\n{err_msg}\n")
                partial_filename = f"{workflow.id.lower()}_partial.md"
                partial_content = _build_summary(workflow, step_log, partial_filename)
                return AgentResult(
                    content=partial_content,
                    tool_calls_count=total_tool_calls,
                    tokens_used=total_tokens,
                )
            # fail_fast=False: registra erro e continua
            step_results[step.output_key] = err_msg
            step_log.append(
                f"\n## Etapa {i}/{len(workflow.steps)}: {step.agent_name} ⚠️ ERRO\n"
                f"*{step.description}*\n\n{err_msg}\n\n---"
            )
            continue

        step_results[step.output_key] = result.content
        total_tokens += result.tokens_used
        total_tool_calls += result.tool_calls_count

        step_log.append(
            f"\n## Etapa {i}/{len(workflow.steps)}: {step.agent_name}\n"
            f"*{step.description}*\n\n"
            f"{result.content}\n\n---"
        )

    # Salvar resultado completo
    output_file = (
        OUTPUT_DIR / f"{workflow.id.lower()}_{hashlib.sha1(task.encode()).hexdigest()[:8]}.md"
    )
    output_file.write_text("\n".join(step_log), encoding="utf-8")
    logger.info("Workflow %s concluído → %s", workflow.id, output_file.name)

    # Resumo final
    final_content = _build_summary(workflow, step_log, output_file.name)

    return AgentResult(
        content=final_content,
        tool_calls_count=total_tool_calls,
        tokens_used=total_tokens,
    )


def _build_step_context(
    workflow: WorkflowDef,
    step: WorkflowStep,
    step_num: int,
    total: int,
    previous_results: dict[str, str],
) -> str:
    lines = [
        "## Contexto do Workflow",
        "",
        f"- **Workflow:** {workflow.id} — {workflow.name}",
        f"- **Etapa atual:** {step_num} de {total}",
        "",
    ]

    if previous_results:
        lines.append("### Resultados das Etapas Anteriores\n")
        for key, content in previous_results.items():
            preview = content[:2500] + ("..." if len(content) > 2500 else "")
            lines.append(f"**{key}:**\n{preview}\n")

    lines.append(f"### Sua Tarefa nesta Etapa\n{step.description}")
    return "\n".join(lines)


def _build_summary(
    workflow: WorkflowDef,
    step_log: list[str],
    filename: str,
) -> str:
    return (
        f"**Workflow {workflow.id} concluído:** {workflow.name}\n\n"
        f"Resultado salvo em `output/workflows/{filename}`\n\n"
        + "\n".join(step_log[2:])  # pula header e tarefa original
    )
