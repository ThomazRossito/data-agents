"""
commands/health.py — Slash command /health

Verifica conectividade das plataformas configuradas sem passar pelo Supervisor.
Combina checagem de credenciais com ping TCP leve aos endpoints.
Retorno instantâneo — sem LLM, sem MCP calls.

Uso:
    /health    → tabela de status de todas as plataformas
"""

from __future__ import annotations

import socket
from urllib.parse import urlparse

from rich.console import Console
from rich.table import Table
from rich.text import Text


def _tcp_reachable(host: str, port: int = 443, timeout: float = 3.0) -> bool:
    """Retorna True se conseguir abrir uma conexão TCP ao host:port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _check_url(url: str, timeout: float = 3.0) -> tuple[bool, str]:
    """Faz TCP connect na URL. Retorna (ok, detalhe)."""
    if not url:
        return False, "URL não configurada"
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        ok = _tcp_reachable(host, port, timeout)
        return ok, "TCP OK" if ok else "Conexão recusada / timeout"
    except Exception as exc:
        return False, str(exc)[:60]


def _build_platform_rows() -> tuple[list[dict], int, int, int]:
    """
    Lê credenciais + endpoints e retorna linhas prontas para render.

    Cada linha: {"name", "cred_ok", "reachable", "detail", "missing"}.
    Também retorna contagens (ok, warn, err).
    """
    from config.settings import settings
    from config.mcp_servers import ALWAYS_ACTIVE_MCPS

    cred_status = settings.validate_platform_credentials()
    always_active = set(ALWAYS_ACTIVE_MCPS)

    platform_endpoints: dict[str, str] = {
        "databricks": settings.databricks_host or "",
        "fabric": "https://api.fabric.microsoft.com",
        "fabric_official": "https://api.fabric.microsoft.com",
        "fabric_sql": settings.fabric_sql_endpoint or "",
        "fabric_rti": settings.kusto_service_uri or "",
    }

    rows: list[dict] = []
    ok_count = warn_count = err_count = 0

    for name, info in cred_status.items():
        if name == "anthropic":
            continue

        cred_ok = name in always_active or info.get("ready", False)
        missing_list: list[str] = info.get("missing", [])
        endpoint = platform_endpoints.get(name, "")

        if not cred_ok:
            rows.append(
                {
                    "name": name,
                    "cred_ok": False,
                    "reachable": None,
                    "detail": ", ".join(missing_list) or "Sem credenciais",
                    "missing": missing_list,
                }
            )
            err_count += 1
        elif endpoint:
            reachable, conn_detail = _check_url(endpoint)
            rows.append(
                {
                    "name": name,
                    "cred_ok": True,
                    "reachable": reachable,
                    "detail": "Endpoint alcançável" if reachable else conn_detail[:60],
                    "missing": [],
                }
            )
            if reachable:
                ok_count += 1
            else:
                warn_count += 1
        else:
            rows.append(
                {
                    "name": name,
                    "cred_ok": True,
                    "reachable": True,
                    "detail": "Sem endpoint fixo (credenciais OK)",
                    "missing": [],
                }
            )
            ok_count += 1

    return rows, ok_count, warn_count, err_count


def handle_health_command(console: Console) -> None:
    """Exibe status de conectividade das plataformas. Sem LLM, sem MCP."""
    rows, ok_count, warn_count, err_count = _build_platform_rows()

    table = Table(
        title="Health Check — Plataformas",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        expand=False,
    )
    table.add_column("Plataforma", style="bold", min_width=18)
    table.add_column("Credenciais", justify="center", min_width=12)
    table.add_column("Conectividade", justify="center", min_width=14)
    table.add_column("Detalhes", min_width=36)

    for row in rows:
        cred_cell = Text("✓", style="bold green") if row["cred_ok"] else Text("✗", style="bold red")

        if not row["cred_ok"]:
            conn_cell = Text("—", style="dim")
            detail = Text(row["detail"], style="dim red")
        elif row["reachable"]:
            conn_cell = Text("✓", style="bold green")
            detail = Text(row["detail"], style="dim green")
        else:
            conn_cell = Text("⚠", style="bold yellow")
            detail = Text(row["detail"], style="dim yellow")

        table.add_row(row["name"], cred_cell, conn_cell, detail)

    console.print()
    console.print(table)
    console.print(
        f"\n  [bold green]{ok_count} OK[/bold green] · "
        f"[yellow]{warn_count} avisos[/yellow] · "
        f"[red]{err_count} inativos[/red]\n"
    )


def handle_health_command_chainlit() -> str:
    """Versão Chainlit: retorna Markdown em vez de imprimir com Rich."""
    rows, ok_count, warn_count, err_count = _build_platform_rows()

    lines = ["### Health Check — Plataformas\n"]
    lines.append("| Plataforma | Credenciais | Conectividade | Detalhes |")
    lines.append("|------------|:-----------:|:-------------:|---------|")

    for row in rows:
        cred_md = "✅" if row["cred_ok"] else "❌"
        if not row["cred_ok"]:
            conn_md = "—"
            detail_md = row["detail"]
        elif row["reachable"]:
            conn_md = "✅"
            detail_md = row["detail"]
        else:
            conn_md = "⚠️"
            detail_md = row["detail"]

        lines.append(f"| `{row['name']}` | {cred_md} | {conn_md} | {detail_md} |")

    lines.append("")
    lines.append(f"**{ok_count} OK** · {warn_count} avisos · {err_count} inativos")
    return "\n".join(lines)
