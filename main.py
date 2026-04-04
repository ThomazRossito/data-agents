"""
Data Agents — Entry Point Principal

Sistema Multi-Agentes para Engenharia e Análise de Dados.
Suporta dois modos:
  - Interativo: loop de chat no terminal
  - Single-query: executa um único prompt (passado como argumento CLI)

Uso:
  python main.py                          # modo interativo
  python main.py "Analise a tabela X"     # single-query
"""

import asyncio
import sys
from typing import AsyncIterator

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from claude_agent_sdk import (
    ClaudeSDKClient,
    query,
    AssistantMessage,
    ResultMessage,
    TextBlock,
)

from agents.supervisor import build_supervisor_options

console = Console()


def print_banner() -> None:
    banner = Text()
    banner.append("  DATA AGENTS\n", style="bold cyan")
    banner.append("  Sistema Multi-Agentes · Databricks + Microsoft Fabric\n", style="dim")
    banner.append("  Powered by Claude Agent SDK + MCP\n\n", style="dim")

    # Novos créditos adicionados
    banner.append("  Desenvolvido por: \n", style="bold cyan")
    banner.append("  Thomaz Antonio Rossito Neto\n", style="bold")
    banner.append("  Specialist Data & AI Solutions Architect | Center of Excellence CoE @CI&T\n", style="dim")
    # Adicionando o LinkedIn
    banner.append("  LinkedIn: ", style="bold")
    banner.append("https://www.linkedin.com/in/thomaz-antonio-rossito-neto/\n", style="dim")
    # Adicionando o GitHub
    banner.append("  GitHub: ", style="bold")
    banner.append("https://github.com/ThomazRossito/\n", style="dim")
    console.print(Panel(banner, border_style="cyan"))
    console.print()
    console.print("[dim]Digite sua solicitação em linguagem natural.[/dim]")
    console.print("[dim]Comandos: [bold]sair[/bold] para encerrar | [bold]limpar[/bold] para nova sessão[/dim]\n")


async def run_interactive() -> None:
    """Loop interativo com histórico de sessão mantido entre mensagens."""
    print_banner()
    options = build_supervisor_options()

    async with ClaudeSDKClient(options=options) as client:
        while True:
            try:
                user_input = console.input("[bold green]Você:[/bold green] ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ("sair", "exit", "quit", "q"):
                    console.print("\n[bold cyan]Encerrando sessão. Até a próxima![/bold cyan]")
                    break

                if user_input.lower() in ("limpar", "clear", "reset"):
                    console.clear()
                    print_banner()
                    # Reconnecta para nova sessão
                    await client.disconnect()
                    await client.connect()
                    continue

                console.print()

                # --- BMAD-METHOD: Slash Commands Parsing ---
                override_agent = None
                bmad_prompt = user_input

                if user_input.startswith("/sql "):
                    override_agent = "data_modeling_agent"
                    bmad_prompt = f"IGNORE PLANEJAMENTO E PASSE ISSO DIRETAMENTE PARA O data_modeling_agent: {user_input[5:]}"
                    console.print(f"[bold yellow]🚀 [BMAD Express] Direcionando para: {override_agent}...[/bold yellow]")

                elif user_input.startswith("/spark "):
                    override_agent = "data_engineering_agent"
                    bmad_prompt = f"IGNORE PLANEJAMENTO E PASSE ISSO DIRETAMENTE PARA O data_engineering_agent: {user_input[7:]}"
                    console.print(f"[bold yellow]🚀 [BMAD Express] Direcionando para: {override_agent}...[/bold yellow]")

                elif user_input.startswith("/plan "):
                    # Força a criação de um PRD
                    bmad_prompt = f"Como Product Manager, crie um PRD detalhado na pasta `output/` usando a ferramenta Bash para a seguinte task e valide comigo antes de acionar qualquer agente especialista: {user_input[6:]}"
                    console.print("[bold purple]🗺️ [BMAD Agile] Iniciando sessão de Context Engineering...[/bold purple]")

                await client.query(bmad_prompt)

                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock) and block.text.strip():
                                console.print("[bold blue]Agente:[/bold blue]")
                                console.print(Markdown(block.text))
                                console.print()

                    elif isinstance(message, ResultMessage):
                        parts = []
                        if message.total_cost_usd:
                            parts.append(f"Custo: ${message.total_cost_usd:.4f}")
                        if message.num_turns:
                            parts.append(f"Turns: {message.num_turns}")
                        if message.duration_ms:
                            parts.append(f"Tempo: {message.duration_ms / 1000:.1f}s")
                        if parts:
                            console.print(f"[dim]💰 {' | '.join(parts)}[/dim]\n")

            except KeyboardInterrupt:
                console.print("\n[yellow]Interrompido. Digite 'sair' para encerrar.[/yellow]")
                continue
            except Exception as e:
                console.print(f"\n[bold red]Erro:[/bold red] {e}\n")
                continue


async def run_single_query(prompt: str) -> None:
    """Executa uma única solicitação e exibe o resultado."""
    options = build_supervisor_options()

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    console.print(Markdown(block.text))

        elif isinstance(message, ResultMessage):
            if message.result:
                console.print(f"\n[dim]Resultado finalizado. Custo: ${message.total_cost_usd or 0:.4f}[/dim]")


def main() -> None:
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        asyncio.run(run_single_query(prompt))
    else:
        asyncio.run(run_interactive())


if __name__ == "__main__":
    main()
