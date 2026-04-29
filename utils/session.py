"""utils.session — Persistência e resume de sessões.

Cada sessão é um arquivo JSONL em logs/sessions/<session_id>.jsonl.
Session ID = YYYYMMDDTHHMMSS-<uuid8> gerado no __init__.

Uso:
    mgr = SessionManager()
    mgr.record(user_input="...", result_content="...")
    context = mgr.load_last_session()   # resume da sessão anterior
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from config.settings import settings

logger = logging.getLogger("data_agents.session")

SESSIONS_DIR = Path(__file__).parent.parent / "logs" / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

_MAX_RESUME_CHARS = 4000

_SECRET_RE = re.compile(
    r"(token|password|api[_-]?key|secret|bearer|dapi|ghp_|sk-|pat_)\s*[:=]?\s*[\w\-/+]{8,}",
    re.IGNORECASE,
)


def _redact(s: str) -> str:
    return _SECRET_RE.sub(r"\1=***REDACTED***", s)


def _new_session_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    uid = uuid.uuid4().hex[:8]
    return f"{ts}-{uid}"


class SessionManager:
    """Grava transcrições e permite resume da sessão anterior."""

    def __init__(self, session_id: str | None = None) -> None:
        self.session_id = session_id or _new_session_id()
        self._path = SESSIONS_DIR / f"{self.session_id}.jsonl"
        self._turn = 0

    def record(self, user_input: str, result_content: str) -> None:
        self._turn += 1
        entry = {
            "turn": self._turn,
            "timestamp": datetime.now(UTC).isoformat(),
            "user": _redact(user_input[:2000]),
            "agent": _redact(result_content[:3000]),
        }
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ── Resume ───────────────────────────────────────────────────────────────

    @staticmethod
    def load_last_session(
        max_turns: int | None = None,
        max_chars: int = _MAX_RESUME_CHARS,
    ) -> str:
        """
        Carrega os últimos `max_turns` do arquivo de sessão mais recente.
        Retorna string pronta para injeção como contexto.
        """
        if max_turns is None:
            max_turns = settings.session_max_resume_turns
        files = sorted(SESSIONS_DIR.glob("*.jsonl"), reverse=True)
        if not files:
            return "Nenhuma sessão anterior encontrada."

        recent = files[0]
        lines = recent.read_text(encoding="utf-8").splitlines()
        turns = []
        for line in reversed(lines):
            try:
                turns.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(turns) >= max_turns:
                break

        turns.reverse()
        parts = [
            f"## Sessão anterior: `{recent.stem}`\n"
            f"Últimos {len(turns)} turno(s):\n"
        ]
        total_chars = len(parts[0])
        for t in turns:
            block = (
                f"\n**Turno {t['turn']}** ({t['timestamp'][:19]})\n"
                f"**Usuário:** {t['user']}\n"
                f"**Agente:** {t['agent']}\n"
            )
            if total_chars + len(block) > max_chars:
                parts.append("\n[...truncado para caber no contexto...]")
                break
            parts.append(block)
            total_chars += len(block)

        return "".join(parts)

    @staticmethod
    def list_sessions(n: int = 10) -> str:
        """Lista as últimas `n` sessões com contagem de turnos."""
        files = sorted(SESSIONS_DIR.glob("*.jsonl"), reverse=True)[:n]
        if not files:
            return "Nenhuma sessão registrada."
        lines = ["| Sessão | Turnos |", "|--------|--------|"]
        for f in files:
            count = sum(1 for _ in f.open())
            lines.append(f"| `{f.stem}` | {count} |")
        return "\n".join(lines)
