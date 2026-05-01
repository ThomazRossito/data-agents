"""
commands/eval.py — Loop de avaliação de qualidade por sessão.

Pergunta ao usuário uma nota ao final de cada sessão e persiste em
logs/evals.jsonl para análise futura de qualidade por agente/comando.

Importado por:
  - main.py           (CLI — pergunta antes de on_session_end)
  - ui/chainlit_app.py (Chainlit — react action com estrelas)
  - commands/mcp.py   (não — independente)

Formato do registro em logs/evals.jsonl:
  {
    "session_id": "...",
    "timestamp": "2026-05-01T12:00:00Z",
    "rating": 4,           # 1–5
    "comment": "...",      # opcional
    "session_type": "...", # interactive | /plan | /sql | etc.
    "cost_usd": 0.08,
    "turns": 12
  }
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("data_agents.eval")

_EVALS_PATH = Path(__file__).parent.parent / "logs" / "evals.jsonl"


def save_eval(
    session_id: str,
    rating: int,
    comment: str = "",
    session_type: str = "interactive",
    cost_usd: float = 0.0,
    turns: int = 0,
) -> None:
    """Persiste uma avaliação em logs/evals.jsonl."""
    _EVALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "rating": rating,
        "comment": comment,
        "session_type": session_type,
        "cost_usd": round(cost_usd, 6),
        "turns": turns,
    }
    with _EVALS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    logger.info(f"[eval] sessão={session_id} rating={rating}/5")


def load_evals() -> list[dict]:
    """Lê todos os registros de avaliação."""
    if not _EVALS_PATH.exists():
        return []
    records = []
    with _EVALS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def get_eval_summary() -> dict:
    """Resumo agregado das avaliações para o /eval command."""
    records = load_evals()
    if not records:
        return {"total": 0, "avg_rating": 0.0, "by_type": {}}

    total = len(records)
    avg = sum(r["rating"] for r in records) / total

    by_type: dict[str, dict] = {}
    for r in records:
        t = r.get("session_type", "unknown")
        if t not in by_type:
            by_type[t] = {"count": 0, "sum": 0}
        by_type[t]["count"] += 1
        by_type[t]["sum"] += r["rating"]

    return {
        "total": total,
        "avg_rating": round(avg, 2),
        "by_type": {
            t: {"count": v["count"], "avg": round(v["sum"] / v["count"], 2)}
            for t, v in sorted(by_type.items(), key=lambda x: -x[1]["count"])
        },
    }


def prompt_eval_cli(
    console,  # rich.console.Console
    session_id: str,
    session_type: str = "interactive",
    cost_usd: float = 0.0,
    turns: int = 0,
) -> None:
    """
    Exibe o prompt de avaliação no CLI e salva o resultado.
    Não bloqueia se o usuário pressionar Enter sem digitar nada.
    """
    try:
        console.print(
            "\n[dim]Como foi esta sessão? "
            "[[bold]1[/bold]-[bold]5[/bold] ou Enter para pular][/dim] ",
            end="",
        )
        raw = input().strip()
        if not raw:
            return
        rating = int(raw)
        if not 1 <= rating <= 5:
            return

        console.print("[dim]Comentário opcional (Enter para pular):[/dim] ", end="")
        comment = input().strip()

        save_eval(
            session_id=session_id,
            rating=rating,
            comment=comment,
            session_type=session_type,
            cost_usd=cost_usd,
            turns=turns,
        )
        stars = "★" * rating + "☆" * (5 - rating)
        console.print(f"[dim]Avaliação registrada: {stars} ({rating}/5)[/dim]\n")
    except (ValueError, EOFError, KeyboardInterrupt):
        pass


def handle_eval_command(user_input: str, console) -> None:
    """Handler do /eval command — exibe resumo das avaliações."""
    summary = get_eval_summary()

    if summary["total"] == 0:
        console.print("[dim]Nenhuma avaliação registrada ainda.[/dim]")
        console.print(
            "[dim]As avaliações são coletadas ao encerrar cada sessão (sair/exit).[/dim]\n"
        )
        return

    from rich.table import Table

    table = Table(
        title=f"Avaliações de Qualidade — {summary['total']} sessões",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
    )
    table.add_column("Comando/Tipo", style="bold", min_width=20)
    table.add_column("Sessões", justify="right", min_width=8)
    table.add_column("Média", justify="center", min_width=10)
    table.add_column("Stars", min_width=12)

    for stype, stats in summary["by_type"].items():
        avg = stats["avg"]
        filled = round(avg)
        stars = "★" * filled + "☆" * (5 - filled)
        color = "green" if avg >= 4 else "yellow" if avg >= 3 else "red"
        table.add_row(
            stype,
            str(stats["count"]),
            f"[{color}]{avg:.1f}[/{color}]",
            f"[{color}]{stars}[/{color}]",
        )

    console.print()
    console.print(table)
    avg_all = summary["avg_rating"]
    filled_all = round(avg_all)
    console.print(
        f"\n  Média geral: [bold]{'★' * filled_all}{'☆' * (5 - filled_all)}[/bold] "
        f"([bold]{avg_all:.1f}[/bold]/5.0)\n"
    )
