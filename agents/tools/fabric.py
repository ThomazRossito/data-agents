"""Tools Microsoft Fabric para o loop agentico OpenAI — REST API v1."""

from __future__ import annotations

import base64
import json
import logging
import re
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
    """Obtém token OAuth2. Suporta sp (client_credentials) e interactive (DefaultAzureCredential)."""
    cached = _TOKEN_CACHE.get(scope)
    if cached and time.monotonic() < cached[1]:
        return cached[0]

    auth_mode = getattr(settings, "fabric_auth_mode", "sp").lower()

    if auth_mode == "interactive":
        from azure.identity import AzureCliCredential
        tenant_id = settings.azure_tenant_id or None
        credential = AzureCliCredential(tenant_id=tenant_id)
        token_obj = credential.get_token(scope)
        access_token = token_obj.token
        expires_in = max(int(token_obj.expires_on) - int(time.time()) - 60, 60)
        _TOKEN_CACHE[scope] = (access_token, time.monotonic() + expires_in)
        return access_token

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
_ONELAKE_BASE = "https://onelake.dfs.fabric.microsoft.com"
_ONELAKE_SCOPE = "https://storage.azure.com/.default"


def _get(path: str, params: dict | None = None) -> dict:
    resp = requests.get(f"{_FABRIC_BASE}{path}", headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, payload: dict) -> dict | None:
    resp = requests.post(f"{_FABRIC_BASE}{path}", headers=_headers(), json=payload, timeout=60)
    resp.raise_for_status()
    if resp.content:
        return resp.json()
    # Jobs assíncronos retornam 202 com ID no header Location
    location = resp.headers.get("Location", "")
    if location:
        job_instance_id = location.rstrip("/").split("/")[-1]
        return {"status": "accepted", "job_instance_id": job_instance_id, "location": location}
    return None


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


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def _resolve_lakehouse_id(workspace_id: str, lakehouse_id_or_name: str) -> str:
    """Aceita UUID ou nome de exibição (ex: 'dev_lakehouse') e retorna sempre o UUID.

    Se já for UUID, retorna imediatamente sem chamada extra.
    Se for nome, busca via fabric_list_lakehouses no workspace informado.
    """
    if _UUID_RE.match(lakehouse_id_or_name):
        return lakehouse_id_or_name
    workspace_id = workspace_id or settings.fabric_workspace_id
    lakehouses = json.loads(_fabric_list_lakehouses(workspace_id))
    for lh in lakehouses:
        if lh.get("displayName", "").lower() == lakehouse_id_or_name.lower():
            return lh["id"]
    raise ValueError(
        f"Lakehouse '{lakehouse_id_or_name}' não encontrado no workspace {workspace_id}. "
        f"Disponíveis: {[l['displayName'] for l in lakehouses]}"
    )


def _fabric_get_lakehouse_tables(workspace_id: str, lakehouse_id: str) -> str:
    try:
        data = _get(f"/workspaces/{workspace_id}/lakehouses/{lakehouse_id}/tables")
        tables = [
            {"name": t["name"], "type": t.get("type", ""), "format": t.get("format", "")}
            for t in data.get("data", [])
        ]
        return json.dumps(tables)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 400:
            return json.dumps({"error": "SQL Endpoint ainda não provisionado ou sem tabelas Delta registradas no lakehouse."})
        raise


def _fabric_run_notebook(
    workspace_id: str,
    item_id: str,
    parameters: dict | None = None,
    wait_for_completion: bool = False,
    timeout_seconds: int = 600,
) -> str:
    payload: dict = {}
    if parameters:
        payload["executionData"] = {"parameters": parameters}
    job_url = (
        f"/workspaces/{workspace_id}/items/{item_id}"
        "/jobs/instances?jobType=RunNotebook"
    )
    data = _post(job_url, payload or {})
    job_instance_id = (data or {}).get("job_instance_id")

    if not wait_for_completion or not job_instance_id:
        return json.dumps(data or {"status": "accepted"})

    # Polling interno — evita gastar turns do LLM em cada verificação de status
    poll_interval = 10
    elapsed = 0
    while elapsed < timeout_seconds:
        time.sleep(poll_interval)
        elapsed += poll_interval
        try:
            status_data = _get(
                f"/workspaces/{workspace_id}/items/{item_id}/jobs/instances/{job_instance_id}"
            )
        except requests.HTTPError:
            break
        status = status_data.get("status", "")
        if status in ("Succeeded", "Failed", "Cancelled", "Deduped"):
            return json.dumps({
                "notebook_id": item_id,
                "job_instance_id": job_instance_id,
                "status": status,
                "duration_seconds": elapsed,
                "failureReason": status_data.get("failureReason"),
            })
    return json.dumps({
        "notebook_id": item_id,
        "job_instance_id": job_instance_id,
        "status": "Timeout",
        "duration_seconds": elapsed,
    })


