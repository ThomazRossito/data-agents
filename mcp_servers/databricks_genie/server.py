"""
Databricks Genie — MCP Server Customizado.

Expõe as tools da Genie Conversation API e Space Management API do Databricks,
resolvendo o gap do databricks-mcp-server oficial que não inclui as tools de Genie
(ask_genie, get_genie, create_or_update_genie, migrate_genie, delete_genie).

REGISTRY DE SPACES: Suporta um JSON registry de Genie Spaces com nomes amigáveis,
similar ao registry de lakehouses do fabric_sql. O agente pode referenciar um space
por nome (ex: "retail-sales") em vez de pelo space_id longo.

Configuração no .env:

  # Registry de Genie Spaces disponíveis (JSON) — recomendado
  # Chave = nome amigável | Valor = space_id do Databricks
  DATABRICKS_GENIE_SPACES={"retail-sales": "01f117197b5319fb972e10a45735b28c",
                            "hr-analytics": "01abc123..."}

  # Space padrão (usado quando o agente não especifica qual)
  DATABRICKS_GENIE_DEFAULT_SPACE=retail-sales

  # Credenciais Databricks (compartilhadas com databricks-mcp-server)
  DATABRICKS_HOST=https://adb-xxxx.azuredatabricks.net
  DATABRICKS_TOKEN=dapi...

Como encontrar o Space ID:
  Databricks workspace → AI/BI → Genie → abra o Space → copie o ID da URL
  Formato: 01f1xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

Autenticação: Bearer Token (DATABRICKS_TOKEN) via REST API.
Nenhuma dependência adicional além de `requests` (já incluído no Python stdlib via urllib).

Pré-requisitos:
  Nenhum além do que já existe no projeto (requests incluso via databricks-sdk/httpx).
"""

from __future__ import annotations

import json
import logging
import os
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("databricks_genie_mcp")

# ─── FastMCP Server ───────────────────────────────────────────────────────────

mcp = FastMCP("databricks-genie")

# ─── Constantes ──────────────────────────────────────────────────────────────

_GENIE_API = "/api/2.0/genie/spaces"
_POLL_INTERVAL_S = 2  # segundos entre polls de status
_DEFAULT_TIMEOUT_S = 120  # timeout padrão para ask_genie


# ─── Registry de Spaces ──────────────────────────────────────────────────────


def _get_spaces_registry() -> dict[str, str]:
    """
    Carrega o registry de Genie Spaces do DATABRICKS_GENIE_SPACES (JSON).
    Formato: {"nome-amigavel": "space_id_databricks", ...}
    """
    raw = os.environ.get("DATABRICKS_GENIE_SPACES", "").strip()
    if not raw:
        return {}
    try:
        registry = json.loads(raw)
        if not isinstance(registry, dict):
            raise ValueError("DATABRICKS_GENIE_SPACES deve ser um objeto JSON.")
        return registry
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao parsear DATABRICKS_GENIE_SPACES: {e}")
        return {}


def _resolve_space_id(space: str | None) -> str:
    """
    Resolve o space_id a partir de um nome amigável ou space_id direto.

    Prioridade:
      1. space especificado → checa no registry (nome amigável → space_id)
      2. space especificado mas não no registry → assume que é um space_id direto
      3. space=None → usa o default (DATABRICKS_GENIE_DEFAULT_SPACE)

    Returns:
        space_id resolvido

    Raises:
        RuntimeError se não há default configurado e space não foi especificado.
    """
    registry = _get_spaces_registry()

    if space:
        # Tenta resolver como nome amigável
        if space in registry:
            return registry[space]
        # Assume que é um space_id direto (IDs têm formato alfanumérico longo)
        return space

    # Sem space explícito → usa o default
    default_name = os.environ.get("DATABRICKS_GENIE_DEFAULT_SPACE", "").strip()
    if default_name and registry:
        space_id = registry.get(default_name)
        if space_id:
            return space_id
        raise RuntimeError(
            f"DATABRICKS_GENIE_DEFAULT_SPACE='{default_name}' não encontrado no registry.\n"
            f"Spaces no registry: {list(registry.keys())}"
        )

    if default_name:
        # Default configurado mas sem registry — assume que é um space_id direto
        return default_name

    raise RuntimeError(
        "Nenhum Genie Space configurado.\n\n"
        "Opção 1 — Registry com nomes amigáveis (recomendado):\n"
        '  DATABRICKS_GENIE_SPACES={"retail-sales": "01f117197b5319fb972e10a45735b28c"}\n'
        "  DATABRICKS_GENIE_DEFAULT_SPACE=retail-sales\n\n"
        "Opção 2 — Space ID direto como default:\n"
        "  DATABRICKS_GENIE_DEFAULT_SPACE=01f117197b5319fb972e10a45735b28c\n\n"
        "Como encontrar o Space ID:\n"
        "  Databricks → AI/BI → Genie → abra o Space → copie o ID da URL"
        + (f"\n\nSpaces no registry: {list(registry.keys())}" if registry else "")
    )


