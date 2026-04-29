"""Tools Databricks para o loop agentico OpenAI — REST API v2.x/v3."""

from __future__ import annotations

import json
import logging

import requests

from config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.databricks_token}",
        "Content-Type": "application/json",
    }


def _url(path: str) -> str:
    return f"{settings.databricks_host.rstrip('/')}{path}"


def _get(path: str, params: dict | None = None) -> dict:
    resp = requests.get(_url(path), headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, payload: dict) -> dict:
    resp = requests.post(_url(path), headers=_headers(), json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Implementações
# ---------------------------------------------------------------------------

def _dbr_sql_execute(statement: str, catalog: str = "", schema: str = "") -> str:
    """Executa SQL no SQL Warehouse configurado."""
    wh_id = settings.databricks_sql_warehouse_id
    if not wh_id:
        return "DATABRICKS_SQL_WAREHOUSE_ID não configurado."
    catalog = catalog or settings.databricks_catalog
    schema = schema or settings.databricks_schema
    payload: dict = {
        "statement": statement,
        "warehouse_id": wh_id,
        "catalog": catalog,
        "schema": schema,
        "wait_timeout": "50s",
        "disposition": "INLINE",
        "format": "JSON_ARRAY",
    }
    data = _post("/api/2.0/sql/statements", payload)
    status = data.get("status", {}).get("state", "UNKNOWN")
    if status in ("SUCCEEDED",):
        result = data.get("result", {})
        cols = [c["name"] for c in result.get("schema", {}).get("columns", [])]
        rows = result.get("data_array", [])
        if not rows:
            return f"Query OK, 0 linhas. Colunas: {cols}"
        preview = rows[:50]
        return json.dumps(
            {"columns": cols, "rows": preview, "total_rows": len(rows)},
            ensure_ascii=False,
        )
    return f"Status: {status}. Detalhes: {json.dumps(data.get('status', {}))}"


def _dbr_list_catalogs() -> str:
    data = _get("/api/2.1/unity-catalog/catalogs")
    catalogs = [c["name"] for c in data.get("catalogs", [])]
    return json.dumps(catalogs)


def _dbr_list_schemas(catalog: str) -> str:
    data = _get("/api/2.1/unity-catalog/schemas", params={"catalog_name": catalog})
    schemas = [s["name"] for s in data.get("schemas", [])]
    return json.dumps(schemas)


def _dbr_list_tables(catalog: str, schema: str) -> str:
    data = _get(
        "/api/2.1/unity-catalog/tables",
        params={"catalog_name": catalog, "schema_name": schema, "max_results": 200},
    )
    tables = [
        {"name": t["name"], "type": t.get("table_type", ""), "full": t.get("full_name", "")}
        for t in data.get("tables", [])
    ]
    return json.dumps(tables)


def _dbr_get_table_schema(full_name: str) -> str:
    """full_name = catalog.schema.table"""
    data = _get(f"/api/2.1/unity-catalog/tables/{full_name}")
    cols = [
        {"name": c["name"], "type": c.get("type_text", ""), "nullable": c.get("nullable", True)}
        for c in data.get("columns", [])
    ]
    return json.dumps(
        {"table": full_name, "columns": cols, "properties": data.get("properties", {})}
    )


def _dbr_run_job(job_id: str, notebook_params: dict | None = None) -> str:
    payload: dict = {"job_id": int(job_id)}
    if notebook_params:
        payload["notebook_params"] = notebook_params
    data = _post("/api/2.1/jobs/run-now", payload)
    return json.dumps({"run_id": data.get("run_id"), "number_in_job": data.get("number_in_job")})


def _dbr_get_job_run_status(run_id: str) -> str:
    data = _get("/api/2.1/jobs/runs/get", params={"run_id": run_id, "include_history": False})
    state = data.get("state", {})
    return json.dumps({
        "run_id": run_id,
        "life_cycle_state": state.get("life_cycle_state"),
        "result_state": state.get("result_state"),
        "state_message": state.get("state_message"),
        "start_time": data.get("start_time"),
        "end_time": data.get("end_time"),
    })


def _dbr_list_jobs(name_contains: str = "") -> str:
    params: dict = {"limit": 50, "expand_tasks": False}
    if name_contains:
        params["name"] = name_contains
    data = _get("/api/2.1/jobs/list", params=params)
    jobs = [
        {"job_id": j["job_id"], "name": j.get("settings", {}).get("name", "")}
        for j in data.get("jobs", [])
    ]
    return json.dumps(jobs)


def _dbr_list_clusters() -> str:
    data = _get("/api/2.0/clusters/list")
    clusters = [
        {
            "cluster_id": c["cluster_id"],
            "cluster_name": c.get("cluster_name", ""),
            "state": c.get("state", ""),
        }
        for c in data.get("clusters", [])
    ]
    return json.dumps(clusters)


# ---------------------------------------------------------------------------
# OpenAI function schemas
# ---------------------------------------------------------------------------

DATABRICKS_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "dbr_sql_execute",
            "description": (
                "Executa uma query SQL no Databricks SQL Warehouse. "
                "Use para consultar tabelas Unity Catalog, explorar dados ou rodar DDL."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "statement": {"type": "string", "description": "SQL a executar"},
                    "catalog": {
                        "type": "string",
                        "description": "Catalog Unity Catalog (opcional, usa default se omitido)",
                    },
                    "schema": {"type": "string", "description": "Schema (opcional)"},
                },
                "required": ["statement"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_list_catalogs",
            "description": (
                "Lista todos os catalogs Unity Catalog disponíveis no workspace Databricks."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_list_schemas",
            "description": "Lista schemas dentro de um catalog Unity Catalog.",
            "parameters": {
                "type": "object",
                "properties": {"catalog": {"type": "string", "description": "Nome do catalog"}},
                "required": ["catalog"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_list_tables",
            "description": "Lista tabelas em um schema Unity Catalog.",
            "parameters": {
                "type": "object",
                "properties": {
                    "catalog": {"type": "string"},
                    "schema": {"type": "string"},
                },
                "required": ["catalog", "schema"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_get_table_schema",
            "description": (
                "Retorna colunas e tipos de uma tabela Unity Catalog "
                "pelo nome completo (catalog.schema.table)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name": {"type": "string", "description": "catalog.schema.table"},
                },
                "required": ["full_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_run_job",
            "description": "Dispara a execução de um Databricks Job pelo job_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "ID numérico do job"},
                    "notebook_params": {
                        "type": "object",
                        "description": "Parâmetros opcionais (key/value) para notebooks tasks",
                    },
                },
                "required": ["job_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_get_job_run_status",
            "description": "Consulta o status de uma execução de job pelo run_id.",
            "parameters": {
                "type": "object",
                "properties": {"run_id": {"type": "string", "description": "ID da execução"}},
                "required": ["run_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_list_jobs",
            "description": "Lista jobs do workspace Databricks, opcionalmente filtrando por nome.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name_contains": {
                        "type": "string",
                        "description": "Filtro parcial de nome (opcional)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_list_clusters",
            "description": "Lista clusters ativos e inativos do workspace Databricks.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_DISPATCH_MAP = {
    "dbr_sql_execute": lambda a: _dbr_sql_execute(
        a["statement"], a.get("catalog", ""), a.get("schema", "")
    ),
    "dbr_list_catalogs": lambda _: _dbr_list_catalogs(),
    "dbr_list_schemas": lambda a: _dbr_list_schemas(a["catalog"]),
    "dbr_list_tables": lambda a: _dbr_list_tables(a["catalog"], a["schema"]),
    "dbr_get_table_schema": lambda a: _dbr_get_table_schema(a["full_name"]),
    "dbr_run_job": lambda a: _dbr_run_job(a["job_id"], a.get("notebook_params")),
    "dbr_get_job_run_status": lambda a: _dbr_get_job_run_status(a["run_id"]),
    "dbr_list_jobs": lambda a: _dbr_list_jobs(a.get("name_contains", "")),
    "dbr_list_clusters": lambda _: _dbr_list_clusters(),
}


def dispatch_databricks(name: str, args: dict) -> str:
    fn = _DISPATCH_MAP.get(name)
    if fn is None:
        return f"Tool Databricks '{name}' não reconhecida."
    try:
        return fn(args)
    except requests.HTTPError as exc:
        logger.error(
            "Databricks API error [%s]: %s",
            name,
            exc.response.text if exc.response else exc,
        )
        return f"Erro Databricks API: {exc}"
    except Exception as exc:
        logger.error("Tool Databricks [%s] exception: %s", name, exc)
        return f"Erro ao executar {name}: {exc}"
