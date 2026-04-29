#!/usr/bin/env python3
"""MCP Server Databricks — expõe tools Databricks para VS Code Copilot via stdio."""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que o projeto está no path quando executado pelo VS Code
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP

from agents.tools.databricks import (
    _dbr_get_job_run_status,
    _dbr_get_table_schema,
    _dbr_list_catalogs,
    _dbr_list_clusters,
    _dbr_list_jobs,
    _dbr_list_schemas,
    _dbr_list_tables,
    _dbr_run_job,
    _dbr_sql_execute,
)

mcp = FastMCP("databricks")


@mcp.tool()
def dbr_sql_execute(statement: str, catalog: str = "", schema: str = "") -> str:
    """Executa SQL no Databricks SQL Warehouse configurado."""
    return _dbr_sql_execute(statement, catalog, schema)


@mcp.tool()
def dbr_list_catalogs() -> str:
    """Lista catalogs Unity Catalog do workspace Databricks."""
    return _dbr_list_catalogs()


@mcp.tool()
def dbr_list_schemas(catalog: str) -> str:
    """Lista schemas de um catalog Unity Catalog."""
    return _dbr_list_schemas(catalog)


@mcp.tool()
def dbr_list_tables(catalog: str, schema: str) -> str:
    """Lista tabelas em catalog.schema."""
    return _dbr_list_tables(catalog, schema)


@mcp.tool()
def dbr_get_table_schema(full_name: str) -> str:
    """Retorna schema de catalog.schema.table."""
    return _dbr_get_table_schema(full_name)


@mcp.tool()
def dbr_run_job(job_id: str, notebook_params: dict | None = None) -> str:
    """Dispara execução de um Databricks Job."""
    return _dbr_run_job(job_id, notebook_params)


@mcp.tool()
def dbr_get_job_run_status(run_id: str) -> str:
    """Consulta status de uma execução de job."""
    return _dbr_get_job_run_status(run_id)


@mcp.tool()
def dbr_list_jobs(name_contains: str = "") -> str:
    """Lista jobs do workspace, opcionalmente filtrando por nome."""
    return _dbr_list_jobs(name_contains)


@mcp.tool()
def dbr_list_clusters() -> str:
    """Lista clusters do workspace Databricks."""
    return _dbr_list_clusters()


if __name__ == "__main__":
    mcp.run(transport="stdio")
