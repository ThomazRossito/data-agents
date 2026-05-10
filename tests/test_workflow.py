"""Testes para commands/workflow.py — WorkflowRunner, WorkflowState, builders."""

from unittest.mock import patch

import pytest

from commands.workflow import (
    WORKFLOW_REGISTRY,
    StepResult,
    WorkflowResult,
    WorkflowState,
    WorkflowStep,
    WorkflowRunner,
    _group_steps,
    build_wf01_pipeline_end_to_end,
    build_wf02_star_schema,
    build_wf03_cross_platform,
    build_wf04_governance_audit,
    build_wf05_relational_migration,
)


# ─── WorkflowState ────────────────────────────────────────────────────────────


class TestWorkflowState:
    def test_empty_context_returns_empty_string(self):
        state = WorkflowState(wf_id="WF-01", query="teste")
        step = WorkflowStep(agent="spark-expert", task="tarefa")
        assert state.build_context_for(step) == ""

    def test_add_and_build_context(self):
        state = WorkflowState(wf_id="WF-01", query="criar pipeline")
        state.add("spark-expert", "Output do spark-expert: código Bronze criado")
        step = WorkflowStep(agent="data-quality-steward", task="validar {context}")
        ctx = state.build_context_for(step)
        assert "spark-expert" in ctx
        assert "Output do spark-expert" in ctx

    def test_inject_context_replaces_placeholder(self):
        state = WorkflowState(wf_id="WF-01", query="pipeline")
        state.add("spark-expert", "Bronze criado com sucesso")
        step = WorkflowStep(agent="data-quality-steward", task="Valide: {context}")
        result = state.inject_context("Valide: {context}", step)
        assert "{context}" not in result
        assert "Bronze criado" in result

    def test_inject_context_appends_when_no_placeholder(self):
        state = WorkflowState(wf_id="WF-01", query="pipeline")
        state.add("spark-expert", "Bronze pronto")
        step = WorkflowStep(agent="data-quality-steward", task="Valide os dados")
        result = state.inject_context("Valide os dados", step)
        assert "Valide os dados" in result
        assert "Bronze pronto" in result

    def test_inject_context_no_change_when_empty(self):
        state = WorkflowState(wf_id="WF-01", query="pipeline")
        step = WorkflowStep(agent="spark-expert", task="primeira etapa")
        result = state.inject_context("primeira etapa", step)
        assert result == "primeira etapa"

    def test_multiple_outputs_in_context(self):
        state = WorkflowState(wf_id="WF-02", query="star schema")
        state.add("sql-expert", "Descoberta: 5 tabelas Silver")
        state.add("spark-expert", "Star Schema implementado em 3 tabelas")
        step = WorkflowStep(agent="data-quality-steward", task="Valide {context}")
        ctx = state.build_context_for(step)
        assert "sql-expert" in ctx
        assert "spark-expert" in ctx
        assert "5 tabelas Silver" in ctx


# ─── WorkflowResult ───────────────────────────────────────────────────────────


class TestWorkflowResult:
    def _make_step_result(self, success: bool = True) -> StepResult:
        step = WorkflowStep(agent="spark-expert", task="t", phase="Bronze")
        return StepResult(
            step=step, output="output", cost_usd=0.01, duration_seconds=1.0, success=success
        )

    def test_success_true_when_no_failures(self):
        result = WorkflowResult(
            wf_id="WF-01",
            query="q",
            steps_completed=[self._make_step_result(True)],
            steps_failed=[],
            total_cost_usd=0.01,
            total_duration_seconds=1.0,
        )
        assert result.success is True

    def test_success_false_when_steps_failed(self):
        result = WorkflowResult(
            wf_id="WF-01",
            query="q",
            steps_completed=[],
            steps_failed=[self._make_step_result(False)],
            total_cost_usd=0.0,
            total_duration_seconds=0.5,
        )
        assert result.success is False

    def test_success_false_when_aborted(self):
        result = WorkflowResult(
            wf_id="WF-01",
            query="q",
            steps_completed=[self._make_step_result(True)],
            steps_failed=[],
            total_cost_usd=0.01,
            total_duration_seconds=1.0,
            aborted=True,
            abort_reason="usuário cancelou",
        )
        assert result.success is False

    def test_summary_contains_wf_id(self):
        result = WorkflowResult(
            wf_id="WF-03",
            query="migrar vendas",
            steps_completed=[self._make_step_result(True)],
            steps_failed=[],
            total_cost_usd=0.05,
            total_duration_seconds=10.0,
        )
        summary = result.summary()
        assert "WF-03" in summary
        assert "migrar vendas" in summary

    def test_summary_marks_aborted(self):
        result = WorkflowResult(
            wf_id="WF-01",
            query="q",
            steps_completed=[],
            steps_failed=[],
            total_cost_usd=0.0,
            total_duration_seconds=0.0,
            aborted=True,
            abort_reason="etapa X",
        )
        summary = result.summary()
        assert "etapa X" in summary


# ─── _group_steps ─────────────────────────────────────────────────────────────


