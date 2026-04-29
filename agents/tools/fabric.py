"""Tools Microsoft Fabric para o loop agentico OpenAI — REST API v1."""

from __future__ import annotations

import json
import logging
import time

import requests

from config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_TOKEN_CACHE: dict[str, tuple[str, float]] = {}
_FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
_POWERBI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"


def _get_token(scope: str = _FABRIC_SCOPE) -> str:
    """Obtém token OAuth2 via client_credentials. Cache por escopo."""
    cached = _TOKEN_CACHE.get(scope)
    if cached and time.monotonic() < cached[1]:
        return cached[0]
    tenant = settings.azure_tenant_id
    if not tenant or not settings.azure_client_id:
        raise RuntimeError("AZURE_TENANT_ID e AZURE_CLIENT_ID são obrigatórios para tools Fabric.")
    url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    resp = requests.post(url, data={
        "grant_type": "client_credentials",
        "client_id": settings.azure_client_id,
        "client_secret": settings.azure_client_secret,
        "scope": scope,
    }, timeout=15)
    resp.raise_for_status()
    token_data = resp.json()
    access_token = token_data["access_token"]
    expires_in = int(token_data.get("expires_in", 3600)) - 60
    _TOKEN_CACHE[scope] = (access_token, time.monotonic() + expires_in)
    return access_token


def _headers(scope: str = _FABRIC_SCOPE) -> dict[str, str]:
    return {"Authorization": f"Bearer {_get_token(scope)}", "Content-Type": "application/json"}


_FABRIC_BASE = "https://api.fabric.microsoft.com/v1"


