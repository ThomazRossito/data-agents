"""cli.main — Entry point do comando `data-agent`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from rich.console import Console  # noqa: E402
from rich.markdown import Markdown  # noqa: E402

console = Console()


def _lazy_supervisor():
    """Inicializa Supervisor só quando necessário."""
    from agents.supervisor import Supervisor
    return Supervisor()


def cmd_start(args: argparse.Namespace) -> None:
    """Menu interativo."""
    from cli.menu import run_menu
    sup = _lazy_supervisor()
    run_menu(sup)


def cmd_run(args: argparse.Namespace) -> None:
    """Executa arquivo(s) de tarefa."""
    from cli.runner import list_task_files, run_task_file
    from hooks import audit_hook, cost_guard_hook

    target = Path(args.file)
    sup = _lazy_supervisor()

    if target.is_dir():
        files = list_task_files(target)
        if not files:
            console.print(f"[yellow]Nenhum arquivo de tarefa em {target}[/yellow]")
            sys.exit(1)
        for f in files:
            console.print(f"\n[bold]▶ {f.name}[/bold]")
            result = run_task_file(f, sup)
            console.print(Markdown(result.content))
            audit_hook.record("cli:run", str(f), result.tokens_used, result.tool_calls_count)
            cost_guard_hook.track("general", result.tokens_used)
    else:
        if not target.exists():
            console.print(f"[red]Arquivo não encontrado: {target}[/red]")
            sys.exit(1)
        result = run_task_file(target, sup)
        console.print(Markdown(result.content))
        audit_hook.record("cli:run", str(target), result.tokens_used, result.tool_calls_count)
        cost_guard_hook.track("general", result.tokens_used)


def cmd_agent(args: argparse.Namespace) -> None:
    """Atalho direto: data-agent spark "otimizar join"."""
    from hooks import audit_hook, cost_guard_hook, security_hook

    command = args.command
    task = " ".join(args.task)
    user_input = f"/{command} {task}" if not command.startswith("/") else f"{command} {task}"

    ok, reason = security_hook.check_input(user_input)
    if not ok:
        console.print(f"[red]Bloqueado:[/red] {reason}")
        sys.exit(1)

    sup = _lazy_supervisor()
    with console.status("[bold green]Processando..."):
        result = sup.route(user_input)

    audit_hook.record(f"cli:{command}", task, result.tokens_used, result.tool_calls_count)
    cost_guard_hook.track("general", result.tokens_used)
    console.print(Markdown(result.content))

    summary = cost_guard_hook.session_summary()
    console.print(
        f"[dim]tokens: {result.tokens_used} | "
        f"sessão: {summary['total_tokens']} ({summary['budget_pct']}% budget)[/dim]"
    )


def cmd_health(args: argparse.Namespace) -> None:
    """Health check das plataformas."""
    from agents.health import run_health_check
    with console.status("Verificando conectividade..."):
        result = run_health_check()
    console.print(Markdown(result.content))


def cmd_list(args: argparse.Namespace) -> None:
    """Lista agentes disponíveis."""
    from rich.table import Table

    from agents.loader import AGENT_COMMANDS, load_all

    agents = load_all()
    table = Table(title="Agentes disponíveis", show_lines=False)
    table.add_column("Comando", style="cyan")
    table.add_column("Agente", style="white")
    table.add_column("Tier", style="dim")

    cmd_to_agent = {v: k for k, v in AGENT_COMMANDS.items() if not v.startswith("_")}
    for name in sorted(agents):
        agent = agents[name]
        cmd = cmd_to_agent.get(name, "—")
        table.add_row(cmd, name, agent.config.tier)

    console.print(table)


def cmd_tasks(args: argparse.Namespace) -> None:
    """Lista arquivos de tarefa disponíveis."""
    from rich.tree import Tree

    from cli.runner import TASKS_DIR, list_task_files

    files = list_task_files(Path(args.dir) if args.dir else None)
    root = Path(args.dir) if args.dir else TASKS_DIR

    if not files:
        console.print(f"[yellow]Nenhum arquivo de tarefa em {root}[/yellow]")
        return

    tree = Tree(f"📂 {root}")
    folders: dict[str, object] = {}
    for f in files:
        folder_name = f.parent.name
        if folder_name not in folders:
            folders[folder_name] = tree.add(f"📁 {folder_name}/")
        folders[folder_name].add(f"[cyan]{f.name}[/cyan]")  # type: ignore[attr-defined]

    console.print(tree)


# ── Agentes como subcomandos diretos ────────────────────────────────────────

_DIRECT_COMMANDS = {
    "spark", "sql", "pipeline", "quality", "naming", "governance",
    "dbt", "python", "fabric", "lakehouse", "ops", "ai", "devops",
    "geral", "review", "plan", "party",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="data-agent",
        description="data-agents-copilot — orquestrador multi-agente",
    )
    sub = parser.add_subparsers(dest="subcommand")

    # data-agent start
    sub.add_parser("start", help="Menu interativo (padrão sem argumentos)")

    # data-agent run <file|dir>
    p_run = sub.add_parser("run", help="Executar arquivo de tarefa (.yaml / .md)")
    p_run.add_argument("file", help="Caminho para .yaml, .md ou pasta de tarefas")

    # data-agent health
    sub.add_parser("health", help="Verificar conectividade das plataformas")

    # data-agent list
    sub.add_parser("list", help="Listar agentes disponíveis")

    # data-agent tasks
    p_tasks = sub.add_parser("tasks", help="Listar arquivos de tarefa")
    p_tasks.add_argument("--dir", help="Pasta alternativa (padrão: tasks/)")

    # data-agent <agente> "<texto>"
    for cmd in sorted(_DIRECT_COMMANDS):
        p = sub.add_parser(cmd, help=f"Acesso direto ao agente /{cmd}")
        p.add_argument("task", nargs="+", help="Texto da tarefa")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.subcommand is None or args.subcommand == "start":
        cmd_start(args)
    elif args.subcommand == "run":
        cmd_run(args)
    elif args.subcommand == "health":
        cmd_health(args)
    elif args.subcommand == "list":
        cmd_list(args)
    elif args.subcommand == "tasks":
        cmd_tasks(args)
    elif args.subcommand in _DIRECT_COMMANDS:
        args.command = args.subcommand
        cmd_agent(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
