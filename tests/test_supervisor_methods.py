"""Testes para Supervisor — _assess_confidence, _check_escalation, route."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agents.base import AgentConfig, AgentResult, BaseAgent


def _make_agent(name="mock_agent", content="resposta mock") -> BaseAgent:
    cfg = AgentConfig(name=name, tier="T2", system_prompt="mock")
    agent = MagicMock(spec=BaseAgent)
    agent.config = cfg
    agent.run.return_value = AgentResult(
        content=content, tool_calls_count=0, tokens_used=10
    )
    return agent


def _make_supervisor():
    """Cria Supervisor com todos os agentes mockados."""
    agents = {
        "supervisor": _make_agent("supervisor"),
        "geral": _make_agent("geral", "resposta geral"),
        "sql_expert": _make_agent("sql_expert", "resposta sql"),
        "spark_expert": _make_agent("spark_expert"),
        "pipeline_architect": _make_agent("pipeline_architect"),
        "data_quality": _make_agent("data_quality"),
        "naming_guard": _make_agent("naming_guard", "naming ok"),
        "governance_auditor": _make_agent("governance_auditor"),
        "dbt_expert": _make_agent("dbt_expert"),
        "python_expert": _make_agent("python_expert"),
        "fabric_expert": _make_agent("fabric_expert"),
        "databricks_ai": _make_agent("databricks_ai"),
        "devops_engineer": _make_agent("devops_engineer"),
        "lakehouse_engineer": _make_agent("lakehouse_engineer"),
        "qa_reviewer": _make_agent("qa_reviewer"),
    }
    with patch("agents.supervisor.load_all", return_value=agents), \
         patch("agents.supervisor._try_init_memory", return_value=False), \
         patch("agents.supervisor._try_init_kg", return_value=False), \
         patch("agents.supervisor._init_session", return_value=None):
        from agents.supervisor import Supervisor
        sup = Supervisor()
    sup._agents = agents
    sup._supervisor_agent = agents["supervisor"]
    return sup


# ---------------------------------------------------------------------------
# _assess_confidence
# ---------------------------------------------------------------------------

def test_assess_confidence_advisory():
    sup = _make_supervisor()
    criticality, threshold, confidence, decision = sup._assess_confidence(
        "como funciona o Python?", ""
    )
    assert criticality == "ADVISORY"
    assert decision == "PROCEED"
    assert confidence >= 0.80


def test_assess_confidence_standard_with_kb():
    sup = _make_supervisor()
    criticality, threshold, confidence, decision = sup._assess_confidence(
        "criar pipeline bronze ao gold",
        "## KB: pipeline-design\nconteúdo extenso de KB " * 20,
    )
    assert criticality == "STANDARD"
    assert decision == "PROCEED"
    # confidence para STANDARD com KB hit é 0.78, threshold é 0.90
    # mas decision é PROCEED (supervisor não recusa STANDARD)
    assert confidence > 0


def test_assess_confidence_critical_refuse():
    sup = _make_supervisor()
    criticality, threshold, confidence, decision = sup._assess_confidence(
        "DROP TABLE customers", ""
    )
    assert criticality == "CRITICAL"
    assert decision == "REFUSE"


def test_assess_confidence_important_proceed_with_kb():
    sup = _make_supervisor()
    _, _, _, decision = sup._assess_confidence(
        "deploy em produção",
        "## KB: ci-cd\nconteúdo relevante " * 30,
    )
    assert decision == "PROCEED"


# ---------------------------------------------------------------------------
# _check_escalation
# ---------------------------------------------------------------------------

def test_check_escalation_passthrough():
    sup = _make_supervisor()
    original = AgentResult(content="Resposta normal", tool_calls_count=0, tokens_used=5)
    result = sup._check_escalation(original, "task")
    assert result.content == "Resposta normal"


def test_check_escalation_kb_miss_adds_note():
    sup = _make_supervisor()
    original = AgentResult(
        content="resposta\n\nKB_MISS: true",
        tool_calls_count=0,
        tokens_used=5,
    )
    result = sup._check_escalation(original, "task")
    assert "KB_MISS detectado" in result.content


def test_check_escalation_escalate_to_existing_agent():
    sup = _make_supervisor()
    original = AgentResult(
        content="resposta\n\nESCALATE_TO: spark_expert",
        tool_calls_count=0,
        tokens_used=5,
    )
    with patch.object(sup, "_load_kb_context", return_value=""), \
         patch.object(sup, "_inject_preflight_context", return_value=""):
        sup._check_escalation(original, "task spark")
    # spark_expert.run foi chamado
    sup._agents["spark_expert"].run.assert_called()


def test_check_escalation_escalate_to_missing_agent():
    sup = _make_supervisor()
    original = AgentResult(
        content="ESCALATE_TO: nonexistent_agent",
        tool_calls_count=0,
        tokens_used=5,
    )
    result = sup._check_escalation(original, "task")
    # Sem agente disponível, retorna original
    assert result.content == original.content


# ---------------------------------------------------------------------------
# route
# ---------------------------------------------------------------------------

def test_route_health_returns_health():
    sup = _make_supervisor()
    with patch.object(sup, "_route_health", return_value=AgentResult(
        content="health ok", tool_calls_count=0, tokens_used=0
    )):
        result = sup.route("/health")
    assert result.content == "health ok"


def test_route_explicit_sql_command():
    sup = _make_supervisor()
    with patch.object(sup, "_load_kb_context", return_value=""), \
         patch.object(sup, "_load_memory_context", return_value=""), \
         patch.object(sup, "_load_external_context", return_value=""), \
         patch.object(sup, "_inject_preflight_context", return_value=""), \
         patch.object(sup, "_check_escalation", side_effect=lambda r, _: r), \
         patch.object(sup, "_post_process"):
        result = sup.route("/sql SELECT id FROM tbl LIMIT 10")
    sup._agents["sql_expert"].run.assert_called()
    assert result is not None


def test_route_geral_fallback():
    sup = _make_supervisor()
    with patch.object(sup, "_post_process"), \
         patch("agents.supervisor.detect_workflow", return_value=None):
        result = sup.route("o que é um lakeid?")
    assert result is not None


def test_route_table_creation_triggers_governance():
    sup = _make_supervisor()
    with patch.object(sup, "_route_governance") as mock_gov, \
         patch.object(sup, "_post_process"):
        mock_gov.return_value = AgentResult(
            content="naming ok", tool_calls_count=0, tokens_used=0
        )
        sup.route("criar tabela bronze.orders")
    mock_gov.assert_called_once()


def test_route_complex_task_triggers_prd():
    sup = _make_supervisor()
    with patch.object(sup, "_plan_and_delegate") as mock_prd, \
         patch.object(sup, "_post_process"), \
         patch("agents.supervisor.detect_workflow", return_value=None):
        mock_prd.return_value = AgentResult(
            content="PRD + execução", tool_calls_count=0, tokens_used=0
        )
        sup.route("criar pipeline bronze silver gold completo no Fabric")
    mock_prd.assert_called_once()


# ---------------------------------------------------------------------------
# _inject_preflight_context
# ---------------------------------------------------------------------------

def test_inject_preflight_context_fields():
    sup = _make_supervisor()
    preflight = sup._inject_preflight_context(
        "sql_expert", "SELECT 1", "## KB: sql-patterns\n" * 20
    )
    assert "AGENT: sql_expert" in preflight
    assert "CONFIDENCE" in preflight
    assert "STATUS" in preflight


# ---------------------------------------------------------------------------
# list_agents / get_agent
# ---------------------------------------------------------------------------

def test_list_agents_includes_core():
    sup = _make_supervisor()
    agents = sup.list_agents()
    for name in ("sql_expert", "spark_expert", "supervisor", "geral"):
        assert name in agents


def test_get_agent_returns_agent():
    sup = _make_supervisor()
    agent = sup.get_agent("sql_expert")
    assert agent is not None
    assert agent is sup._agents["sql_expert"]


def test_get_agent_returns_none_for_missing():
    sup = _make_supervisor()
    assert sup.get_agent("nonexistent_agent") is None
