"""
ui/config.py — Constantes compartilhadas entre chat.py e chainlit_app.py.

Centraliza labels de tools, nomes de agentes, grupos de comandos e CSS
para evitar duplicação e garantir consistência entre as interfaces.
"""

# ── Labels de tools (tool_name → texto amigável) ─────────────────────────────
TOOL_LABELS: dict[str, str] = {
    # SDK tools
    "Agent": "🤖 Delegando para agente especialista",
    "Read": "📖 Lendo arquivo",
    "Write": "✍️  Salvando arquivo",
    "Edit": "✏️  Editando arquivo",
    "Grep": "🔍 Buscando conteúdo",
    "Glob": "📂 Listando arquivos",
    "Bash": "⚙️  Executando comando",
    "AskUserQuestion": "❓ Aguardando resposta",
    # Databricks
    "mcp__databricks__execute_sql": "🗄️  SQL no Databricks",
    "mcp__databricks__execute_sql_multi": "🗄️  SQL paralelo no Databricks",
    "mcp__databricks__list_catalogs": "📋 Unity Catalog — catálogos",
    "mcp__databricks__list_schemas": "📋 Unity Catalog — schemas",
    "mcp__databricks__list_tables": "📋 Unity Catalog — tabelas",
    "mcp__databricks__describe_table": "🔎 Inspecionando tabela",
    "mcp__databricks__get_table_stats_and_schema": "📊 Stats + schema da tabela",
    "mcp__databricks__sample_table": "📊 Amostra de dados",
    "mcp__databricks__run_job_now": "🚀 Disparando Job Databricks",
    "mcp__databricks__wait_for_run": "⏳ Aguardando conclusão do Job",
    "mcp__databricks__start_pipeline": "🚀 Iniciando Pipeline LakeFlow",
    "mcp__databricks__get_pipeline": "📡 Status do Pipeline",
    "mcp__databricks__execute_code": "⚡ Executando código serverless",
    "mcp__databricks__create_or_update_genie": "🧞 Configurando Genie Space",
    "mcp__databricks__create_or_update_dashboard": "📊 Criando AI/BI Dashboard",
    "mcp__databricks__manage_ka": "🧠 Knowledge Assistant",
    "mcp__databricks__manage_mas": "🤖 Mosaic AI Supervisor Agent",
    "mcp__databricks__query_serving_endpoint": "🔮 Consultando endpoint ML",
    "mcp__databricks__get_serving_endpoint": "🔮 Inspecionando endpoint ML",
    "mcp__databricks__list_serving_endpoints": "🔮 Endpoints de Model Serving",
    "mcp__databricks__list_jobs": "⚙️  Listando Jobs",
    "mcp__databricks__get_job": "⚙️  Detalhes do Job",
    "mcp__databricks__list_clusters": "☁️  Clusters disponíveis",
    "mcp__databricks__list_warehouses": "🏭 SQL Warehouses",
    # Databricks Genie
    "mcp__databricks_genie__genie_create_space": "🧞 Criando Genie Space",
    "mcp__databricks_genie__genie_list_spaces": "🧞 Listando Genie Spaces",
    "mcp__databricks_genie__genie_start_conversation": "💬 Iniciando conversa Genie",
    "mcp__databricks_genie__genie_query": "💬 Query no Genie",
    # Microsoft Fabric
    "mcp__fabric_official__list_workspaces": "📋 Workspaces do Fabric",
    "mcp__fabric_official__get_workspace": "📋 Detalhes do workspace",
    "mcp__fabric_official__list_items": "📋 Itens do workspace",
    "mcp__fabric_community__list_items": "📋 Itens do Fabric workspace",
    "mcp__fabric_community__list_tables": "📋 Tabelas via Community MCP",
    "mcp__fabric_community__get_lineage": "🔗 Linhagem de dados Fabric",
    "mcp__fabric_sql__fabric_sql_execute": "🗄️  SQL no Fabric Lakehouse",
    "mcp__fabric_sql__fabric_sql_list_tables": "📋 Tabelas Fabric (todos schemas)",
    "mcp__fabric_sql__fabric_sql_describe_table": "🔎 Schema da tabela Fabric",
    "mcp__fabric_rti__kusto_query": "🔍 Query KQL (Eventhouse)",
    "mcp__fabric_rti__kusto_list_databases": "📋 Databases KQL",
    "mcp__fabric_rti__kusto_list_tables": "📋 Tabelas KQL",
    "mcp__fabric_semantic__get_semantic_model_tmdl": "📐 TMDL do Semantic Model",
    "mcp__fabric_semantic__list_semantic_models": "📐 Listando Semantic Models",
    "mcp__fabric_semantic__update_definition": "📐 Atualizando medida DAX",
    # Outras plataformas
    "mcp__context7__get-library-docs": "📚 Consultando documentação",
    "mcp__context7__resolve-library-id": "📚 Resolvendo biblioteca",
    "mcp__postgres__query": "🐘 Query PostgreSQL",
    "mcp__tavily__tavily-search": "🌐 Buscando na web",
    "mcp__tavily__tavily-extract": "🌐 Extraindo página web",
    "mcp__github__search_repositories": "🐙 Buscando repositórios GitHub",
    "mcp__github__get_file_contents": "🐙 Lendo arquivo GitHub",
    "mcp__github__list_pull_requests": "🐙 Pull Requests GitHub",
    "mcp__firecrawl__scrape": "🕷️  Scraping de página",
    "mcp__firecrawl__crawl": "🕷️  Crawling de site",
    "mcp__firecrawl__search": "🕷️  Busca + scraping",
    "mcp__memory_mcp__read_graph": "🧠 Lendo knowledge graph",
    "mcp__memory_mcp__add_entities": "🧠 Atualizando knowledge graph",
    "mcp__memory_mcp__add_relations": "🧠 Adicionando relações ao grafo",
    "mcp__memory_mcp__search_nodes": "🧠 Buscando no knowledge graph",
    "mcp__migration_source__get_ddl": "🔄 Extraindo DDL da origem",
    "mcp__migration_source__list_tables": "🔄 Inventário do banco de origem",
    "mcp__migration_source__get_table_stats": "🔄 Estatísticas do banco de origem",
    # Fabric Official — OneLake file ops
    "mcp__fabric_official__list_lakehouses": "📋 Listando Lakehouses",
    "mcp__fabric_official__onelake_upload_file": "⬆️  Enviando arquivo para OneLake",
    "mcp__fabric_official__onelake_list_files": "📂 Listando arquivos no OneLake",
    # Databricks — pipeline e volume ops
    "mcp__databricks__create_or_update_pipeline": "🔧 Criando/atualizando Pipeline LakeFlow",
    "mcp__databricks__upload_to_volume": "⬆️  Enviando arquivo para Volume",
    "mcp__databricks__list_volume_files": "📂 Listando arquivos no Volume",
    # Fabric RTI
    "mcp__fabric_rti__kusto_command": "⚙️  Executando comando KQL",
}


