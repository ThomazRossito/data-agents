"""
commands/sessions.py — Slash command /sessions

Lista sessões registradas no projeto, agregando informação do transcript
(hooks/transcript_hook.py) e do checkpoint (hooks/checkpoint.py).

Uso:
    /sessions          → tabela Rich com as últimas 20 sessões
    /sessions all      → todas as sessões
    /sessions <id>     → detalhes de uma sessão específica

A resume-session propriamente dita é responsabilidade de `/resume` (T4.3);
este módulo cuida apenas de listagem e inspeção.
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table

from hooks.checkpoint import (
    build_resume_prompt,
    list_sessions as list_checkpoint_sessions,
    load_session_by_id,
)
from hooks.transcript_hook import (
    build_resume_prompt_from_transcript,
    list_transcripts,
    load_transcript,
)

_DEFAULT_LIMIT = 20

# Default budget for /resume: 30 turns x 2000 chars = ~15k tokens (~8% of 180k budget).
_RESUME_MAX_TURNS = 30
_RESUME_MAX_CHARS_PER_TURN = 2000


def list_all_sessions() -> list[dict[str, Any]]:
    """
    Unifica sessões registradas em transcript e checkpoint.

    Transcript tem turns e custo acumulado; checkpoint tem o motivo de
    encerramento (budget_exceeded / user_reset / normal_exit / ...). Unimos
    pelo session_id. Entradas com transcript vazio mas com checkpoint ainda
    entram — permitem visualizar sessões antigas que nunca chegaram a gerar
    transcript (criadas antes de T4.1).

    Returns:
        Lista de dicts ordenada por last_timestamp desc.
    """
    transcripts = {t["session_id"]: t for t in list_transcripts()}
    checkpoints = {c["session_id"]: c for c in list_checkpoint_sessions()}

    merged: list[dict[str, Any]] = []
    for sid in set(transcripts) | set(checkpoints):
        t = transcripts.get(sid, {})
        c = checkpoints.get(sid, {})
        last_prompt = t.get("last_user_prompt") or c.get("last_prompt") or ""
        merged.append(
            {
                "session_id": sid,
                "first_timestamp": t.get("first_timestamp") or c.get("timestamp") or "",
                "last_timestamp": t.get("last_timestamp") or c.get("timestamp") or "",
                "turn_count": int(t.get("turn_count") or 0),
                "total_cost_usd": float(t.get("total_cost_usd") or c.get("cost_usd") or 0.0),
                "last_user_prompt": last_prompt[:120],
                "reason": c.get("reason") or "",
                "has_transcript": sid in transcripts,
                "has_checkpoint": sid in checkpoints,
            }
        )

    merged.sort(key=lambda s: s["last_timestamp"], reverse=True)
    return merged


def render_sessions_table(console: Console, limit: int = _DEFAULT_LIMIT) -> int:
    """
    Renderiza uma tabela Rich com as sessões mais recentes.

    Args:
        console: Rich Console onde imprimir.
        limit: Número máximo de linhas a exibir (None/0 = todas).

    Returns:
        Quantidade de sessões exibidas.
    """
    sessions = list_all_sessions()
    if not sessions:
        console.print(
            "[dim]Nenhuma sessão registrada. Arquivos aparecem em "
            "`logs/sessions/<id>.jsonl` após o primeiro turno.[/dim]"
        )
        return 0

    if limit and limit > 0:
        display = sessions[:limit]
    else:
        display = sessions

    table = Table(
        title=f"Sessões registradas ({len(display)}/{len(sessions)})",
        show_lines=False,
        header_style="bold cyan",
    )
    table.add_column("Session ID", style="yellow", no_wrap=True)
    table.add_column("Início", style="dim")
    table.add_column("Última atividade", style="dim")
    table.add_column("Turns", justify="right")
    table.add_column("Custo", justify="right")
    table.add_column("Status", style="magenta")
    table.add_column("Último prompt")

    for s in display:
        status_parts = []
        if s["has_transcript"]:
            status_parts.append("📝")
        if s["has_checkpoint"]:
            status_parts.append(f"💾 {s['reason']}" if s["reason"] else "💾")
        status = " ".join(status_parts) or "—"

        table.add_row(
            s["session_id"],
            (s["first_timestamp"] or "")[:19],
            (s["last_timestamp"] or "")[:19],
            str(s["turn_count"]) if s["turn_count"] else "—",
            f"${s['total_cost_usd']:.4f}",
            status,
            s["last_user_prompt"] or "[dim](sem prompt registrado)[/dim]",
        )

    console.print(table)
    if limit and len(sessions) > limit:
        console.print(
            f"[dim]...e mais {len(sessions) - limit} sessões. "
            f"Use `/sessions all` para ver todas.[/dim]"
        )
    return len(display)


def render_session_details(console: Console, session_id: str) -> bool:
    """
    Exibe o transcript completo de uma sessão.

    Args:
        console: Rich Console.
        session_id: ID da sessão a inspecionar.

    Returns:
        True se a sessão existia; False caso contrário.
    """
    entries = load_transcript(session_id)
    if not entries:
        console.print(
            f"[yellow]Sessão `{session_id}` não encontrada "
            f"(ou sem transcript). Use `/sessions` para listar.[/yellow]"
        )
        return False

    console.print(
        f"[bold cyan]Transcript de `{session_id}` ({len(entries)} entradas)[/bold cyan]\n"
    )
    for entry in entries:
        role = entry.get("role", "?")
        ts = (entry.get("timestamp") or "")[:19]
        content = entry.get("content") or ""
        tools = entry.get("tools_used") or []
        cost = entry.get("cost_usd")

        badge = "[green]👤 User[/green]" if role == "user" else "[blue]🤖 Assistant[/blue]"
        header = f"{badge} [dim]({ts})[/dim]"
        if tools:
            header += f" [dim]— tools: {', '.join(tools[:6])}[/dim]"
        if cost is not None:
            header += f" [dim]— ${cost:.4f}[/dim]"
        console.print(header)

        preview = content if len(content) <= 1000 else content[:1000] + "\n[dim]...(truncado)[/dim]"
        console.print(preview)
        console.print()

    return True


def find_last_session_id() -> str | None:
    """
    Retorna o session_id mais recente disponível (transcript ou checkpoint).

    Returns:
        session_id ou None se não houver nenhuma sessão registrada.
    """
    sessions = list_all_sessions()
    return sessions[0]["session_id"] if sessions else None


def build_resume_prompt_for_session(
    session_id: str,
    max_turns: int = _RESUME_MAX_TURNS,
    max_chars_per_turn: int = _RESUME_MAX_CHARS_PER_TURN,
) -> str | None:
    """
    Constrói o prompt de retomada para uma sessão.

    Prefere o transcript (T4.1) quando existe — reconstrói múltiplos turns do
    histórico. Faz fallback para o checkpoint (hooks/checkpoint.py) quando o
    transcript está vazio, garantindo compatibilidade com sessões legadas.

    Args:
        session_id: ID da sessão.
        max_turns: Número máximo de turns user+assistant a incluir do transcript.
        max_chars_per_turn: Teto de caracteres por turno (respeita context budget).

    Returns:
        String com o prompt pronto para enviar ao Supervisor, ou None se não
        houver dados da sessão (nem transcript nem checkpoint).
    """
    prompt = build_resume_prompt_from_transcript(
        session_id, max_turns=max_turns, max_chars_per_turn=max_chars_per_turn
    )
    if prompt:
        return prompt

    # Fallback: checkpoint-based (sessão sem transcript)
    checkpoint = load_session_by_id(session_id)
    if checkpoint:
        return build_resume_prompt(checkpoint)

    return None


def handle_sessions_command(user_input: str, console: Console) -> None:
    """
    Dispatcher do slash command /sessions.

    Args:
        user_input: String completa digitada pelo usuário (com "/sessions ...").
        console: Rich Console para saída.
    """
    parts = user_input.split(maxsplit=1)
    arg = parts[1].strip() if len(parts) > 1 else ""

    if not arg:
        render_sessions_table(console, limit=_DEFAULT_LIMIT)
        return

    if arg.lower() == "all":
        render_sessions_table(console, limit=0)
        return

    # Qualquer outro argumento é tratado como session_id para inspeção detalhada.
    render_session_details(console, arg)
