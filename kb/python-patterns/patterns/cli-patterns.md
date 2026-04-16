# Padrões de CLIs com Typer e Rich

## Estrutura de CLI com Typer

```python
# cli.py
from __future__ import annotations
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

app = typer.Typer(
    name="data-cli",
    help="Ferramenta de engenharia de dados.",
    no_args_is_help=True,
)
console = Console()
```

## Subcomandos (App Groups)

```python
pipeline_app = typer.Typer(help="Gerenciamento de pipelines.")
app.add_typer(pipeline_app, name="pipeline")

@pipeline_app.command("run")
def pipeline_run(
    name: str = typer.Argument(help="Nome do pipeline"),
    env: str = typer.Option("dev", "--env", "-e", help="Ambiente alvo"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulação sem execução"),
) -> None:
    """Executa um pipeline de dados."""
    if dry_run:
        console.print(f"[yellow]DRY RUN:[/] Would run '{name}' in '{env}'")
        return
    with Progress(SpinnerColumn(), TextColumn("{task.description}")) as progress:
        task = progress.add_task(f"Running {name}...", total=None)
        run_pipeline(name, env)
        progress.update(task, completed=True)
    console.print(f"[green]✓[/] Pipeline '{name}' completed.")

@pipeline_app.command("list")
def pipeline_list(
    env: str = typer.Option("dev", "--env", "-e"),
    format: str = typer.Option("table", "--format", "-f",
                               help="Formato de saída: table, json, csv"),
) -> None:
    """Lista pipelines disponíveis."""
    pipelines = get_pipelines(env)

    if format == "json":
        import json
        console.print_json(json.dumps([p.dict() for p in pipelines]))
        return

    table = Table(title=f"Pipelines — {env}")
    table.add_column("Name", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Last Run")
    for p in pipelines:
        table.add_row(p.name, p.status, p.last_run)
    console.print(table)
```

## Callbacks de Validação

```python
def validate_env(value: str) -> str:
    allowed = {"dev", "staging", "prod"}
    if value not in allowed:
        raise typer.BadParameter(f"Must be one of: {', '.join(allowed)}")
    return value

@app.command()
def deploy(
    env: str = typer.Argument(callback=validate_env),
) -> None:
    ...
```

## Prompt Interativo

```python
@app.command()
def init(
    name: str = typer.Option(None, prompt="Project name"),
    force: bool = typer.Option(False, "--force", "-f",
                               help="Overwrite if exists"),
) -> None:
    if not force and project_exists(name):
        typer.confirm(f"Project '{name}' exists. Overwrite?", abort=True)
    create_project(name)
```

## Rich — Output Estruturado

```python
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.tree import Tree

console = Console()

# Panel com título
console.print(Panel("[bold]Pipeline Summary[/]", expand=False))

# Código com syntax highlight
code = "SELECT COUNT(*) FROM events WHERE ts > NOW() - INTERVAL 1 DAY"
console.print(Syntax(code, "sql", theme="monokai"))

# Árvore hierárquica
tree = Tree("Pipeline: ingest_events")
bronze = tree.add("[cyan]Bronze")
bronze.add("raw_events (auto_loader)")
silver = tree.add("[green]Silver")
silver.add("events (streaming table)")
console.print(tree)

# Logging via rich handler
import logging
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.INFO,
    handlers=[RichHandler(rich_tracebacks=True)],
    format="%(message)s",
)
log = logging.getLogger(__name__)
```

## Exit Codes e Erros

```python
@app.command()
def check(name: str) -> None:
    result = validate(name)
    if not result.ok:
        console.print(f"[red]✗[/] Validation failed: {result.reason}")
        raise typer.Exit(code=1)    # exit code não-zero para scripts/CI
    console.print("[green]✓[/] Validation passed.")
```

## Regras de Ouro

1. **`no_args_is_help=True`** — evita executar sem argumentos e confundir o usuário.
2. **Subcomandos para CLIs com > 3 comandos** — `pipeline run`, `pipeline list`.
3. **`--format` sempre inclui `json`** — permite integração com `jq` e scripts.
4. **Exit code 1 em erros** — bash e CI esperam código não-zero para detectar falha.
5. **Console separado do app** — não misturar `print()` com `console.print()`.
6. **Validação via callback, não no corpo do comando** — mensagem de erro mais clara.