class TestGroupSteps:
    def test_sequential_steps_each_own_group(self):
        steps = [
            WorkflowStep(agent="a1", task="t1", phase="P1"),
            WorkflowStep(agent="a2", task="t2", phase="P2"),
            WorkflowStep(agent="a3", task="t3", phase="P3"),
        ]
        groups = _group_steps(steps)
        assert len(groups) == 3
        assert all(len(g) == 1 for g in groups)

    def test_parallel_steps_merged_in_group(self):
        steps = [
            WorkflowStep(agent="a1", task="t1", phase="P1"),
            WorkflowStep(agent="a2", task="t2", phase="P2", parallel_with=["P3"]),
            WorkflowStep(agent="a3", task="t3", phase="P3", parallel_with=["P2"]),
        ]
        groups = _group_steps(steps)
        assert len(groups) == 2
        assert len(groups[0]) == 1  # P1 sozinho
        assert len(groups[1]) == 2  # P2 e P3 juntos

    def test_all_sequential_no_parallel(self):
        steps = [WorkflowStep(agent=f"a{i}", task=f"t{i}", phase=f"P{i}") for i in range(4)]
        groups = _group_steps(steps)
        assert len(groups) == 4

    def test_empty_steps_returns_empty(self):
        assert _group_steps([]) == []


# ─── Builders e WORKFLOW_REGISTRY ────────────────────────────────────────────


class TestWorkflowBuilders:
    def test_wf01_has_at_least_5_steps(self):
        steps = build_wf01_pipeline_end_to_end()
        assert len(steps) >= 5

    def test_wf01_starts_with_spark_expert(self):
        steps = build_wf01_pipeline_end_to_end()
        assert steps[0].agent == "spark-expert"

    def test_wf01_has_parallel_quality_and_governance(self):
        steps = build_wf01_pipeline_end_to_end()
        parallel_agents = {s.agent for s in steps if s.parallel_with}
        assert "data-quality-steward" in parallel_agents
        assert "governance-auditor" in parallel_agents

    def test_wf02_has_4_steps(self):
        steps = build_wf02_star_schema()
        assert len(steps) >= 4

    def test_wf02_starts_with_sql_expert(self):
        steps = build_wf02_star_schema()
        assert steps[0].agent == "sql-expert"

    def test_wf03_has_parallel_sql_and_spark(self):
        steps = build_wf03_cross_platform()
        parallel_agents = {s.agent for s in steps if s.parallel_with}
        assert "sql-expert" in parallel_agents
        assert "spark-expert" in parallel_agents

    def test_wf04_ends_with_compliance_report(self):
        steps = build_wf04_governance_audit()
        assert steps[-1].phase == "Compliance Report"

    def test_wf05_starts_with_migration_expert(self):
        steps = build_wf05_relational_migration()
        assert steps[0].agent == "migration-expert"

    def test_wf05_has_human_approval_step(self):
        steps = build_wf05_relational_migration()
        approval_steps = [s for s in steps if s.require_human_approval]
        assert len(approval_steps) >= 1

    def test_wf05_has_parallel_ddl_and_pipeline(self):
        steps = build_wf05_relational_migration()
        parallel_agents = {s.agent for s in steps if s.parallel_with}
        assert "sql-expert" in parallel_agents
        assert "spark-expert" in parallel_agents

    def test_workflow_registry_has_all_five(self):
        for wf_id in ("WF-01", "WF-02", "WF-03", "WF-04", "WF-05"):
            assert wf_id in WORKFLOW_REGISTRY

    def test_workflow_registry_entries_have_required_keys(self):
        for wf_id, entry in WORKFLOW_REGISTRY.items():
            assert "name" in entry, f"{wf_id} sem 'name'"
            assert "description" in entry, f"{wf_id} sem 'description'"
            assert "builder" in entry, f"{wf_id} sem 'builder'"
            assert "when" in entry, f"{wf_id} sem 'when'"
            assert callable(entry["builder"]), f"{wf_id} 'builder' não é callable"

    def test_workflow_registry_builders_return_nonempty_steps(self):
        for wf_id, entry in WORKFLOW_REGISTRY.items():
            steps = entry["builder"]()
            assert len(steps) > 0, f"{wf_id} builder retornou lista vazia"


# ─── WorkflowRunner (mock do SDK) ─────────────────────────────────────────────


class TestWorkflowRunner:
    def _make_runner_with_mock(self, steps: list[WorkflowStep]):
        """Cria um WorkflowRunner com sdk_query mockado para retornar output fixo."""
        runner = WorkflowRunner(wf_id="WF-TEST", steps=steps)
        return runner

    @pytest.mark.asyncio
    async def test_run_returns_workflow_result(self):
        steps = [WorkflowStep(agent="spark-expert", task="tarefa simples", phase="P1")]
        runner = WorkflowRunner(wf_id="WF-TEST", steps=steps)

        async def mock_query(prompt, options):
            class FakeResult:
                total_cost_usd = 0.01

            yield FakeResult()

        with patch("commands.workflow.sdk_query", side_effect=mock_query):
            result = await runner.run("query de teste")

        assert isinstance(result, WorkflowResult)
        assert result.wf_id == "WF-TEST"

    @pytest.mark.asyncio
    async def test_human_pause_callback_abort(self):
        steps = [
            WorkflowStep(agent="spark-expert", task="t1", phase="P1"),
            WorkflowStep(agent="sql-expert", task="t2", phase="P2", require_human_approval=True),
        ]

        async def deny_callback(wf_id, phase, ctx):
            return False  # abortar

        async def mock_query(prompt, options):
            class FakeResult:
                total_cost_usd = 0.005

            yield FakeResult()

        runner = WorkflowRunner(
            wf_id="WF-TEST",
            steps=steps,
            human_pause_callback=deny_callback,
        )

        with patch("commands.workflow.sdk_query", side_effect=mock_query):
            result = await runner.run("query")

        assert result.aborted is True
        assert result.success is False
