"""
Configurações globais via Pydantic BaseSettings.
Carregadas automaticamente do arquivo .env na raiz do projeto.

Inclui validação de credenciais por plataforma e diagnóstico de startup.
"""

import logging
import warnings
from typing import ClassVar, TypedDict

from pydantic import field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger("data_agents.config")


class _PlatformConfig(TypedDict):
    """Estrutura interna usada para validação de credenciais por plataforma."""

    fields: dict[str, str]
    required: list[str]


class Settings(BaseSettings):
    # --- Claude / Anthropic ---
    anthropic_api_key: str = ""
    # URL base do proxy (ex: Flow LiteLLM). Vazio = usa api.anthropic.com padrão.
    anthropic_base_url: str = ""

    # --- Databricks ---
    databricks_host: str = ""
    databricks_token: str = ""
    databricks_sql_warehouse_id: str = ""

    # --- Microsoft Fabric / Azure ---
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    fabric_workspace_id: str = ""
    fabric_api_base_url: str = "https://api.fabric.microsoft.com/v1"
    # GUID do Lakehouse de ontologia — necessário para upload via ADLS Gen2 com URL correta.
    # Fabric UI → Lakehouse → Settings → ID (ou Fabric REST API /items).
    fabric_lakehouse_ontologia_id: str = ""
    fabric_mcp_server_path: str = "./mcp_servers/fabric/Fabric.Mcp.Server"
    # Comando do Fabric Community MCP — pode ser sobrescrito no .env com caminho absoluto
    # Exemplo conda: /opt/anaconda3/envs/multi_agents/bin/microsoft-fabric-mcp
    fabric_community_command: str = "microsoft-fabric-mcp"

    # --- Fabric SQL Analytics Endpoint (MCP Customizado — multi-lakehouse) ---
    # Resolve a limitação da REST API que só lista o schema dbo.
    # Conecta via TDS (pyodbc + AAD Bearer Token) ao SQL Analytics Endpoint.
    #
    # Registry de lakehouses (JSON) — recomendado para múltiplos lakehouses:
    #   FABRIC_SQL_LAKEHOUSES={"TARN_LH_DEV": "tarn-dev.datawarehouse.fabric.microsoft.com",
    #                          "TARN_LH_PROD": "tarn-prod.datawarehouse.fabric.microsoft.com"}
    #   FABRIC_SQL_DEFAULT_LAKEHOUSE=TARN_LH_DEV
    #
    # Como encontrar o endpoint: Portal Fabric → Lakehouse → SQL Analytics Endpoint → "Server"
    fabric_sql_lakehouses: str = "{}"  # JSON: {"NOME_LH": "endpoint.fabric.microsoft.com"}
    fabric_sql_default_lakehouse: str = ""  # lakehouse usado quando o agente não especifica
    # Backward compat (variáveis legadas para um único lakehouse)
    fabric_sql_endpoint: str = ""
    fabric_lakehouse_name: str = ""
    # Comando do servidor — instalado via pip install -e .
    # Exemplo conda: /opt/anaconda3/envs/multi_agents/bin/fabric-sql-mcp
    fabric_sql_command: str = "fabric-sql-mcp"

    # --- Databricks Genie (MCP Customizado — Conversation API + Space Management) ---
    # Resolve o gap do databricks-mcp-server que não expõe as tools de Genie.
    # Conecta à Genie REST API usando DATABRICKS_HOST + DATABRICKS_TOKEN (sem deps extras).
    #
    # Registry de Genie Spaces (JSON) — recomendado para múltiplos spaces:
    #   DATABRICKS_GENIE_SPACES={"retail-sales": "01f117197b5319fb972e10a45735b28c",
    #                             "hr-analytics": "01abc123..."}
    #   DATABRICKS_GENIE_DEFAULT_SPACE=retail-sales
    #
    # Como encontrar o Space ID:
    #   Databricks → AI/BI → Genie → abra o Space → copie o ID da URL
    databricks_genie_spaces: str = "{}"  # JSON: {"nome-amigavel": "space_id"}
    databricks_genie_default_space: str = ""  # space usado quando o agente não especifica
    # Comando do servidor — instalado via pip install -e .
    # Exemplo conda: /opt/anaconda3/envs/multi_agents/bin/databricks-genie-mcp
    databricks_genie_command: str = "databricks-genie-mcp"

    # --- Fabric Semantic MCP (MCP Customizado — introspecção de Semantic Models) ---
    # Resolve o gap do fabric_community que não expõe TMDL, medidas DAX, relacionamentos e RLS.
    # Usa Power BI REST API (getDefinition + executeQueries) e Fabric REST API v1.
    # Reutiliza as credenciais Azure (AZURE_TENANT_ID + AZURE_CLIENT_ID + AZURE_CLIENT_SECRET).
    # Requer permissão no Power BI Admin Portal:
    #   Tenant Settings → Developer Settings → "Allow service principals to use Power BI APIs"
    # Comando: fabric-semantic-mcp (entry point em pyproject.toml)
    # Exemplo conda: /opt/anaconda3/envs/multi_agents/bin/fabric-semantic-mcp
    fabric_semantic_command: str = "fabric-semantic-mcp"

    # --- Fabric RTI ---
    kusto_service_uri: str = ""
    kusto_service_default_db: str = ""

    # --- Context7 (MCP — Documentação atualizada de bibliotecas) ---
    # Sem credenciais no plano gratuito (repos públicos).
    # Plano Pro requer conta em context7.com — configure CONTEXT7_API_KEY para ativá-lo.
    # Free: 1.000 requests/mês | Pro: $7/seat/mês (repos privados)
    context7_api_key: str = ""  # opcional — vazio = plano gratuito (repos públicos)

    # --- Tavily (MCP — Busca web otimizada para LLMs) ---
    # Obrigatório. Obtenha em: https://app.tavily.com/
    # Free: 1.000 créditos/mês (sem cartão) | Pago: $0.008/crédito
    tavily_api_key: str = ""

    # --- GitHub (MCP — Gestão de repositórios, issues e pull requests) ---
    # Obrigatório. Crie em: GitHub → Settings → Developer Settings → PAT (classic)
    # Escopos: repo, read:org (para repos privados)
    # Gratuito via Personal Access Token
    github_personal_access_token: str = ""

    # --- Firecrawl (MCP — Web scraping e crawling estruturado) ---
    # Obrigatório. Obtenha em: https://www.firecrawl.dev/app/api-keys
    # Free: 500 créditos/mês | Pago: a partir de $16/mês (3.000 créditos)
    firecrawl_api_key: str = ""

    # --- PostgreSQL (MCP — Queries somente leitura em banco PostgreSQL) ---
    # Connection string completa do banco alvo.
    # Formato: postgresql://usuario:senha@host:5432/banco
    # Formato cloud: postgresql://usuario:senha@host:5432/banco?sslmode=require
    # Gratuito (open source oficial da Anthropic)
    postgres_url: str = ""  # vazio = MCP postgres não será ativado

    # --- Migration Source (MCP Customizado — fontes de migração relacionais) ---
    # Registry de bancos de origem para migração (JSON). Suporta SQL Server e PostgreSQL.
    # Formato: {"NOME": {"type": "sqlserver|postgresql", "host": "...", "port": ..., "database": "...", "user": "...", "password": "..."}}
    # SQL Server requer ODBC Driver 17 ou 18 instalado no sistema.
    # PostgreSQL usa psycopg2-binary (sem dependência de sistema).
    migration_sources: str = "{}"
    migration_default_source: str = ""
    # Comando do servidor — instalado via pip install -e .
    # Exemplo conda: /opt/anaconda3/envs/multi_agents/bin/migration-source-mcp
    migration_source_command: str = "migration-source-mcp"

    # --- Permissões dos Agentes ---
    # "bypassPermissions" (padrão): agentes executam sem pedir confirmação — ideal para automação.
    # "acceptEdits": agentes pedem confirmação antes de operações write/execute — recomendado
    # em ambientes multi-usuário ou onde auditoria manual é necessária.
    # Override via .env: AGENT_PERMISSION_MODE=acceptEdits
    agent_permission_mode: str = "bypassPermissions"

    # --- Configurações do Sistema ---
    default_model: str = (
        "claude-sonnet-4-6"  # Supervisor model. Use Opus only for /plan (enable_thinking=True).
    )
    max_budget_usd: float = 5.0
    max_turns: int = 50
    log_level: str = "INFO"
    # Nível de log para o console (o que o usuário vê no terminal).
    # "WARNING" esconde logs operacionais (OUTPUT COMPRIMIDO, custo, etc).
    # O arquivo JSONL sempre captura tudo em DEBUG independentemente.
    console_log_level: str = "WARNING"
    audit_log_path: str = "./logs/audit.jsonl"

    # --- Model Routing por Tier ---
    # Mapeamento tier -> modelo. Permite override global da estratégia de modelo por tier.
    # Se um tier não estiver no mapa, o agente usa o model declarado no seu frontmatter.
    # Override via .env: TIER_MODEL_MAP='{"T1": "claude-opus-4-6", "T2": "claude-sonnet-4-6"}'
    tier_model_map: dict[str, str] = {}

    # --- Token Budgets por Tier (Ch. 5 — Agent Loop) ---
    # Mapeamento tier -> maxTurns: limita o número máximo de chamadas de tool por sub-agente.
    # T0 (haiku, zero MCP): conversacional puro, sem tools — pouquíssimos turns necessários.
    # T1 (pipelines complexos, cross-platform) precisam de mais turns.
    # T2 (análise especializada, escopo restrito) precisam de menos.
    # T3 (conversacional com tools limitadas) precisam de poucos turns.
    # Override via .env: TIER_TURNS_MAP='{"T0": 3, "T1": 25, "T2": 15, "T3": 5}'
    tier_turns_map: dict[str, int] = {"T0": 3, "T1": 20, "T2": 12, "T3": 5}

    # --- Effort por Tier (Ch. 5 — Agent Loop) ---
    # Mapeamento tier -> effort: controla o nível de "esforço" do modelo por agente.
    # T0: "low" — Haiku respondendo perguntas conceituais, sem raciocínio profundo necessário.
    # "high": raciocínio mais profundo, maior custo e latência — para tarefas complexas T1.
    # "medium": balanceado — para tarefas especializadas T2.
    # "low": rápido e eficiente — para tarefas conversacionais T3.
    # Override via .env: TIER_EFFORT_MAP='{"T0": "low", "T1": "high", "T2": "medium", "T3": "low"}'
    tier_effort_map: dict[str, str] = {"T0": "low", "T1": "high", "T2": "medium", "T3": "low"}

    # --- KB Injection ---
    # Se True, injeta o conteúdo dos index.md das KBs relevantes no prompt de cada agente.
    # Baseado no campo kb_domains do frontmatter. Desabilite para economizar tokens no prompt.
    inject_kb_index: bool = True

    # --- Idle Timeout ---
    # Tempo de inatividade (em minutos) antes de oferecer reset automático da sessão.
    # Se 0, desabilita o idle timeout. Padrão: 30 minutos.
    idle_timeout_minutes: int = 30

    # --- Memory System ---
    # Se True, habilita o sistema de memória persistente (captura + retrieval).
    # Desabilite para economizar custo do Sonnet lateral (~$0.003-0.01 por query).
    memory_enabled: bool = True
    # Se True, injeta memórias relevantes no system prompt antes de cada query.
    # Requer memory_enabled=True. Cada injeção custa ~$0.003-0.01 (Sonnet lateral).
    memory_retrieval_enabled: bool = True
    # Se True, captura automaticamente contexto da sessão via hook PostToolUse.
    memory_capture_enabled: bool = True

    # --- Memory Decay (dias para atingir confidence 0.1) ---
    # Controla a velocidade de obsolescência de cada tipo de memória.
    # None = nunca decai (USER e ARCHITECTURE por padrão).
    # PROGRESS: tarefas em andamento ficam obsoletas rapidamente (padrão 7 dias).
    # FEEDBACK: orientações do usuário persistem mais (padrão 90 dias).
    # PIPELINE_STATUS: status de pipelines de dados (padrão 14 dias).
    # Override via .env: MEMORY_DECAY_PROGRESS_DAYS=14
    memory_decay_progress_days: float = 7.0
    memory_decay_feedback_days: float = 90.0
    memory_decay_pipeline_status_days: float = 14.0

    # --- Skill Auto-Refresh ---
    # Se True, habilita a atualização automática das Skills via scripts/refresh_skills.py.
    # O script chama a Anthropic Messages API direta (sem MCP, sem agente) e usa o
    # tool nativo web_search para buscar docs atualizadas das plataformas.
    # Execute manualmente: make refresh-skills
    # Agendamento automático: configurado via SKILL_REFRESH_INTERVAL_DAYS.
    skill_refresh_enabled: bool = True
    # Intervalo em dias entre refreshes. Padrão: 3 dias.
    # Override via .env: SKILL_REFRESH_INTERVAL_DAYS=5
    skill_refresh_interval_days: int = 3
    # Domínios de skill a atualizar no refresh automático.
    # Override via .env: SKILL_REFRESH_DOMAINS=databricks,fabric
    skill_refresh_domains: str = "databricks,fabric"

    # --- Memory Instant Capture Patterns ---
    # Padrões regex para captura instantânea de memórias sem chamada LLM.
    # Cada padrão é uma string "regex::tipo" onde tipo é: feedback, architecture, progress.
    # Padrão vazio usa os 5 padrões default. Override via .env para adicionar novos tipos.
    # Ex: MEMORY_INSTANT_PATTERNS='["(?i)#concern\\s*[:\\-]?\\s*(.+)::architecture"]'
    memory_instant_patterns: list[str] = []

    # Máx de capturas instantâneas por output de tool (evita buffer bloat)
    memory_max_captures_per_output: int = 10

    # --- Memory Daily Log Cleanup ---
    # Se True, apaga daily logs compilados após N dias (reduz acúmulo de arquivos).
    # Logs compilados já tiveram seu conteúdo extraído para o store — são redundantes.
    # Override via .env: MEMORY_AUTO_CLEAN_DAILY_LOGS=true
    memory_auto_clean_daily_logs: bool = True
    # Quantos dias manter logs compilados antes de apagar. Padrão: 30 dias.
    # Override via .env: MEMORY_KEEP_COMPILED_DAYS=30
    memory_keep_compiled_days: int = 30

    # --- Memory Extraction Model ---
    # Modelo usado pelo extractor e retrieval para chamadas laterais (sem SDK).
    # Haiku é suficiente para extração/retrieval e ~4x mais barato que Sonnet.
    # Override via .env: MEMORY_EXTRACTOR_MODEL=claude-sonnet-4-6
    memory_extractor_model: str = "claude-haiku-4-5"
    memory_extractor_max_tokens: int = 2048
    memory_retrieval_model: str = "claude-haiku-4-5"
    memory_retrieval_max_tokens: int = 1024
    # Número máximo de memórias recuperadas por query (retrieval semântico).
    # Override via .env: MEMORY_RETRIEVAL_MAX=10
    memory_retrieval_max: int = 10

    # --- Business Monitor ---
    monitor_enabled: bool = True
    monitor_start_hour: int = 8
    monitor_end_hour: int = 23
    monitor_interval_minutes: int = 30
    monitor_manifest_path: str = "config/monitor_manifest.yaml"
    monitor_alert_email_to: str = ""

    # SMTP para envio de alertas por email (ex: Gmail com App Password)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # Databricks SQL Warehouse ID (para execução direta via SDK no monitor daemon)
    databricks_warehouse_id: str = ""

    # Fabric SQL Endpoint (para monitores com platform: fabric_sql)
    fabric_sql_server: str = ""
    fabric_sql_user: str = ""
    fabric_sql_password: str = ""
    fabric_sql_database: str = ""

    # --- Output Compressor Limits ---
    # Limites de truncagem do output_compressor_hook.py.
    # Reduzir MAX_OUTPUT_CHARS economiza tokens de contexto em troca de menos detalhe.
    # Override via .env: COMPRESSOR_MAX_SQL_ROWS=20
    compressor_max_sql_rows: int = 20
    compressor_max_list_items: int = 15
    compressor_max_file_lines: int = 80
    compressor_max_bash_lines: int = 40
    compressor_max_output_chars: int = 3_500

    # Limites específicos para migration-expert (mcp__migration_source__*).
    # DDLs e schemas extraídos de SQL Server/PostgreSQL são legitimamente grandes.
    # Override via .env: COMPRESSOR_MIGRATION_MAX_FILE_LINES=300
    compressor_migration_max_file_lines: int = 300
    compressor_migration_max_output_chars: int = 10_000

    # --- Context Budget Thresholds ---
    # Limite de tokens de input por sessão (context window do Claude: 200K tokens).
    # 180K é o teto conservador para deixar margem para a resposta final.
    # Override via .env: CONTEXT_BUDGET_INPUT_LIMIT=180000
    context_budget_input_limit: int = 180_000
    # Limiares: 80% → WARNING, 95% → ERROR + salva checkpoint.
    context_budget_warn_threshold: float = 0.80
    context_budget_critical_threshold: float = 0.95
    # T4.4: limiar para disparar sumarização lateral via Haiku (compactação do
    # histórico em 7 campos estruturados). Default 65% — abaixo do warn para
    # agir preventivamente antes do usuário sentir o impacto.
    context_budget_summarize_threshold: float = 0.65

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # --- Campos internos (não carregados do .env) ---
    _available_platforms: ClassVar[list[str]] = []

    # ─── Validators ───────────────────────────────────────────────

    @field_validator(
        "fabric_community_command",
        "fabric_sql_command",
        "databricks_genie_command",
        "fabric_semantic_command",
        "migration_source_command",
        mode="before",
    )
    @classmethod
    def validate_mcp_command(cls, v: str) -> str:
        """Valida que comandos MCP não contêm path separators ou metacaracteres shell."""
        import re as _re

        if not v:
            return v
        # Permite apenas nomes de comando simples: letras, dígitos, hífens, underscores, pontos
        # Bloqueia path separators (/ \), metacaracteres shell (; | & $ ` ( ) < > ! ~ {})
        if not _re.match(r"^[a-zA-Z0-9_./-]+$", v):
            raise ValueError(
                f"Comando MCP inválido: '{v}'. "
                "Use apenas letras, dígitos, hífens, underscores, pontos e barras de path. "
                "Metacaracteres shell (;|&$`()!~{}) não são permitidos."
            )
        # Bloqueia traversal e metacaracteres perigosos
        dangerous = ["..", ";", "|", "&", "$", "`", "(", ")", "<", ">", "!", "~", "{", "}"]
        for char in dangerous:
            if char in v:
                raise ValueError(f"Comando MCP inválido: '{v}' contém caractere proibido '{char}'.")
        return v

    @field_validator("anthropic_api_key")
    @classmethod
    def validate_anthropic_key(cls, v: str) -> str:
        """Valida que a API key da Anthropic está presente e tem formato esperado."""
        if not v or v.startswith("sk-ant-..."):
            warnings.warn(
                "⚠️  ANTHROPIC_API_KEY não configurada. O sistema não funcionará sem ela. "
                "Configure no arquivo .env ou como variável de ambiente.",
                UserWarning,
                stacklevel=2,
            )
        return v

    @field_validator("max_budget_usd")
    @classmethod
    def validate_budget(cls, v: float) -> float:
        """Garante que o budget máximo está dentro de limites razoáveis."""
        if v <= 0:
            raise ValueError("MAX_BUDGET_USD deve ser maior que zero.")
        if v > 100:
            warnings.warn(
                f"⚠️  MAX_BUDGET_USD={v} é muito alto. Considere reduzir para evitar custos inesperados.",
                UserWarning,
                stacklevel=2,
            )
        return v

    @field_validator("max_turns")
    @classmethod
    def validate_max_turns(cls, v: int) -> int:
        """Garante que max_turns está dentro de limites razoáveis."""
        if v < 1:
            raise ValueError("MAX_TURNS deve ser pelo menos 1.")
        if v > 200:
            warnings.warn(
                f"⚠️  MAX_TURNS={v} é muito alto. Sessões longas podem gerar custos elevados.",
                UserWarning,
                stacklevel=2,
            )
        return v

    # ─── Platform Validation ──────────────────────────────────────

    def validate_platform_credentials(self) -> dict[str, dict]:
        """
        Verifica quais plataformas têm credenciais válidas configuradas.

        Returns:
            Dict com status de cada plataforma:
            {
                "anthropic": {"ready": True, "missing": []},
                "databricks": {"ready": False, "missing": ["DATABRICKS_TOKEN"]},
                ...
            }
        """
        platforms: dict[str, _PlatformConfig] = {
            "anthropic": {
                "fields": {"ANTHROPIC_API_KEY": self.anthropic_api_key},
                "required": ["ANTHROPIC_API_KEY"],
            },
            "databricks": {
                "fields": {
                    "DATABRICKS_HOST": self.databricks_host,
                    "DATABRICKS_TOKEN": self.databricks_token,
                    "DATABRICKS_SQL_WAREHOUSE_ID": self.databricks_sql_warehouse_id,
                },
                "required": ["DATABRICKS_HOST", "DATABRICKS_TOKEN"],
            },
            "fabric": {
                "fields": {
                    "AZURE_TENANT_ID": self.azure_tenant_id,
                    "FABRIC_WORKSPACE_ID": self.fabric_workspace_id,
                },
                "required": ["AZURE_TENANT_ID", "FABRIC_WORKSPACE_ID"],
            },
            "fabric_official": {
                # MCP oficial Microsoft — usa cache `az login` local em runtime,
                # não recebe env vars. Gating aqui é apenas indicativo de "setup Fabric
                # existe"; a autenticação real acontece na primeira tool call.
                "fields": {
                    "AZURE_TENANT_ID": self.azure_tenant_id,
                    "FABRIC_WORKSPACE_ID": self.fabric_workspace_id,
                },
                "required": ["AZURE_TENANT_ID", "FABRIC_WORKSPACE_ID"],
            },
            "fabric_sql": {
                # SQL Analytics Endpoint — resolve limitação do schema dbo da REST API
                # Considera configurado se tiver registry OU variáveis legadas
                "fields": {
                    "AZURE_TENANT_ID": self.azure_tenant_id,
                    "FABRIC_SQL_LAKEHOUSES_OR_LEGACY": (
                        self.fabric_sql_lakehouses
                        if self.fabric_sql_lakehouses not in ("{}", "")
                        else self.fabric_sql_endpoint
                    ),
                },
                "required": ["AZURE_TENANT_ID", "FABRIC_SQL_LAKEHOUSES_OR_LEGACY"],
            },
            "databricks_genie": {
                # Reusa credenciais Databricks + pelo menos um space configurado
                "fields": {
                    "DATABRICKS_HOST": self.databricks_host,
                    "DATABRICKS_TOKEN": self.databricks_token,
                    "DATABRICKS_GENIE_SPACES_OR_DEFAULT": (
                        self.databricks_genie_spaces
                        if self.databricks_genie_spaces not in ("{}", "")
                        else self.databricks_genie_default_space
                    ),
                },
                "required": [
                    "DATABRICKS_HOST",
                    "DATABRICKS_TOKEN",
                    "DATABRICKS_GENIE_SPACES_OR_DEFAULT",
                ],
            },
            "fabric_semantic": {
                # Reutiliza credenciais Azure do fabric — considera pronto quando fabric está pronto
                "fields": {
                    "AZURE_TENANT_ID": self.azure_tenant_id,
                    "FABRIC_WORKSPACE_ID": self.fabric_workspace_id,
                },
                "required": ["AZURE_TENANT_ID", "FABRIC_WORKSPACE_ID"],
            },
            "fabric_rti": {
                "fields": {
                    "KUSTO_SERVICE_URI": self.kusto_service_uri,
                    "KUSTO_SERVICE_DEFAULT_DB": self.kusto_service_default_db,
                },
                "required": ["KUSTO_SERVICE_URI", "KUSTO_SERVICE_DEFAULT_DB"],
            },
            # ── MCPs externos (sem plataforma de dados própria) ──────────────
            # Context7: sem credenciais obrigatórias no plano free → sempre "ready"
            "context7": {
                "fields": {"_no_credentials_required": "true"},
                "required": [],  # free tier não requer credenciais
            },
            # Tavily: requer API key
            "tavily": {
                "fields": {"TAVILY_API_KEY": self.tavily_api_key},
                "required": ["TAVILY_API_KEY"],
            },
            # GitHub: requer Personal Access Token
            "github": {
                "fields": {"GITHUB_PERSONAL_ACCESS_TOKEN": self.github_personal_access_token},
                "required": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
            },
            # Firecrawl: requer API key
            "firecrawl": {
                "fields": {"FIRECRAWL_API_KEY": self.firecrawl_api_key},
                "required": ["FIRECRAWL_API_KEY"],
            },
            # Postgres: requer connection string
            "postgres": {
                "fields": {"POSTGRES_URL": self.postgres_url},
                "required": ["POSTGRES_URL"],
            },
            # Migration Source: requer registry com ao menos uma fonte configurada
            "migration_source": {
                "fields": {
                    "MIGRATION_SOURCES": (
                        self.migration_sources if self.migration_sources not in ("{}", "") else ""
                    ),
                },
                "required": ["MIGRATION_SOURCES"],
            },
            # Memory MCP: sem credenciais → sempre "ready"
            "memory_mcp": {
                "fields": {"_no_credentials_required": "true"},
                "required": [],
            },
        }

        results: dict[str, dict] = {}

        for platform, config in platforms.items():
            missing = [
                name
                for name in config["required"]
                if not config["fields"].get(name, "").strip()
                or config["fields"].get(name, "").startswith("sk-ant-...")
            ]
            results[platform] = {
                "ready": len(missing) == 0,
                "missing": missing,
            }

        return results

    def get_available_platforms(self) -> list[str]:
        """Retorna lista de plataformas MCP com credenciais válidas."""
        status = self.validate_platform_credentials()
        return [name for name, info in status.items() if info["ready"] and name != "anthropic"]

    def startup_diagnostics(self) -> None:
        """
        Executa diagnóstico completo no startup e emite warnings/errors.
        Chamado uma vez no início da aplicação.
        """
        status = self.validate_platform_credentials()

        # Anthropic é obrigatória
        if not status["anthropic"]["ready"]:
            logger.error(
                "❌ ANTHROPIC_API_KEY não configurada. O sistema não funcionará. "
                "Configure no .env ou como variável de ambiente."
            )

        # Plataformas de dados — pelo menos uma deve estar configurada
        data_platforms = [
            "databricks",
            "databricks_genie",
            "fabric",
            "fabric_sql",
            "fabric_rti",
            "migration_source",
        ]
        any_ready = any(status[p]["ready"] for p in data_platforms)

        if not any_ready:
            logger.warning(
                "⚠️  Nenhuma plataforma de dados configurada. "
                "Configure pelo menos Databricks ou Fabric no .env para usar os MCP servers."
            )

        # Diagnóstico individual
        for platform in data_platforms:
            info = status[platform]
            if info["ready"]:
                logger.info(f"✅ {platform.upper()}: credenciais configuradas.")
            elif info["missing"]:
                logger.warning(
                    f"⚠️  {platform.upper()}: variáveis ausentes: {', '.join(info['missing'])}. "
                    f"MCP server desta plataforma não será ativado."
                )

        # MCPs externos (sem plataforma de dados própria)
        external_mcps = ["context7", "memory_mcp", "tavily", "github", "firecrawl", "postgres"]
        for mcp in external_mcps:
            info = status[mcp]
            if info["ready"]:
                logger.info(f"✅ {mcp.upper()}: configurado.")
            elif info["missing"]:
                logger.info(
                    f"ℹ️  {mcp.upper()}: variáveis ausentes: {', '.join(info['missing'])}. "
                    f"Configure no .env para ativar."
                )

        logger.info(
            f"📋 Configuração: model={self.default_model}, "
            f"budget=${self.max_budget_usd}, max_turns={self.max_turns}"
        )


settings = Settings()