def _get(path: str, params: dict | None = None) -> dict:
    resp = requests.get(f"{_FABRIC_BASE}{path}", headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, payload: dict) -> dict | None:
    resp = requests.post(f"{_FABRIC_BASE}{path}", headers=_headers(), json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json() if resp.content else None


# ---------------------------------------------------------------------------
# Implementações
# ---------------------------------------------------------------------------

def _fabric_list_workspaces() -> str:
    data = _get("/workspaces")
    ws = [{"id": w["id"], "displayName": w["displayName"]} for w in data.get("value", [])]
    return json.dumps(ws)


def _fabric_list_items(workspace_id: str, item_type: str = "") -> str:
    params = {}
    if item_type:
        params["type"] = item_type
    data = _get(f"/workspaces/{workspace_id}/items", params=params or None)
    items = [
        {"id": i["id"], "displayName": i["displayName"], "type": i["type"]}
        for i in data.get("value", [])
    ]
    return json.dumps(items)


def _fabric_get_item(workspace_id: str, item_id: str) -> str:
    data = _get(f"/workspaces/{workspace_id}/items/{item_id}")
    return json.dumps(data)


def _fabric_list_lakehouses(workspace_id: str) -> str:
    workspace_id = workspace_id or settings.fabric_workspace_id
    data = _get(f"/workspaces/{workspace_id}/lakehouses")
    lh = [{"id": lk["id"], "displayName": lk["displayName"]} for lk in data.get("value", [])]
    return json.dumps(lh)


def _fabric_get_lakehouse_tables(workspace_id: str, lakehouse_id: str) -> str:
    data = _get(f"/workspaces/{workspace_id}/lakehouses/{lakehouse_id}/tables")
    tables = [
        {"name": t["name"], "type": t.get("type", ""), "format": t.get("format", "")}
        for t in data.get("data", [])
    ]
    return json.dumps(tables)


def _fabric_run_notebook(workspace_id: str, item_id: str, parameters: dict | None = None) -> str:
    payload: dict = {}
    if parameters:
        payload["executionData"] = {"parameters": parameters}
    job_url = (
        f"/workspaces/{workspace_id}/items/{item_id}"
        "/jobs/instances?jobType=RunNotebook"
    )
    data = _post(job_url, payload or {})
    return json.dumps(data or {"status": "accepted"})


def _fabric_get_job_instance(workspace_id: str, item_id: str, job_instance_id: str) -> str:
    data = _get(f"/workspaces/{workspace_id}/items/{item_id}/jobs/instances/{job_instance_id}")
    return json.dumps({
        "id": data.get("id"),
        "status": data.get("status"),
        "startTimeUtc": data.get("startTimeUtc"),
        "endTimeUtc": data.get("endTimeUtc"),
        "failureReason": data.get("failureReason"),
    })


def _fabric_list_pipelines(workspace_id: str) -> str:
    return _fabric_list_items(workspace_id, "DataPipeline")


# ---------------------------------------------------------------------------
# OpenAI function schemas
# ---------------------------------------------------------------------------

FABRIC_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "fabric_list_workspaces",
            "description": (
                "Lista todos os workspaces Microsoft Fabric disponíveis "
                "para a service principal configurada."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fabric_list_items",
            "description": (
                "Lista itens de um workspace Fabric. Pode filtrar por tipo: "
                "Lakehouse, Notebook, DataPipeline, Warehouse, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {"type": "string", "description": "ID do workspace Fabric"},
                    "item_type": {
                        "type": "string",
                        "description": "Tipo do item para filtrar (opcional)",
                    },
                },
                "required": ["workspace_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fabric_get_item",
            "description": "Retorna detalhes de um item específico de um workspace Fabric.",
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {"type": "string"},
                    "item_id": {"type": "string"},
                },
                "required": ["workspace_id", "item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fabric_list_lakehouses",
            "description": "Lista Lakehouses de um workspace Fabric com seus IDs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {
                        "type": "string",
                        "description": "ID do workspace (opcional, usa default)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fabric_get_lakehouse_tables",
            "description": "Lista tabelas Delta/Parquet de um Lakehouse Fabric.",
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {"type": "string"},
                    "lakehouse_id": {"type": "string"},
                },
                "required": ["workspace_id", "lakehouse_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fabric_run_notebook",
            "description": (
                "Executa um Notebook no Fabric via job on-demand e retorna o job instance ID."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {"type": "string"},
                    "item_id": {"type": "string", "description": "ID do notebook no Fabric"},
                    "parameters": {
                        "type": "object",
                        "description": "Parâmetros para o notebook (opcional)",
                    },
                },
                "required": ["workspace_id", "item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fabric_get_job_instance",
            "description": (
                "Consulta o status de um job instance (notebook run, pipeline run) no Fabric."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {"type": "string"},
                    "item_id": {"type": "string"},
                    "job_instance_id": {"type": "string"},
                },
                "required": ["workspace_id", "item_id", "job_instance_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fabric_list_pipelines",
            "description": "Lista Data Pipelines de um workspace Fabric.",
            "parameters": {
                "type": "object",
                "properties": {"workspace_id": {"type": "string"}},
                "required": ["workspace_id"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_DISPATCH_MAP = {
    "fabric_list_workspaces": lambda _: _fabric_list_workspaces(),
    "fabric_list_items": lambda a: _fabric_list_items(a["workspace_id"], a.get("item_type", "")),
    "fabric_get_item": lambda a: _fabric_get_item(a["workspace_id"], a["item_id"]),
    "fabric_list_lakehouses": lambda a: _fabric_list_lakehouses(a.get("workspace_id", "")),
    "fabric_get_lakehouse_tables": lambda a: _fabric_get_lakehouse_tables(
        a["workspace_id"], a["lakehouse_id"]
    ),
    "fabric_run_notebook": lambda a: _fabric_run_notebook(
        a["workspace_id"], a["item_id"], a.get("parameters")
    ),
    "fabric_get_job_instance": lambda a: _fabric_get_job_instance(
        a["workspace_id"], a["item_id"], a["job_instance_id"]
    ),
    "fabric_list_pipelines": lambda a: _fabric_list_pipelines(a["workspace_id"]),
}


def dispatch_fabric(name: str, args: dict) -> str:
    fn = _DISPATCH_MAP.get(name)
    if fn is None:
        return f"Tool Fabric '{name}' não reconhecida."
    try:
        return fn(args)
    except requests.HTTPError as exc:
        logger.error("Fabric API error [%s]: %s", name, exc.response.text if exc.response else exc)
        return f"Erro Fabric API: {exc}"
    except Exception as exc:
        logger.error("Tool Fabric [%s] exception: %s", name, exc)
        return f"Erro ao executar {name}: {exc}"
