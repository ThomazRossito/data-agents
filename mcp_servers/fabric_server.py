#!/usr/bin/env python3
"""MCP Server Microsoft Fabric — expõe tools Fabric para VS Code Copilot via stdio."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP

from agents.tools.fabric import (
    _fabric_get_item,
    _fabric_get_job_instance,
    _fabric_get_lakehouse_tables,
    _fabric_list_items,
    _fabric_list_lakehouses,
    _fabric_list_pipelines,
    _fabric_list_workspaces,
    _fabric_run_notebook,
)

mcp = FastMCP("fabric")


@mcp.tool()
def fabric_list_workspaces() -> str:
    """Lista workspaces Microsoft Fabric disponíveis."""
    return _fabric_list_workspaces()


@mcp.tool()
def fabric_list_items(workspace_id: str, item_type: str = "") -> str:
    """Lista itens de um workspace Fabric (Lakehouse, Notebook, DataPipeline, etc.)."""
    return _fabric_list_items(workspace_id, item_type)


@mcp.tool()
def fabric_get_item(workspace_id: str, item_id: str) -> str:
    """Retorna detalhes de um item do workspace Fabric."""
    return _fabric_get_item(workspace_id, item_id)


@mcp.tool()
def fabric_list_lakehouses(workspace_id: str = "") -> str:
    """Lista Lakehouses de um workspace Fabric."""
    return _fabric_list_lakehouses(workspace_id)


@mcp.tool()
def fabric_get_lakehouse_tables(workspace_id: str, lakehouse_id: str) -> str:
    """Lista tabelas Delta/Parquet de um Lakehouse Fabric."""
    return _fabric_get_lakehouse_tables(workspace_id, lakehouse_id)


@mcp.tool()
def fabric_run_notebook(workspace_id: str, item_id: str, parameters: dict | None = None) -> str:
    """Executa um Notebook no Fabric e retorna o job instance ID."""
    return _fabric_run_notebook(workspace_id, item_id, parameters)


@mcp.tool()
def fabric_get_job_instance(workspace_id: str, item_id: str, job_instance_id: str) -> str:
    """Consulta status de um job instance (notebook run, pipeline run) no Fabric."""
    return _fabric_get_job_instance(workspace_id, item_id, job_instance_id)


@mcp.tool()
def fabric_list_pipelines(workspace_id: str) -> str:
    """Lista Data Pipelines de um workspace Fabric."""
    return _fabric_list_pipelines(workspace_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")