# ─── HTTP Helpers ─────────────────────────────────────────────────────────────


def _get_credentials() -> tuple[str, str]:
    """Retorna (host, token) do Databricks."""
    host = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
    token = os.environ.get("DATABRICKS_TOKEN", "")
    if not host:
        raise RuntimeError(
            "DATABRICKS_HOST não configurado. "
            "Adicione ao .env: DATABRICKS_HOST=https://adb-xxxx.azuredatabricks.net"
        )
    if not token:
        raise RuntimeError(
            "DATABRICKS_TOKEN não configurado. Adicione ao .env: DATABRICKS_TOKEN=dapi..."
        )
    return host, token


def _api_request(
    method: str,
    path: str,
    body: dict | None = None,
    *,
    timeout: int = 30,
) -> dict:
    """
    Executa uma requisição HTTP à API do Databricks.

    Args:
        method: "GET", "POST", "PUT", "PATCH", "DELETE"
        path: Path relativo (ex: "/api/2.0/genie/spaces")
        body: Payload JSON (opcional)
        timeout: Timeout em segundos

    Returns:
        Dict da resposta JSON ou {} para respostas sem corpo (204)

    Raises:
        RuntimeError com mensagem clara em caso de erro HTTP
    """
    host, token = _get_credentials()
    url = f"{host}{path}"

    data = json.dumps(body).encode("utf-8") if body else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            raw = resp.read()
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8")
            error_json = json.loads(error_body)
            msg = error_json.get("message", error_body)
        except Exception:
            msg = error_body or str(e)
        raise RuntimeError(f"HTTP {e.code} {e.reason} — {method} {path}\nDetalhe: {msg}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Erro de conexão ao Databricks: {e.reason}\nVerifique DATABRICKS_HOST: {host}"
        ) from e