def tool_label(name: str) -> str:
    """Retorna label amigável para uma tool. Fallback: nome humanizado."""
    if name in TOOL_LABELS:
        return TOOL_LABELS[name]
    clean = name.replace("mcp__", "").replace("__", " → ").replace("_", " ").title()
    return f"🔧 {clean}"


# ── Nomes de exibição por agente ──────────────────────────────────────────────
AGENT_DISPLAY_NAMES: dict[str, str] = {
    "databricks-engineer": "Databricks Engineer",
    "databricks-ai": "Databricks AI",
    "python-expert": "Python Expert",
    "migration-expert": "Migration Expert",
    "data-quality-steward": "Data Quality Steward",
    "governance-auditor": "Governance Auditor",
    "fabric-engineer": "Fabric Engineer",
    "fabric-rti": "Fabric RTI",
    "fabric-ontology": "Fabric Ontology",
    "business-analyst": "Business Analyst",
    "dbt-expert": "dbt Expert",
    "data-contracts-engineer": "Data Contracts Engineer",
    "data-mesh-architect": "Data Mesh Architect",
    "geral": "Geral",
}

# Tier de cada agente — lido dinamicamente do registry para evitar dessincronização
from config.agent_meta import get_agent_tiers as _get_agent_tiers  # noqa: E402

AGENT_TIERS: dict[str, str] = _get_agent_tiers()

TIER_COLORS: dict[str, str] = {
    "T1": "#3FB950",  # verde (core engineering)
    "T2": "#A78BFA",  # roxo (especialistas)
    "T3": "#FCD34D",  # âmbar (conversacional)
}


def agent_display_name(raw: str) -> str:
    """Retorna nome de exibição do agente. Fallback: title case."""
    return AGENT_DISPLAY_NAMES.get(raw, raw.replace("-", " ").title())


