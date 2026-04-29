"""Testes para agents/base.py — AgentConfig, BaseAgent loop, _dispatch_tool."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agents.base import AgentConfig, AgentResult, BaseAgent


def _make_config(**kwargs) -> AgentConfig:
    defaults = {
        "name": "test_agent",
        "tier": "T2",
        "system_prompt": "Você é um agente de teste.",
        "skills": [],
        "tools": [],
    }
    defaults.update(kwargs)
    return AgentConfig(**defaults)


def _mock_response(content: str, tokens: int = 10) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = None
    usage = MagicMock()
    usage.total_tokens = tokens
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    return resp


# ---------------------------------------------------------------------------
# AgentConfig
# ---------------------------------------------------------------------------

def test_agent_config_defaults():
    cfg = AgentConfig(name="x", tier="T2", system_prompt="hello")
    assert cfg.skills == []
    assert cfg.tools == []


def test_agent_config_with_values():
    cfg = _make_config(skills=["sql-queries"], tools=[{"type": "function"}])
    assert "sql-queries" in cfg.skills
    assert cfg.tools[0]["type"] == "function"


# ---------------------------------------------------------------------------
# AgentResult
# ---------------------------------------------------------------------------

def test_agent_result_fields():
    r = AgentResult(content="resposta", tool_calls_count=2, tokens_used=100)
    assert r.content == "resposta"
    assert r.tool_calls_count == 2
    assert r.tokens_used == 100


# ---------------------------------------------------------------------------
# BaseAgent._build_system
# ---------------------------------------------------------------------------

def test_build_system_no_skills():
    agent = BaseAgent(_make_config(system_prompt="PROMPT"))
    assert agent._build_system() == "PROMPT"


def test_build_system_with_existing_skill(tmp_path, monkeypatch):
    skill_dir = tmp_path / "skills" / "skills" / "pyspark"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("## PySpark Best Practices")
    monkeypatch.setattr("agents.base.SKILLS_DIR", tmp_path / "skills" / "skills")

    agent = BaseAgent(_make_config(skills=["pyspark"]))
    system = agent._build_system()
    assert "PySpark Best Practices" in system
    assert "Skill: pyspark" in system


def test_build_system_missing_skill():
    agent = BaseAgent(_make_config(skills=["nonexistent_xyz"]))
    # Não levanta exceção, simplesmente ignora a skill ausente
    system = agent._build_system()
    assert "nonexistent_xyz" not in system


# ---------------------------------------------------------------------------
# BaseAgent.run — resposta direta
# ---------------------------------------------------------------------------

def test_run_returns_direct_response():
    agent = BaseAgent(_make_config())
    mock_resp = _mock_response("Resposta direta", tokens=42)

    with patch("agents.base.settings") as mock_settings:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        mock_settings.copilot_client = mock_client
        mock_settings.model_for_tier.return_value = "gpt-4o"
        mock_settings.turns_for_tier.return_value = 5

        agent.model = "gpt-4o"
        agent.max_turns = 5
        result = agent.run("pergunta")

    assert result.content == "Resposta direta"
    assert result.tokens_used == 42
    assert result.tool_calls_count == 0


def test_run_with_context_adds_message():
    agent = BaseAgent(_make_config())
    mock_resp = _mock_response("OK")
    calls = []

    def capture_create(**kwargs):
        calls.append(kwargs["messages"])
        return mock_resp

    with patch("agents.base.settings") as mock_settings:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = capture_create
        mock_settings.copilot_client = mock_client
        mock_settings.model_for_tier.return_value = "gpt-4o"
        mock_settings.turns_for_tier.return_value = 5

        agent.model = "gpt-4o"
        agent.max_turns = 5
        agent.run("task", context="contexto extra")

    messages = calls[0]
    roles = [m["role"] for m in messages]
    assert "system" in roles
    assert roles.count("user") == 2
    assert any("contexto extra" in str(m.get("content", "")) for m in messages)


# ---------------------------------------------------------------------------
# BaseAgent.run — tool calls
# ---------------------------------------------------------------------------

def test_run_handles_tool_call_then_finish():
    agent = BaseAgent(
        _make_config(tools=[{"type": "function", "function": {"name": "dbr_list_catalogs"}}])
    )

    # Turn 1: tool call
    tool_call = MagicMock()
    tool_call.id = "tc_001"
    tool_call.function.name = "dbr_list_catalogs"
    tool_call.function.arguments = "{}"
    msg_tool = MagicMock()
    msg_tool.content = None
    msg_tool.tool_calls = [tool_call]
    usage1 = MagicMock()
    usage1.total_tokens = 20
    resp1 = MagicMock()
    resp1.choices = [MagicMock(message=msg_tool)]
    resp1.usage = usage1

    # Turn 2: resposta final
    resp2 = _mock_response("Resultado final", tokens=15)

    with patch("agents.base.settings") as mock_settings, \
         patch("agents.base.BaseAgent._dispatch_tool", return_value="[catalogs]") as mock_dispatch:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [resp1, resp2]
        mock_settings.copilot_client = mock_client
        mock_settings.model_for_tier.return_value = "gpt-4o"
        mock_settings.turns_for_tier.return_value = 5

        agent.model = "gpt-4o"
        agent.max_turns = 5
        result = agent.run("lista catalogs")

    mock_dispatch.assert_called_once_with("dbr_list_catalogs", "{}")
    assert result.content == "Resultado final"
    assert result.tool_calls_count == 1
    assert result.tokens_used == 35


# ---------------------------------------------------------------------------
# BaseAgent.run — max_turns
# ---------------------------------------------------------------------------

def test_run_respects_max_turns():
    agent = BaseAgent(_make_config())
    # Sempre retorna tool_call para forçar loop
    tool_call = MagicMock()
    tool_call.id = "tc_x"
    tool_call.function.name = "some_tool"
    tool_call.function.arguments = "{}"
    msg = MagicMock()
    msg.content = "loop"
    msg.tool_calls = [tool_call]
    usage = MagicMock()
    usage.total_tokens = 5
    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    resp.usage = usage

    with patch("agents.base.settings") as mock_settings, \
         patch("agents.base.BaseAgent._dispatch_tool", return_value="ok"):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = resp
        mock_settings.copilot_client = mock_client
        mock_settings.model_for_tier.return_value = "gpt-4o"
        mock_settings.turns_for_tier.return_value = 2

        agent.model = "gpt-4o"
        agent.max_turns = 2
        result = agent.run("task")

    # Deve encerrar após max_turns sem lançar exceção
    assert result is not None
    assert mock_client.chat.completions.create.call_count == 2


# ---------------------------------------------------------------------------
# BaseAgent._dispatch_tool
# ---------------------------------------------------------------------------

def test_dispatch_tool_routes_via_agents_tools():
    agent = BaseAgent(_make_config())
    with patch("agents.tools.dispatch_tool", return_value='["result"]') as mock_dt:
        result = agent._dispatch_tool("dbr_list_catalogs", "{}")
    # Agora dispatch_tool recebe dict (args_parsed), não a string bruta
    mock_dt.assert_called_once_with("dbr_list_catalogs", {})
    assert result == '["result"]'
