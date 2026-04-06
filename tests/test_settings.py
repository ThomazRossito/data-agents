"""Testes de validação do config/settings.py."""

import pytest
from config.settings import Settings


class TestSettingsValidation:
    """Testes para validação de configurações."""

    def test_default_values(self):
        """Verifica que os valores padrão são razoáveis."""
        s = Settings()
        assert s.max_budget_usd == 5.0
        assert s.max_turns == 50
        assert s.log_level == "INFO"
        assert s.default_model == "claude-opus-4-6"

    def test_budget_must_be_positive(self):
        """Verifica que budget negativo ou zero é rejeitado."""
        with pytest.raises(ValueError, match="maior que zero"):
            Settings(max_budget_usd=0)

        with pytest.raises(ValueError, match="maior que zero"):
            Settings(max_budget_usd=-1.0)

    def test_max_turns_must_be_positive(self):
        """Verifica que max_turns menor que 1 é rejeitado."""
        with pytest.raises(ValueError, match="pelo menos 1"):
            Settings(max_turns=0)

    def test_high_budget_emits_warning(self):
        """Verifica que budget alto emite warning."""
        with pytest.warns(UserWarning, match="muito alto"):
            Settings(max_budget_usd=150.0)

    def test_high_turns_emits_warning(self):
        """Verifica que max_turns alto emite warning."""
        with pytest.warns(UserWarning, match="muito alto"):
            Settings(max_turns=300)


class TestPlatformCredentials:
    """Testes para validação de credenciais por plataforma."""

    def test_no_credentials_returns_not_ready(self):
        """Sem credenciais, nenhuma plataforma de dados deve estar ready."""
        # Força todos os campos de credencial a string vazia para isolar do ambiente
        s = Settings(
            databricks_host="",
            databricks_token="",
            databricks_sql_warehouse_id="",
            azure_tenant_id="",
            azure_client_id="",
            azure_client_secret="",
            fabric_workspace_id="",
            kusto_service_uri="",
            kusto_service_default_db="",
        )
        status = s.validate_platform_credentials()
        for platform, info in status.items():
            if platform != "anthropic":
                assert not info["ready"], f"{platform} deveria estar not ready"

    def test_databricks_ready_with_credentials(self):
        """Com host e token, Databricks deve estar ready."""
        s = Settings(
            databricks_host="https://adb-123.azuredatabricks.net",
            databricks_token="dapi12345",
        )
        status = s.validate_platform_credentials()
        assert status["databricks"]["ready"]
        assert status["databricks"]["missing"] == []

    def test_databricks_not_ready_without_token(self):
        """Sem token, Databricks não deve estar ready."""
        # Força token vazio para isolar do ambiente de CI (que pode ter DATABRICKS_TOKEN)
        s = Settings(
            databricks_host="https://adb-123.azuredatabricks.net",
            databricks_token="",
        )
        status = s.validate_platform_credentials()
        assert not status["databricks"]["ready"]
        assert "DATABRICKS_TOKEN" in status["databricks"]["missing"]

    def test_fabric_ready_with_credentials(self):
        """Com tenant_id e workspace_id, Fabric deve estar ready."""
        s = Settings(
            azure_tenant_id="tenant-123",
            fabric_workspace_id="ws-456",
        )
        status = s.validate_platform_credentials()
        assert status["fabric"]["ready"]

    def test_get_available_platforms_filters_correctly(self):
        """Apenas plataformas com credenciais devem aparecer."""
        s = Settings(
            databricks_host="https://adb-123.azuredatabricks.net",
            databricks_token="dapi12345",
        )
        available = s.get_available_platforms()
        assert "databricks" in available
        assert "fabric" not in available
        assert "fabric_rti" not in available
