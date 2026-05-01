"""
Parser de Slash Commands para o Data Agents CLI.

As definições de comandos vivem em `config/commands.yaml` — fonte única de verdade.
Este módulo é apenas um loader + parser + help generator.

Uso:
    from commands.parser import parse_command, get_help_text

    result = parse_command("/sql SELECT * FROM tabela")
    if result:
        print(result.agent, result.doma_prompt)
"""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class CommandResult:
    """Resultado do parsing de um slash command."""

    command: str
    agent: str | None
    doma_prompt: str
    doma_mode: str
    display_message: str


@dataclass(frozen=True)
class CommandDefinition:
    """Definição de um slash command carregada do YAML."""

    name: str
    agent: str | None
    doma_mode: str
    description: str
    skills: list[str]
    prompt_template: str
    display_template: str


_COMMANDS_YAML = Path(__file__).resolve().parent.parent / "config" / "commands.yaml"


def _load_registry() -> dict[str, CommandDefinition]:
    with _COMMANDS_YAML.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    registry: dict[str, CommandDefinition] = {}
    for name, cfg in (data.get("commands") or {}).items():
        registry[name] = CommandDefinition(
            name=name,
            agent=cfg.get("agent"),
            doma_mode=cfg["doma_mode"],
            description=cfg["description"],
            skills=list(cfg.get("skills") or []),
            prompt_template=cfg["prompt_template"],
            display_template=cfg["display_template"],
        )
    return registry


COMMAND_REGISTRY: dict[str, CommandDefinition] = _load_registry()


def parse_command(user_input: str) -> CommandResult | None:
    """Parse um slash command. Retorna CommandResult ou None se inválido."""
    if not user_input.startswith("/"):
        return None

    parts = user_input.split(maxsplit=1)
    command_name = parts[0][1:].lower()
    task = parts[1] if len(parts) > 1 else ""

    definition = COMMAND_REGISTRY.get(command_name)
    if definition is None:
        return None

    return CommandResult(
        command=f"/{command_name}",
        agent=definition.agent,
        doma_prompt=definition.prompt_template.format(task=task),
        doma_mode=definition.doma_mode,
        display_message=definition.display_template.format(
            agent=definition.agent or "supervisor",
            task=task,
        ),
    )


def get_help_text() -> str:
    """Gera o texto de ajuda com todos os comandos (Rich markup)."""
    mode_badge = {
        "express": "[yellow]Express[/yellow]",
        "full": "[purple]Full[/purple]",
        "internal": "[cyan]Internal[/cyan]",
    }
    lines = ["[bold]Comandos disponíveis:[/bold]\n"]
    for name, definition in COMMAND_REGISTRY.items():
        badge = mode_badge.get(definition.doma_mode, definition.doma_mode)
        lines.append(f"  [bold green]/{name:<12}[/bold green] {badge:<20} {definition.description}")
    lines.append("")
    lines.append(
        "  [bold green]/help[/bold green]         [dim]Internal[/dim]              Exibe esta ajuda."
    )
    lines.append(
        "  [bold green]/exit[/bold green]         [dim]Internal[/dim]              Encerra a sessão."
    )
    lines.append("")
    lines.append("[bold]Controle de sessão:[/bold]\n")
    lines.append(
        "  [bold cyan]continuar[/bold cyan]     Retoma a sessão anterior a partir do checkpoint salvo."
    )
    lines.append(
        "  [bold cyan]limpar[/bold cyan]        Reseta a sessão atual (salva checkpoint antes)."
    )
    lines.append("  [bold cyan]sair[/bold cyan]          Encerra o Data Agents.")
    lines.append("")
    return "\n".join(lines)
