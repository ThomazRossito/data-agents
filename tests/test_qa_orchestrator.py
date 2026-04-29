"""Testes para orchestrator/ — models, QAOrchestrator, protocolo completo."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from agents.base import AgentResult, BaseAgent
from orchestrator.models import (
    DeliveryResult,
    ScoreReport,
    TaskSpec,
    parse_json_from_llm,
)
from orchestrator.qa_orchestrator import QAOrchestrator, should_bypass

# ---------------------------------------------------------------------------
# parse_json_from_llm
# ---------------------------------------------------------------------------

def test_parse_json_plain():
    assert parse_json_from_llm('{"a": 1}') == {"a": 1}


def test_parse_json_in_code_block():
    text = '```json\n{"decision": "APPROVE"}\n```'
    assert parse_json_from_llm(text) == {"decision": "APPROVE"}


def test_parse_json_with_prefix_text():
    text = 'Aqui está o resultado:\n{"score": 0.8}'
    assert parse_json_from_llm(text) == {"score": 0.8}


def test_parse_json_returns_empty_on_failure():
    assert parse_json_from_llm("não é json") == {}


# ---------------------------------------------------------------------------
# TaskSpec
# ---------------------------------------------------------------------------

def test_task_spec_new_id_unique():
    id1 = TaskSpec.new_id()
    id2 = TaskSpec.new_id()
    assert id1 != id2
    assert len(id1) == 8


def test_task_spec_to_json_str_parseable():
    spec = TaskSpec(
        task_id="abc12345",
        objective="criar pipeline",
        deliverables=["notebook PySpark"],
        acceptance_criteria=["pipeline lê bronze e escreve silver"],
        agent_name="spark_expert",
        risks=["dados nulos"],
    )
    data = json.loads(spec.to_json_str())
    assert data["task_id"] == "abc12345"
    assert data["version"] == 1
    assert "pipeline" in data["objective"]


def test_task_spec_version_default():
    spec = TaskSpec(
        task_id="x", objective="o", deliverables=[], acceptance_criteria=[],
        agent_name="geral", risks=[],
    )
    assert spec.version == 1


# ---------------------------------------------------------------------------
# ScoreReport.summary
# ---------------------------------------------------------------------------

def test_score_report_summary_passed():
    report = ScoreReport(
        task_id="t1",
        score=0.9,
        passed=True,
        criteria_results=[
            {"criterion": "Entregou código", "passed": True, "evidence": "código presente"}
        ],
        issues=[],
        recommendations=["adicionar testes"],
    )
    summary = report.summary()
    assert "✅" in summary
    assert "90%" in summary
    assert "PASSOU" in summary
    assert "adicionar testes" in summary


def test_score_report_summary_failed():
    report = ScoreReport(
        task_id="t2",
        score=0.5,
        passed=False,
        criteria_results=[
            {"criterion": "Critério A", "passed": True, "evidence": "ok"},
            {"criterion": "Critério B", "passed": False, "evidence": "ausente"},
        ],
        issues=["missing schema"],
        recommendations=[],
    )
    summary = report.summary()
    assert "❌" in summary
    assert "FALHOU" in summary
    assert "missing schema" in summary


def test_score_report_score_threshold_custom():
    report = ScoreReport(
        task_id="t3", score=0.65, passed=False,
        criteria_results=[], issues=[], recommendations=[],
    )
    summary = report.summary(threshold=0.6)
    assert "60%" in summary


# ---------------------------------------------------------------------------
# should_bypass
# ---------------------------------------------------------------------------

def testshould_bypass_health():
    assert should_bypass("/health") is True


def testshould_bypass_help():
    assert should_bypass("/help") is True
    assert should_bypass("help") is True
    assert should_bypass("ajuda") is True


def testshould_bypass_party():
    assert should_bypass("/party criar pipeline em paralelo") is True


def testshould_bypass_kg():
    assert should_bypass("/kg list") is True


def test_should_not_bypass_plan():
    assert should_bypass("/plan criar lakehouse bronze") is False


def test_should_not_bypass_sql():
    assert should_bypass("/sql SELECT * FROM tbl LIMIT 10") is False


def test_should_not_bypass_generic_task():
    assert should_bypass("criar um pipeline delta live tables") is False


# ---------------------------------------------------------------------------
# Helpers para QAOrchestrator
# ---------------------------------------------------------------------------

def _make_qa_agent(review_json: dict | None = None, verify_json: dict | None = None) -> BaseAgent:
    agent = MagicMock(spec=BaseAgent)
    responses = []
    if review_json is not None:
        responses.append(AgentResult(
            content=json.dumps(review_json), tool_calls_count=0, tokens_used=5
        ))
    if verify_json is not None:
        responses.append(AgentResult(
            content=json.dumps(verify_json), tool_calls_count=0, tokens_used=5
        ))
    if responses:
        agent.run.side_effect = responses
    else:
        agent.run.return_value = AgentResult(content="{}", tool_calls_count=0, tokens_used=5)
    return agent


def _make_mock_supervisor(
    draft_spec: TaskSpec | None = None,
    revise_spec: TaskSpec | None = None,
    route_content: str = "resultado",
) -> MagicMock:
    sup = MagicMock()
    if draft_spec is None:
        draft_spec = TaskSpec(
            task_id="test01",
            objective="criar pipeline",
            deliverables=["notebook"],
            acceptance_criteria=["pipeline lê bronze"],
            agent_name="spark_expert",
            risks=[],
        )
    sup.draft_spec.return_value = (draft_spec, 50, 0)
    revised = (
        revise_spec
        if revise_spec
        else TaskSpec(
            task_id=draft_spec.task_id,
            objective=draft_spec.objective,
            deliverables=draft_spec.deliverables,
            acceptance_criteria=draft_spec.acceptance_criteria + ["critério extra"],
            agent_name=draft_spec.agent_name,
            risks=draft_spec.risks,
            version=2,
        )
    )
    sup.revise_spec.return_value = (revised, 30, 0)
    sup.route.return_value = AgentResult(
        content=route_content, tool_calls_count=1, tokens_used=50
    )
    # get_agent default — mock agent que aceita run(task, context=...)
    mock_agent = MagicMock()
    mock_agent.run.return_value = AgentResult(
        content=route_content, tool_calls_count=1, tokens_used=50
    )
    sup.get_agent.return_value = mock_agent
    return sup


# ---------------------------------------------------------------------------
# QAOrchestrator.negotiate_spec
# ---------------------------------------------------------------------------

def test_negotiate_spec_approves_on_first_round():
    review = {"decision": "APPROVE", "feedback": "ok", "proposed_additions": []}
    qa_agent = _make_qa_agent(review_json=review)
    sup = _make_mock_supervisor()

    orchestrator = QAOrchestrator(sup, qa_agent, max_rounds=3)
    spec, rounds, _tokens, _calls = orchestrator.negotiate_spec("criar pipeline")

    assert rounds == 1
    sup.draft_spec.assert_called_once()
    sup.revise_spec.assert_not_called()


def test_negotiate_spec_revises_on_request_changes():
    review1 = {
        "decision": "REQUEST_CHANGES",
        "feedback": "adicionar critério",
        "proposed_additions": ["crit X"],
    }
    review2 = {"decision": "APPROVE", "feedback": "ok agora", "proposed_additions": []}
    qa_agent = _make_qa_agent()
    qa_agent.run.side_effect = [
        AgentResult(content=json.dumps(review1), tool_calls_count=0, tokens_used=5),
        AgentResult(content=json.dumps(review2), tool_calls_count=0, tokens_used=5),
    ]
    sup = _make_mock_supervisor()

    orchestrator = QAOrchestrator(sup, qa_agent, max_rounds=3)
    spec, rounds, _t, _c = orchestrator.negotiate_spec("criar pipeline")

    assert rounds == 2
    sup.revise_spec.assert_called_once()


def test_negotiate_spec_forces_proceed_after_max_rounds():
    review = {"decision": "REQUEST_CHANGES", "feedback": "ainda falta", "proposed_additions": []}
    qa_agent = _make_qa_agent()
    qa_agent.run.return_value = AgentResult(
        content=json.dumps(review), tool_calls_count=0, tokens_used=5
    )
    sup = _make_mock_supervisor()

    orchestrator = QAOrchestrator(sup, qa_agent, max_rounds=2)
    spec, rounds, _t, _c = orchestrator.negotiate_spec("task")

    assert rounds == 2
    assert sup.revise_spec.call_count == 2


# ---------------------------------------------------------------------------
# QAOrchestrator.execute
# ---------------------------------------------------------------------------

def test_execute_calls_supervisor_route():
    qa_agent = _make_qa_agent()
    sup = _make_mock_supervisor(route_content="pipeline criado")
    orchestrator = QAOrchestrator(sup, qa_agent)

    spec = TaskSpec(
        task_id="e01", objective="o", deliverables=["d"], acceptance_criteria=["c"],
        agent_name="spark_expert", risks=[],
    )
    delivery = orchestrator.execute("criar pipeline", spec)

    # Novo comportamento: chama agente direto via get_agent, não supervisor.route
    sup.get_agent.assert_called_once_with("spark_expert")
    sup.route.assert_not_called()
    assert delivery.content == "pipeline criado"
    assert delivery.tokens_used == 50
    assert delivery.spec_version == 1


def test_execute_falls_back_to_route_when_agent_invalid():
    qa_agent = _make_qa_agent()
    sup = _make_mock_supervisor(route_content="fallback")
    sup.get_agent.return_value = None  # agente não existe
    orchestrator = QAOrchestrator(sup, qa_agent)

    spec = TaskSpec(
        task_id="e02", objective="o", deliverables=[], acceptance_criteria=[],
        agent_name="agente_inexistente", risks=[],
    )
    orchestrator.execute("task", spec)

    sup.route.assert_called_once_with("task")


# ---------------------------------------------------------------------------
# QAOrchestrator.verify
# ---------------------------------------------------------------------------

def test_verify_score_all_passed():
    verify_response = {
        "criteria_results": [
            {"criterion": "C1", "passed": True, "evidence": "presente"},
            {"criterion": "C2", "passed": True, "evidence": "presente"},
        ],
        "issues": [],
        "recommendations": [],
    }
    qa_agent = _make_qa_agent(verify_json=verify_response)
    sup = _make_mock_supervisor()
    orchestrator = QAOrchestrator(sup, qa_agent, pass_threshold=0.7)

    spec = TaskSpec(
        task_id="v01", objective="o", deliverables=["d"],
        acceptance_criteria=["C1", "C2"], agent_name="spark_expert", risks=[],
    )
    delivery = DeliveryResult(
        task_id="v01", spec_version=1, content="entrega",
        tool_calls_count=0, tokens_used=10,
    )
    report, _t, _c = orchestrator.verify(spec, delivery)

    assert report.score == 1.0
    assert report.passed is True


def test_verify_score_half_passed():
    verify_response = {
        "criteria_results": [
            {"criterion": "C1", "passed": True, "evidence": "ok"},
            {"criterion": "C2", "passed": False, "evidence": "ausente"},
        ],
        "issues": ["C2 não atendido"],
        "recommendations": [],
    }
    qa_agent = _make_qa_agent(verify_json=verify_response)
    sup = _make_mock_supervisor()
    orchestrator = QAOrchestrator(sup, qa_agent, pass_threshold=0.7)

    spec = TaskSpec(
        task_id="v02", objective="o", deliverables=[], acceptance_criteria=["C1", "C2"],
        agent_name="geral", risks=[],
    )
    delivery = DeliveryResult(
        task_id="v02", spec_version=1, content="entrega parcial",
        tool_calls_count=0, tokens_used=10,
    )
    report, _t, _c = orchestrator.verify(spec, delivery)

    assert report.score == 0.5
    assert report.passed is False
    assert "C2 não atendido" in report.issues


def test_verify_no_criteria_fails_closed():
    """Fail-closed: sem criteria_results → score=0.0, passed=False (era 1.0/True)."""
    verify_response = {"criteria_results": [], "issues": [], "recommendations": []}
    qa_agent = _make_qa_agent(verify_json=verify_response)
    sup = _make_mock_supervisor()
    orchestrator = QAOrchestrator(sup, qa_agent, pass_threshold=0.7)

    spec = TaskSpec(
        task_id="v03", objective="o", deliverables=[], acceptance_criteria=[],
        agent_name="geral", risks=[],
    )
    delivery = DeliveryResult(
        task_id="v03", spec_version=1, content="ok",
        tool_calls_count=0, tokens_used=5,
    )
    report, _t, _c = orchestrator.verify(spec, delivery)
    assert report.score == 0.0
    assert report.passed is False


# ---------------------------------------------------------------------------
# QAOrchestrator.handle — integração
# ---------------------------------------------------------------------------

def test_handle_bypass_skips_qa():
    qa_agent = _make_qa_agent()
    sup = _make_mock_supervisor()
    orchestrator = QAOrchestrator(sup, qa_agent)

    result, report = orchestrator.handle("/health")

    sup.route.assert_called_once_with("/health")
    sup.draft_spec.assert_not_called()
    assert report is None


def test_handle_full_protocol():
    review = {"decision": "APPROVE", "feedback": "ok", "proposed_additions": []}
    verify = {
        "criteria_results": [{"criterion": "C1", "passed": True, "evidence": "ok"}],
        "issues": [],
        "recommendations": [],
    }
    qa_agent = MagicMock(spec=BaseAgent)
    qa_agent.run.side_effect = [
        AgentResult(content=json.dumps(review), tool_calls_count=0, tokens_used=5),
        AgentResult(content=json.dumps(verify), tool_calls_count=0, tokens_used=5),
    ]
    sup = _make_mock_supervisor(route_content="pipeline criado com sucesso")
    orchestrator = QAOrchestrator(sup, qa_agent, pass_threshold=0.7)

    result, report = orchestrator.handle("criar pipeline bronze no Databricks")

    assert result.content == "pipeline criado com sucesso"
    assert report is not None
    assert report.passed is True
    assert report.score == 1.0


# ---------------------------------------------------------------------------
# Supervisor.draft_spec / revise_spec (integração light)
# ---------------------------------------------------------------------------

def test_supervisor_draft_spec_returns_task_spec():
    from agents.supervisor import Supervisor

    mock_supervisor_agent = MagicMock()
    mock_supervisor_agent.run.return_value = AgentResult(
        content=json.dumps({
            "objective": "criar pipeline",
            "deliverables": ["notebook PySpark"],
            "acceptance_criteria": ["lê bronze, escreve silver"],
            "agent_name": "spark_expert",
            "risks": ["dados nulos"],
        }),
        tool_calls_count=0,
        tokens_used=20,
    )

    with patch("agents.supervisor.load_all", return_value={"supervisor": mock_supervisor_agent}), \
         patch("agents.supervisor._try_init_memory", return_value=False), \
         patch("agents.supervisor._try_init_kg", return_value=False), \
         patch("agents.supervisor._init_session", return_value=None):
        sup = Supervisor()
    sup._supervisor_agent = mock_supervisor_agent

    spec, _tokens, _calls = sup.draft_spec("criar um pipeline de ingestão")
    assert spec.objective == "criar pipeline"
    assert spec.agent_name == "spark_expert"
    assert spec.version == 1
    assert len(spec.task_id) == 8


def test_supervisor_revise_spec_increments_version():
    from agents.supervisor import Supervisor

    original = TaskSpec(
        task_id="abc", objective="original", deliverables=["d1"],
        acceptance_criteria=["c1"], agent_name="geral", risks=[], version=1,
    )
    mock_supervisor_agent = MagicMock()
    mock_supervisor_agent.run.return_value = AgentResult(
        content=json.dumps({
            "objective": "original revisado",
            "deliverables": ["d1", "d2"],
            "acceptance_criteria": ["c1", "c2"],
            "agent_name": "geral",
            "risks": [],
            "version": 2,
        }),
        tool_calls_count=0,
        tokens_used=15,
    )

    with patch("agents.supervisor.load_all", return_value={"supervisor": mock_supervisor_agent}), \
         patch("agents.supervisor._try_init_memory", return_value=False), \
         patch("agents.supervisor._try_init_kg", return_value=False), \
         patch("agents.supervisor._init_session", return_value=None):
        sup = Supervisor()
    sup._supervisor_agent = mock_supervisor_agent

    revised, _tokens, _calls = sup.revise_spec(original, "adicionar critério c2", ["c2"])
    assert revised.version == 2
    assert revised.task_id == "abc"
