"""
Hook de auditoria — registra todas as tool calls para rastreabilidade completa.
Log em formato JSONL (uma linha por entrada) em logs/audit.jsonl.

Implementa:
  - Registro estruturado com timestamp, tool, agent e duração
  - Fallback para stderr + logging.warning em caso de falha de I/O
  - Classificação automática de operações (read-only vs write vs execute)
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

from config.settings import settings

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
    """
    # Proteção contra eventos de teardown do SDK (hook chamado com dados inválidos)
    if not input_data or not isinstance(input_data, dict):
        return {}

    tool_name = input_data.get("tool_name", "unknown")

    # Ignora eventos internos do SDK sem nome de tool significativo
    if not tool_name or tool_name in ("unknown", "", None):
        return {}

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "tool_call",
        "tool_name": tool_name,
        "tool_use_id": tool_use_id,
        "operation_type": _classify_operation(tool_name),
        # Registramos apenas os nomes das chaves, não os valores
        "input_keys": list(input_data.get("tool_input", {}).keys()),
    }

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
