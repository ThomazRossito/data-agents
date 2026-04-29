"""Testes para config/settings.py."""
from __future__ import annotations

import pytest


def test_settings_loads_without_github_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    import config.settings as mod
    # Reinicializar para capturar a mudança de env
    s = mod.Settings()
    assert s.github_token == ""


def test_settings_copilot_client_raises_without_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    from config.settings import Settings
    s = Settings()
    with pytest.raises(EnvironmentError, match="GITHUB_TOKEN"):
        _ = s.copilot_client


def test_settings_has_databricks_false_by_default():
    from config.settings import Settings
    s = Settings()
    assert s.has_databricks() is False


def test_settings_has_fabric_false_by_default():
    from config.settings import Settings
    s = Settings()
    assert s.has_fabric() is False


def test_settings_diagnostics_structure():
    from config.settings import Settings
    s = Settings()
    d = s.diagnostics()
    assert "copilot" in d
    assert "databricks" in d
    assert "fabric" in d


def test_settings_model_for_tier_default():
    from config.settings import Settings
    s = Settings()
    model = s.model_for_tier("T1")
    assert isinstance(model, str)
    assert len(model) > 0


def test_settings_model_for_tier_unknown_falls_back():
    from config.settings import Settings
    s = Settings()
    model = s.model_for_tier("T99")
    assert model == s.default_model


def test_settings_qa_enabled_default():
    from config.settings import Settings
    s = Settings()
    assert s.qa_enabled is True
    assert s.qa_score_threshold == 0.7
