"""
Parser de Slash Commands para o Data Agents CLI.

Implementa:
  - Registry extensível de comandos com metadata
  - Parsing robusto com validação de argumentos
  - Help automático baseado no registry
  - Integração com BMAD Method (Express, Full, Auto)

Uso:
    from commands.parser import parse_command, get_help_text

    result = parse_command("/sql SELECT * FROM tabela")
    if result:
        print(result.agent, result.bmad_prompt)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    """Resultado do parsing de um slash command."""

    command: str
    """Nome do comando (ex: '/sql', '/plan')."""

    agent: str | None
    """Nome do agente alvo (ex: 'sql-expert'). None para comandos internos."""

    bmad_prompt: str
    """Prompt BMAD formatado para enviar ao Supervisor."""

    bmad_mode: str
    """Modo BMAD: 'express', 'full', 'auto' ou 'internal'."""

    display_message: str
    """Mensagem para exibir no console (Rich markup)."""


@dataclass(frozen=True)
class CommandDefinition:
    """Definição de um slash command no registry."""

    name: str
    """Nome do comando (sem /)."""

    agent: str | None
    """Agente alvo. None para comandos internos."""

    bmad_mode: str
    """Modo BMAD: 'express', 'full', 'auto' ou 'internal'."""

    description: str
    """Descrição para o help."""

    skills: list[str]
    """Skills que o agente deve ler antes de executar."""

    prompt_template: str
    """Template do prompt BMAD. {task} será substituído pela tarefa do usuário."""

    display_template: str
    """Template da mensagem de console. {agent} será substituído."""


# ─── Registry de Comandos ─────────────────────────────────────────

COMMAND_REGISTRY: dict[str, CommandDefinition] = {
    "sql": CommandDefinition(
        name="sql",
        agent="sql-expert",
        bmad_mode="express",
        description="Envia tarefa SQL diretamente para o SQL Expert (BMAD Express).",
        skills=["skills/sql_generation.md"],
        prompt_template=(
            "[BMAD EXPRESS] Delegue IMEDIATAMENTE para sql-expert. "
            "Não crie PRD, não peça aprovação. "
            "Instrua o agente a ler as skills relevantes do seu Mapa de Skills "
            "antes de gerar código. Tarefa: {task}"
        ),
        display_template="[bold yellow]🚀 [BMAD Express] Direcionando para: {agent}[/bold yellow]",
    ),
    "spark": CommandDefinition(
        name="spark",
        agent="spark-expert",
        bmad_mode="express",
        description="Envia tarefa PySpark diretamente para o Spark Expert (BMAD Express).",
        skills=["skills/databricks/databricks-spark-declarative-pipelines/SKILL.md"],
        prompt_template=(
            "[BMAD EXPRESS] Delegue IMEDIATAMENTE para spark-expert. "
            "Não crie PRD, não peça aprovação. "
            "Instrua o agente a ler as skills relevantes do seu Mapa de Skills "
            "antes de gerar código. Tarefa: {task}"
        ),
        display_template="[bold yellow]🚀 [BMAD Express] Direcionando para: {agent}[/bold yellow]",
    ),
    "pipeline": CommandDefinition(
        name="pipeline",
        agent="pipeline-architect",
        bmad_mode="express",
        description="Envia tarefa de pipeline para o Pipeline Architect (BMAD Express).",
        skills=["skills/pipeline_design.md"],
        prompt_template=(
            "[BMAD EXPRESS] Delegue IMEDIATAMENTE para pipeline-architect. "
            "Não crie PRD, não peça aprovação. "
            "Instrua o agente a ler as skills relevantes do seu Mapa de Skills "
            "antes de gerar código. Tarefa: {task}"
        ),
        display_template="[bold yellow]🚀 [BMAD Express] Direcionando para: {agent}[/bold yellow]",
    ),
    "fabric": CommandDefinition(
        name="fabric",
        agent="pipeline-architect",
        bmad_mode="express",
        description="Envia tarefa Fabric para o Pipeline Architect com contexto Fabric (BMAD Express).",
        skills=[
            "skills/fabric/fabric-medallion/SKILL.md",
            "skills/fabric/fabric-direct-lake/SKILL.md",
            "skills/fabric/fabric-data-factory/SKILL.md",
        ],
        prompt_template=(
            "[BMAD EXPRESS] Delegue IMEDIATAMENTE para pipeline-architect. "
            "Não crie PRD, não peça aprovação. "
            "Instrua o agente a ler as skills de Fabric "
            "(skills/fabric/) antes de gerar código. "
            "Use os MCP tools do Fabric (fabric, fabric_community, fabric_rti). "
            "Tarefa: {task}"
        ),
        display_template="[bold yellow]🚀 [BMAD Express] Direcionando para: {agent} (Fabric)[/bold yellow]",
    ),
    "plan": CommandDefinition(
        name="plan",
        agent=None,
        bmad_mode="full",
        description="Inicia o fluxo BMAD completo com PRD e aprovação.",
        skills=[],
        prompt_template=(
            "Como Product Manager/Arquiteto (BMAD Passo 1), você deve criar um PRD completo para a tarefa abaixo. "
            "ANTES de escrever qualquer linha do PRD, use a ferramenta Read para ler os skills relevantes: "
            "(1) Identifique o tipo de tarefa (SDP, Structured Streaming, Jobs, Fabric Lakehouse, RTI, etc). "
            "(2) Consulte o Mapa de Skills no seu system prompt para decidir quais SKILL.md ler. "
            "(3) Leia TODOS os skills identificados antes de começar o PRD. "
            "(4) Crie um PRD detalhado em `output/prd_<nome_descritivo>.md` usando Bash, incluindo: "
            "arquitetura Medallion moderna (Bronze→Silver→Gold), padrões obrigatórios por camada, "
            "agentes a acionar e ordem de execução. "
            "Se a tarefa envolver Star Schema ou Gold Layer com dim_*/fact_*, inclua no PRD as regras de "
            "`skills/star_schema_design.md`: autonomia das dimensões, geração sintética de dim_data via SEQUENCE, "
            "e INNER JOIN obrigatório nas fact_*. "
            "(5) Apresente o resumo do PRD e aguarde aprovação antes de delegar. "
            "Tarefa: {task}"
        ),
        display_template="[bold purple]🗺️ [BMAD Agile] Iniciando Context Engineering — lendo skills relevantes...[/bold purple]",
    ),
    "health": CommandDefinition(
        name="health",
        agent=None,
        bmad_mode="internal",
        description="Verifica a conectividade com as plataformas configuradas.",
        skills=[],
        prompt_template=(
            "Execute um diagnóstico de conectividade: "
            "(1) Verifique quais plataformas MCP estão configuradas e acessíveis. "
            "(2) Para Databricks: tente listar catálogos via mcp__databricks__list_catalogs. "
            "(3) Para Fabric: tente listar workspaces via mcp__fabric__list_workspaces. "
            "(4) Para Fabric RTI: tente listar databases via mcp__fabric_rti__kusto_list_databases. "
            "(5) Apresente um relatório de status de cada plataforma."
        ),
        display_template="[bold cyan]🏥 [Health Check] Verificando conectividade das plataformas...[/bold cyan]",
    ),
    "status": CommandDefinition(
        name="status",
        agent=None,
        bmad_mode="internal",
        description="Lista PRDs gerados e status da sessão atual.",
        skills=[],
        prompt_template=(
            "Liste todos os arquivos PRD existentes na pasta output/ usando Glob e Read. "
            "Para cada PRD encontrado, mostre: nome do arquivo, data de criação, "
            "e as primeiras 5 linhas do conteúdo. "
            "Se a pasta output/ não existir ou estiver vazia, informe que nenhum PRD foi gerado."
        ),
        display_template="[bold cyan]📋 [Status] Consultando PRDs e estado da sessão...[/bold cyan]",
    ),
    "review": CommandDefinition(
        name="review",
        agent=None,
        bmad_mode="internal",
        description="Revisita um PRD existente sem recriar do zero.",
        skills=[],
        prompt_template=(
            "Leia o PRD mais recente da pasta output/ (ou o PRD especificado: {task}). "
            "Apresente um resumo do PRD e pergunte ao usuário se deseja: "
            "(1) Continuar a implementação a partir deste PRD, "
            "(2) Modificar algum aspecto da arquitetura, ou "
            "(3) Descartar e criar um novo PRD."
        ),
        display_template="[bold purple]🔄 [Review] Revisitando PRD existente...[/bold purple]",
    ),
    "quality": CommandDefinition(
        name="quality",
        agent="data-quality-steward",
        bmad_mode="express",
        description="Envia tarefa de qualidade de dados para o Data Quality Steward (BMAD Express).",
        skills=["kb/data-quality/index.md", "skills/data_quality.md"],
        prompt_template=(
            "[BMAD EXPRESS] Delegue IMEDIATAMENTE para data-quality-steward. "
            "Não crie PRD, não peça aprovação. "
            "Instrua o agente a ler `kb/data-quality/index.md` antes de executar. "
            "Tarefa: {task}"
        ),
        display_template="[bold yellow]🔍 [BMAD Express] Direcionando para: {agent}[/bold yellow]",
    ),
    "governance": CommandDefinition(
        name="governance",
        agent="governance-auditor",
        bmad_mode="express",
        description="Envia tarefa de governança para o Governance Auditor (BMAD Express).",
        skills=["kb/governance/index.md"],
        prompt_template=(
            "[BMAD EXPRESS] Delegue IMEDIATAMENTE para governance-auditor. "
            "Não crie PRD, não peça aprovação. "
            "Instrua o agente a ler `kb/governance/index.md` antes de executar. "
            "Tarefa: {task}"
        ),
        display_template="[bold yellow]🔐 [BMAD Express] Direcionando para: {agent}[/bold yellow]",
    ),
    "semantic": CommandDefinition(
        name="semantic",
        agent="semantic-modeler",
        bmad_mode="express",
        description="Envia tarefa de modelagem semântica para o Semantic Modeler (BMAD Express).",
        skills=["kb/semantic-modeling/index.md", "skills/fabric/fabric-direct-lake/SKILL.md"],
        prompt_template=(
            "[BMAD EXPRESS] Delegue IMEDIATAMENTE para semantic-modeler. "
            "Não crie PRD, não peça aprovação. "
            "Instrua o agente a ler `kb/semantic-modeling/index.md` antes de executar. "
            "Tarefa: {task}"
        ),
        display_template="[bold yellow]📊 [BMAD Express] Direcionando para: {agent}[/bold yellow]",
    ),
}


def parse_command(user_input: str) -> CommandResult | None:
    """
    Faz o parsing de um slash command e retorna o resultado formatado.

    Args:
        user_input: Input do usuário (ex: '/sql SELECT * FROM tabela').

    Returns:
        CommandResult se for um slash command válido, None caso contrário.
    """
    if not user_input.startswith("/"):
        return None

    # Separar comando e tarefa
    parts = user_input.split(maxsplit=1)
    command_name = parts[0][1:].lower()  # Remove o '/'
    task = parts[1] if len(parts) > 1 else ""

    if command_name not in COMMAND_REGISTRY:
        return None

    definition = COMMAND_REGISTRY[command_name]

    return CommandResult(
        command=f"/{command_name}",
        agent=definition.agent,
        bmad_prompt=definition.prompt_template.format(task=task),
        bmad_mode=definition.bmad_mode,
        display_message=definition.display_template.format(
            agent=definition.agent or "supervisor"
        ),
    )


def get_help_text() -> str:
    """
    Gera o texto de ajuda com todos os comandos disponíveis.

    Returns:
        String formatada com Rich markup para exibição no console.
    """
    lines = ["[bold]Comandos disponíveis:[/bold]\n"]

    for name, definition in COMMAND_REGISTRY.items():
        mode_badge = {
            "express": "[yellow]Express[/yellow]",
            "full": "[purple]Full[/purple]",
            "internal": "[cyan]Internal[/cyan]",
        }.get(definition.bmad_mode, definition.bmad_mode)

        lines.append(
            f"  [bold green]/{name:<12}[/bold green] {mode_badge:<20} {definition.description}"
        )

    lines.append("")
    lines.append("  [bold green]/help[/bold green]         [dim]Internal[/dim]              Exibe esta ajuda.")
    lines.append("  [bold green]/exit[/bold green]         [dim]Internal[/dim]              Encerra a sessão.")
    lines.append("")

    return "\n".join(lines)