def _fabric_write_onelake_file(
    workspace_id: str,
    lakehouse_id: str,
    path: str,
    content: str,
) -> str:
    """Faz upload de um arquivo de texto para OneLake Files via ADLS Gen2 API.

    path deve ser relativo ao lakehouse, ex: 'Files/src/utils/framework.py'
    """
    workspace_id = workspace_id or settings.fabric_workspace_id
    lakehouse_id = _resolve_lakehouse_id(workspace_id, lakehouse_id)
    token = _get_token(_ONELAKE_SCOPE)
    hdrs = {"Authorization": f"Bearer {token}"}
    base = f"{_ONELAKE_BASE}/{workspace_id}/{lakehouse_id}"
    path = path.lstrip("/")

    # 1. Create (allocate) — comprimento exacto necessário
    encoded = content.encode("utf-8")
    create_url = f"{base}/{path}?resource=file&overwrite=true"
    r = requests.put(create_url, headers=hdrs, timeout=30)
    if r.status_code not in (200, 201):
        return json.dumps({"error": f"Create falhou: HTTP {r.status_code} — {r.text[:200]}"})

    # 2. Append — envia o conteúdo em posição 0
    append_url = f"{base}/{path}?action=append&position=0"
    r = requests.patch(append_url, headers={**hdrs, "Content-Type": "application/octet-stream"}, data=encoded, timeout=60)
    if r.status_code not in (200, 202):
        return json.dumps({"error": f"Append falhou: HTTP {r.status_code} — {r.text[:200]}"})

    # 3. Flush — confirma escrita
    flush_url = f"{base}/{path}?action=flush&position={len(encoded)}"
    r = requests.patch(flush_url, headers=hdrs, timeout=30)
    if r.status_code not in (200, 202):
        return json.dumps({"error": f"Flush falhou: HTTP {r.status_code} — {r.text[:200]}"})

    return json.dumps({"uploaded": path, "bytes": len(encoded)})


def _fabric_get_job_instance(workspace_id: str, item_id: str, job_instance_id: str) -> str:
    try:
        data = _get(f"/workspaces/{workspace_id}/items/{item_id}/jobs/instances/{job_instance_id}")
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 400:
            return json.dumps({
                "error": "400 Bad Request — item_id inválido para este endpoint. "
                "Este endpoint só funciona para itens executáveis (Notebook, DataPipeline, "
                "SparkJobDefinition). Não use lakehouse_id aqui.",
            })
        raise
    return json.dumps({
        "id": data.get("id"),
        "status": data.get("status"),
        "startTimeUtc": data.get("startTimeUtc"),
        "endTimeUtc": data.get("endTimeUtc"),
        "failureReason": data.get("failureReason"),
    })


def _fabric_list_onelake_files(
    workspace_id: str,
    lakehouse_id: str,
    path: str = "Files",
    recursive: bool = False,
) -> str:
    """Lista arquivos/pastas na seção Files de um Lakehouse via OneLake ADLS Gen2 API.

    path: caminho relativo dentro do lakehouse (ex: "Files", "Files/raw", "Files/raw/contas").
    """
    workspace_id = workspace_id or settings.fabric_workspace_id
    lakehouse_id = _resolve_lakehouse_id(workspace_id, lakehouse_id)
    # OneLake ADLS Gen2: workspace = filesystem, item/path = directory
    directory = f"{lakehouse_id}/{path}"
    url = f"{_ONELAKE_BASE}/{workspace_id}"
    params = {
        "resource": "filesystem",
        "directory": directory,
        "recursive": str(recursive).lower(),
    }
    token = _get_token(_ONELAKE_SCOPE)
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    if resp.status_code == 404:
        return json.dumps({"paths": [], "note": f"Caminho '{path}' não encontrado no lakehouse."})
    resp.raise_for_status()
    body = resp.json()
    paths = body.get("paths", [])
    result = [
        {
            "name": p.get("name", "").split("/")[-1],
            "full_path": p.get("name", ""),
            "isDirectory": p.get("isDirectory") in (True, "true"),
            "contentLength": p.get("contentLength"),
            "lastModified": p.get("lastModified"),
        }
        for p in paths
    ]
    return json.dumps(result)