def _error_response(e: Exception) -> str:
    return json.dumps(
        {"error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()},
        ensure_ascii=False,
        indent=2,
    )


# ─── Polling de Mensagem Genie ────────────────────────────────────────────────


def _poll_message(
    space_id: str,
    conversation_id: str,
    message_id: str,
    timeout_seconds: int,
) -> dict:
    """
    Faz polling até a mensagem Genie completar ou o timeout estourar.

    Returns:
        Dict com status, sql, columns, data, row_count, text_response, error
    """
    host, _ = _get_credentials()
    deadline = time.time() + timeout_seconds
    msg_path = f"{_GENIE_API}/{space_id}/conversations/{conversation_id}/messages/{message_id}"

    while time.time() < deadline:
        msg = _api_request("GET", msg_path)
        status = msg.get("status", "EXECUTING_QUERY")

        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            break

        time.sleep(_POLL_INTERVAL_S)
    else:
        return {
            "status": "TIMEOUT",
            "error": f"Timeout após {timeout_seconds}s. Tente aumentar timeout_seconds.",
            "conversation_id": conversation_id,
            "message_id": message_id,
        }

    if status != "COMPLETED":
        return {
            "status": status,
            "error": msg.get("error", {}).get("message", f"Status: {status}"),
            "conversation_id": conversation_id,
            "message_id": message_id,
        }

    # Busca resultado da query
    result: dict[str, Any] = {
        "status": "COMPLETED",
        "conversation_id": conversation_id,
        "message_id": message_id,
    }

    # Texto explicativo (se Genie pediu clarificação em vez de gerar SQL)
    attachments = msg.get("attachments", [])
    for att in attachments:
        if att.get("text"):
            result["text_response"] = att["text"].get("content", "")

    # Resultado da query SQL
    query_result_path = f"{msg_path}/query-result"
    try:
        qr = _api_request("GET", query_result_path)
        statement = qr.get("statement_response", {})
        result["sql"] = statement.get("statement", "")

        schema = statement.get("result", {}).get("data_typed_array", None)
        manifest = statement.get("manifest", {})

        columns = [c["name"] for c in manifest.get("schema", {}).get("columns", [])]
        result["columns"] = columns

        if schema is not None:
            rows = []
            for row in schema:
                values = [v.get("str") for v in row.get("values", [])]
                rows.append(values)
            result["data"] = rows
            result["row_count"] = len(rows)
        else:
            result["data"] = []
            result["row_count"] = 0

    except RuntimeError as e:
        # Pode não ter resultado de query (resposta só textual)
        if "404" not in str(e):
            result["query_result_error"] = str(e)

    return result


# ─── MCP Tools ───────────────────────────────────────────────────────────────


@mcp.tool()
def genie_diagnostics() -> str:
    """
    Diagnóstico completo da conexão ao Databricks Genie API.
    Execute este tool quando houver erros de conexão ou autenticação.
    Também lista os Genie Spaces configurados no registry.
    """
    report: dict[str, Any] = {"status": "ok", "checks": []}

    def check(name: str, ok: bool, detail: str) -> None:
        report["checks"].append({"check": name, "status": "✅" if ok else "❌", "detail": detail})
        if not ok:
            report["status"] = "error"

    # Credenciais
    host = os.environ.get("DATABRICKS_HOST", "")
    token = os.environ.get("DATABRICKS_TOKEN", "")
    check("DATABRICKS_HOST", bool(host), host or "Não configurado — adicione ao .env")
    check(
        "DATABRICKS_TOKEN",
        bool(token),
        f"{token[:12]}***" if token else "Não configurado — adicione ao .env",
    )

    # Registry
    registry = _get_spaces_registry()
    default = os.environ.get("DATABRICKS_GENIE_DEFAULT_SPACE", "")
    check(
        "DATABRICKS_GENIE_SPACES (registry)",
        bool(registry),
        f"{len(registry)} space(s): {list(registry.keys())}"
        if registry
        else "Não configurado (opcional — pode usar space_id direto nas tools)",
    )
    check(
        "DATABRICKS_GENIE_DEFAULT_SPACE",
        bool(default),
        default or "Não configurado (será necessário passar space= em cada chamada)",
    )

    # Conectividade
    if host and token:
        try:
            resp = _api_request("GET", _GENIE_API, timeout=15)
            spaces = resp.get("genie_spaces", [])
            check(
                "Conectividade API Genie",
                True,
                f"OK — {len(spaces)} space(s) acessível(is) no workspace",
            )
        except RuntimeError as e:
            check("Conectividade API Genie", False, str(e))

    return json.dumps(report, ensure_ascii=False, indent=2)


@mcp.tool()
def genie_list_spaces() -> str:
    """
    Lista todos os Genie Spaces disponíveis no workspace Databricks.
    Retorna ID, nome, descrição e warehouse de cada space.
    """
    try:
        resp = _api_request("GET", _GENIE_API)
        spaces = resp.get("genie_spaces", [])
        registry = _get_spaces_registry()

        result = []
        for s in spaces:
            space_id = s.get("space_id", s.get("id", ""))
            friendly_name = next((k for k, v in registry.items() if v == space_id), None)
            result.append(
                {
                    "space_id": space_id,
                    "name": s.get("display_name", s.get("title", "")),
                    "description": s.get("description", ""),
                    "warehouse_id": s.get("warehouse_id", ""),
                    "friendly_name": friendly_name,
                }
            )

        return json.dumps(
            {"spaces": result, "count": len(result), "registry": registry},
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def genie_ask(
    question: str,
    space: str | None = None,
    timeout_seconds: int = 120,
) -> str:
    """
    Faz uma pergunta em linguagem natural a um Genie Space.
    O Genie gera o SQL, executa no warehouse e retorna os dados.

    Args:
        question: Pergunta em linguagem natural.
                  Ex: "Qual o total de vendas por produto em 2024?"
        space: Nome amigável ou space_id direto. Se None, usa o default configurado.
               Use genie_list_spaces() para ver os disponíveis.
               Exemplos: "retail-sales", "01f117197b5319fb972e10a45735b28c"
        timeout_seconds: Timeout para aguardar resposta do Genie (padrão: 120s).

    Returns:
        JSON com: status, sql (gerado pelo Genie), columns, data, row_count,
                  conversation_id (para follow-ups), message_id.
    """
    try:
        space_id = _resolve_space_id(space)
        payload = {"content": question}
        resp = _api_request("POST", f"{_GENIE_API}/{space_id}/start-conversation", body=payload)

        conversation_id = resp.get("conversation_id", resp.get("id", ""))
        message = resp.get("message", resp)
        message_id = message.get("message_id", message.get("id", ""))

        result = _poll_message(space_id, conversation_id, message_id, timeout_seconds)
        result["question"] = question
        result["space_id"] = space_id
        result["space_friendly_name"] = space or _resolve_friendly_name(space_id)

        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def genie_followup(
    question: str,
    conversation_id: str,
    space: str | None = None,
    timeout_seconds: int = 120,
) -> str:
    """
    Envia uma pergunta de follow-up em uma conversa Genie existente.
    O Genie usa o contexto da conversa para interpretar referências como
    "aquele resultado", "por região", "no mesmo período".

    Args:
        question: Pergunta de follow-up. Ex: "Quebre isso por categoria de produto."
        conversation_id: ID da conversa anterior (retornado por genie_ask).
        space: Nome amigável ou space_id. Se None, usa o default.
        timeout_seconds: Timeout em segundos (padrão: 120s).

    Returns:
        JSON com: status, sql, columns, data, row_count, conversation_id, message_id.
    """
    try:
        space_id = _resolve_space_id(space)
        payload = {"content": question}
        path = f"{_GENIE_API}/{space_id}/conversations/{conversation_id}/messages"
        resp = _api_request("POST", path, body=payload)

        message_id = resp.get("message_id", resp.get("id", ""))
        result = _poll_message(space_id, conversation_id, message_id, timeout_seconds)
        result["question"] = question
        result["space_id"] = space_id

        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def genie_get(space: str | None = None, include_serialized: bool = False) -> str:
    """
    Retorna os detalhes de um Genie Space específico.
    Se space=None, lista todos os spaces (equivalente a genie_list_spaces).

    Args:
        space: Nome amigável ou space_id. Se None, lista todos os spaces.
        include_serialized: Se True, inclui a configuração serializada completa
                            (útil para export/backup). Requer permissão CAN EDIT.

    Returns:
        JSON com detalhes do space: id, nome, tabelas, warehouse, etc.
    """
    try:
        if not space:
            return genie_list_spaces()

        space_id = _resolve_space_id(space)
        params = "?include_serialized_space=true" if include_serialized else ""
        resp = _api_request("GET", f"{_GENIE_API}/{space_id}{params}")

        return json.dumps(resp, ensure_ascii=False, indent=2)
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def genie_create_or_update(
    display_name: str,
    table_identifiers: list[str],
    description: str = "",
    sample_questions: list[str] | None = None,
    warehouse_id: str | None = None,
    space_id: str | None = None,
    serialized_space: str | None = None,
) -> str:
    """
    Cria ou atualiza um Genie Space.

    Se space_id fornecido → atualiza o space existente.
    Se space_id omitido → busca por display_name; se não encontrar, cria novo.

    Args:
        display_name: Nome exibido no workspace. Ex: "Análise de Vendas Retail"
        table_identifiers: Tabelas Unity Catalog. Ex: ["catalog.schema.silver_sales"]
        description: Descrição do space e das tabelas (ajuda o Genie a gerar melhor SQL).
        sample_questions: Perguntas de exemplo que guiam os usuários.
        warehouse_id: SQL Warehouse para executar as queries. Se None, auto-detecta.
        space_id: ID do space a atualizar. Se None, cria novo ou busca por nome.
        serialized_space: Configuração serializada (da genie_export). Se fornecido,
                          sobrescreve table_identifiers e sample_questions.

    Returns:
        JSON com space_id, display_name e operation (created/updated).
    """
    try:
        payload: dict[str, Any] = {
            "display_name": display_name,
            "description": description,
        }

        if serialized_space:
            payload["serialized_space"] = serialized_space
        else:
            if table_identifiers:
                payload["table_identifiers"] = table_identifiers
            if sample_questions:
                payload["sample_questions"] = sample_questions

        if warehouse_id:
            payload["warehouse_id"] = warehouse_id

        if space_id:
            # Update por ID
            resp = _api_request("PATCH", f"{_GENIE_API}/{space_id}", body=payload)
            resp["operation"] = "updated"
        else:
            # Busca por nome para decidir se cria ou atualiza
            existing = _api_request("GET", _GENIE_API)
            spaces = existing.get("genie_spaces", [])
            found = next(
                (s for s in spaces if s.get("display_name", s.get("title", "")) == display_name),
                None,
            )
            if found:
                sid = found.get("space_id", found.get("id", ""))
                resp = _api_request("PATCH", f"{_GENIE_API}/{sid}", body=payload)
                resp["operation"] = "updated"
                resp["space_id"] = sid
            else:
                resp = _api_request("POST", _GENIE_API, body=payload)
                resp["operation"] = "created"

        return json.dumps(resp, ensure_ascii=False, indent=2)
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def genie_delete(space: str) -> str:
    """
    Exclui um Genie Space permanentemente.

    Args:
        space: Nome amigável ou space_id do space a excluir.
               Use genie_list_spaces() para ver os disponíveis.

    Returns:
        JSON confirmando a exclusão.
    """
    try:
        space_id = _resolve_space_id(space)
        _api_request("DELETE", f"{_GENIE_API}/{space_id}")
        return json.dumps(
            {"status": "deleted", "space_id": space_id},
            ensure_ascii=False,
        )
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def genie_export(space: str | None = None) -> str:
    """
    Exporta a configuração completa de um Genie Space para backup ou migração.
    Inclui tabelas, instruções, SQL de exemplo, join specs e benchmarks.
    Requer permissão CAN EDIT no space.

    Args:
        space: Nome amigável ou space_id. Se None, usa o default configurado.

    Returns:
        JSON com: space_id, title, description, warehouse_id, serialized_space.
        Use serialized_space no genie_import() para clonar ou migrar o space.
    """
    try:
        space_id = _resolve_space_id(space)
        resp = _api_request("GET", f"{_GENIE_API}/{space_id}/export")
        return json.dumps(resp, ensure_ascii=False, indent=2)
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def genie_import(
    serialized_space: str,
    warehouse_id: str,
    title: str | None = None,
    description: str | None = None,
) -> str:
    """
    Importa (clona) um Genie Space a partir de uma configuração exportada.
    Use para clonar um space ou migrar entre workspaces/ambientes.

    Para migrar entre ambientes com catalogs diferentes, faça o replace do
    catalog name em serialized_space antes de chamar esta tool:
        serialized_space = serialized_space.replace("catalog_source", "catalog_destino")

    Args:
        serialized_space: Configuração exportada pelo genie_export() ou genie_get(include_serialized=True).
        warehouse_id: ID do SQL Warehouse no workspace de destino.
                      Use mcp__databricks__list_sql_warehouses para obter os IDs disponíveis.
        title: Título do space importado. Se None, usa o título original.
        description: Descrição do space. Se None, usa a original.

    Returns:
        JSON com: space_id (novo), title, operation="imported".
    """
    try:
        payload: dict[str, Any] = {
            "serialized_space": serialized_space,
            "warehouse_id": warehouse_id,
        }
        if title:
            payload["title"] = title
        if description:
            payload["description"] = description

        resp = _api_request("POST", f"{_GENIE_API}/import", body=payload)
        resp["operation"] = "imported"
        return json.dumps(resp, ensure_ascii=False, indent=2)
    except Exception as e:
        return _error_response(e)


# ─── Helpers internos ─────────────────────────────────────────────────────────


def _resolve_friendly_name(space_id: str) -> str | None:
    """Resolve o nome amigável de um space_id no registry (busca reversa)."""
    registry = _get_spaces_registry()
    return next((k for k, v in registry.items() if v == space_id), None)


# ─── Entry Point ─────────────────────────────────────────────────────────────


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    mcp.run()


if __name__ == "__main__":
    main()
