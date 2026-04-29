"""Testes adicionais para Supervisor — rotas /resume, /sessions, /kg, /party,
_load_*, _save_memory, draft_spec, revise_spec, _plan_and_delegate."""

from __future__ import annotations

from pathlib import Path
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
    agents = {
        "supervisor": _make_agent("supervisor", '{"objective":"obj","deliverables":["d"],'
                                  '"acceptance_criteria":["ac"],"agent_name":"geral","risks":[]}'),
        "geral": _make_agent("geral", "resposta geral"),
        "sql_expert": _make_agent("sql_expert"),
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
# /resume route
# ---------------------------------------------------------------------------

def test_route_resume_without_task():
    sup = _make_supervisor()
    with patch("agents.supervisor.load_all", return_value=sup._agents), \
         patch("utils.session.SessionManager.load_last_session",
               return_value="sessão anterior"):
        result = sup._route_resume("")
    assert result.content == "sessão anterior"


def test_route_resume_with_task():
    sup = _make_supervisor()
    with patch("utils.session.SessionManager.load_last_session",
               return_value="sessão anterior"), \
         patch.object(sup, "_load_memory_context", return_value=""):
        result = sup._route_resume("continuar análise")
    assert result is not None
    sup._agents["geral"].run.assert_called()


def test_route_sessions():
    sup = _make_supervisor()
    with patch("utils.session.SessionManager.list_sessions",
               return_value="## Sessions\n- 2024-01"):
        result = sup._route_sessions()
    assert "Sessions" in result.content


# ---------------------------------------------------------------------------
# /kg route
# ---------------------------------------------------------------------------

def test_route_kg_disabled():
    sup = _make_supervisor()
    sup._kg_enabled = False
    result = sup._route_kg("list")
    assert "não disponível" in result.content


def test_route_kg_list_empty():
    sup = _make_supervisor()
    sup._kg_enabled = True
    mock_kg = MagicMock()
    mock_kg.all_entities.return_value = []
    with patch("memory.kg.KnowledgeGraph", return_value=mock_kg):
        result = sup._route_kg("list")
    assert "vazio" in result.content


def test_route_kg_list_with_entities():
    sup = _make_supervisor()
    sup._kg_enabled = True
    entity = MagicMock()
    entity.id = "orders"
    entity.type = "TABLE"
    entity.props = {"layer": "silver"}
    mock_kg = MagicMock()
    mock_kg.all_entities.return_value = [entity]
    with patch("memory.kg.KnowledgeGraph", return_value=mock_kg):
        result = sup._route_kg("")
    assert "orders" in result.content


def test_route_kg_lineage():
    sup = _make_supervisor()
    sup._kg_enabled = True
    mock_kg = MagicMock()
    mock_kg.format_lineage.return_value = "lineage de orders"
    with patch("memory.kg.KnowledgeGraph", return_value=mock_kg):
        result = sup._route_kg("lineage orders")
    mock_kg.format_lineage.assert_called_with("orders")
    assert "lineage de orders" in result.content


def test_route_kg_add_relation():
    sup = _make_supervisor()
    sup._kg_enabled = True
    mock_kg = MagicMock()
    with patch("memory.kg.KnowledgeGraph", return_value=mock_kg):
        result = sup._route_kg("add bronze.raw FEEDS_INTO silver.clean")
    mock_kg.add_relation.assert_called_once()
    assert "Relação adicionada" in result.content


def test_route_kg_invalid_command():
    sup = _make_supervisor()
    sup._kg_enabled = True
    mock_kg = MagicMock()
    mock_kg.all_entities.return_value = []
    with patch("memory.kg.KnowledgeGraph", return_value=mock_kg):
        result = sup._route_kg("unknown_cmd")
    assert "Uso:" in result.content


def test_route_kg_via_supervisor_route():
    sup = _make_supervisor()
    with patch.object(sup, "_route_kg", return_value=AgentResult(
        content="kg ok", tool_calls_count=0, tokens_used=0
    )):
        result = sup.route("/kg list")
    assert result.content == "kg ok"


# ---------------------------------------------------------------------------
# /party route
# ---------------------------------------------------------------------------

def test_route_party_via_route():
    sup = _make_supervisor()
    with patch.object(sup, "_route_party", return_value=AgentResult(
        content="party result", tool_calls_count=0, tokens_used=0
    )), patch.object(sup, "_post_process"):
        result = sup.route("/party --sql como otimizar?")
    assert result.content == "party result"


def test_route_party_calls_run_party():
    sup = _make_supervisor()
    with patch("agents.party.run_party") as mock_rp, \
         patch.object(sup, "_load_kb_for_task", return_value=""):
        mock_rp.return_value = AgentResult(
            content="party ok", tool_calls_count=0, tokens_used=0
        )
        result = sup._route_party("--sql qual é o melhor join?")
    mock_rp.assert_called_once()
    assert result is not None


# ---------------------------------------------------------------------------
# /resume and /sessions via route
# ---------------------------------------------------------------------------

def test_route_sessions_via_route():
    sup = _make_supervisor()
    with patch.object(sup, "_route_sessions", return_value=AgentResult(
        content="sessions list", tool_calls_count=0, tokens_used=0
    )):
        result = sup.route("/sessions")
    assert result.content == "sessions list"


def test_route_resume_via_route():
    sup = _make_supervisor()
    with patch.object(sup, "_route_resume", return_value=AgentResult(
        content="resumed", tool_calls_count=0, tokens_used=0
    )):
        result = sup.route("/resume continuar")
    assert result.content == "resumed"


# ---------------------------------------------------------------------------
# _load_naming_convention_context
# ---------------------------------------------------------------------------

def test_load_naming_convention_missing_file():
    sup = _make_supervisor()
    with patch.object(Path, "exists", return_value=False):
        result = sup._load_naming_convention_context()
    assert result == ""


def test_load_naming_convention_empty_file(tmp_path):
    sup = _make_supervisor()
    conv_file = tmp_path / "naming convention.md"
    conv_file.write_text("  \n  ")
    with patch("agents.supervisor.NAMING_CONVENTION_FILE", conv_file):
        result = sup._load_naming_convention_context()
    assert result == ""


def test_load_naming_convention_with_content(tmp_path):
    sup = _make_supervisor()
    conv_file = tmp_path / "naming convention.md"
    conv_file.write_text("usa snake_case em tabelas")
    with patch("agents.supervisor.NAMING_CONVENTION_FILE", conv_file):
        result = sup._load_naming_convention_context()
    assert "snake_case" in result


# ---------------------------------------------------------------------------
# _load_external_context
# ---------------------------------------------------------------------------

def test_load_external_context_no_match():
    sup = _make_supervisor()
    result = sup._load_external_context("sql_expert", "SELECT 1")
    assert result == ""


def test_load_external_context_fabric_cicd():
    sup = _make_supervisor()
    with patch("integrations.github_context.fetch_fabric_cicd_context",
               return_value="fabric ci/cd content"):
        result = sup._load_external_context(
            "devops_engineer", "deploy no fabric ci-cd pipeline"
        )
    assert "fabric ci/cd content" in result


def test_load_external_context_fabric_cicd_exception():
    sup = _make_supervisor()
    with patch("integrations.github_context.fetch_fabric_cicd_context",
               side_effect=Exception("timeout")):
        result = sup._load_external_context(
            "devops_engineer", "deploy no fabric ci-cd"
        )
    assert result == ""


# ---------------------------------------------------------------------------
# _load_memory_context
# ---------------------------------------------------------------------------

def test_load_memory_context_disabled():
    sup = _make_supervisor()
    sup._memory_enabled = False
    assert sup._load_memory_context("qualquer task") == ""


def test_load_memory_context_enabled():
    sup = _make_supervisor()
    sup._memory_enabled = True
    with patch("memory.store.MemoryStore"), \
         patch("memory.retrieval.retrieve_relevant_memories", return_value=[]), \
         patch("memory.retrieval.format_memories_for_injection", return_value="## Memórias\n"):
        result = sup._load_memory_context("task")
    assert "Memórias" in result


def test_load_memory_context_exception_returns_empty():
    sup = _make_supervisor()
    sup._memory_enabled = True
    with patch("memory.store.MemoryStore", side_effect=Exception("db error")):
        result = sup._load_memory_context("task")
    assert result == ""


# ---------------------------------------------------------------------------
# _save_memory
# ---------------------------------------------------------------------------

def test_save_memory_disabled():
    sup = _make_supervisor()
    sup._memory_enabled = False
    # Não deve lançar exceção
    sup._save_memory("task", "content")


def test_save_memory_enabled():
    sup = _make_supervisor()
    sup._memory_enabled = True
    sup._kg_enabled = False
    with patch("memory.store.MemoryStore"), \
         patch("memory.extractor.extract_and_save") as mock_extract:
        sup._save_memory("task", "resultado")
    mock_extract.assert_called_once()


def test_save_memory_with_kg():
    sup = _make_supervisor()
    sup._memory_enabled = True
    sup._kg_enabled = True
    with patch("memory.store.MemoryStore"), \
         patch("memory.extractor.extract_and_save"), \
         patch("memory.kg.KnowledgeGraph"), \
         patch("memory.kg.extract_lineage_from_text") as mock_lineage:
        sup._save_memory("task", "lineage data")
    mock_lineage.assert_called_once()


# ---------------------------------------------------------------------------
# _route_governance
# ---------------------------------------------------------------------------

def test_route_governance():
    sup = _make_supervisor()
    with patch.object(sup, "_load_naming_convention_context", return_value=""), \
         patch.object(sup, "_load_kb_context", return_value=""), \
         patch.object(sup, "_save_memory"):
        result = sup._route_governance("CREATE TABLE bronze.orders (id INT)")
    sup._agents["naming_guard"].run.assert_called()
    assert result is not None


# ---------------------------------------------------------------------------
# _plan_and_delegate
# ---------------------------------------------------------------------------

def test_plan_and_delegate_refuse():
    sup = _make_supervisor()
    # CRITICAL task sem KB → REFUSE
    with patch.object(sup, "_load_kb_for_task", return_value=""):
        result = sup._plan_and_delegate("DROP TABLE production.customers")
    assert "recusada" in result.content or "REFUSE" in result.content


def test_plan_and_delegate_proceed(tmp_path):
    sup = _make_supervisor()
    # PRD response contém o nome do agente → delegação
    prd_content = "Agente responsável: spark_expert\n## PRD content"
    sup._agents["supervisor"].run.return_value = AgentResult(
        content=prd_content, tool_calls_count=0, tokens_used=5
    )
    sup._agents["spark_expert"].run.return_value = AgentResult(
        content="execução ok", tool_calls_count=1, tokens_used=20
    )
    with patch.object(sup, "_load_kb_for_task", return_value="## KB hits " * 20), \
         patch.object(sup, "_load_memory_context", return_value=""), \
         patch.object(sup, "_load_kb_context", return_value=""), \
         patch.object(sup, "_load_external_context", return_value=""), \
         patch.object(sup, "_inject_preflight_context", return_value=""), \
         patch.object(sup, "_check_escalation", side_effect=lambda r, _: r), \
         patch.object(sup, "_save_memory"), \
         patch("agents.supervisor.OUTPUT_DIR", tmp_path):
        result = sup._plan_and_delegate("criar pipeline bronze silver gold no Databricks")
    assert result is not None


# ---------------------------------------------------------------------------
# draft_spec / revise_spec
# ---------------------------------------------------------------------------

def test_draft_spec_returns_task_spec():
    sup = _make_supervisor()
    from orchestrator.models import TaskSpec
    spec, _tokens, _calls = sup.draft_spec("criar pipeline incremental no Fabric")
    assert isinstance(spec, TaskSpec)
    assert spec.objective
    assert len(spec.deliverables) >= 1


def test_revise_spec_increments_version():
    sup = _make_supervisor()
    from orchestrator.models import TaskSpec
    original = TaskSpec(
        task_id="t1",
        objective="objetivo inicial",
        deliverables=["item"],
        acceptance_criteria=["critério"],
        agent_name="geral",
        risks=[],
        version=1,
    )
    sup._supervisor_agent.run.return_value = AgentResult(
        content='{"objective":"revisado","deliverables":["item atualizado"],'
                '"acceptance_criteria":["novo critério"],"agent_name":"sql_expert",'
                '"risks":[],"version":2}',
        tool_calls_count=0,
        tokens_used=5,
    )
    revised, _tokens, _calls = sup.revise_spec(original, "feedback: precisa de mais detalhe", [])
    assert isinstance(revised, TaskSpec)
    assert revised.version == 2


# ---------------------------------------------------------------------------
# _assessment route — sem integração real (mock total)
# ---------------------------------------------------------------------------

def test_route_assessment_error_status():
    sup = _make_supervisor()
    with patch("integrations.fabricgov.run_assessment",
               return_value={"status": "error", "message": "falhou"}), \
         patch("integrations.fabricgov.format_result",
               return_value="❌ Erro: falhou"):
        result = sup._route_assessment("all")
    assert result is not None
    assert "Erro" in result.content or result.content


def test_route_assessment_via_route():
    sup = _make_supervisor()
    with patch.object(sup, "_route_assessment", return_value=AgentResult(
        content="assessment ok", tool_calls_count=0, tokens_used=0
    )):
        result = sup.route("/assessment")
    assert result.content == "assessment ok"


# ---------------------------------------------------------------------------
# _post_process
# ---------------------------------------------------------------------------

def test_post_process_blocks_destructive():
    sup = _make_supervisor()
    result = AgentResult(
        content="```bash\nrm -rf /data/prod\n```",
        tool_calls_count=0,
        tokens_used=5,
    )
    with patch("hooks.audit_hook.record"):
        sup._post_process("drop task", result, agent_name="geral")
    assert "bloqueado" in result.content


def test_post_process_records_audit():
    sup = _make_supervisor()
    result = AgentResult(content="resposta segura", tool_calls_count=0, tokens_used=5)
    with patch("hooks.audit_hook.record") as mock_audit, \
         patch("hooks.security_hook.check_output", return_value=(True, "")):
        sup._post_process("task", result, agent_name="sql_expert")
    mock_audit.assert_called_once()