def _fabric_read_onelake_file(
    workspace_id: str,
    lakehouse_id: str,
    path: str,
    max_bytes: int = 16384,
) -> str:
    """Lê o conteúdo de um arquivo no OneLake via ADLS Gen2 API.

    path: caminho relativo ao lakehouse, ex: 'Tables/bronze/brz_clientes/_delta_log/00000000000000000000.json'
    max_bytes: limite de leitura (default 16KB). Use 0 para ler o arquivo completo (cuidado com arquivos grandes).
    """
    workspace_id = workspace_id or settings.fabric_workspace_id
    lakehouse_id = _resolve_lakehouse_id(workspace_id, lakehouse_id)
    token = _get_token(_ONELAKE_SCOPE)
    headers: dict = {"Authorization": f"Bearer {token}"}
    if max_bytes > 0:
        headers["Range"] = f"bytes=0-{max_bytes - 1}"
    url = f"{_ONELAKE_BASE}/{workspace_id}/{lakehouse_id}/{path}"
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code == 404:
        return json.dumps({"error": f"Arquivo não encontrado: {path}"})
    resp.raise_for_status()
    return json.dumps({"path": path, "content": resp.text, "truncated": max_bytes > 0})


def _fabric_list_pipelines(workspace_id: str) -> str:
    return _fabric_list_items(workspace_id, "DataPipeline")


def _fabric_get_notebook_definition(workspace_id: str, notebook_id: str) -> str:
    """Retorna o conteúdo (.ipynb) de um notebook existente no Fabric.

    Usa format=ipynb obrigatoriamente.
    Trata 200 (inline) e 202 (async com polling via operationId).
    """
    import base64 as _b64

    workspace_id = workspace_id or settings.fabric_workspace_id
    token = _get_token(_FABRIC_SCOPE)
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    # format=ipynb é obrigatório para obter o conteúdo .ipynb
    url = f"{_FABRIC_BASE}/workspaces/{workspace_id}/notebooks/{notebook_id}/getDefinition?format=ipynb"

    resp = requests.post(url, headers=hdrs, json={}, timeout=60)

    if resp.status_code == 200:
        data = resp.json()
    elif resp.status_code == 202:
        location = resp.headers.get("Location") or resp.headers.get("location")
        if not location:
            return json.dumps({"error": "202 sem Location header"})
        # Polling — Fabric retorna status da operação até Succeeded, depois dados em resourceLocation
        data = None
        for _ in range(30):
            time.sleep(3)
            poll = requests.get(location, headers=hdrs, timeout=30)
            if poll.status_code not in (200, 202):
                return json.dumps({"error": f"Polling falhou: HTTP {poll.status_code} — {poll.text[:200]}"})
            poll_data = poll.json()
            op_status = poll_data.get("status", "")
            if op_status == "Succeeded":
                # 1. Tenta resourceLocation (algumas APIs retornam isso)
                resource_location = poll_data.get("resourceLocation")
                if resource_location:
                    final = requests.get(resource_location, headers=hdrs, timeout=30)
                    final.raise_for_status()
                    data = final.json()
                else:
                    # 2. Padrão Fabric LRO: GET {operationUrl}/result
                    result_url = location.rstrip("/") + "/result"
                    final = requests.get(result_url, headers=hdrs, timeout=30)
                    if final.status_code == 200:
                        data = final.json()
                    else:
                        # 3. Fallback: dados inline no corpo da poll
                        data = poll_data
                break
            elif op_status == "Failed":
                return json.dumps({"error": f"Operação falhou: {poll_data.get('error', poll_data)}"})
            # InProgress / NotStarted — continua polling
        if data is None:
            return json.dumps({"error": "Timeout aguardando getDefinition (90s)"})
    else:
        return json.dumps({"error": f"HTTP {resp.status_code} — {resp.text[:300]}"})

    parts = (data.get("definition") or {}).get("parts", [])
    for part in parts:
        if part.get("path", "").endswith(".ipynb"):
            try:
                content = _b64.b64decode(part["payload"]).decode("utf-8")
                return json.dumps({"notebook_id": notebook_id, "ipynb_content": content})
            except Exception as exc:
                return json.dumps({"error": f"Falha ao decodificar payload: {exc}"})
    return json.dumps({"error": "Nenhuma parte .ipynb encontrada", "raw": str(data)[:500]})


