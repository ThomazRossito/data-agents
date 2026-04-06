"""Testes de definição dos agentes."""

import pytest
from agents.definitions.sql_expert import create_sql_expert
from agents.definitions.spark_expert import create_spark_expert
from agents.definitions.pipeline_architect import create_pipeline_architect


def test_sql_expert_has_required_fields():
    agent = create_sql_expert()
    assert agent.description
    assert agent.prompt
    assert agent.tools
    assert agent.model == "sonnet"
    # SQL Expert não deve ter Bash (apenas leitura)
    assert "Bash" not in (agent.tools or [])


def test_spark_expert_has_no_mcp_tools():
    agent = create_spark_expert()
    # Spark Expert não acessa MCP — apenas gera código
    mcp_tools = [t for t in (agent.tools or []) if t.startswith("mcp__")]
    assert len(mcp_tools) == 0, f"Spark Expert não deveria ter MCP tools: {mcp_tools}"


def test_pipeline_architect_has_both_platforms():
    agent = create_pipeline_architect()
    tools = agent.tools or []
    has_databricks = any("databricks" in t for t in tools)
    has_fabric = any("fabric" in t for t in tools)
    assert has_databricks, "Pipeline Architect deve ter tools do Databricks"
    assert has_fabric, "Pipeline Architect deve ter tools do Fabric"


def test_pipeline_architect_model_is_opus():
    agent = create_pipeline_architect()
    assert agent.model == "opus"


def test_all_agents_have_descriptions():
    for create_fn in [create_sql_expert, create_spark_expert, create_pipeline_architect]:
        agent = create_fn()
        assert len(agent.description) > 20, "Description muito curta"


def test_sql_expert_has_rti_tools():
    agent = create_sql_expert()
    rti_tools = [t for t in (agent.tools or []) if "fabric_rti" in t]
    assert len(rti_tools) > 0, "SQL Expert deve ter tools do Fabric RTI para KQL" 
