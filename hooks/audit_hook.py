"""
Hook de auditoria — registra todas as tool calls para rastreabilidade completa.
Log em formato JSONL (uma linha por entrada) em logs/audit.jsonl.

Implementa:
  - Registro estruturado com timestamp, tool, agent e duração
  - Fallback para stderr + logging.warning em caso de falha de I/O
  - Classificação automática de operações (read-only vs write vs execute)
  - Categorização de erros (auth, timeout, rate_limit, mcp, business_logic, unknown)
  - Detecção de plataforma para análise por agente
"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any

from config.settings import settings

# Padrão que mascara valores após flags sensíveis em comandos shell
_SECRET_FLAG_PATTERN = re.compile(
    r"((?:--?(?:token|password|key|secret|api[_-]?key|pat|pw|passwd|auth|credential|cred))"
    r"(?:\s+|=))\S+",
    re.IGNORECASE,
)


def _sanitize_command(cmd: str) -> str:
    """Mascara valores de flags sensíveis em comandos shell para evitar vazamento em logs."""
    return _SECRET_FLAG_PATTERN.sub(r"\1***", cmd)


logger = logging.getLogger("data_agents.audit")

# ─── Classificação de operações ───────────────────────────────────

WRITE_OPERATIONS = {
    "mcp__databricks__execute_sql",
    "mcp__databricks__run_job_now",
    "mcp__databricks__start_pipeline",
    "mcp__databricks__start_cluster",
    "mcp__databricks__import_notebook",
    "mcp__fabric__onelake_upload_file",
    "mcp__fabric__onelake_delete_file",
    "mcp__fabric__onelake_create_directory",
    "mcp__fabric_rti__kusto_command",
    "mcp__fabric_rti__kusto_ingest_inline_into_table",
    "mcp__fabric_rti__eventstream_create",
    "mcp__fabric_rti__eventstream_update",
    "mcp__fabric_rti__eventstream_delete",
    "mcp__fabric_rti__activator_create_trigger",
    "Bash",
    "Write",
}

EXECUTE_OPERATIONS = {
    "mcp__databricks__run_job_now",
    "mcp__databricks__start_pipeline",
    "mcp__databricks__start_cluster",
    "mcp__databricks__cancel_run",
    "mcp__databricks__stop_pipeline",
    "Bash",
}


def _classify_operation(tool_name: str) -> str:
    """Classifica a operação como read, write ou execute."""
    if tool_name in EXECUTE_OPERATIONS:
        return "execute"
    if tool_name in WRITE_OPERATIONS:
        return "write"
    return "read"


# ─── Categorização de erros ──────────────────────────────────────

# Padrões regex para categorizar erros pelo conteúdo da mensagem
_ERROR_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "auth",
        re.compile(
            r"(?i)(unauthorized|forbidden|403|401|invalid.?token|credential|"
            r"authentication|permission.?denied|access.?denied|not.?authorized)"
        ),
    ),
    (
        "timeout",
        re.compile(
            r"(?i)(timeout|timed?\s*out|deadline.?exceeded|connection.?timed|"
            r"read.?timeout|connect.?timeout)"
        ),
    ),
    (
        "rate_limit",
        re.compile(
            r"(?i)(rate.?limit|429|too.?many.?requests|throttl|quota.?exceeded|"
            r"overloaded|capacity)"
        ),
    ),
    (
        "mcp_connection",
        re.compile(
            r"(?i)(mcp.?(?:error|fail|connection)|server.?disconnect|"
            r"connection.?refused|connection.?reset|broken.?pipe|eof)"
        ),
    ),
    (
        "not_found",
        re.compile(
            r"(?i)(not.?found|404|does.?not.?exist|no.?such|table.?not.?found|"
            r"schema.?not.?found|catalog.?not.?found)"
        ),
    ),
    (
        "validation",
        re.compile(
            r"(?i)(validation.?error|invalid.?input|malformed|parse.?error|"
            r"syntax.?error|type.?error|schema.?mismatch)"
        ),
    ),
]


def _classify_error(error_text: str) -> str:
    """
    Categoriza um erro pelo conteúdo da mensagem.

    Categorias:
      - auth: Erros de autenticação/autorização (401, 403, token inválido)
      - timeout: Timeouts de conexão ou execução
      - rate_limit: Limites de taxa da API (429, throttling)
      - mcp_connection: Falhas de conexão com servidores MCP
      - not_found: Recursos não encontrados (404, tabela inexistente)
      - validation: Erros de validação de input ou schema
      - unknown: Erros não categorizados
    """
    if not error_text:
        return "unknown"
    for category, pattern in _ERROR_PATTERNS:
        if pattern.search(error_text):
            return category
    return "unknown"


def _detect_platform(tool_name: str) -> str | None:
    """Detecta a plataforma a partir do nome da tool MCP."""
    if tool_name.startswith("mcp__"):
        parts = tool_name.split("__")
        if len(parts) >= 2:
            return parts[1]  # databricks, fabric, fabric_rti, fabric_community
    return None


def _extract_cache_metrics(input_data: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """
    Extrai métricas de cache da resposta do LLM quando disponíveis.

    O Claude Agent SDK v0.1.61 (abril/2026) ainda não expõe cache_control nativamente
    (issue #626 do repo oficial), então cache_creation_input_tokens e cache_read_input_tokens
    geralmente são 0. Esta função já está preparada para ler esses campos assim que o SDK
    expuser — hoje ela faz sondagem defensiva em input_data e context.

    Campos retornados (quando presentes):
      - cache_write_tokens: tokens escritos no cache (custo 1.25× base)
      - cache_read_tokens: tokens lidos do cache (custo 0.10× base, 90% desconto)
      - input_tokens: tokens de input não-cacheados
      - output_tokens: tokens de output gerados
    """
    metrics: dict[str, Any] = {}

    # Sonda 1: usage dentro de input_data (formato esperado se SDK passar)
    usage = input_data.get("usage") or {}

    # Sonda 2: atributo usage no context
    if not usage and ctx is not None:
        usage = getattr(ctx, "usage", None) or {}
        # Alguns SDKs expõem via dict
        if isinstance(ctx, dict):
            usage = ctx.get("usage") or usage

    if not isinstance(usage, dict) or not usage:
        return metrics

    cache_write = usage.get("cache_creation_input_tokens")
    cache_read = usage.get("cache_read_input_tokens")
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")

    if cache_write is not None:
        metrics["cache_write_tokens"] = cache_write
    if cache_read is not None:
        metrics["cache_read_tokens"] = cache_read
    if input_tokens is not None:
        metrics["input_tokens"] = input_tokens
    if output_tokens is not None:
        metrics["output_tokens"] = output_tokens

    # Hit rate calculado quando temos ambos os campos
    if cache_write is not None and cache_read is not None:
        total = cache_write + cache_read
        metrics["cache_hit_rate"] = (cache_read / total) if total > 0 else 0.0

    return metrics


async def audit_tool_usage(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    """
    Registra cada tool call com timestamp, nome, classificação e chaves de input.

    Não registra valores completos para evitar vazamento de dados sensíveis.
    Em caso de falha de I/O, faz fallback para stderr e logging.warning.
    Robusto a eventos de teardown/shutdown do SDK (input_data pode ser None ou
    ter formato inesperado durante o encerramento da sessão).

    Campos adicionais (v2):
      - error_category: Categoria do erro (auth, timeout, rate_limit, etc.)
      - platform: Plataforma MCP (databricks, fabric, fabric_rti)
      - has_error: Flag booleana para facilitar filtragem no dashboard
    """
    # Proteção contra eventos de teardown do SDK (hook chamado com dados inválidos)
    if not input_data or not isinstance(input_data, dict):
        return {}

    tool_name = input_data.get("tool_name", "unknown")

    # Ignora eventos internos do SDK sem nome de tool significativo
    if not tool_name or tool_name in ("unknown", "", None):
        return {}

    # Detectar erros no output da tool (se disponível no input_data)
    tool_output = input_data.get("tool_output", "") or ""
    tool_error = input_data.get("tool_error", "") or ""
    error_text = tool_error or ""

    # Também checa se o output contém indicadores de erro
    if not error_text and isinstance(tool_output, str):
        if any(kw in tool_output.lower() for kw in ["error", "failed", "exception", "traceback"]):
            error_text = tool_output[:500]

    has_error = bool(error_text)
    error_category = _classify_error(error_text) if has_error else None

    tool_input = input_data.get("tool_input", {}) or {}

    log_entry: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "tool_call",
        "tool_name": tool_name,
        "tool_use_id": tool_use_id,
        "operation_type": _classify_operation(tool_name),
        # Registramos apenas os nomes das chaves, não os valores
        "input_keys": list(tool_input.keys()),
        # Campos v2: categorização de erros e plataforma
        "platform": _detect_platform(tool_name),
        "has_error": has_error,
    }

    # Para Read/Write/Glob/Grep: registra o path acessado (sem conteúdo sensível).
    # Isso permite rastrear quais KBs, Skills e arquivos os agentes estão consultando.
    if tool_name in ("Read", "Write", "Glob") and "file_path" in tool_input:
        log_entry["file_path"] = str(tool_input["file_path"])
    elif tool_name == "Grep" and "path" in tool_input:
        log_entry["file_path"] = str(tool_input.get("path", ""))
    elif tool_name == "Bash" and "command" in tool_input:
        # Registra apenas os primeiros 120 chars do comando, com secrets mascarados
        sanitized = _sanitize_command(str(tool_input["command"]))
        log_entry["command_preview"] = sanitized[:120]

    # Adiciona campos de erro somente quando há erro (economia de espaço)
    if has_error:
        log_entry["error_category"] = error_category
        log_entry["error_preview"] = error_text[:200]

    # Métricas de cache (preparadas para quando o SDK expuser nativamente — issue #626).
    # Hoje geralmente vazio; quando presente, grava cache_write/read/hit_rate no JSONL.
    cache_metrics = _extract_cache_metrics(input_data, context)
    if cache_metrics:
        log_entry.update(cache_metrics)

    log_line = json.dumps(log_entry, ensure_ascii=False) + "\n"
    log_path = settings.audit_log_path

    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_line)
    except OSError as e:
        # Fallback 1: logging estruturado
        logger.warning(
            f"Falha ao gravar audit log em {log_path}: {e}. "
            f"Registro: tool={tool_name}, id={tool_use_id}"
        )
        # Fallback 2: stderr (último recurso, sempre disponível)
        try:
            sys.stderr.write(f"[AUDIT FALLBACK] {log_line}")
        except Exception:
            pass  # Auditoria nunca deve bloquear execução

    return {}
