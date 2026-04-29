"""Testes para agents/tools — schemas, dispatcher e registry."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from agents.tools import dispatch_tool, load_tools_for_mcps
from agents.tools.databricks import DATABRICKS_TOOLS, dispatch_databricks
from agents.tools.fabric import FABRIC_TOOLS, dispatch_fabric

# ---------------------------------------------------------------------------
# load_tools_for_mcps
# ---------------------------------------------------------------------------

def test_load_tools_databricks():
    tools = load_tools_for_mcps(["databricks"])
    names = {t["function"]["name"] for t in tools}
    assert "dbr_sql_execute" in names
    assert "dbr_list_catalogs" in names
    assert "dbr_run_job" in names


def test_load_tools_fabric():
    tools = load_tools_for_mcps(["fabric"])
    names = {t["function"]["name"] for t in tools}
    assert "fabric_list_workspaces" in names
    assert "fabric_list_lakehouses" in names
    assert "fabric_run_notebook" in names


def test_load_tools_both():
    tools = load_tools_for_mcps(["databricks", "fabric"])
    assert len(tools) == len(DATABRICKS_TOOLS) + len(FABRIC_TOOLS)


def test_load_tools_unknown_mcp():
    tools = load_tools_for_mcps(["nonexistent"])
    assert tools == []


def test_load_tools_empty():
    assert load_tools_for_mcps([]) == []


# ---------------------------------------------------------------------------
# Tool schema structure
# ---------------------------------------------------------------------------

def test_databricks_tool_schemas_structure():
    for tool in DATABRICKS_TOOLS:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        params = fn["parameters"]
        assert params["type"] == "object"
        assert "properties" in params
        assert "required" in params


def test_fabric_tool_schemas_structure():
    for tool in FABRIC_TOOLS:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn


# ---------------------------------------------------------------------------
# dispatch_tool — roteamento global
# ---------------------------------------------------------------------------

def test_dispatch_tool_routes_to_databricks():
    with patch("agents.tools.databricks._get") as mock_get:
        mock_get.return_value = {"catalogs": [{"name": "main"}]}
        result = dispatch_tool("dbr_list_catalogs", "{}")
        assert "main" in result


def test_dispatch_tool_routes_to_fabric():
    with patch("agents.tools.fabric._get_token", return_value="fake_token"), \
         patch("agents.tools.fabric._get") as mock_get:
        mock_get.return_value = {"value": [{"id": "ws1", "displayName": "WS 1"}]}
        result = dispatch_tool("fabric_list_workspaces", "{}")
        assert "ws1" in result


def test_dispatch_tool_unknown():
    result = dispatch_tool("nonexistent_tool", "{}")
    assert "não encontrada" in result


# ---------------------------------------------------------------------------
# dispatch_databricks
# ---------------------------------------------------------------------------

def test_dbr_sql_execute_success():
    mock_response = {
        "status": {"state": "SUCCEEDED"},
        "result": {
            "schema": {"columns": [{"name": "id"}, {"name": "name"}]},
            "data_array": [["1", "Alice"], ["2", "Bob"]],
        },
    }
    with patch("agents.tools.databricks._post", return_value=mock_response), \
         patch("agents.tools.databricks.settings") as mock_settings:
        mock_settings.databricks_sql_warehouse_id = "wh123"
        mock_settings.databricks_catalog = "main"
        mock_settings.databricks_schema = "default"
        result = dispatch_databricks("dbr_sql_execute", {"statement": "SELECT 1"})
    data = json.loads(result)
    assert data["columns"] == ["id", "name"]
    assert len(data["rows"]) == 2


def test_dbr_sql_execute_no_warehouse():
    with patch("agents.tools.databricks.settings") as mock_settings:
        mock_settings.databricks_sql_warehouse_id = ""
        result = dispatch_databricks("dbr_sql_execute", {"statement": "SELECT 1"})
    assert "DATABRICKS_SQL_WAREHOUSE_ID" in result


def test_dbr_list_catalogs():
    with patch("agents.tools.databricks._get") as mock_get:
        mock_get.return_value = {"catalogs": [{"name": "main"}, {"name": "dev"}]}
        result = dispatch_databricks("dbr_list_catalogs", {})
    assert json.loads(result) == ["main", "dev"]


def test_dbr_list_schemas():
    with patch("agents.tools.databricks._get") as mock_get:
        mock_get.return_value = {"schemas": [{"name": "bronze"}, {"name": "silver"}]}
        result = dispatch_databricks("dbr_list_schemas", {"catalog": "main"})
    assert "bronze" in json.loads(result)


def test_dbr_list_tables():
    with patch("agents.tools.databricks._get") as mock_get:
        mock_get.return_value = {"tables": [{
            "name": "orders", "table_type": "MANAGED",
            "full_name": "main.sales.orders",
        }]}
        result = dispatch_databricks("dbr_list_tables", {"catalog": "main", "schema": "sales"})
    tables = json.loads(result)
    assert tables[0]["name"] == "orders"


def test_dbr_get_table_schema():
    with patch("agents.tools.databricks._get") as mock_get:
        mock_get.return_value = {
            "columns": [{"name": "id", "type_text": "bigint", "nullable": False}],
            "properties": {},
        }
        result = dispatch_databricks("dbr_get_table_schema", {"full_name": "main.sales.orders"})
    data = json.loads(result)
    assert data["columns"][0]["name"] == "id"


def test_dbr_run_job():
    with patch("agents.tools.databricks._post") as mock_post:
        mock_post.return_value = {"run_id": 42, "number_in_job": 1}
        result = dispatch_databricks("dbr_run_job", {"job_id": "123"})
    assert json.loads(result)["run_id"] == 42


def test_dbr_get_job_run_status():
    with patch("agents.tools.databricks._get") as mock_get:
        mock_get.return_value = {
            "state": {"life_cycle_state": "TERMINATED", "result_state": "SUCCESS"},
            "start_time": 1000,
            "end_time": 2000,
        }
        result = dispatch_databricks("dbr_get_job_run_status", {"run_id": "99"})
    data = json.loads(result)
    assert data["life_cycle_state"] == "TERMINATED"


def test_dbr_list_jobs():
    with patch("agents.tools.databricks._get") as mock_get:
        mock_get.return_value = {"jobs": [{"job_id": 1, "settings": {"name": "etl_job"}}]}
        result = dispatch_databricks("dbr_list_jobs", {})
    assert json.loads(result)[0]["name"] == "etl_job"


def test_dbr_list_clusters():
    with patch("agents.tools.databricks._get") as mock_get:
        mock_get.return_value = {"clusters": [{
            "cluster_id": "cl1", "cluster_name": "main", "state": "RUNNING",
        }]}
        result = dispatch_databricks("dbr_list_clusters", {})
    assert json.loads(result)[0]["state"] == "RUNNING"


def test_dispatch_databricks_http_error():
    http_err = requests.HTTPError(response=MagicMock(text="Unauthorized"))
    with patch("agents.tools.databricks._get", side_effect=http_err):
        result = dispatch_databricks("dbr_list_catalogs", {})
    assert "Erro Databricks API" in result


def test_dispatch_databricks_unknown_tool():
    result = dispatch_databricks("dbr_nonexistent", {})
    assert "não reconhecida" in result


# ---------------------------------------------------------------------------
# dispatch_fabric
# ---------------------------------------------------------------------------

def test_fabric_list_workspaces():
    with patch("agents.tools.fabric._get_token", return_value="tok"), \
         patch("agents.tools.fabric._get") as mock_get:
        mock_get.return_value = {"value": [{"id": "ws1", "displayName": "Prod WS"}]}
        result = dispatch_fabric("fabric_list_workspaces", {})
    assert json.loads(result)[0]["id"] == "ws1"


def test_fabric_list_items():
    with patch("agents.tools.fabric._get_token", return_value="tok"), \
         patch("agents.tools.fabric._get") as mock_get:
        mock_get.return_value = {"value": [{"id": "nb1", "displayName": "NB1", "type": "Notebook"}]}
        result = dispatch_fabric("fabric_list_items", {"workspace_id": "ws1"})
    assert json.loads(result)[0]["type"] == "Notebook"


def test_fabric_list_lakehouses():
    with patch("agents.tools.fabric._get_token", return_value="tok"), \
         patch("agents.tools.fabric._get") as mock_get, \
         patch("agents.tools.fabric.settings") as mock_s:
        mock_s.fabric_workspace_id = "ws1"
        mock_get.return_value = {"value": [{"id": "lh1", "displayName": "Bronze"}]}
        result = dispatch_fabric("fabric_list_lakehouses", {})
    assert "lh1" in result


def test_fabric_get_lakehouse_tables():
    with patch("agents.tools.fabric._get_token", return_value="tok"), \
         patch("agents.tools.fabric._get") as mock_get:
        mock_get.return_value = {"data": [{"name": "orders", "type": "Managed", "format": "Delta"}]}
        result = dispatch_fabric(
            "fabric_get_lakehouse_tables",
            {"workspace_id": "ws1", "lakehouse_id": "lh1"},
        )
    assert json.loads(result)[0]["name"] == "orders"


def test_fabric_run_notebook():
    with patch("agents.tools.fabric._get_token", return_value="tok"), \
         patch("agents.tools.fabric._post") as mock_post:
        mock_post.return_value = {"id": "job1"}
        result = dispatch_fabric("fabric_run_notebook", {"workspace_id": "ws1", "item_id": "nb1"})
    assert json.loads(result)["id"] == "job1"


def test_fabric_get_job_instance():
    with patch("agents.tools.fabric._get_token", return_value="tok"), \
         patch("agents.tools.fabric._get") as mock_get:
        mock_get.return_value = {
            "id": "ji1", "status": "Completed",
            "startTimeUtc": "2024-01-01T00:00:00Z",
            "endTimeUtc": "2024-01-01T01:00:00Z",
        }
        result = dispatch_fabric(
            "fabric_get_job_instance",
            {"workspace_id": "ws1", "item_id": "nb1", "job_instance_id": "ji1"},
        )
    assert json.loads(result)["status"] == "Completed"


def test_dispatch_fabric_http_error():
    http_err = requests.HTTPError(response=MagicMock(text="Forbidden"))
    with patch("agents.tools.fabric._get_token", return_value="tok"), \
         patch("agents.tools.fabric._get", side_effect=http_err):
        result = dispatch_fabric("fabric_list_workspaces", {})
    assert "Erro Fabric API" in result


def test_dispatch_fabric_unknown_tool():
    result = dispatch_fabric("fabric_nonexistent", {})
    assert "não reconhecida" in result


# ---------------------------------------------------------------------------
# Token cache
# ---------------------------------------------------------------------------

def test_fabric_token_no_credentials():
    from agents.tools.fabric import _get_token
    with patch("agents.tools.fabric.settings") as mock_s:
        mock_s.azure_tenant_id = ""
        mock_s.azure_client_id = ""
        with pytest.raises(RuntimeError, match="AZURE_TENANT_ID"):
            _get_token()
