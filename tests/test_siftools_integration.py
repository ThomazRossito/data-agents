"""Testes para o pruning semântico de tools via siftools.

Foco nas invariantes que o pruning global por top-k NÃO garantia e que
motivaram a correção: um agente multi-plataforma (ex: sql-expert com
Databricks + Fabric SQL + Fabric Official + ...) não pode perder TODAS as
tools de um servidor MCP declarado só porque outro servidor dominou o
ranking de similaridade contra a descrição do agente.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agents import siftools_integration


class _FakeResult:
    def __init__(self, tools: list[str]) -> None:
        self.tools = tools


class _FakeRouter:
    def __init__(self, ranking: list[str]) -> None:
        self._ranking = ranking

    def route(self, _query: str) -> _FakeResult:
        return _FakeResult(self._ranking)


@pytest.fixture
def fake_index(monkeypatch):
    """Reseta os singletons do módulo e devolve um index fake."""
    monkeypatch.setattr(siftools_integration, "_index_singleton", None)
    monkeypatch.setattr(siftools_integration, "_router_singleton", None)
    monkeypatch.setattr(siftools_integration, "_index_failed", False)
    index = MagicMock()
    monkeypatch.setattr(siftools_integration, "_get_index", lambda: index)
    return index


def _install_router(monkeypatch, ranking: list[str]) -> None:
    monkeypatch.setattr(siftools_integration, "_router_singleton", _FakeRouter(ranking))


def test_pruning_disabled_returns_input_verbatim(monkeypatch):
    monkeypatch.setenv("SIFTOOLS_PRUNING_ENABLED", "false")
    tools = ["Read", "mcp__databricks__x", "mcp__fabric_sql__y"]
    assert siftools_integration.prune_agent_tools(tools, "desc") == tools


def test_pruning_short_circuits_when_below_top_k(monkeypatch, fake_index):
    """Se o agente já tem <= top_k tools MCP, pruning não roda."""
    monkeypatch.setenv("SIFTOOLS_PRUNING_ENABLED", "true")
    monkeypatch.setenv("SIFTOOLS_TOP_K", "15")

    tools = ["Read"] + [f"mcp__x__t{i}" for i in range(10)]
    # _router_singleton continua None — provaria que não foi chamado se explodisse.
    assert siftools_integration.prune_agent_tools(tools, "desc") == tools


def test_pruning_preserves_floor_per_mcp_server(monkeypatch, fake_index):
    """Regressão: sql-expert não pode perder fabric_sql inteiro.

    Cenário: 9 "servidores" declarados. O ranking global está enviesado para
    Databricks (simulando a situação real em que a descrição estática do
    agente tem mais afinidade com tools de SQL em Unity Catalog). Sem piso
    por servidor, top-15 seria 100% Databricks e fabric_sql desapareceria.
    Com piso MIN_PER_SERVER=2, cada servidor declarado sobrevive.
    """
    monkeypatch.setenv("SIFTOOLS_PRUNING_ENABLED", "true")
    monkeypatch.setenv("SIFTOOLS_TOP_K", "15")
    monkeypatch.setenv("SIFTOOLS_MIN_PER_SERVER", "2")

    databricks = [f"mcp__databricks__t{i}" for i in range(50)]
    fabric_official = [f"mcp__fabric_official__t{i}" for i in range(10)]
    fabric_sql = [f"mcp__fabric_sql__t{i}" for i in range(8)]
    context7 = [f"mcp__context7__t{i}" for i in range(3)]

    ranking = databricks + fabric_official + fabric_sql + context7
    declared = ranking[:]
    _install_router(monkeypatch, ranking)

    result = siftools_integration.prune_agent_tools(
        tools=["Read", "Bash"] + declared,
        agent_description="Especialista em SQL e metadados — Databricks + Fabric",
    )

    assert "Read" in result and "Bash" in result

    for server in ("databricks", "fabric_official", "fabric_sql", "context7"):
        prefix = f"mcp__{server}__"
        count = sum(1 for t in result if t.startswith(prefix))
        assert count >= 2, (
            f"servidor {server!r} sumiu após pruning — count={count}, "
            f"resultado={[t for t in result if t.startswith('mcp__')]}"
        )


def test_pruning_floor_overrides_top_k_when_necessary(monkeypatch, fake_index):
    """Se MIN_PER_SERVER × num_servers > top_k, o piso vence.

    Melhor manter cobertura multi-servidor do que respeitar o teto global —
    o teto é uma otimização, o piso é uma garantia de correção.
    """
    monkeypatch.setenv("SIFTOOLS_PRUNING_ENABLED", "true")
    monkeypatch.setenv("SIFTOOLS_TOP_K", "6")
    monkeypatch.setenv("SIFTOOLS_MIN_PER_SERVER", "2")

    servers = ["a", "b", "c", "d"]  # 4 servidores × piso 2 = 8 > top_k 6
    ranking = [f"mcp__{s}__t{i}" for s in servers for i in range(3)]
    _install_router(monkeypatch, ranking)

    result = siftools_integration.prune_agent_tools(
        tools=ranking,
        agent_description="multi-plataforma",
    )

    for s in servers:
        assert any(t.startswith(f"mcp__{s}__") for t in result), f"{s!r} sumiu"


def test_pruning_keeps_declared_only(monkeypatch, fake_index):
    """Tools fora da allowed-list declarada não devem aparecer no resultado,
    mesmo que apareçam no ranking do router."""
    monkeypatch.setenv("SIFTOOLS_PRUNING_ENABLED", "true")
    monkeypatch.setenv("SIFTOOLS_TOP_K", "15")

    declared = [f"mcp__declared__t{i}" for i in range(20)]
    undeclared = [f"mcp__forbidden__t{i}" for i in range(20)]
    # Router ranqueia forbidden primeiro — ainda assim não deve vazar.
    _install_router(monkeypatch, undeclared + declared)

    result = siftools_integration.prune_agent_tools(
        tools=declared,
        agent_description="desc",
    )

    for t in result:
        assert not t.startswith("mcp__forbidden__"), f"{t} vazou da allowed-list"
