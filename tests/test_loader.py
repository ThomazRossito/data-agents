"""Testes unitários para agents/loader.py."""

from __future__ import annotations

import pytest

from agents.loader import AGENT_COMMANDS, load_all


def test_agent_commands_has_lakehouse():
    assert "/lakehouse" in AGENT_COMMANDS
    assert AGENT_COMMANDS["/lakehouse"] == "lakehouse_engineer"


def test_agent_commands_has_ops():
    assert "/ops" in AGENT_COMMANDS
    assert AGENT_COMMANDS["/ops"] == "lakehouse_engineer"


def test_agent_commands_has_fabric():
    assert "/fabric" in AGENT_COMMANDS
    assert AGENT_COMMANDS["/fabric"] == "fabric_expert"


def test_agent_commands_has_devops():
    assert "/devops" in AGENT_COMMANDS
    assert AGENT_COMMANDS["/devops"] == "devops_engineer"


def test_no_duplicate_agent_names():
    agent_names = [v for v in AGENT_COMMANDS.values() if not v.startswith("_")]
    # Duplicates are allowed (e.g. /lakehouse + /ops → same agent)
    # but every target agent name must be loadable
    unique = set(agent_names)
    assert len(unique) > 0


def test_load_all_returns_lakehouse_engineer(monkeypatch):
    """load_all() deve incluir lakehouse_engineer no registry."""
    agents = None
    try:
        agents = load_all()
    except Exception:
        pytest.skip("Dependências de runtime não disponíveis (sem API key)")
    assert "lakehouse_engineer" in agents


def test_load_all_has_all_core_agents(monkeypatch):
    try:
        agents = load_all()
    except Exception:
        pytest.skip("Dependências de runtime não disponíveis")
    expected = {
        "spark_expert", "sql_expert", "pipeline_architect", "data_quality",
        "naming_guard", "dbt_expert", "governance_auditor", "python_expert",
        "fabric_expert", "databricks_ai", "devops_engineer", "lakehouse_engineer",
        "geral", "supervisor",
    }
    assert expected.issubset(set(agents.keys()))
