"""
Fixtures globais de teste.

Garante que testes nunca escrevam nos bancos SQLite de produção
(long_term.db, short_term.db, embedder_cache.db).
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_memory_dbs(tmp_path, monkeypatch):
    """
    Redireciona todos os caminhos de banco SQLite de memória para tmp_path.

    Aplicado automaticamente em todos os testes. Garante que:
      - LongTermMemory não escreve em memory/data/long_term.db
      - ShortTermMemory não escreve em memory/data/short_term.db
      - LocalEmbedder não escreve em memory/data/embedder_cache.db
    """
    from config.settings import settings

    monkeypatch.setattr(settings, "long_term_db_path", str(tmp_path / "long_term.db"))
    monkeypatch.setattr(settings, "short_term_db_path", str(tmp_path / "short_term.db"))
    monkeypatch.setattr(settings, "embedder_cache_db_path", str(tmp_path / "embedder_cache.db"))
