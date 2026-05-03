import json
from functools import cached_property

from openai import OpenAI
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── GitHub Copilot ──────────────────────────────────────────────────────
    github_token: str = Field("", alias="GITHUB_TOKEN")
    default_model: str = Field("claude-sonnet-4-6", alias="DEFAULT_MODEL")
    tier_model_map: dict = Field(
        default={"T1": "claude-sonnet-4-6", "T2": "gpt-4.1", "T3": "gpt-4.1-mini"},
        alias="TIER_MODEL_MAP",
    )
    tier_turns_map: dict = Field(
        default={"T1": 8, "T2": 5, "T3": 3},
        alias="TIER_TURNS_MAP",
    )

    # ── Databricks ──────────────────────────────────────────────────────────
    databricks_host: str = Field("", alias="DATABRICKS_HOST")
    databricks_token: str = Field("", alias="DATABRICKS_TOKEN")
    databricks_sql_warehouse_id: str = Field("", alias="DATABRICKS_SQL_WAREHOUSE_ID")
    databricks_catalog: str = Field("main", alias="DATABRICKS_CATALOG")
    databricks_schema: str = Field("default", alias="DATABRICKS_SCHEMA")

    # ── Microsoft Fabric ────────────────────────────────────────────────────
    azure_tenant_id: str = Field("", alias="AZURE_TENANT_ID")
    azure_client_id: str = Field("", alias="AZURE_CLIENT_ID")
    azure_client_secret: str = Field("", alias="AZURE_CLIENT_SECRET")
    fabric_workspace_id: str = Field("", alias="FABRIC_WORKSPACE_ID")
    fabric_lakehouse_id: str = Field("", alias="FABRIC_LAKEHOUSE_ID")
    fabric_lakehouse_name: str = Field("dev_lakehouse", alias="FABRIC_LAKEHOUSE_NAME")
    # sp | interactive (DefaultAzureCredential / browser) | device
    fabric_auth_mode: str = Field("sp", alias="FABRIC_AUTH_MODE")

    # ── Controles ───────────────────────────────────────────────────────────
    qa_enabled: bool = Field(True, alias="QA_ENABLED")
    qa_max_rounds: int = Field(1, alias="QA_MAX_ROUNDS")
    qa_score_threshold: float = Field(0.7, alias="QA_SCORE_THRESHOLD")

    max_budget_tokens: int = Field(500_000, alias="MAX_BUDGET_TOKENS")
    llm_max_tokens: int = Field(4096, alias="LLM_MAX_TOKENS")
    console_log_level: str = Field("WARNING", alias="CONSOLE_LOG_LEVEL")
    output_max_chars: int = Field(8000, alias="OUTPUT_MAX_CHARS")
    session_max_resume_turns: int = Field(10, alias="SESSION_MAX_RESUME_TURNS")
    github_personal_access_token: str = Field("", alias="GITHUB_PERSONAL_ACCESS_TOKEN")
    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")
    local_repo_path: str = Field("", alias="LOCAL_REPO_PATH")

    @field_validator("tier_model_map", "tier_turns_map", mode="before")
    @classmethod
    def parse_json_field(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    def _get_copilot_session_token(self) -> str:
        import urllib.request

        if not self.github_token:
            raise OSError(
                "GITHUB_TOKEN não configurado. "
                "Adicione ao .env ou exporte a variável antes de usar o Copilot."
            )
        req = urllib.request.Request(
            "https://api.github.com/copilot_internal/v2/token",
            headers={
                "Authorization": f"token {self.github_token}",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        return data["token"]

    @cached_property
    def copilot_client(self) -> OpenAI:
        session_token = self._get_copilot_session_token()
        return OpenAI(
            base_url="https://api.githubcopilot.com",
            api_key=session_token,
            default_headers={
                "Copilot-Integration-Id": "vscode-chat",
                "Editor-Version": "vscode/1.90.0",
            },
        )

    @cached_property
    def llm_client(self) -> OpenAI:
        if self.anthropic_api_key:
            return OpenAI(
                base_url="https://api.anthropic.com/v1",
                api_key=self.anthropic_api_key,
                default_headers={"anthropic-version": "2023-06-01"},
            )
        return self.copilot_client

    def model_for_tier(self, tier: str) -> str:
        return self.tier_model_map.get(tier, self.default_model)

    def turns_for_tier(self, tier: str) -> int:
        return self.tier_turns_map.get(tier, 10)

    def has_databricks(self) -> bool:
        host = self.databricks_host or ""
        token = self.databricks_token or ""
        # Rejeita placeholders do .env de exemplo
        if "workspace-name" in host or "xxx" in token.lower():
            return False
        return bool(host and token)

    def has_fabric(self) -> bool:
        workspace = self.fabric_workspace_id or ""
        tenant = self.azure_tenant_id or ""
        client = self.azure_client_id or ""
        # Rejeita placeholders
        if "xxx" in workspace.lower() or "xxx" in tenant.lower():
            return False
        return bool(tenant and client and workspace)

    def diagnostics(self) -> dict:
        return {
            "copilot": bool(self.github_token),
            "anthropic": bool(self.anthropic_api_key),
            "databricks": self.has_databricks(),
            "fabric": self.has_fabric(),
        }


settings = Settings()
