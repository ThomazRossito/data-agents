"""Chainlit UI — interface web do data-agents-copilot."""

import asyncio

import chainlit as cl

from agents.supervisor import Supervisor
from config.settings import settings
from hooks import audit_hook, cost_guard_hook, security_hook
from orchestrator.qa_orchestrator import QAOrchestrator, should_bypass

# Inicializados em on_chat_start para evitar import-time side effects
supervisor: Supervisor | None = None
qa_orchestrator: QAOrchestrator | None = None
_init_lock = asyncio.Lock()  # serializa lazy init em chats concorrentes

_HELP = """\
**data-agents-copilot** — comandos disponíveis:

| Comando | Agente | Uso |
|---|---|---|
| `/plan <tarefa>` | Supervisor | Tarefas complexas com PRD |
| `/spark <tarefa>` | Spark Expert | PySpark, Delta Lake, DLT |
| `/sql <tarefa>` | SQL Expert | Queries, modelagem, Unity Catalog |
| `/pipeline <tarefa>` | Pipeline Architect | ETL/ELT com execução |
| `/quality <tarefa>` | Data Quality | Validação, DQX, profiling |
| `/naming <tarefa>` | Naming Guard | Auditoria de nomenclatura |
| `/governance <tarefa>` | Governance Auditor | PII, LGPD, controles de acesso |
| `/dbt <tarefa>` | dbt Expert | Models, snapshots, incremental |
| `/python <tarefa>` | Python Expert | Código Python, testes |
| `/fabric <tarefa>` | Fabric Expert | Lakehouse, OneLake, Direct Lake |
| `/lakehouse <tarefa>` | Lakehouse Engineer | Implantação, migração, sustentação |
| `/ops <tarefa>` | Lakehouse Engineer | Manutenção, incidente, custo |
| `/ai <tarefa>` | Databricks AI | Agent Bricks, Genie, MLflow |
| `/assessment` | fabricgov + Governance Auditor | Assessment completo de governança Fabric |
| `/assessment --days 28` | fabricgov + Governance Auditor | Assessment com 28 dias de histórico |
| `/devops <tarefa>` | DevOps Engineer | DABs, Azure DevOps, Fabric CI/CD |
| `/geral <pergunta>` | Geral | Conceitual, sem MCP |
| `/review <artefato>` | Supervisor | Review de código/pipeline |
| `/party <tarefa>` | Party Mode | Múlti-agente em paralelo |
| `/health` | — | Status dos agentes |
| `/help` | — | Este menu |
"""


@cl.on_chat_start
async def on_start():
    global supervisor, qa_orchestrator
    async with _init_lock:
        if supervisor is None:
            supervisor = Supervisor()
            _qa_agent = supervisor.get_agent("qa_reviewer")
            qa_orchestrator = (
                QAOrchestrator(
                    supervisor,
                    _qa_agent,
                    max_rounds=settings.qa_max_rounds,
                    pass_threshold=settings.qa_score_threshold,
                )
                if settings.qa_enabled and _qa_agent
                else None
            )
    await cl.Message(content=_HELP).send()


@cl.on_message
async def on_message(message: cl.Message):
    if supervisor is None:
        await cl.Message(content="Aguarde — inicializando agentes...").send()
        return

    user_input = message.content.strip()

    if user_input.lower() in ("/help", "help", "ajuda"):
        await cl.Message(content=_HELP).send()
        return

    # Checagem de segurança
    allowed, reason = security_hook.check(user_input)
    if not allowed:
        await cl.Message(content=f"Bloqueado pelo hook de segurança: {reason}").send()
        return

    loop = asyncio.get_running_loop()

    if qa_orchestrator and not should_bypass(user_input):
        async with cl.Step(name="📋 Negociando Spec") as step:
            spec, rounds, _neg_tok, _neg_calls = await loop.run_in_executor(
                None, qa_orchestrator.negotiate_spec, user_input
            )
            step.output = f"v{spec.version} — {rounds} round(s) | agente: {spec.agent_name}"

        async with cl.Step(name="🤖 Executando") as step:
            delivery = await loop.run_in_executor(
                None, qa_orchestrator.execute, user_input, spec
            )
            step.output = f"Tokens: {delivery.tokens_used}"

        async with cl.Step(name="✅ Verificando Qualidade") as step:
            report, _ver_tok, _ver_calls = await loop.run_in_executor(
                None, qa_orchestrator.verify, spec, delivery
            )
            icon = "✅" if report.passed else "❌"
            step.output = f"{icon} Score: {report.score:.0%}"
        audit_hook.record(
            agent="qa_orchestrator",
            task=user_input,
            tokens_used=delivery.tokens_used,
            tool_calls=delivery.tool_calls_count,
        )
        cost_guard_hook.track("qa_orchestrator", delivery.tokens_used)

        score_block = "\n\n---\n\n" + report.summary(settings.qa_score_threshold)
        await cl.Message(content=delivery.content + score_block).send()
    else:
        async with cl.Step(name="Processando") as step:
            step.input = user_input
            result = await loop.run_in_executor(None, supervisor.route, user_input)

            audit_hook.record(
                agent="supervisor_route",
                task=user_input,
                tokens_used=result.tokens_used,
                tool_calls=result.tool_calls_count,
            )
            cost_guard_hook.track("general", result.tokens_used)

            summary = cost_guard_hook.session_summary()
            step.output = (
                f"Tokens: {result.tokens_used} | "
                f"Total sessão: {summary['total_tokens']} "
                f"({summary['budget_pct']}% budget)"
            )

        await cl.Message(content=result.content).send()
