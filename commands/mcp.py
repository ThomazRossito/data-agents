"""
commands/mcp.py — Slash command /mcp

Exibe o status dos MCP servers configurados no projeto em tempo de execução,
lendo diretamente de validate_platform_credentials() e build_mcp_registry().

Uso:
    /mcp          → tabela com status de todos os MCPs
    /mcp <nome>   → filtra pelo nome do MCP (ex: /mcp tavily)

Importado por main.py (CLI) e ui/chainlit_app.py (Chainlit).
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text


def handle_mcp_command(user_input: str, console: Console) -> None:
    """Exibe status dos MCPs. Aceita filtro opcional: /mcp <nome>."""
    from config.settings import settings

    parts = user_input.strip().split(maxsplit=1)
    filter_name = parts[1].strip().lower() if len(parts) > 1 else ""

    status = settings.validate_platform_credentials()

    always_active = {"context7", "memory_mcp"}

    table = Table(
        title="Status dos MCP Servers",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        expand=False,
    )
    table.add_column("MCP", style="bold", min_width=20)
    table.add_column("Status", justify="center", min_width=8)
    table.add_column("Detalhes", min_width=40)

    active_count = 0
    inactive_count = 0

    for name, info in status.items():
        if name == "anthropic":
            continue
        if filter_name and filter_name not in name.lower():
            continue

        if name in always_active:
            status_cell = Text("● ATIVO", style="bold green")
            detail = Text("Sem credenciais — sempre ativo", style="dim")
            active_count += 1
        elif info["ready"]:
            status_cell = Text("● ATIVO", style="bold green")
            detail = Text("Credenciais configuradas", style="dim green")
            active_count += 1
        else:
            status_cell = Text("○ INATIVO", style="bold red")
            missing = ", ".join(info.get("missing", []))
            detail = Text(f"Falta: {missing}", style="dim red")
            inactive_count += 1

        table.add_row(name, status_cell, detail)

    console.print()
    console.print(table)

    if not filter_name:
        total = active_count + inactive_count
        console.print(
            f"\n  [bold green]{active_count} ativos[/bold green] · "
            f"[red]{inactive_count} inativos[/red] · "
            f"[dim]{total} total[/dim] "
            f"  [dim](configure as chaves ausentes no .env)[/dim]\n"
        )


def handle_mcp_command_chainlit(user_input: str) -> str:
    """Versão Chainlit: retorna Markdown em vez de imprimir com Rich."""
    from config.settings import settings

    parts = user_input.strip().split(maxsplit=1)
    filter_name = parts[1].strip().lower() if len(parts) > 1 else ""

    status = settings.validate_platform_credentials()
    always_active = {"context7", "memory_mcp"}

    lines = ["### Status dos MCP Servers\n"]
    lines.append("| MCP | Status | Detalhes |")
    lines.append("|-----|--------|----------|")

    active_count = 0
    inactive_count = 0

    for name, info in status.items():
        if name == "anthropic":
            continue
        if filter_name and filter_name not in name.lower():
            continue

        if name in always_active:
            status_md = "🟢 ATIVO"
            detail = "Sem credenciais — sempre ativo"
            active_count += 1
        elif info["ready"]:
            status_md = "🟢 ATIVO"
            detail = "Credenciais configuradas"
            active_count += 1
        else:
            status_md = "🔴 INATIVO"
            missing = ", ".join(info.get("missing", []))
            detail = f"Falta: `{missing}`"
            inactive_count += 1

        lines.append(f"| `{name}` | {status_md} | {detail} |")

    total = active_count + inactive_count
    lines.append(
        f"\n**{active_count} ativos** · {inactive_count} inativos · {total} total"
        + (" · configure as chaves ausentes no `.env`" if inactive_count else "")
    )

    return "\n".join(lines)