def _fabric_delete_item(workspace_id: str, item_id: str) -> str:
    """Deleta um item (notebook, pasta, etc.) do workspace Fabric."""
    workspace_id = workspace_id or settings.fabric_workspace_id
    url = f"{_FABRIC_BASE}/workspaces/{workspace_id}/items/{item_id}"
    token = _get_token(_FABRIC_SCOPE)
    resp = requests.delete(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if resp.status_code in (200, 204):
        return json.dumps({"deleted": item_id})
    return json.dumps({"error": f"HTTP {resp.status_code}", "detail": resp.text[:300]})


def _fabric_update_notebook_definition(
    workspace_id: str,
    notebook_id: str,
    ipynb_content: str = "",
    cells: list[dict] | None = None,
    default_lakehouse_id: str = "",
    default_lakehouse_name: str = "",
) -> str:
    """Atualiza o conteúdo de um notebook existente sem deletar/recriar.

    Aceita ipynb_content (JSON .ipynb) ou cells (lista de {cell_type, source}).
    default_lakehouse_id: injeta metadado trident para que spark.table() funcione no Fabric.
    """
    workspace_id = workspace_id or settings.fabric_workspace_id
    if not ipynb_content and cells:
        ipynb_content = _build_ipynb(
            cells,
            default_lakehouse_id=default_lakehouse_id,
            default_lakehouse_name=default_lakehouse_name,
            workspace_id=workspace_id,
        )
    elif ipynb_content and default_lakehouse_id:
        # Injeta trident no ipynb existente
        try:
            nb = json.loads(ipynb_content)
            nb.setdefault("metadata", {})["trident"] = {
                "lakehouse": {
                    "default_lakehouse": default_lakehouse_id,
                    "default_lakehouse_name": default_lakehouse_name or default_lakehouse_id,
                    "default_lakehouse_workspace_id": workspace_id or settings.fabric_workspace_id,
                    "known_lakehouses": [{"id": default_lakehouse_id}],
                }
            }
            ipynb_content = json.dumps(nb, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            pass
    if not ipynb_content:
        return json.dumps({"error": "Forneça ipynb_content ou cells"})

    encoded = base64.b64encode(ipynb_content.encode()).decode()
    payload = {
        "definition": {
            "format": "ipynb",
            "parts": [{"path": "notebook-content.ipynb", "payload": encoded, "payloadType": "InlineBase64"}],
        }
    }
    token = _get_token(_FABRIC_SCOPE)
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{_FABRIC_BASE}/workspaces/{workspace_id}/notebooks/{notebook_id}/updateDefinition"
    resp = requests.post(url, headers=hdrs, json=payload, timeout=60)
    if resp.status_code == 200:
        return json.dumps({"updated": notebook_id})
    if resp.status_code == 202:
        location = resp.headers.get("Location") or resp.headers.get("location")
        if location:
            for _ in range(20):
                time.sleep(3)
                poll = requests.get(location, headers=hdrs, timeout=30)
                poll_data = poll.json()
                if poll_data.get("status") == "Succeeded":
                    return json.dumps({"updated": notebook_id})
                if poll_data.get("status") == "Failed":
                    return json.dumps({"error": f"updateDefinition falhou: {poll_data.get('error', poll_data)}"})
        return json.dumps({"updated": notebook_id, "note": "202 aceito"})
    return json.dumps({"error": f"HTTP {resp.status_code}", "detail": resp.text[:300]})


def _fabric_find_or_create_folder(workspace_id: str, folder_path: str) -> str:
    """Garante que o caminho de pasta existe no workspace via endpoint /folders.

    folder_path pode ser 'src/utils' ou 'src/bronze' etc.
    Retorna o folder_id da pasta folha.
    """
    workspace_id = workspace_id or settings.fabric_workspace_id
    segments = [s for s in folder_path.strip("/").split("/") if s]
    if not segments:
        return json.dumps({"error": "folder_path vazio"})

    token = _get_token(_FABRIC_SCOPE)
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Lista pastas existentes via /folders
    list_resp = requests.get(
        f"{_FABRIC_BASE}/workspaces/{workspace_id}/folders",
        headers=hdrs,
        timeout=30,
    )
    if list_resp.status_code == 404:
        # Workspace folders não suportado neste workspace/tier
        return json.dumps({"error": "Workspace folders não suportado via API neste workspace. Use naming convention no displayName."})
    list_resp.raise_for_status()
    existing_folders = list_resp.json().get("value", [])

    parent_id: str | None = None
    for segment in segments:
        match = next(
            (f for f in existing_folders
             if f.get("displayName") == segment and f.get("parentFolderId") == parent_id),
            None,
        )
        if match:
            parent_id = match["id"]
        else:
            payload: dict = {"displayName": segment}
            if parent_id:
                payload["parentFolderId"] = parent_id
            create_resp = requests.post(
                f"{_FABRIC_BASE}/workspaces/{workspace_id}/folders",
                headers=hdrs,
                json=payload,
                timeout=30,
            )
            if create_resp.status_code == 404:
                return json.dumps({"error": "Endpoint /folders não disponível. Use naming convention no displayName."})
            create_resp.raise_for_status()
            folder_data = create_resp.json()
            parent_id = folder_data.get("id")
            existing_folders.append({**folder_data, "parentFolderId": payload.get("parentFolderId")})

    return json.dumps({"folder_id": parent_id, "folder_path": folder_path})


def _build_ipynb(
    cells: list[dict],
    default_lakehouse_id: str = "",
    default_lakehouse_name: str = "",
    workspace_id: str = "",
) -> str:
    """Constrói string JSON .ipynb a partir de lista de células {cell_type, source}.

    Quando default_lakehouse_id é fornecido, adiciona metadado `trident` para que o
    Spark session resolva spark.table() e saveAsTable() sem contexto explícito de catalog.
    """
    nb_cells = []
    for c in cells:
        cell_type = c.get("cell_type", "code")
        source = c.get("source", "")
        if isinstance(source, str):
            source_lines = [l + "\n" for l in source.splitlines()]
            if source_lines:
                source_lines[-1] = source_lines[-1].rstrip("\n")
        else:
            source_lines = source
        cell: dict = {
            "cell_type": cell_type,
            "metadata": {},
            "source": source_lines,
        }
        if cell_type == "code":
            cell["outputs"] = []
            cell["execution_count"] = None
        else:
            cell["attachments"] = {}
        nb_cells.append(cell)

    metadata: dict = {
        "kernelspec": {"display_name": "PySpark", "language": "python", "name": "synapse_pyspark"},
        "language_info": {"name": "python"},
    }
    if default_lakehouse_id:
        metadata["trident"] = {
            "lakehouse": {
                "default_lakehouse": default_lakehouse_id,
                "default_lakehouse_name": default_lakehouse_name or default_lakehouse_id,
                "default_lakehouse_workspace_id": workspace_id or settings.fabric_workspace_id,
                "known_lakehouses": [{"id": default_lakehouse_id}],
            }
        }

    nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": metadata,
        "cells": nb_cells,
    }
    return json.dumps(nb, ensure_ascii=False)


def _fabric_create_notebook(
    workspace_id: str,
    display_name: str,
    ipynb_content: str = "",
    cells: list[dict] | None = None,
    folder_path: str = "",
    default_lakehouse_id: str = "",
    default_lakehouse_name: str = "",
) -> str:
    """Cria um Notebook no Fabric.

    Aceita ipynb_content (JSON .ipynb completo) OU cells (lista de {cell_type, source}).
    folder_path organiza o notebook em pastas do workspace (ex: 'src/utils', 'src/bronze').
    default_lakehouse_id/name: configura metadado trident para que spark.table() funcione.
    """
    workspace_id = workspace_id or settings.fabric_workspace_id
    if not ipynb_content and cells:
        ipynb_content = _build_ipynb(
            cells,
            default_lakehouse_id=default_lakehouse_id,
            default_lakehouse_name=default_lakehouse_name,
            workspace_id=workspace_id,
        )
    if not ipynb_content:
        return json.dumps({"error": "Forneça ipynb_content (JSON .ipynb) ou cells (lista de células)"})

    folder_id: str | None = None
    if folder_path:
        folder_result = json.loads(_fabric_find_or_create_folder(workspace_id, folder_path))
        if "error" in folder_result:
            return json.dumps({"error": f"Falha ao criar pasta '{folder_path}': {folder_result['error']}"})
        folder_id = folder_result.get("folder_id")

    encoded = base64.b64encode(ipynb_content.encode()).decode()
    payload: dict = {
        "displayName": display_name,
        "definition": {
            "format": "ipynb",
            "parts": [
                {
                    "path": "notebook-content.ipynb",
                    "payload": encoded,
                    "payloadType": "InlineBase64",
                }
            ],
        },
    }
    if folder_id:
        payload["folderId"] = folder_id

    # Usa POST direto para capturar o notebook_id do header Location (API retorna 201 com body vazio)
    token = _get_token(_FABRIC_SCOPE)
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{_FABRIC_BASE}/workspaces/{workspace_id}/notebooks"

    try:
        resp = requests.post(url, headers=hdrs, json=payload, timeout=60)
        resp.raise_for_status()
    except requests.HTTPError as exc:
        # Se 409 Conflict, notebook já existe — delete e recria
        if exc.response is not None and exc.response.status_code == 409:
            try:
                # Tenta listar notebooks para encontrar o existente
                items_resp = requests.get(
                    f"{_FABRIC_BASE}/workspaces/{workspace_id}/items",
                    headers=hdrs,
                    params={"type": "Notebook"},
                    timeout=30,
                )
                items_resp.raise_for_status()
                items = items_resp.json().get("value", [])
                existing = next(
                    (i for i in items if i.get("displayName") == display_name),
                    None,
                )
                if existing:
                    # Delete existente
                    del_resp = requests.delete(
                        f"{_FABRIC_BASE}/workspaces/{workspace_id}/items/{existing['id']}",
                        headers=hdrs,
                        timeout=30,
                    )
                    del_resp.raise_for_status()
                    logger.info("Notebook '%s' deletado (409 conflict)", display_name)
                    # Retenta POST
                    resp = requests.post(url, headers=hdrs, json=payload, timeout=60)
                    resp.raise_for_status()
                else:
                    raise exc
            except Exception:
                raise exc
        else:
            raise exc

    notebook_id: str | None = None
    if resp.content:
        try:
            body = resp.json()
            if isinstance(body, dict):
                notebook_id = body.get("id")
        except (json.JSONDecodeError, ValueError):
            pass
    if not notebook_id:
        location = resp.headers.get("Location", "")
        if location:
            notebook_id = location.rstrip("/").split("/")[-1]

    return json.dumps({
        "notebook_id": notebook_id,
        "display_name": display_name,
        "status": "created",
        "folder_path": folder_path,
    })


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
                "Executa um Notebook no Fabric. "
                "Use wait_for_completion=true para aguardar o resultado dentro da tool (recomendado quando executando múltiplos notebooks em sequência — evita polls manuais)."
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
                    "wait_for_completion": {
                        "type": "boolean",
                        "description": "Se true, aguarda o fim da execução e retorna o status final. Padrão: false.",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Timeout em segundos para aguardar (padrão: 600).",
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
            "name": "fabric_get_notebook_definition",
            "description": "Retorna o conteúdo ipynb de um notebook existente no Fabric. Use para ler um notebook antes de recriar em outra pasta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {"type": "string", "description": "ID do workspace (opcional)"},
                    "notebook_id": {"type": "string", "description": "ID do notebook no Fabric"},
                },
                "required": ["notebook_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fabric_delete_item",
            "description": "Deleta um item (notebook, pasta, etc.) do workspace Fabric. Use após recriar o notebook na pasta correta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {"type": "string", "description": "ID do workspace (opcional)"},
                    "item_id": {"type": "string", "description": "ID do item a deletar"},
                },
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fabric_find_or_create_folder",
            "description": (
                "Cria ou localiza uma pasta (ou hierarquia de pastas) no workspace Fabric. "
                "Use ANTES de fabric_create_notebook quando precisar organizar notebooks em pastas. "
                "Retorna o folder_id que deve ser passado para fabric_create_notebook."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {
                        "type": "string",
                        "description": "ID do workspace (opcional)",
                    },
                    "folder_path": {
                        "type": "string",
                        "description": "Caminho da pasta, ex: 'src/utils' ou 'src/bronze'",
                    },
                },
                "required": ["folder_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fabric_create_notebook",
            "description": (
                "Cria um Notebook Item no Microsoft Fabric. "
                "OBRIGATÓRIO: sempre passar default_lakehouse_id (UUID do lakehouse) e default_lakehouse_name — "
                "sem eles o spark.table() falha pois o Spark session não tem contexto de lakehouse. "
                "Use 'cells' com o código Python. "
                "O campo notebook_id no retorno é o ID a usar em fabric_run_notebook."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {
                        "type": "string",
                        "description": "ID do workspace (opcional)",
                    },
                    "display_name": {
                        "type": "string",
                        "description": "Nome do notebook (sem barras — use folder_path para pastas)",
                    },
                    "default_lakehouse_id": {
                        "type": "string",
                        "description": "UUID do lakehouse padrão. OBRIGATÓRIO para que spark.table() resolva corretamente. Ex: 'bccadc52-6f73-4d80-97a0-74a64933a1ab'",
                    },
                    "default_lakehouse_name": {
                        "type": "string",
                        "description": "Nome de exibição do lakehouse padrão. Ex: 'dev_lakehouse'",
                    },
                    "folder_path": {
                        "type": "string",
                        "description": "Pasta destino no workspace, ex: 'src/utils' ou 'src/bronze'. A pasta é criada automaticamente se não existir.",
                    },
                    "cells": {
                        "type": "array",
                        "description": "Lista de células: [{\"cell_type\": \"code\"|\"markdown\", \"source\": \"<código>\"}]",
                        "items": {
                            "type": "object",
                            "properties": {
                                "cell_type": {"type": "string", "enum": ["code", "markdown"]},
                                "source": {"type": "string"},
                            },
                            "required": ["cell_type", "source"],
                        },
                    },
                    "ipynb_content": {
                        "type": "string",
                        "description": "JSON .ipynb completo (alternativa a cells)",
                    },
                },
                "required": ["display_name", "default_lakehouse_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fabric_update_notebook_definition",
            "description": (
                "Atualiza o conteúdo de um notebook existente no Fabric sem deletar/recriar. "
                "Use quando o notebook já existe e você quer corrigir código ou injetar o default_lakehouse_id. "
                "Sempre passar default_lakehouse_id para garantir que spark.table() funcione na execução."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {"type": "string", "description": "ID do workspace (opcional)"},
                    "notebook_id": {"type": "string", "description": "ID do notebook a atualizar"},
                    "default_lakehouse_id": {
                        "type": "string",
                        "description": "UUID do lakehouse padrão — injeta metadado trident. Ex: 'bccadc52-6f73-4d80-97a0-74a64933a1ab'",
                    },
                    "default_lakehouse_name": {
                        "type": "string",
                        "description": "Nome do lakehouse. Ex: 'dev_lakehouse'",
                    },
                    "ipynb_content": {
                        "type": "string",
                        "description": "JSON .ipynb completo com o novo conteúdo",
                    },
                    "cells": {
                        "type": "array",
                        "description": "Lista de células: [{\"cell_type\": \"code\"|\"markdown\", \"source\": \"<código>\"}]",
                        "items": {
                            "type": "object",
                            "properties": {
                                "cell_type": {"type": "string"},
                                "source": {"type": "string"},
                            },
                        },
                    },
                },
                "required": ["notebook_id"],
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
    {
        "type": "function",
        "function": {
            "name": "fabric_write_onelake_file",
            "description": (
                "Faz upload de um arquivo de texto (Python, SQL, JSON, Notebook .py, etc.) para OneLake Files "
                "via ADLS Gen2 API. "
                "Convenção de paths: notebooks Bronze em 'Files/src/bronze/', Silver em 'Files/src/silver/', "
                "utilitários em 'Files/src/utils/'. "
                "lakehouse_id aceita UUID ou nome (ex: 'dev_lakehouse') — o nome é resolvido automaticamente."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {"type": "string", "description": "ID do workspace (opcional)"},
                    "lakehouse_id": {
                        "type": "string",
                        "description": "UUID ou nome do Lakehouse (ex: 'dev_lakehouse' ou 'bccadc52-...')",
                    },
                    "path": {
                        "type": "string",
                        "description": (
                            "Caminho relativo ao lakehouse. "
                            "Notebooks Silver: 'Files/src/silver/slv_<entidade>.py'. "
                            "Notebooks Bronze: 'Files/src/bronze/brz_<entidade>.py'."
                        ),
                    },
                    "content": {"type": "string", "description": "Conteúdo do arquivo"},
                },
                "required": ["lakehouse_id", "path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fabric_read_onelake_file",
            "description": (
                "Lê o conteúdo de um arquivo no OneLake (ADLS Gen2). "
                "Use para: (1) ler delta logs para inferir schema — path='Tables/<schema>/<tabela>/_delta_log/00000000000000000000.json', "
                "o campo metaData.schemaString contém colunas e tipos; "
                "(2) ler notebooks Bronze existentes em 'Files/src/bronze/' antes de criar versões Silver; "
                "(3) ler qualquer arquivo JSON/CSV/TXT no lakehouse. "
                "max_bytes=16384 é suficiente para schemas. Use 0 para arquivo completo (notebooks). "
                "lakehouse_id aceita UUID ou nome (ex: 'dev_lakehouse')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {"type": "string", "description": "ID do workspace (opcional)"},
                    "lakehouse_id": {
                        "type": "string",
                        "description": "UUID ou nome do Lakehouse (ex: 'dev_lakehouse')",
                    },
                    "path": {
                        "type": "string",
                        "description": (
                            "Caminho relativo ao lakehouse. "
                            "Delta log: 'Tables/bronze/brz_clientes/_delta_log/00000000000000000000.json'. "
                            "Notebook Bronze: 'Files/src/bronze/brz_clientes.py'."
                        ),
                    },
                    "max_bytes": {
                        "type": "integer",
                        "description": "Máximo de bytes a ler (default 16384). Use 0 para arquivo completo.",
                    },
                },
                "required": ["lakehouse_id", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fabric_list_onelake_files",
            "description": (
                "Lista arquivos e pastas em um Lakehouse via OneLake ADLS Gen2 API. "
                "NÃO use fabric_run_notebook para listar arquivos — use esta tool. "
                "Para ver notebooks Bronze existentes: path='Files/src/bronze', recursive=true. "
                "Para ver notebooks Silver: path='Files/src/silver'. "
                "Para ver tabelas Delta: path='Tables'. "
                "lakehouse_id aceita UUID ou nome (ex: 'dev_lakehouse') — resolvido automaticamente."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {
                        "type": "string",
                        "description": "ID do workspace (opcional, usa FABRIC_WORKSPACE_ID)",
                    },
                    "lakehouse_id": {
                        "type": "string",
                        "description": "UUID ou nome do Lakehouse (ex: 'dev_lakehouse' ou 'bccadc52-...')",
                    },
                    "path": {
                        "type": "string",
                        "description": (
                            "Caminho relativo dentro do lakehouse. "
                            "Ex: 'Files/src/bronze', 'Files/src/silver', 'Tables/bronze'."
                        ),
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Se true, lista recursivamente. Default: false.",
                    },
                },
                "required": ["lakehouse_id"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def _dispatch_create_notebook(a: dict) -> str:
    name = a.get("display_name") or a.get("displayName") or a.get("name") or ""
    if not name:
        return json.dumps({"error": "display_name obrigatório"})

    workspace_id = a.get("workspace_id") or settings.fabric_workspace_id
    lakehouse_id = a.get("default_lakehouse_id") or settings.fabric_lakehouse_id
    lakehouse_name = a.get("default_lakehouse_name") or settings.fabric_lakehouse_name or "dev_lakehouse"

    return _fabric_create_notebook(
        workspace_id,
        name,
        ipynb_content=a.get("ipynb_content", ""),
        cells=a.get("cells"),
        folder_path=a.get("folder_path") or a.get("folderPath", ""),
        default_lakehouse_id=lakehouse_id,
        default_lakehouse_name=lakehouse_name,
    )


_DISPATCH_MAP = {
    "fabric_list_workspaces": lambda _: _fabric_list_workspaces(),
    "fabric_list_items": lambda a: _fabric_list_items(a["workspace_id"], a.get("item_type", "")),
    "fabric_get_item": lambda a: _fabric_get_item(a["workspace_id"], a["item_id"]),
    "fabric_list_lakehouses": lambda a: _fabric_list_lakehouses(a.get("workspace_id", "")),
    "fabric_get_lakehouse_tables": lambda a: _fabric_get_lakehouse_tables(
        a["workspace_id"], a["lakehouse_id"]
    ),
    "fabric_run_notebook": lambda a: _fabric_run_notebook(
        a["workspace_id"], a["item_id"], a.get("parameters"),
        wait_for_completion=a.get("wait_for_completion", False),
        timeout_seconds=int(a.get("timeout_seconds", 600)),
    ),
    "fabric_get_job_instance": lambda a: _fabric_get_job_instance(
        a["workspace_id"], a["item_id"], a["job_instance_id"]
    ),
    "fabric_list_pipelines": lambda a: _fabric_list_pipelines(a["workspace_id"]),
    "fabric_get_notebook_definition": lambda a: _fabric_get_notebook_definition(
        a.get("workspace_id", ""), a["notebook_id"]
    ),
    "fabric_delete_item": lambda a: _fabric_delete_item(
        a.get("workspace_id", ""), a["item_id"]
    ),
    "fabric_find_or_create_folder": lambda a: _fabric_find_or_create_folder(
        a.get("workspace_id", ""), a["folder_path"]
    ),
    "fabric_create_notebook": lambda a: _dispatch_create_notebook(a),
    "fabric_write_onelake_file": lambda a: _fabric_write_onelake_file(
        a.get("workspace_id", ""), a["lakehouse_id"], a["path"], a["content"]
    ),
    "fabric_read_onelake_file": lambda a: _fabric_read_onelake_file(
        a.get("workspace_id", ""),
        a["lakehouse_id"],
        a["path"],
        int(a.get("max_bytes", 16384)),
    ),
    "fabric_list_onelake_files": lambda a: _fabric_list_onelake_files(
        a.get("workspace_id", ""),
        a["lakehouse_id"],
        a.get("path", "Files"),
        a.get("recursive", False),
    ),
    "fabric_update_notebook_definition": lambda a: _fabric_update_notebook_definition(
        a.get("workspace_id", ""),
        a["notebook_id"],
        ipynb_content=a.get("ipynb_content", ""),
        cells=a.get("cells"),
    ),
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
