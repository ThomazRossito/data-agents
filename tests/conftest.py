"""Fixtures compartilhadas para a suite de testes."""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _ensure_github_token(monkeypatch):
    """Garante GITHUB_TOKEN disponível sem precisar do .env real.

    `Settings()` é instanciado em import-time — então além do setenv
    (que afeta novas instâncias), também sobrescreve a instância singleton.
    """
    if not os.environ.get("GITHUB_TOKEN"):
        monkeypatch.setenv("GITHUB_TOKEN", "test_token_fixture")
    from config.settings import settings
    if not settings.github_token:
        monkeypatch.setattr(settings, "github_token", "test_token_fixture")
