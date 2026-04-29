"""Hook de auditoria — registra todas as interações em JSONL."""

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
AUDIT_FILE = LOG_DIR / "audit.jsonl"

logger = logging.getLogger(__name__)

_SECRET_RE = re.compile(
    r"(token|password|api[_-]?key|secret|bearer|dapi|ghp_|sk-|pat_)\s*[:=]?\s*[\w\-/+]{8,}",
    re.IGNORECASE,
)


def _redact(s: str) -> str:
    return _SECRET_RE.sub(r"\1=***REDACTED***", s)


def record(agent: str, task: str, tokens_used: int, tool_calls: int) -> None:
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "agent": agent,
        "task_preview": _redact(task[:200]),
        "tokens_used": tokens_used,
        "tool_calls": tool_calls,
    }
    with AUDIT_FILE.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    logger.debug("Audit: %s", entry)
