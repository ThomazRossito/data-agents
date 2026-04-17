"""
Parser de Slash Commands para o Data Agents CLI.

Implementa:
  - Registry extensível de comandos com metadata
  - Parsing robusto com validação de argumentos
  - Help automático baseado no registry
  - Integração com DOMA (Data Orchestration Method for Agents) — modos Express, Full, Auto

Uso:
    from commands.parser import parse_command, get_help_text

    result = parse_command("/sql SELECT * FROM tabela")
    if result:
        print(result.agent, result.doma_prompt)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    """Resultado do parsing de um slash command."""

    command: str
    """Nome do comando (ex: '/sql', '/plan')."""

    agent: str | None
    """Nome do agente alvo (ex: 'sql-expert'). None para comandos internos."""

    doma_prompt: str
    """Prompt DOMA formatado para enviar ao Supervisor."""

    doma_mode: str
    """Modo DOMA: 'express', 'full', 'auto' ou 'internal'."""

    display_message: str
    """Mensagem para exibir no console (Rich markup)."""


@dataclass(frozen=True)
class CommandDefinition:
    """Definição de um slash command no registry."""

    name: str
    """Nome do comando (sem /)."""

    agent: str | None
    """Agente alvo. None para comandos internos."""

    doma_mode: str
    """Modo DOMA: 'express', 'full', 'auto' ou 'internal'."""

    description: str
    """Descrição para o help."""

    skills: list[str]
    """Skills que o agente deve ler antes de executar."""

    prompt_template: str
    """Template do prompt DOMA. {task} será substituído pela tarefa do usuário."""

    display_template: str
    """Template da mensagem de console. {agent} será substituído."""


# ─── Registry de Comandos ─────────────────────────────────────────

COMMAND_REGISTRY: dict[str, CommandDefinition] = {
    "brief": CommandDefinition(
        name="brief",
        agent="business-analyst",
        doma_mode="full",
        description=(
            "Processa transcript de reunião ou briefing e gera backlog estruturado (P0/P1/P2). "
            "Use antes do /plan quando o input for um documento bruto de negócio."
        ),
        skills=["templates/backlog.md"],
        prompt_template=(
            "[DOMA INTAKE] Delegue IMEDIATAMENTE para business-analyst. "
            "NÃO crie PRD, NÃO peça aprovação neste momento. "
            "O agente deve: "
            "(1) Ler o template em `templates/backlog.md` para entender o formato de saída. "
            "(2) Processar o documento abaixo extraindo stakeholders, decisões, requisitos e restrições. "
            "(3) Mapear cada requisito ao domínio técnico correto (Databricks/Fabric/pipelines/SQL/etc). "
            "(4) Priorizar os itens em P0 (crítico, máx 3), P1 (importante) e P2 (desejável). "
            "(5) Garantir que o diretório `output/backlog/` existe (Bash: mkdir -p output/backlog). "
            "(6) Salvar o backlog preenchido em `output/backlog/backlog_<nome_descritivo>.md` via Write. "
            "(7) Apresentar resumo com contagem por prioridade e o próximo passo: "
            "    /plan output/backlog/backlog_<nome_descritivo>.md "
            "IMPORTANTE: Se o input for um caminho de arquivo (ex: inputs/reuniao.txt), "
            "leia o arquivo com Read() antes de processar. "
            "Documento: {task}"
        ),
        display_template="[bold blue]📋 [DOMA Intake] Processando documento com: {agent}[/bold blue]",
    ),
    "sql": CommandDefinition(
        name="sql",
        agent="sql-expert",
        doma_mode="express",
        description="Envia tarefa SQL diretamente para o SQL Expert (DOMA Express).",
        skills=["skills/sql_generation.md"],
        prompt_template=(
            "[DOMA EXPRESS] Delegue IMEDIATAMENTE para sql-expert. "
            "Não crie PRD, não peça aprovação. "
            "Instrua o agente a ler as skills relevantes do seu Mapa de Skills "
            "antes de gerar código. Tarefa: {task}"
        ),
        display_template="[bold yellow]🚀 [DOMA Express] Direcionando para: {agent}[/bold yellow]",
    ),
    "spark": CommandDefinition(
        name="spark",
        agent="spark-expert",
        doma_mode="express",
        description="Envia tarefa PySpark diretamente para o Spark Expert (DOMA Express).",
        skills=["skills/databricks/databricks-spark-declarative-pipelines/SKILL.md"],
        prompt_template=(
            "[DOMA EXPRESS] Delegue IMEDIATAMENTE para spark-expert. "
            "Não crie PRD, não peça aprovação. "
            "Instrua o agente a ler as skills relevantes do seu Mapa de Skills "
            "antes de gerar código. Tarefa: {task}"
        ),
        display_template="[bold yellow]🚀 [DOMA Express] Direcionando para: {agent}[/bold yellow]",
    ),
    "pipeline": CommandDefinition(
        name="pipeline",
        agent="pipeline-architect",
        doma_mode="express",
        description="Envia tarefa de pipeline para o Pipeline Architect (DOMA Express).",
        skills=["skills/pipeline_design.md"],
        prompt_template=(
            "[DOMA EXPRESS] Delegue IMEDIATAMENTE para pipeline-architect. "
            "Não crie PRD, não peça aprovação. "
            "Instrua o agente a ler as skills relevantes do seu Mapa de Skills "
            "antes de gerar código. Tarefa: {task}"
        ),
        display_template="[bold yellow]🚀 [DOMA Express] Direcionando para: {agent}[/bold yellow]",
    ),
    "fabric": CommandDefinition(
        name="fabric",
        agent="pipeline-architect",
        doma_mode="express",
        description="Envia tarefa Fabric para o agente correto (DOMA Express). Roteia automaticamente para semantic-modeler quando a tarefa envolve Semantic Model, Direct Lake, DAX ou Power BI.",
        skills=[
            "skills/fabric/fabric-medallion/SKILL.md",
            "skills/fabric/fabric-direct-lake/SKILL.md",
            "skills/fabric/fabric-data-factory/SKILL.md",
        ],
        prompt_template=(
            "[DOMA EXPRESS — FABRIC] Avalie a tarefa abaixo e delegue IMEDIATAMENTE ao agente correto. "
            "NÃO crie PRD, NÃO peça aprovação. "
            "\n\n⛔ RESTRIÇÃO ABSOLUTA DE PLATAFORMA:\n"
            "Este comando é exclusivo para Microsoft Fabric. "
            "NUNCA use ferramentas Databricks (mcp__databricks__*) neste contexto. "
            "Se as ferramentas Fabric não retornarem dados, reporte o erro claramente — "
            "NUNCA substitua por dados do Databricks. Dados de plataforma errada são inaceitáveis.\n"
            "\nPARA DESCOBERTA DE TABELAS NO LAKEHOUSE (schemas bronze/silver/gold):\n"
            "→ Use PRIMEIRO mcp__fabric_sql__fabric_sql_list_tables() — acessa todos os schemas via SQL Analytics Endpoint.\n"
            "→ Se fabric_sql não estiver disponível, use mcp__fabric_community__list_tables() — mas este só retorna schema dbo.\n"
            "→ Se ambos falharem, informe o erro e oriente o usuário a configurar fabric_sql no .env.\n"
            "\nREGRAS DE ROTEAMENTO (aplique antes de delegar):\n"
            "→ Se a tarefa mencionar: Semantic Model, Direct Lake, Power BI, DAX — "
            "DELEGAR para semantic-modeler.\n"
            "→ Para TODOS os outros casos Fabric (Lakehouse, Data Factory, RTI, Eventhouse, "
            "Bronze/Silver/Gold, tabelas, schemas, pipelines) — "
            "DELEGAR para pipeline-architect ou sql-expert conforme a natureza da tarefa.\n"
            "\nTarefa: {task}"
        ),
        display_template="[bold yellow]🚀 [DOMA Express] Direcionando para: {agent} (Fabric)[/bold yellow]",
    ),
    "plan": CommandDefinition(
        name="plan",
        agent=None,
        doma_mode="full",
        description="Inicia o fluxo DOMA completo com PRD e aprovação.",
        skills=[],
        prompt_template=(
            "Como Product Manager/Arquiteto (DOMA Passo 1), você deve criar um PRD completo para a tarefa abaixo. "
            "ANTES de escrever qualquer linha do PRD, use a ferramenta Read para ler os skills relevantes: "
            "(1) Identifique o tipo de tarefa (SDP, Structured Streaming, Jobs, Fabric Lakehouse, RTI, etc). "
            "(2) Consulte o Mapa de Skills no seu system prompt para decidir quais SKILL.md ler. "
            "(3) Leia TODOS os skills identificados antes de começar o PRD. "
            "(4) Garanta que o diretório `output/prd/` existe (Bash: mkdir -p output/prd). "
            "(5) Crie um PRD detalhado em `output/prd/prd_<nome_descritivo>.md` usando Bash, incluindo: "
            "arquitetura Medallion moderna (Bronze→Silver→Gold), padrões obrigatórios por camada, "
            "agentes a acionar e ordem de execução. "
            "Se a tarefa envolver Star Schema ou Gold Layer com dim_*/fact_*, inclua no PRD as regras de "
            "`skills/star_schema_design.md`: autonomia das dimensões, geração sintética de dim_data via SEQUENCE, "
            "e INNER JOIN obrigatório nas fact_*. "
            "(6) Apresente o resumo do PRD e aguarde aprovação antes de delegar. "
            "Após aprovação: garanta que `output/specs/` existe (mkdir -p output/specs) e salve a SPEC em "
            "`output/specs/spec_<nome_descritivo>.md`. "
            "Tarefa: {task}"
        ),
        display_template="[bold purple]🗺️ [DOMA Agile] Iniciando Context Engineering — lendo skills relevantes...[/bold purple]",
    ),
    "health": CommandDefinition(
        name="health",
        agent=None,
        doma_mode="internal",
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
        doma_mode="internal",
        description="Lista PRDs gerados e status da sessão atual.",
        skills=[],
        prompt_template=(
            "Liste os artefatos gerados nas seguintes pastas usando Glob e Read: "
            "(1) PRDs em `output/prd/` — mostre nome, data e primeiras 5 linhas de cada um. "
            "(2) SPECs em `output/specs/` — mostre nome e primeiras 3 linhas. "
            "(3) Backlogs em `output/backlog/` — mostre nome e prioridades (P0/P1/P2). "
            "Se alguma pasta não existir ou estiver vazia, informe que nenhum artefato foi gerado ainda."
        ),
        display_template="[bold cyan]📋 [Status] Consultando PRDs e estado da sessão...[/bold cyan]",
    ),
    "review": CommandDefinition(
        name="review",
        agent=None,
        doma_mode="internal",
        description="Revisita um PRD existente sem recriar do zero.",
        skills=[],
        prompt_template=(
            "Leia o PRD mais recente da pasta `output/prd/` (ou o PRD especificado: {task}). "
            "Se existir uma SPEC correspondente em `output/specs/`, leia-a também. "
            "Apresente um resumo do PRD e pergunte ao usuário se deseja: "
            "(1) Continuar a implementação a partir deste PRD, "
            "(2) Modificar algum aspecto da arquitetura, ou "
            "(3) Descartar e criar um novo PRD."
        ),
        display_template="[bold purple]🔄 [Review] Revisitando PRD existente...[/bold purple]",
    ),
    "dbt": CommandDefinition(
        name="dbt",
        agent="dbt-expert",
        doma_mode="express",
        description="Envia tarefa dbt diretamente para o dbt Expert (DOMA Express). Use para models, testes, snapshots, seeds, documentação e boas práticas de projeto dbt.",
        skills=["kb/sql-patterns/index.md"],
        prompt_template=(
            "[DOMA EXPRESS] Delegue IMEDIATAMENTE para dbt-expert. "
            "Não crie PRD, não peça aprovação. "
            "Instrua o agente a ler `kb/sql-patterns/index.md` antes de executar "
            "e a buscar documentação atualizada via context7 se necessário. "
            "Tarefa: {task}"
        ),
        display_template="[bold yellow]🛠️ [DOMA Express] Direcionando para: {agent}[/bold yellow]",
    ),
    "quality": CommandDefinition(
        name="quality",
        agent="data-quality-steward",
        doma_mode="express",
        description="Envia tarefa de qualidade de dados para o Data Quality Steward (DOMA Express).",
        skills=["kb/data-quality/index.md", "skills/data_quality.md"],
        prompt_template=(
            "[DOMA EXPRESS] Delegue IMEDIATAMENTE para data-quality-steward. "
            "Não crie PRD, não peça aprovação. "
            "Instrua o agente a ler `kb/data-quality/index.md` antes de executar. "
            "Tarefa: {task}"
        ),
        display_template="[bold yellow]🔍 [DOMA Express] Direcionando para: {agent}[/bold yellow]",
    ),
    "governance": CommandDefinition(
        name="governance",
        agent="governance-auditor",
        doma_mode="express",
        description="Envia tarefa de governança para o Governance Auditor (DOMA Express).",
        skills=["kb/governance/index.md"],
        prompt_template=(
            "[DOMA EXPRESS] Delegue IMEDIATAMENTE para governance-auditor. "
            "Não crie PRD, não peça aprovação. "
            "Instrua o agente a ler `kb/governance/index.md` antes de executar. "
            "Tarefa: {task}"
        ),
        display_template="[bold yellow]🔐 [DOMA Express] Direcionando para: {agent}[/bold yellow]",
    ),
    "semantic": CommandDefinition(
        name="semantic",
        agent="semantic-modeler",
        doma_mode="express",
        description="Envia tarefa de modelagem semântica para o Semantic Modeler (DOMA Express).",
        skills=["kb/semantic-modeling/index.md", "skills/fabric/fabric-direct-lake/SKILL.md"],
        prompt_template=(
            "[DOMA EXPRESS] Delegue IMEDIATAMENTE para semantic-modeler. "
            "Não crie PRD, não peça aprovação. "
            "Instrua o agente a ler `kb/semantic-modeling/index.md` antes de executar. "
            "Tarefa: {task}"
        ),
        display_template="[bold yellow]📊 [DOMA Express] Direcionando para: {agent}[/bold yellow]",
    ),
    "python": CommandDefinition(
        name="python",
        agent="python-expert",
        doma_mode="express",
        description=(
            "Envia tarefa Python diretamente para o Python Expert (DOMA Express). "
            "Use para: pacotes, automação, APIs REST, CLIs, testes pytest, pandas/polars, FastAPI."
        ),
        skills=["kb/python/index.md"],
        prompt_template=(
            "[DOMA EXPRESS] Delegue IMEDIATAMENTE para python-expert. "
            "Não crie PRD, não peça aprovação. "
            "Instrua o agente a buscar documentação atualizada via context7 se necessário "
            "e a seguir PEP 8, type hints e mínimo de dependências externas. "
            "Tarefa: {task}"
        ),
        display_template="[bold yellow]🐍 [DOMA Express] Direcionando para: {agent}[/bold yellow]",
    ),
    "migrate": CommandDefinition(
        name="migrate",
        agent="migration-expert",
        doma_mode="full",
        description=(
            "Inicia assessment e migração de SQL Server ou PostgreSQL para Databricks/Fabric. "
            "Gera PRD de migração com mapeamento de tipos, Medallion e estratégia de cutover. "
            "Exemplos: /migrate sql-server para databricks | /migrate postgres para fabric"
        ),
        skills=["kb/migration/index.md"],
        prompt_template=(
            "[DOMA MIGRATE] Delegue IMEDIATAMENTE para migration-expert. "
            "Não gere SQL diretamente. O agente deve: "
            "(1) Ler `kb/migration/index.md` para regras de mapeamento de tipos e anti-padrões. "
            "(2) Conectar ao banco de origem via migration_source MCP para extrair DDL e estatísticas. "
            "(3) Gerar assessment de complexidade (LOW/MEDIUM/HIGH) por objeto. "
            "(4) Propor arquitetura Medallion Bronze→Silver→Gold no destino. "
            "(5) Salvar o plano de migração em `output/migration/migration_plan_<nome>.md`. "
            "(6) Apresentar resumo e aguardar aprovação antes de gerar scripts. "
            "Tarefa: {task}"
        ),
        display_template="[bold yellow]🚚 [DOMA Migrate] Iniciando assessment com: {agent}[/bold yellow]",
    ),
    "skill": CommandDefinition(
        name="skill",
        agent="skill-updater",
        doma_mode="express",
        description=(
            "Atualiza Skills com documentação recente via context7/tavily/firecrawl. "
            "Exemplos: /skill databricks | /skill fabric | /skill dbt | /skill (atualiza todos)"
        ),
        skills=[],
        prompt_template=(
            "[DOMA EXPRESS] Delegue IMEDIATAMENTE para skill-updater. "
            "Não crie PRD, não peça aprovação. "
            "O agente deve buscar a documentação mais recente para o domínio solicitado "
            "e atualizar ou criar os arquivos SKILL.md correspondentes. "
            "Domínio/tarefa: {task}"
        ),
        display_template="[bold yellow]🔄 [DOMA Express] Atualizando Skills com: {agent}[/bold yellow]",
    ),
    "genie": CommandDefinition(
        name="genie",
        agent="semantic-modeler",
        doma_mode="express",
        description="Cria ou atualiza Genie Spaces no Databricks para Conversational BI (DOMA Express).",
        skills=["kb/semantic-modeling/index.md"],
        prompt_template=(
            "[DOMA EXPRESS — GENIE] Delegue IMEDIATAMENTE para semantic-modeler. "
            "Não crie PRD, não peça aprovação. "
            "O agente deve usar as ferramentas Databricks Genie (mcp__databricks_genie__*) "
            "para criar ou atualizar o Genie Space conforme solicitado. "
            "Instrua o agente a ler `kb/semantic-modeling/index.md` antes de executar. "
            "Tarefa: {task}"
        ),
        display_template="[bold yellow]🧞 [DOMA Express] Criando Genie Space com: {agent}[/bold yellow]",
    ),
    "dashboard": CommandDefinition(
        name="dashboard",
        agent="semantic-modeler",
        doma_mode="express",
        description="Cria ou publica AI/BI Dashboards no Databricks (DOMA Express).",
        skills=["kb/semantic-modeling/index.md"],
        prompt_template=(
            "[DOMA EXPRESS — DASHBOARD] Delegue IMEDIATAMENTE para semantic-modeler. "
            "Não crie PRD, não peça aprovação. "
            "O agente deve usar as ferramentas Databricks AI/BI Dashboard "
            "para criar ou publicar o dashboard conforme solicitado. "
            "Instrua o agente a ler `kb/semantic-modeling/index.md` antes de executar. "
            "Tarefa: {task}"
        ),
        display_template="[bold yellow]📈 [DOMA Express] Criando Dashboard com: {agent}[/bold yellow]",
    ),
    "party": CommandDefinition(
        name="party",
        agent=None,
        doma_mode="internal",
        description=(
            "Convoca múltiplos agentes especialistas em paralelo para perspectivas independentes. "
            "Grupos: padrão (sql+spark+pipeline) | --quality | --arch | --full. "
            "Ou especifique agentes: /party sql-expert spark-expert <query>."
        ),
        skills=[],
        prompt_template="{task}",
        display_template="[bold magenta]🎉 [DOMA Party Mode] Convocando agentes em paralelo...[/bold magenta]",
    ),
    "memory": CommandDefinition(
        name="memory",
        agent=None,
        doma_mode="internal",
        description=(
            "Gerencia o sistema de memória persistente. "
            "Subcomandos: status, flush, compile, lint, search <query>."
        ),
        skills=[],
        prompt_template=("[MEMORY COMMAND] {task}"),
        display_template="[bold cyan]🧠 [Memory] Gerenciando memória persistente...[/bold cyan]",
    ),
    "geral": CommandDefinition(
        name="geral",
        agent="geral",
        doma_mode="express",
        description=(
            "Pergunta conversacional respondida pelo Claude Haiku. "
            "Ideal para dúvidas técnicas, conceitos, explicações e perguntas gerais de dados. "
            "Rápido e econômico."
        ),
        skills=[],
        prompt_template=(
            "[DOMA EXPRESS] Delegue IMEDIATAMENTE para geral. "
            "NÃO leia arquivos, NÃO use ferramentas, NÃO consulte KBs. "
            "O agente responde do próprio conhecimento. Não crie PRD, não peça aprovação. "
            "Pergunta: {task}"
        ),
        display_template="[bold cyan]💬 [Geral] Respondendo com Claude Haiku...[/bold cyan]",
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
        doma_prompt=definition.prompt_template.format(task=task),
        doma_mode=definition.doma_mode,
        display_message=definition.display_template.format(agent=definition.agent or "supervisor"),
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
        }.get(definition.doma_mode, definition.doma_mode)

        lines.append(
            f"  [bold green]/{name:<12}[/bold green] {mode_badge:<20} {definition.description}"
        )

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
