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

    # --- Fabric RTI ---
    kusto_service_uri: str = ""
    kusto_service_default_db: str = ""

    # --- Configurações do Sistema ---
    default_model: str = "bedrock/anthropic.claude-4-6-sonnet"
    # default_model: str = "claude-opus-4-6"
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
    # Override via .env: TIER_MODEL_MAP='{"T1": "claude-opus-4-6", "T2": "claude-haiku-3-5"}'
    tier_model_map: dict[str, str] = {}

    # --- Token Budgets por Tier (Ch. 5 — Agent Loop) ---
    # Mapeamento tier -> maxTurns: limita o número máximo de chamadas de tool por sub-agente.
    # Agentes T1 (pipelines complexos, cross-platform) precisam de mais turns.
    # Agentes T2 (análise especializada, escopo restrito) precisam de menos.
    # Agentes T3 (conversacional, sem tools) precisam de muito poucos.
    # Override via .env: TIER_TURNS_MAP='{"T1": 25, "T2": 15, "T3": 5}'
    tier_turns_map: dict[str, int] = {"T1": 20, "T2": 12, "T3": 5}

    # --- Effort por Tier (Ch. 5 — Agent Loop) ---
    # Mapeamento tier -> effort: controla o nível de "esforço" do modelo por agente.
    # "high": raciocínio mais profundo, maior custo e latência — para tarefas complexas T1.
    # "medium": balanceado — para tarefas especializadas T2.
    # "low": rápido e eficiente — para tarefas conversacionais T3.
    # Override via .env: TIER_EFFORT_MAP='{"T1": "high", "T2": "medium", "T3": "low"}'
    tier_effort_map: dict[str, str] = {"T1": "high", "T2": "medium", "T3": "low"}

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # --- Campos internos (não carregados do .env) ---
    _available_platforms: ClassVar[list[str]] = []

    # ─── Validators ───────────────────────────────────────────────

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
            "fabric_rti": {
                "fields": {
                    "KUSTO_SERVICE_URI": self.kusto_service_uri,
                    "KUSTO_SERVICE_DEFAULT_DB": self.kusto_service_default_db,
                },
                "required": ["KUSTO_SERVICE_URI", "KUSTO_SERVICE_DEFAULT_DB"],
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
        data_platforms = ["databricks", "databricks_genie", "fabric", "fabric_sql", "fabric_rti"]
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

        logger.info(
            f"📋 Configuração: model={self.default_model}, "
            f"budget=${self.max_budget_usd}, max_turns={self.max_turns}"
        )


settings = Settings()
