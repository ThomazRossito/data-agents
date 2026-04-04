"""
Configurações globais via Pydantic BaseSettings.
Carregadas automaticamente do arquivo .env na raiz do projeto.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Claude / Anthropic ---
    anthropic_api_key: str = ""

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

    # --- Fabric RTI ---
    kusto_service_uri: str = ""
    kusto_service_default_db: str = ""

    # --- Configurações do Sistema ---
    default_model: str = "claude-opus-4-6"
    max_budget_usd: float = 5.0
    max_turns: int = 50
    log_level: str = "INFO"
    audit_log_path: str = "./logs/audit.jsonl"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
