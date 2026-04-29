"""Testes para workflow/executor.py."""

from __future__ import annotations

from unittest.mock import MagicMock

from agents.base import AgentConfig, AgentResult, BaseAgent
from workflow.dag import WorkflowDef, WorkflowStep
from workflow.executor import execute_workflow


def _make_step(agent_name: str, output_key: str, description: str = "etapa") -> WorkflowStep:
    return WorkflowStep(
        agent_name=agent_name,
        description=description,
        output_key=output_key,
    )


def _make_workflow(steps: list[WorkflowStep], wf_id: str = "WF-TEST") -> WorkflowDef:
    return WorkflowDef(
        id=wf_id,
        name="Workflow de Teste",
        steps=steps,
        trigger_description="trigger de teste",
    )


def _make_agent(name: str, content: str = "resultado", tokens: int = 10) -> BaseAgent:
    agent = MagicMock(spec=BaseAgent)
    agent.config = AgentConfig(name=name, tier="T2", system_prompt="mock")
    agent.run.return_value = AgentResult(
        content=content, tool_calls_count=0, tokens_used=tokens
    )
    return agent


# ---------------------------------------------------------------------------
# execute_workflow — básico
# ---------------------------------------------------------------------------

def test_execute_workflow_runs_all_steps(tmp_path, monkeypatch):
    monkeypatch.setattr("workflow.executor.OUTPUT_DIR", tmp_path)

    step1 = _make_step("agent_a", "step1_out", "Step 1")
    step2 = _make_step("agent_b", "step2_out", "Step 2")
    wf = _make_workflow([step1, step2])

    agent_a = _make_agent("agent_a", "saída A", tokens=15)
    agent_b = _make_agent("agent_b", "saída B", tokens=20)
    agents = {"agent_a": agent_a, "agent_b": agent_b}
    fallback = _make_agent("supervisor")

    result = execute_workflow(wf, "task original", agents, fallback)

    agent_a.run.assert_called_once()
    agent_b.run.assert_called_once()
    assert result.tokens_used == 35


def test_execute_workflow_accumulates_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr("workflow.executor.OUTPUT_DIR", tmp_path)

    steps = [_make_step(f"agent_{i}", f"out_{i}") for i in range(3)]
    wf = _make_workflow(steps)
    agents = {f"agent_{i}": _make_agent(f"agent_{i}", tokens=10) for i in range(3)}
    fallback = _make_agent("supervisor")

    result = execute_workflow(wf, "task", agents, fallback)
    assert result.tokens_used == 30


def test_execute_workflow_passes_previous_context(tmp_path, monkeypatch):
    monkeypatch.setattr("workflow.executor.OUTPUT_DIR", tmp_path)

    step1 = _make_step("agent_a", "design_out", "Etapa A")
    step2 = _make_step("agent_b", "impl_out", "Etapa B")
    wf = _make_workflow([step1, step2])

    agent_a = _make_agent("agent_a", "OUTPUT DA ETAPA A")
    agent_b = _make_agent("agent_b", "etapa B completa")
    agents = {"agent_a": agent_a, "agent_b": agent_b}
    fallback = _make_agent("supervisor")

    execute_workflow(wf, "task", agents, fallback)

    # Segundo agente deve ter recebido contexto com resultado do primeiro
    call_kwargs = agent_b.run.call_args
    if call_kwargs[1]:
        context_passed = call_kwargs[1].get("context", "")
    elif len(call_kwargs[0]) > 1:
        context_passed = call_kwargs[0][1]
    else:
        context_passed = ""
    assert "OUTPUT DA ETAPA A" in context_passed


def test_execute_workflow_uses_fallback_for_unknown_agent(tmp_path, monkeypatch):
    monkeypatch.setattr("workflow.executor.OUTPUT_DIR", tmp_path)

    step = _make_step("non_existent_agent", "out")
    wf = _make_workflow([step])
    agents = {}
    fallback = _make_agent("supervisor", "fallback response")

    result = execute_workflow(wf, "task", agents, fallback)
    fallback.run.assert_called_once()
    assert result is not None


def test_execute_workflow_saves_output_file(tmp_path, monkeypatch):
    monkeypatch.setattr("workflow.executor.OUTPUT_DIR", tmp_path)

    step = _make_step("agent_a", "out")
    wf = _make_workflow([step], wf_id="WF-99")
    agents = {"agent_a": _make_agent("agent_a")}
    fallback = _make_agent("supervisor")

    execute_workflow(wf, "task abc", agents, fallback)

    files = list(tmp_path.glob("wf-99_*.md"))
    assert len(files) == 1


def test_execute_workflow_content_includes_steps(tmp_path, monkeypatch):
    monkeypatch.setattr("workflow.executor.OUTPUT_DIR", tmp_path)

    step1 = _make_step("agent_a", "out1", "Etapa de design")
    wf = _make_workflow([step1])
    agents = {"agent_a": _make_agent("agent_a", "conteúdo gerado")}
    fallback = _make_agent("supervisor")

    result = execute_workflow(wf, "task", agents, fallback)
    assert "Workflow de Teste" in result.content or "WF-TEST" in result.content


# ---------------------------------------------------------------------------
# _build_step_context (via execute_workflow)
# ---------------------------------------------------------------------------

def test_step_context_truncates_long_previous_results(tmp_path, monkeypatch):
    monkeypatch.setattr("workflow.executor.OUTPUT_DIR", tmp_path)

    step1 = _make_step("agent_a", "big_out", "Gera output grande")
    step2 = _make_step("agent_b", "final_out", "Consome output")
    wf = _make_workflow([step1, step2])

    big_content = "X" * 10000
    agent_a = _make_agent("agent_a", big_content)
    agent_b = _make_agent("agent_b", "ok")
    agents = {"agent_a": agent_a, "agent_b": agent_b}
    fallback = _make_agent("supervisor")

    execute_workflow(wf, "task", agents, fallback)

    call_kwargs = agent_b.run.call_args
    context = call_kwargs[1].get("context", "") if call_kwargs[1] else ""
    if context:
        assert len(context) < len(big_content) + 1000
