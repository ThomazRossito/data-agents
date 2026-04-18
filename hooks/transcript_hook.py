"""
Transcript Hook — Persistência append-only do histórico conversacional por sessão.

Complementa `hooks/checkpoint.py` (que guarda só o último prompt + metadados).
Este módulo grava **todo** o turno, incluindo:
  - role ("user" ou "assistant")
  - content (texto completo)
  - timestamp
  - tools_used (lista de tools disparadas no turno)
  - cost_usd / turns / duration_ms (quando disponível)

Arquivo: `logs/sessions/<session_id>.jsonl` (append-only, uma entrada por linha).

O transcript é complementar, não substitui o checkpoint. `/resume` vai preferir
o transcript quando existir, com fallback para build_resume_prompt().
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import settings

logger = logging.getLogger("data_agents.transcript")

SESSIONS_DIR: Path = Path(settings.audit_log_path).parent / "sessions"


def get_transcript_path(session_id: str) -> Path:
    """Retorna o path do arquivo de transcript para um session_id."""
    return SESSIONS_DIR / f"{session_id}.jsonl"


def append_turn(
    session_id: str,
    role: str,
    content: str,
    tools_used: list[str] | None = None,
    cost_usd: float | None = None,
    turns: int | None = None,
    duration_ms: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Registra um turno da conversa no arquivo de transcript da sessão.

    Falhas de I/O são logadas mas não propagam — um transcript incompleto é
    aceitável, travar a conversa do usuário não é.

    Args:
        session_id: Identificador da sessão (ex: "cli-abc12345").
        role: "user" ou "assistant".
        content: Texto do turno (prompt ou resposta completa).
        tools_used: Lista de nomes de tools disparadas neste turno.
        cost_usd: Custo do turno em USD (quando aplicável — só para assistant).
        turns: Número de turns internos gastos pelo agente no turno.
        duration_ms: Duração do turno em milissegundos.
        metadata: Campos adicionais livres (ex: session_type, agent, command).
    """
    if not session_id or not role or content is None:
        return

    entry: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "role": role,
        "content": content,
    }
    if tools_used:
        entry["tools_used"] = list(tools_used)
    if cost_usd is not None:
        entry["cost_usd"] = float(cost_usd)
    if turns is not None:
        entry["turns"] = int(turns)
    if duration_ms is not None:
        entry["duration_ms"] = int(duration_ms)
    if metadata:
        entry["metadata"] = metadata

    path = get_transcript_path(session_id)
    try:
        os.makedirs(path.parent, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.warning(f"Falha ao gravar transcript em {path}: {e}")


def load_transcript(session_id: str) -> list[dict[str, Any]]:
    """
    Carrega o transcript completo de uma sessão, na ordem cronológica.

    Linhas malformadas são ignoradas silenciosamente para garantir robustez
    mesmo que o arquivo tenha sido parcialmente corrompido.

    Args:
        session_id: Identificador da sessão.

    Returns:
        Lista de entries do transcript; vazia se o arquivo não existir.
    """
    path = get_transcript_path(session_id)
    if not path.exists():
        return []

    entries: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError as e:
        logger.warning(f"Falha ao ler transcript {path}: {e}")
    return entries


def list_transcripts() -> list[dict[str, Any]]:
    """
    Lista todas as sessões que têm transcript em `logs/sessions/*.jsonl`.

    Para cada uma retorna:
      - session_id
      - first_timestamp / last_timestamp
      - turn_count
      - total_cost_usd (somando os cost_usd de cada entry)
      - last_user_prompt (último content de role=user, truncado a 120 chars)

    Ordenação: mais recente primeiro (por last_timestamp desc).
    """
    if not SESSIONS_DIR.exists():
        return []

    results: list[dict[str, Any]] = []
    for path in SESSIONS_DIR.glob("*.jsonl"):
        session_id = path.stem
        entries = load_transcript(session_id)
        if not entries:
            continue

        timestamps = [e.get("timestamp", "") for e in entries if e.get("timestamp")]
        first_ts = min(timestamps) if timestamps else ""
        last_ts = max(timestamps) if timestamps else ""

        total_cost = sum(float(e.get("cost_usd") or 0) for e in entries)
        turn_count = sum(1 for e in entries if e.get("role") == "user")

        last_user = ""
        for entry in reversed(entries):
            if entry.get("role") == "user":
                last_user = (entry.get("content") or "")[:120]
                break

        results.append(
            {
                "session_id": session_id,
                "first_timestamp": first_ts,
                "last_timestamp": last_ts,
                "turn_count": turn_count,
                "total_cost_usd": round(total_cost, 6),
                "last_user_prompt": last_user,
            }
        )

    results.sort(key=lambda s: s["last_timestamp"], reverse=True)
    return results


def build_resume_prompt_from_transcript(
    session_id: str, max_turns: int = 10, max_chars_per_turn: int = 2000
) -> str | None:
    """
    Constrói um prompt de retomada a partir do transcript.

    Inclui os últimos `max_turns` turns (user + assistant, intercalados), cada
    um truncado em `max_chars_per_turn` caracteres para respeitar o budget de
    contexto.

    Args:
        session_id: ID da sessão.
        max_turns: Número máximo de pares user/assistant a incluir.
        max_chars_per_turn: Limite de caracteres por turno.

    Returns:
        Prompt formatado pronto para injeção, ou None se não houver transcript.
    """
    entries = load_transcript(session_id)
    if not entries:
        return None

    # Seleciona os últimos max_turns*2 entries (pares user/assistant)
    tail = entries[-(max_turns * 2) :]

    lines = [
        "## Contexto da Sessão Anterior (Transcript Completo)",
        f"Retomando sessão `{session_id}` com {len(entries)} turns registrados.",
        f"Exibindo os últimos {len(tail)} turnos:",
        "",
    ]

    for entry in tail:
        role = entry.get("role", "?")
        content = (entry.get("content") or "")[:max_chars_per_turn]
        ts = (entry.get("timestamp") or "")[:19]
        tools = entry.get("tools_used") or []
        label = "**Usuário**" if role == "user" else "**Assistente**"
        lines.append(f"### {label} ({ts})")
        lines.append(content)
        if tools:
            lines.append(f"_Tools usadas: {', '.join(tools[:8])}_")
        lines.append("")

    lines.append(
        "**Instrução**: O histórico acima mostra o que já foi discutido. "
        "Responda ao usuário dando continuidade ao contexto, sem recapitular "
        "o que ele já viu. Se o último turno do assistente foi uma pergunta, "
        "aguarde a resposta do usuário; caso contrário, siga o fluxo natural."
    )
    return "\n".join(lines)
