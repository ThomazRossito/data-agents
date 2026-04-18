"""
Session Checkpoint — Salvamento e Recuperação de Contexto entre Sessões

Resolve o problema de perda de contexto quando:
  - O budget é excedido (BudgetExceededError)
  - O usuário executa "limpar" para resetar a sessão
  - O idle timeout reseta automaticamente

O checkpoint salva o último prompt, resumo parcial do que foi feito,
artefatos gerados e custo acumulado. Na próxima sessão, o supervisor
pode ler o checkpoint e retomar de onde parou.

Arquivo de checkpoint: logs/checkpoint.json (sobrescrito a cada save).
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import settings

logger = logging.getLogger("data_agents.checkpoint")

CHECKPOINT_PATH: Path = Path(settings.audit_log_path).parent / "checkpoint.json"
SESSIONS_DIR: Path = Path(settings.audit_log_path).parent / "sessions"


def save_checkpoint(
    last_prompt: str,
    reason: str,
    cost_usd: float = 0.0,
    turns: int = 0,
    output_files: list[str] | None = None,
    session_id: str | None = None,
) -> Path:
    """
    Salva um checkpoint da sessão atual para recuperação posterior.

    T1.2: grava dois arquivos:
      - logs/sessions/<session_id>.json — histórico persistente por sessão
      - logs/checkpoint.json             — "mais recente", consumido por load_checkpoint()

    Se `session_id=None`, fallback para "default" (mantém backcompat dos callers antigos
    que ainda não passam session_id).

    Args:
        last_prompt: Último prompt enviado pelo usuário (até 500 chars).
        reason: Motivo do checkpoint ("budget_exceeded", "user_reset", "idle_timeout",
                "normal_exit", "atexit", "signal_*").
        cost_usd: Custo acumulado da sessão até o momento.
        turns: Número de turns completados.
        output_files: Lista de arquivos gerados na sessão (caminhos relativos).
        session_id: ID único da sessão (ex: "cli-abc12345"). Usado para histórico.

    Returns:
        Path do arquivo de checkpoint mais recente (logs/checkpoint.json).
    """
    if output_files is None:
        output_files = _scan_output_files()

    sid = session_id or "default"

    checkpoint: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": sid,
        "reason": reason,
        "last_prompt": last_prompt[:500],
        "cost_usd": cost_usd,
        "turns": turns,
        "output_files": output_files,
        "budget_limit": settings.max_budget_usd,
        "model": settings.default_model,
    }
    payload = json.dumps(checkpoint, ensure_ascii=False, indent=2)

    try:
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        session_path = SESSIONS_DIR / f"{sid}.json"
        session_path.write_text(payload, encoding="utf-8")

        # Espelho "mais recente" em logs/checkpoint.json (backcompat).
        os.makedirs(CHECKPOINT_PATH.parent, exist_ok=True)
        CHECKPOINT_PATH.write_text(payload, encoding="utf-8")

        logger.info(
            f"Checkpoint salvo: session={sid} reason={reason} cost=${cost_usd:.4f} "
            f"turns={turns} files={len(output_files)}"
        )
    except OSError as e:
        logger.warning(f"Falha ao salvar checkpoint: {e}")

    return CHECKPOINT_PATH


def load_checkpoint() -> dict[str, Any] | None:
    """
    Carrega o checkpoint mais recente, se existir.

    Returns:
        Dict com os dados do checkpoint, ou None se não existir.
    """
    if not CHECKPOINT_PATH.exists():
        return None

    try:
        with open(CHECKPOINT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Checkpoint carregado: reason={data.get('reason')}")
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Falha ao ler checkpoint: {e}")
        return None


def clear_checkpoint() -> None:
    """
    Remove o checkpoint "mais recente" (logs/checkpoint.json) após recuperação bem-sucedida.

    O histórico por sessão em logs/sessions/ é preservado — só o ponteiro de "last"
    é limpo para evitar prompt duplicado na próxima abertura.
    """
    if CHECKPOINT_PATH.exists():
        try:
            os.remove(CHECKPOINT_PATH)
            logger.info("Checkpoint consumido e removido.")
        except OSError as e:
            logger.warning(f"Falha ao remover checkpoint: {e}")


def list_sessions() -> list[dict[str, Any]]:
    """
    Lista todos os checkpoints históricos em logs/sessions/, do mais recente ao mais antigo.

    Cada entrada: {"session_id", "timestamp", "reason", "cost_usd", "turns", "last_prompt"}.
    Returns: lista possivelmente vazia (sessão limpa).
    """
    if not SESSIONS_DIR.exists():
        return []

    results: list[dict[str, Any]] = []
    for path in SESSIONS_DIR.glob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            results.append(
                {
                    "session_id": data.get("session_id", path.stem),
                    "timestamp": data.get("timestamp", ""),
                    "reason": data.get("reason", "unknown"),
                    "cost_usd": data.get("cost_usd", 0.0),
                    "turns": data.get("turns", 0),
                    "last_prompt": (data.get("last_prompt") or "")[:120],
                }
            )
        except (json.JSONDecodeError, OSError) as e:
            logger.debug(f"Sessão inválida {path}: {e}")

    results.sort(key=lambda s: s["timestamp"], reverse=True)
    return results


def load_session_by_id(session_id: str) -> dict[str, Any] | None:
    """Carrega um checkpoint específico do histórico por session_id."""
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Falha ao carregar sessão {session_id}: {e}")
        return None


def build_resume_prompt(checkpoint: dict[str, Any]) -> str:
    """
    Constrói um prompt de resumo para o supervisor retomar a sessão anterior.

    O prompt é injetado automaticamente na próxima sessão como contexto
    para que o supervisor saiba o que foi feito e o que falta.

    Args:
        checkpoint: Dict carregado via load_checkpoint().

    Returns:
        String formatada para injeção como prompt do supervisor.
    """
    reason_labels = {
        "budget_exceeded": "o orçamento da sessão foi excedido",
        "user_reset": "o usuário resetou a sessão",
        "idle_timeout": "a sessão expirou por inatividade",
        "normal_exit": "o usuário encerrou a sessão normalmente",
        "atexit": "o processo encerrou (fallback atexit)",
        "signal_sigterm": "o processo recebeu SIGTERM",
        "signal_sighup": "o processo recebeu SIGHUP",
        "abnormal_exit": "a sessão terminou abruptamente",
    }

    reason = checkpoint.get("reason", "unknown")
    reason_text = reason_labels.get(reason, reason)

    prompt = checkpoint.get("last_prompt", "")
    cost = checkpoint.get("cost_usd", 0)
    turns = checkpoint.get("turns", 0)
    files = checkpoint.get("output_files", [])
    ts = checkpoint.get("timestamp", "")

    parts = [
        "## Contexto da Sessão Anterior (Checkpoint Automático)\n",
        f"A sessão anterior foi interrompida porque **{reason_text}**.",
        f"- **Timestamp**: {ts[:19]}",
        f"- **Custo acumulado**: ${cost:.4f}",
        f"- **Turns completados**: {turns}",
        f"- **Último prompt do usuário**: {prompt}" if prompt else "",
    ]

    if files:
        parts.append(f"\n**Arquivos gerados na sessão anterior** ({len(files)}):")
        for f_path in files[:20]:  # Limita a 20 para não poluir
            parts.append(f"  - `{f_path}`")

    parts.append(
        "\n**Instrução**: "
        "1. Leia AGORA os arquivos listados acima (especialmente os de `output/`) usando a tool Read. "
        "2. Com base no conteúdo lido, determine objetivamente: o trabalho estava CONCLUÍDO ou INCOMPLETO? "
        "3. Responda ao usuário em UMA mensagem direta: "
        "'✅ Trabalho concluído: <o que foi entregue>' OU "
        "'🔄 Trabalho incompleto: <o que foi feito> / <o que falta>'. "
        "Não faça perguntas. Não liste opções genéricas. Vá direto ao ponto."
    )

    return "\n".join(p for p in parts if p)


def _scan_output_files() -> list[str]:
    """Varre o diretório output/ para listar arquivos gerados."""
    output_dir = Path(settings.audit_log_path).parent.parent / "output"
    if not output_dir.exists():
        return []

    files: list[str] = []
    try:
        for f in sorted(output_dir.rglob("*")):
            if f.is_file() and not f.name.startswith("."):
                files.append(str(f.relative_to(output_dir.parent)))
    except OSError:
        pass

    return files
