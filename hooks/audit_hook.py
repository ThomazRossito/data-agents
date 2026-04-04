"""
Hook de auditoria — registra todas as tool calls para rastreabilidade completa.
Log em formato JSONL (uma linha por entrada) em logs/audit.jsonl.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any

from config.settings import settings


async def audit_tool_usage(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    """
    Registra cada tool call com timestamp, nome e chaves de input.

    Não registra valores completos para evitar vazamento de dados sensíveis.
    """
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool_name": input_data.get("tool_name", "unknown"),
        "tool_use_id": tool_use_id,
        # Registramos apenas os nomes das chaves, não os valores
        "input_keys": list(input_data.get("tool_input", {}).keys()),
    }

    log_path = settings.audit_log_path
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # Falha silenciosa — auditoria não deve bloquear execução

    return {}
