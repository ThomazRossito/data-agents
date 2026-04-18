"""Testes para evals/runner.py — loader + scoring (determinísticos, sem rede)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from evals.runner import (
    DEFAULT_QUERIES_PATH,
    Query,
    Rubric,
    _filter_queries,
    load_queries,
    score_response,
)


# ─── load_queries ────────────────────────────────────────────────────────────


class TestLoadQueries:
    def test_loads_canonical_yaml(self):
        queries = load_queries(DEFAULT_QUERIES_PATH)
        assert len(queries) >= 10, "Esperado ao menos 10 queries canônicas"
        for q in queries:
            assert q.id
            assert q.domain
            assert q.prompt
            assert isinstance(q.rubric, Rubric)

    def test_query_ids_are_unique(self):
        queries = load_queries(DEFAULT_QUERIES_PATH)
        ids = [q.id for q in queries]
        assert len(ids) == len(set(ids)), "IDs de query não são únicos"

    def test_raises_on_missing_queries_key(self, tmp_path: Path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("version: 1\n")
        with pytest.raises(ValueError, match="queries"):
            load_queries(bad)

    def test_raises_on_missing_required_field(self, tmp_path: Path):
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            yaml.safe_dump({"queries": [{"id": "x", "domain": "test"}]}),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="prompt"):
            load_queries(bad)

    def test_default_rubric_when_absent(self, tmp_path: Path):
        good = tmp_path / "good.yaml"
        good.write_text(
            yaml.safe_dump({"queries": [{"id": "x", "domain": "test", "prompt": "Hello?"}]}),
            encoding="utf-8",
        )
        queries = load_queries(good)
        assert queries[0].rubric.must_include == []
        assert queries[0].rubric.min_length == 0


# ─── score_response ──────────────────────────────────────────────────────────


class TestScoreResponse:
    def test_perfect_match(self):
        rubric = Rubric(must_include=["bronze", "silver", "gold"], min_length=10)
        score, passed, failures = score_response(
            "A camada Bronze, depois Silver e por fim Gold.", rubric
        )
        assert score == 1.0
        assert passed is True
        assert failures == []

    def test_case_insensitive(self):
        rubric = Rubric(must_include=["MEDALLION"])
        score, passed, _ = score_response("A arquitetura medallion é comum.", rubric)
        assert score == 1.0
        assert passed is True

    def test_must_not_include_fails_critically(self):
        rubric = Rubric(
            must_include=["delta"],
            must_not_include=["não sei"],
        )
        score, passed, failures = score_response(
            "Desculpe, não sei responder essa pergunta sobre Delta.", rubric
        )
        assert score == 0.0
        assert passed is False
        assert any("must_not_include" in f for f in failures)

    def test_partial_match_gets_half_score(self):
        rubric = Rubric(
            must_include=["bronze", "silver", "gold", "medallion"],
            min_length=10,
        )
        score, passed, failures = score_response(
            "A camada Bronze vem antes da Silver nessa arquitetura.", rubric
        )
        assert score == 0.5
        assert passed is False
        assert any("parcial" in f.lower() for f in failures)

    def test_minority_match_fails(self):
        rubric = Rubric(
            must_include=["bronze", "silver", "gold", "medallion"],
            min_length=5,
        )
        score, passed, _ = score_response("Alguma coisa só sobre Bronze.", rubric)
        assert score == 0.0
        assert passed is False

    def test_length_too_short(self):
        rubric = Rubric(must_include=["x"], min_length=100)
        score, passed, failures = score_response("curta", rubric)
        assert score == 0.0
        assert passed is False
        assert any("curta" in f for f in failures)

    def test_length_too_long(self):
        rubric = Rubric(must_include=["x"], min_length=0, max_length=10)
        score, passed, failures = score_response("x" + "a" * 50, rubric)
        assert score == 0.0
        assert passed is False
        assert any("longa" in f for f in failures)

    def test_empty_must_include_passes_when_length_ok(self):
        rubric = Rubric(must_include=[], min_length=5)
        score, passed, _ = score_response("resposta qualquer", rubric)
        assert score == 1.0
        assert passed is True


# ─── _filter_queries ─────────────────────────────────────────────────────────


class TestFilterQueries:
    @pytest.fixture
    def sample_queries(self) -> list[Query]:
        return [
            Query(id="a", domain="sql", prompt="p1", rubric=Rubric()),
            Query(id="b", domain="spark", prompt="p2", rubric=Rubric()),
            Query(id="c", domain="sql", prompt="p3", rubric=Rubric()),
        ]

    def test_filter_by_domain(self, sample_queries):
        result = _filter_queries(sample_queries, domain="sql", query_id=None, limit=None)
        assert [q.id for q in result] == ["a", "c"]

    def test_filter_by_id(self, sample_queries):
        result = _filter_queries(sample_queries, domain=None, query_id="b", limit=None)
        assert [q.id for q in result] == ["b"]

    def test_filter_by_limit(self, sample_queries):
        result = _filter_queries(sample_queries, domain=None, query_id=None, limit=2)
        assert len(result) == 2

    def test_filter_combines_domain_and_limit(self, sample_queries):
        result = _filter_queries(sample_queries, domain="sql", query_id=None, limit=1)
        assert [q.id for q in result] == ["a"]

    def test_no_filters_returns_all(self, sample_queries):
        result = _filter_queries(sample_queries, None, None, None)
        assert result == sample_queries
