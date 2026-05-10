"""
Testes para `agents.delegation` — mapa declarativo de delegação (T2.4).

Invariants:
  - Todo `route.agent` aponta para um registry válido em `agents/registry/`.
  - A tabela em `kb/task_routing.md` §2 está em sincronia com o YAML.
  - `classify()` é determinístico e não chama LLM.
"""

import re
from pathlib import Path

from agents.delegation import (
    Route,
    classify,
    load_delegation_map,
    render_routing_table,
)

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_DIR = ROOT / "agents" / "registry"
TASK_ROUTING_MD = ROOT / "kb" / "task_routing.md"


class TestDelegationMap:
    def test_yaml_loads(self):
        routes = load_delegation_map()
        assert len(routes) > 0
        assert all(isinstance(r, Route) for r in routes)

    def test_all_agents_exist_in_registry(self):
        """Invariante: todo route aponta para um agente real."""
        registry_agents = {p.stem for p in REGISTRY_DIR.glob("*.md") if p.stem != "_template"}
        for route in load_delegation_map():
            assert route.agent in registry_agents, (
                f"Route '{route.situation}' → agent '{route.agent}' não existe em agents/registry/"
            )

    def test_no_duplicate_situations(self):
        situations = [r.situation for r in load_delegation_map()]
        assert len(situations) == len(set(situations)), "Situações duplicadas no YAML"

    def test_tier_is_valid_when_set(self):
        valid = {"T0", "T1", "T2", "T3", ""}
        for route in load_delegation_map():
            assert route.tier in valid, f"Tier inválido: {route.tier}"


class TestRenderRoutingTable:
    def test_contains_all_routes(self):
        table = render_routing_table()
        for route in load_delegation_map():
            assert route.situation in table
            assert route.agent in table

    def test_table_synced_with_task_routing_md(self):
        """kb/task_routing.md §2 contém a mesma tabela gerada pelo YAML."""
        md = TASK_ROUTING_MD.read_text(encoding="utf-8")
        match = re.search(
            r"<!-- BEGIN delegation_map.*?-->\s*(.*?)\s*<!-- END delegation_map -->",
            md,
            re.DOTALL,
        )
        assert match, "Marker <!-- BEGIN/END delegation_map --> não encontrado"
        embedded = match.group(1).strip()
        generated = render_routing_table().strip()
        assert embedded == generated, (
            "kb/task_routing.md §2 fora de sincronia com delegation_map.yaml. "
            "Rode: python -c 'from agents.delegation import render_routing_table; "
            "print(render_routing_table())'"
        )


class TestClassify:
    def test_returns_none_on_no_match(self):
        assert classify("xyz abc qualquer coisa não relacionada 12345") is None

    def test_matches_spark_keyword(self):
        assert classify("preciso escrever um job pyspark") == "spark-expert"

    def test_matches_dbt_keyword(self):
        assert classify("vamos criar models dbt") == "dbt-expert"

    def test_matches_pii_keyword(self):
        assert classify("campo contém PII de cliente") == "governance-auditor"

    def test_case_insensitive(self):
        assert classify("POWER BI DAX medidas") == "semantic-modeler"

    def test_deterministic(self):
        """Duas chamadas com mesmo input retornam mesmo resultado."""
        q = "criar dashboard ai/bi"
        assert classify(q) == classify(q)
