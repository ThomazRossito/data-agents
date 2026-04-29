"""cli.menu — Menu interativo com questionary."""

from __future__ import annotations

from pathlib import Path

import questionary
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()

_AGENT_CHOICES = [
    questionary.Choice("🔮  Supervisor (PRD + delegação)", value="/plan"),
    questionary.Choice("⚡  Spark Expert (PySpark, Delta Lake)", value="/spark"),
    questionary.Choice("🗄️   SQL Expert (queries, modelagem)", value="/sql"),
    questionary.Choice("🔧  Pipeline Architect (ETL/ELT)", value="/pipeline"),
    questionary.Choice("✅  Data Quality (validação, DQX)", value="/quality"),
    questionary.Choice("📛  Naming Guard (convenções)", value="/naming"),
    questionary.Choice("🛡️   Governance Auditor (PII, LGPD)", value="/governance"),
    questionary.Choice("📦  dbt Expert (models, snapshots)", value="/dbt"),
    questionary.Choice("🐍  Python Expert (código, testes)", value="/python"),
    questionary.Choice("🏛️   Fabric Expert (Lakehouse, OneLake)", value="/fabric"),
    questionary.Choice("🏗️   Lakehouse Engineer (implantação, migração)", value="/lakehouse"),
    questionary.Choice("🤖  Databricks AI (MLflow, Genie)", value="/ai"),
    questionary.Choice("⚙️   DevOps Engineer (DABs, CI/CD)", value="/devops"),
    questionary.Choice("💬  Geral (conceitual)", value="/geral"),
    questionary.Choice("🎉  Party Mode (múlti-agente)", value="/party"),
    questionary.Separator(),
    questionary.Choice("📁  Executar arquivo de tarefa (.yaml / .md)", value="_file"),
    questionary.Choice("🏥  Health Check", value="/health"),
    questionary.Choice("📋  Listar agentes", value="_list"),
    questionary.Choice("📂  Listar tasks disponíveis", value="_tasks"),
    questionary.Separator(),
    questionary.Choice("❌  Sair", value="_exit"),
]


def run_menu(supervisor) -> None:
    """Loop principal do menu interativo."""
    from hooks import audit_hook, cost_guard_hook, security_hook

    _print_header(supervisor)

    while True:
        choice = questionary.select(
            "O que você quer fazer?",
            choices=_AGENT_CHOICES,
            use_shortcuts=False,
        ).ask()

        if choice is None or choice == "_exit":
            console.print("\n[dim]Até logo![/dim]")
            break

        elif choice == "_list":
            agents = supervisor.list_agents()
            console.print(Panel(
                "\n".join(f"  • {a}" for a in sorted(agents)),
                title="Agentes disponíveis",
            ))

        elif choice == "_tasks":
            _show_task_list()

        elif choice == "_file":
            _run_file_flow(supervisor)

        elif choice == "/health":
            from agents.health import run_health_check
            with console.status("Verificando..."):
                result = run_health_check()
            console.print(Markdown(result.content))

        else:
            # Agente direto — pede a tarefa
            task = questionary.text(
                f"Tarefa para {choice}:",
                multiline=False,
            ).ask()

            if not task:
                continue

            user_input = f"{choice} {task}"
            ok, reason = security_hook.check_input(user_input)
            if not ok:
                console.print(f"[red]Bloqueado:[/red] {reason}")
                continue

            with console.status("[bold green]Processando..."):
                result = supervisor.route(user_input)

            audit_hook.record(
                agent="menu",
                task=user_input,
                tokens_used=result.tokens_used,
                tool_calls=result.tool_calls_count,
            )
            cost_guard_hook.track("general", result.tokens_used)
            console.print(Markdown(result.content))
            _print_token_summary(result)


def _run_file_flow(supervisor) -> None:
    """Fluxo de seleção e execução de arquivo de tarefa."""
    from cli.runner import TASKS_DIR, list_task_files, run_task_file

    files = list_task_files()
    if not files:
        console.print(f"[yellow]Nenhum arquivo em {TASKS_DIR}. Crie um .yaml ou .md lá.[/yellow]")
        return

    choices = [
        questionary.Choice(
            f"{p.parent.name}/{p.name}" if p.parent != TASKS_DIR else p.name,
            value=p,
        )
        for p in files
    ] + [questionary.Choice("← Voltar", value=None)]

    selected = questionary.select("Selecionar arquivo de tarefa:", choices=choices).ask()
    if not selected:
        return

    console.print(f"[dim]Executando: {selected}[/dim]")
    with console.status("[bold green]Processando..."):
        result = run_task_file(selected, supervisor)

    console.print(Markdown(result.content))
    _print_token_summary(result)


def _show_task_list() -> None:
    from cli.runner import TASKS_DIR, list_task_files

    files = list_task_files()
    if not files:
        console.print(f"[yellow]Pasta {TASKS_DIR} vazia.[/yellow]")
        return

    by_folder: dict[str, list[Path]] = {}
    for f in files:
        folder = f.parent.name
        by_folder.setdefault(folder, []).append(f)

    lines = []
    for folder, fps in sorted(by_folder.items()):
        lines.append(f"\n  **{folder}/**")
        for fp in fps:
            lines.append(f"    • {fp.name}")

    console.print(Panel("\n".join(lines), title=f"Tasks em {TASKS_DIR}"))


def _print_header(supervisor) -> None:
    agents = supervisor.list_agents()
    from config.settings import settings
    d = settings.diagnostics()
    status = " | ".join(f"{k}: {'✓' if v else '✗'}" for k, v in d.items())
    console.print(Panel(
        f"{status}\n[dim]{len(agents)} agentes carregados[/dim]",
        title="🤖 data-agents-copilot",
        expand=False,
    ))


def _print_token_summary(result) -> None:
    from hooks import cost_guard_hook
    summary = cost_guard_hook.session_summary()
    console.print(
        f"[dim]tokens: {result.tokens_used} | "
        f"sessão: {summary['total_tokens']} ({summary['budget_pct']}% budget)[/dim]"
    )
