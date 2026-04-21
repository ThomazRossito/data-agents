"""
Módulo de persistência de métricas de sessão.
Registra custo, tokens e duração de cada query em logs/sessions.jsonl.

Usado pelo main.py após receber o ResultMessage do Claude Agent SDK.
"""

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import settings
from hooks.checkpoint import _redact_secrets

logger = logging.getLogger("data_agents.session_logger")

# Caminho derivado do mesmo diretório de logs do audit_hook
SESSIONS_LOG_PATH: Path = Path(settings.audit_log_path).parent / "sessions.jsonl"


def log_session_result(
    result_message: Any,
    prompt_preview: str = "",
    session_type: str = "interactive",
) -> None:
    """
    Persiste as métricas de uma query finalizada em logs/sessions.jsonl.

    Extrai total_cost_usd, num_turns e duration_ms do ResultMessage do
    Claude Agent SDK e grava uma linha JSON no arquivo de log de sessões.
    Em caso de falha de I/O, registra aviso via logging sem propagar erro.

    Args:
        result_message: ResultMessage retornado pelo Claude Agent SDK.
            Esperado ter os atributos total_cost_usd, num_turns e duration_ms.
        prompt_preview: Primeiros caracteres do prompt original (máximo 100).
            Nunca registre o prompt completo — pode conter dados sensíveis.
        session_type: Tipo da sessão. Use "interactive" para o loop interativo
            ou "single_query" para execuções via argumento CLI.
    """
    try:
        total_cost_usd: float = float(getattr(result_message, "total_cost_usd", None) or 0.0)
        num_turns: int = int(getattr(result_message, "num_turns", None) or 0)
        duration_ms: int = int(getattr(result_message, "duration_ms", None) or 0)

        duration_s: float = round(duration_ms / 1000, 3)
        cost_per_turn: float | None = (
            round(total_cost_usd / num_turns, 6) if num_turns > 0 else None
        )

        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_type": session_type,
            "prompt_preview": _redact_secrets(prompt_preview[:100]),
            "total_cost_usd": total_cost_usd,
            "num_turns": num_turns,
            "duration_ms": duration_ms,
            "duration_s": duration_s,
            "cost_per_turn": cost_per_turn,
        }

        log_line = json.dumps(log_entry, ensure_ascii=False) + "\n"
        log_path = str(SESSIONS_LOG_PATH)

        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_line)

    except OSError as e:
        logger.warning(
            f"Falha ao gravar session log em {SESSIONS_LOG_PATH}: {e}. "
            f"Métricas: type={session_type}, cost={getattr(result_message, 'total_cost_usd', None)}"
        )
    except Exception as e:
        logger.warning(f"Erro inesperado ao persistir métricas de sessão: {e}")


def load_session_history() -> list[dict]:
    """
    Lê o arquivo logs/sessions.jsonl e retorna todas as entradas como lista.

    Ignora linhas malformadas silenciosamente para garantir robustez mesmo
    que o arquivo esteja corrompido parcialmente.

    Returns:
        Lista de dicts com as métricas de cada sessão registrada.
        Retorna lista vazia se o arquivo não existir.
    """
    sessions: list[dict] = []

    if not SESSIONS_LOG_PATH.exists():
        return sessions

    try:
        with open(SESSIONS_LOG_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    sessions.append(json.loads(line))
                except json.JSONDecodeError:
                    # Linha malformada — ignora e continua
                    continue
    except OSError as e:
        logger.warning(f"Falha ao ler session log em {SESSIONS_LOG_PATH}: {e}")

    return sessions


def get_session_summary() -> dict:
    """
    Calcula e retorna um resumo agregado de todas as sessões registradas.

    Agrega métricas por data para facilitar visualização em dashboards.

    Returns:
        Dict com as seguintes chaves:
            total_sessions (int): Número total de sessões registradas.
            total_cost_usd (float): Soma total de custos em USD.
            avg_cost_per_session (float): Custo médio por sessão.
            total_turns (int): Soma total de turns em todas as sessões.
            avg_turns_per_session (float): Média de turns por sessão.
            total_duration_ms (int): Duração total acumulada em milissegundos.
            sessions_by_date (dict[str, int]): Contagem de sessões por data (YYYY-MM-DD).
            cost_by_date (dict[str, float]): Custo total por data (YYYY-MM-DD).
    """
    sessions = load_session_history()
    total_sessions = len(sessions)

    total_cost_usd: float = 0.0
    total_turns: int = 0
    total_duration_ms: int = 0
    sessions_by_date: dict[str, int] = defaultdict(int)
    cost_by_date: dict[str, float] = defaultdict(float)

    for entry in sessions:
        cost = entry.get("total_cost_usd") or 0.0
        turns = entry.get("num_turns") or 0
        duration = entry.get("duration_ms") or 0
        timestamp = entry.get("timestamp", "")

        total_cost_usd += cost
        total_turns += turns
        total_duration_ms += duration

        # Extrai a data (YYYY-MM-DD) do timestamp ISO 8601
        date_key = timestamp[:10] if len(timestamp) >= 10 else "unknown"
        sessions_by_date[date_key] += 1
        cost_by_date[date_key] += cost

    avg_cost_per_session: float = (
        round(total_cost_usd / total_sessions, 6) if total_sessions > 0 else 0.0
    )
    avg_turns_per_session: float = (
        round(total_turns / total_sessions, 2) if total_sessions > 0 else 0.0
    )

    return {
        "total_sessions": total_sessions,
        "total_cost_usd": round(total_cost_usd, 6),
        "avg_cost_per_session": avg_cost_per_session,
        "total_turns": total_turns,
        "avg_turns_per_session": avg_turns_per_session,
        "total_duration_ms": total_duration_ms,
        "sessions_by_date": dict(sessions_by_date),
        "cost_by_date": {k: round(v, 6) for k, v in cost_by_date.items()},
    }
