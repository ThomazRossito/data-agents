# CLI — Padrões com argparse, Typer e Rich

## argparse — Padrão do Projeto

```python
import argparse
import sys

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Descrição do tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", help="Arquivo de entrada")
    parser.add_argument("--output", "-o", default="-", help="Arquivo de saída (- = stdout)")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem gravar")
    parser.add_argument("--limit", type=int, default=100, metavar="N")
    return parser

def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    # lógica aqui
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

## Typer — CLI Moderno (quando argparse fica verboso)

```python
import typer
from typing import Annotated

app = typer.Typer(help="Descrição do tool")

@app.command()
def run(
    input_file: Annotated[str, typer.Argument(help="Arquivo de entrada")],
    output: Annotated[str, typer.Option("--output", "-o")] = "-",
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    limit: int = 100,
) -> None:
    typer.echo(f"Processando {input_file}")

if __name__ == "__main__":
    app()
```

## Rich — Output de Qualidade

```python
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console(stderr=True)  # separa output de logs

# Tabela
table = Table(title="Resultados", border_style="dim", header_style="bold cyan")
table.add_column("Nome", min_width=20)
table.add_column("Status", justify="center")
table.add_row("pipeline_a", "[green]✓[/green]")
console.print(table)

# Progress bar
with Progress(SpinnerColumn(), TextColumn("{task.description}")) as progress:
    task = progress.add_task("Processando...", total=100)
    for i in range(100):
        progress.advance(task)

# Alerta e erro
console.print("[yellow]⚠️  Aviso:[/yellow] configuração ausente")
console.print("[red]❌ Erro:[/red] falha ao conectar")
```

## Stdin/Stdout/Pipe

```python
import sys

def read_input(source: str) -> str:
    if source == "-":
        if sys.stdin.isatty():
            raise SystemExit("Erro: pipe esperado mas stdin é tty")
        return sys.stdin.read()
    return Path(source).read_text(encoding="utf-8")

def write_output(content: str, dest: str) -> None:
    if dest == "-":
        sys.stdout.write(content)
    else:
        Path(dest).write_text(content, encoding="utf-8")
```

## Confirmação Interativa

```python
def confirm(question: str, default: bool = False) -> bool:
    hint = "S/n" if default else "s/N"
    try:
        answer = input(f"{question} ({hint}): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    if not answer:
        return default
    return answer in ("s", "sim", "y", "yes")
```

## Entry Points em pyproject.toml

```toml
[project.scripts]
meu-tool = "meu_pacote.cli:main"       # argparse/typer: main() retorna int
outro-tool = "meu_pacote.other:app"    # typer: app é instância Typer
```

## Exit Codes Semânticos

```python
# Convenção POSIX — usar em sys.exit() e return main()
EXIT_OK = 0
EXIT_ERROR = 1       # erro genérico
EXIT_USAGE = 2       # argumento inválido (argparse usa 2 automaticamente)
EXIT_INTERRUPTED = 130  # Ctrl+C (128 + SIGINT)
```

## Anti-padrões a Evitar

- ❌ `print()` para mensagens de status — use `console.print()` (rich) ou `logging`
- ❌ `sys.exit()` no meio de funções — retorne int e deixe `main()` chamar
- ❌ `argparse` com `default=None` em campos obrigatórios — use `required=True` explicitamente
- ❌ `shell=True` em subprocess com input do usuário — risco de injeção de comando
- ❌ Capturar `KeyboardInterrupt` sem re-raise ou `sys.exit(130)` — deixa o processo sem encerrar corretamente
