"""Testes para agents/party.py."""
from __future__ import annotations

from unittest.mock import MagicMock

from agents.base import AgentConfig, AgentResult, BaseAgent


def _make_agent(name="mock", content="resposta") -> BaseAgent:
    cfg = AgentConfig(name=name, tier="T2", system_prompt="mock")
    agent = MagicMock(spec=BaseAgent)
    agent.config = cfg
    agent.run.return_value = AgentResult(
        content=content, tool_calls_count=1, tokens_used=20
    )
    return agent


# ---------------------------------------------------------------------------
# parse_party_command
# ---------------------------------------------------------------------------

def test_parse_party_command_sql_preset():
    from agents.party import _PRESETS, parse_party_command

    names, query = parse_party_command("--sql como otimizar uma query?")
    assert names == _PRESETS["--sql"]
    assert query == "como otimizar uma query?"


def test_parse_party_command_full_preset():
    from agents.party import _PRESETS, parse_party_command

    names, query = parse_party_command("--full explique Unity Catalog")
    assert names == _PRESETS["--full"]
    assert "Unity Catalog" in query


def test_parse_party_command_custom_agents():
    from agents.party import parse_party_command

    names, query = parse_party_command("--agents sql_expert,dbt_expert escreva uma CTE")
    assert "sql_expert" in names
    assert "dbt_expert" in names
    assert "escreva uma CTE" in query


def test_parse_party_command_no_flag_uses_default():
    from agents.party import _DEFAULT_PRESET, _PRESETS, parse_party_command

    names, query = parse_party_command("pergunta sem flag")
    assert names == _PRESETS[_DEFAULT_PRESET]
    assert query == "pergunta sem flag"


def test_parse_party_command_empty():
    from agents.party import _DEFAULT_PRESET, _PRESETS, parse_party_command

    names, query = parse_party_command("")
    assert names == _PRESETS[_DEFAULT_PRESET]
    assert query == ""


def test_parse_party_command_quality_preset():
    from agents.party import _PRESETS, parse_party_command

    names, query = parse_party_command("--quality validar incrementais")
    assert names == _PRESETS["--quality"]
    assert "validar incrementais" in query


# ---------------------------------------------------------------------------
# run_party
# ---------------------------------------------------------------------------

def test_run_party_basic():
    from agents.party import run_party

    agents = {
        "sql_expert": _make_agent("sql_expert", "SQL result"),
        "spark_expert": _make_agent("spark_expert", "Spark result"),
    }
    result = run_party("como fazer JOIN?", agents, ["sql_expert", "spark_expert"])
    assert "Party Mode" in result.content
    assert "sql_expert" in result.content
    assert "spark_expert" in result.content
    assert result.tokens_used == 40
    assert result.tool_calls_count == 2


def test_run_party_missing_agent_skipped():
    from agents.party import run_party

    agents = {
        "sql_expert": _make_agent("sql_expert", "SQL result"),
    }
    result = run_party("query", agents, ["sql_expert", "nonexistent_agent"])
    assert "sql_expert" in result.content
    assert "nonexistent_agent" not in result.content


def test_run_party_no_valid_agents():
    from agents.party import run_party

    result = run_party("query", {}, ["nonexistent"])
    assert "Nenhum agente válido" in result.content
    assert result.tool_calls_count == 0


def test_run_party_with_context():
    from agents.party import run_party

    agents = {"sql_expert": _make_agent("sql_expert", "SQL result")}
    result = run_party("query", agents, ["sql_expert"], context="contexto KB")
    agents["sql_expert"].run.assert_called_once_with("query", "contexto KB")
    assert result is not None


def test_run_party_agent_exception_returns_error():
    from agents.party import run_party

    bad_agent = MagicMock(spec=BaseAgent)
    bad_agent.run.side_effect = RuntimeError("agent crash")
    agents = {"sql_expert": bad_agent}

    result = run_party("query", agents, ["sql_expert"])
    assert "Erro" in result.content or "❌" in result.content


def test_run_party_compresses_long_output():
    from agents.party import _PARTY_MAX_CHARS, run_party

    long_content = "x" * (_PARTY_MAX_CHARS + 1000)
    agents = {"sql_expert": _make_agent("sql_expert", long_content)}

    result = run_party("query", agents, ["sql_expert"])
    # Verifica que o output de sql_expert foi truncado (compress aplicado)
    section_start = result.content.find("## 🤖 `sql_expert`")
    section_text = result.content[section_start:]
    assert len(section_text) < len(long_content)


def test_run_party_preserves_agent_order():
    from agents.party import run_party

    agents = {
        "sql_expert": _make_agent("sql_expert", "sql"),
        "spark_expert": _make_agent("spark_expert", "spark"),
        "pipeline_architect": _make_agent("pipeline_architect", "pipe"),
    }
    result = run_party("query", agents, ["sql_expert", "spark_expert", "pipeline_architect"])
    sql_pos = result.content.find("sql_expert")
    spark_pos = result.content.find("spark_expert")
    pipe_pos = result.content.find("pipeline_architect")
    assert sql_pos < spark_pos < pipe_pos