# ── Grupos de comandos para sidebar ──────────────────────────────────────────
COMMAND_GROUPS: dict[str, list[str]] = {
    "📋 Intake & Planejamento": ["/brief", "/plan", "/review", "/status"],
    "⚡ Engenharia Core": ["/sql", "/spark", "/pipeline", "/dbt", "/python", "/migrate"],
    "🤖 AI & Streaming": ["/ai", "/streaming", "/cdc"],
    "🏭 Microsoft Fabric": ["/fabric", "/semantic"],
    "🏗️ Arquitetura": ["/schema", "/medallion", "/mesh"],
    "🔍 Qualidade & Gov.": ["/quality", "/governance", "/contract"],
    "💰 FinOps & Diagnóstico": ["/finops", "/diagnose"],
    "🔧 Sistema": ["/health", "/skill"],
    "🎉 Multi-Agente": ["/party", "/analyze-project", "/workflow"],
    "🧠 Memória": ["/memory"],
    "💬 Conversacional": ["/geral"],
    "📂 Sessões": ["/sessions", "/resume"],
}


# Enriquecimento de labels com argumentos reais da tool call
def enrich_tool_label(tool_name: str, data: dict) -> str:
    """Retorna label enriquecido com args reais. Retorna '' se não houver info relevante."""
    if tool_name == "Read":
        path = data.get("file_path") or data.get("path", "")
        return f"📖 Lendo {path}..." if path else ""
    if tool_name == "Write":
        path = data.get("file_path", "")
        return f"✍️  Salvando {path}..." if path else ""
    if tool_name == "Edit":
        path = data.get("file_path", "")
        return f"✏️  Editando {path}..." if path else ""
    if tool_name == "Bash":
        cmd = data.get("command", "")
        if cmd:
            truncated = cmd[:60] + "..." if len(cmd) > 60 else cmd
            return f"⚙️  Executando: {truncated}"
    if tool_name == "Grep":
        pattern = data.get("pattern", "")
        path = data.get("path", "")
        if pattern and path:
            return f"🔍 Buscando: '{pattern}' em {path}"
        if pattern:
            return f"🔍 Buscando: '{pattern}'"
    if tool_name == "Glob":
        pattern = data.get("pattern", "")
        return f"📂 Listando: {pattern}" if pattern else ""
    if tool_name == "Agent":
        agent = data.get("subagent_type") or data.get("agent_name") or data.get("name", "")
        if agent:
            return f"🤖 Delegando → {agent_display_name(agent)}"
    return ""


# ── Workflows pré-definidos (para monitoring e UI) ────────────────────────────
WORKFLOW_METADATA: dict[str, dict] = {
    "WF-01": {
        "name": "Pipeline End-to-End",
        "icon": "🏗️",
        "description": "Bronze→Silver→Gold + Quality + Governance + Semantic Layer",
        "agents": [
            "databricks-engineer",
            "data-quality-steward",
            "governance-auditor",
            "fabric-engineer",
        ],
        "when": "Criar pipeline Medallion completo do zero",
    },
    "WF-02": {
        "name": "Star Schema",
        "icon": "⭐",
        "description": "Schema Discovery → Star Schema → Quality → Semantic Modeling",
        "agents": ["databricks-engineer", "data-quality-steward", "fabric-engineer"],
        "when": "Criar camada Gold em Star Schema a partir de tabelas Silver",
    },
    "WF-03": {
        "name": "Migração Cross-Platform",
        "icon": "🔀",
        "description": "Design → Databricks+Fabric (paralelo) → Reconciliation → Governance",
        "agents": [
            "databricks-engineer",
            "fabric-engineer",
            "data-quality-steward",
            "governance-auditor",
        ],
        "when": "Migrar pipelines entre Databricks e Fabric",
    },
    "WF-04": {
        "name": "Auditoria de Governança",
        "icon": "🛡️",
        "description": "Access Audit → Data Quality Audit → Compliance Report",
        "agents": ["governance-auditor", "data-quality-steward"],
        "when": "Gerar relatório de compliance e governança",
    },
    "WF-05": {
        "name": "Migração Relacional → Nuvem",
        "icon": "🚚",
        "description": "Assessment → Design → DDL+Pipeline (paralelo) → Reconciliation → PII",
        "agents": [
            "migration-expert",
            "databricks-engineer",
            "data-quality-steward",
            "governance-auditor",
        ],
        "when": "Migrar SQL Server ou PostgreSQL para Databricks/Fabric",
    },
}
