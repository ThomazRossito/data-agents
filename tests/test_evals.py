"""Testes para evals/runner.py — loader + scoring (determinísticos, sem rede)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from evals.runner import (
    DEFAULT_QUERIES_PATH,
    EvalResult,
    Query,
    Rubric,
    _filter_queries,
    detect_regressions,
    load_latest_run,
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


# ─── load_latest_run ─────────────────────────────────────────────────────────


class TestLoadLatestRun:
    def test_returns_none_when_no_logs_dir(self, tmp_path: Path, monkeypatch):
        import evals.runner as runner_mod

        monkeypatch.setattr(runner_mod, "REPO_ROOT", tmp_path)
        assert load_latest_run() is None

    def test_returns_none_when_no_jsonl_files(self, tmp_path: Path, monkeypatch):
        import evals.runner as runner_mod

        (tmp_path / "logs" / "evals").mkdir(parents=True)
        monkeypatch.setattr(runner_mod, "REPO_ROOT", tmp_path)
        assert load_latest_run() is None

    def test_loads_scores_from_latest_file(self, tmp_path: Path, monkeypatch):
        import json
        import evals.runner as runner_mod

        evals_dir = tmp_path / "logs" / "evals"
        evals_dir.mkdir(parents=True)
        run_file = evals_dir / "20260101T000000Z.jsonl"
        records = [
            {"query_id": "medallion-architecture", "score": 1.0},
            {"query_id": "delta-lake-features", "score": 0.5},
        ]
        run_file.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
        monkeypatch.setattr(runner_mod, "REPO_ROOT", tmp_path)
        result = load_latest_run()
        assert result == {"medallion-architecture": 1.0, "delta-lake-features": 0.5}

    def test_picks_most_recent_file(self, tmp_path: Path, monkeypatch):
        import json
        import evals.runner as runner_mod

        evals_dir = tmp_path / "logs" / "evals"
        evals_dir.mkdir(parents=True)
        old = evals_dir / "20260101T000000Z.jsonl"
        old.write_text(json.dumps({"query_id": "q1", "score": 0.0}), encoding="utf-8")
        new = evals_dir / "20260201T000000Z.jsonl"
        new.write_text(json.dumps({"query_id": "q1", "score": 1.0}), encoding="utf-8")
        monkeypatch.setattr(runner_mod, "REPO_ROOT", tmp_path)
        result = load_latest_run()
        assert result == {"q1": 1.0}


# ─── detect_regressions ──────────────────────────────────────────────────────


def _make_result(query_id: str, score: float) -> EvalResult:
    return EvalResult(
        query_id=query_id,
        domain="test",
        score=score,
        passed=score == 1.0,
        response_chars=100,
        cost_usd=0.0,
        duration_s=0.0,
        failures=[],
    )


class TestDetectRegressions:
    def test_no_regression_when_scores_equal(self):
        baseline = {"q1": 1.0, "q2": 0.5}
        results = [_make_result("q1", 1.0), _make_result("q2", 0.5)]
        assert detect_regressions(results, baseline) == []

    def test_detects_drop_from_pass_to_fail(self):
        baseline = {"q1": 1.0}
        results = [_make_result("q1", 0.0)]
        regressions = detect_regressions(results, baseline)
        assert len(regressions) == 1
        assert regressions[0] == ("q1", 1.0, 0.0)

    def test_detects_drop_from_pass_to_partial(self):
        baseline = {"q1": 1.0}
        results = [_make_result("q1", 0.5)]
        regressions = detect_regressions(results, baseline)
        assert regressions[0] == ("q1", 1.0, 0.5)

    def test_improvement_is_not_a_regression(self):
        baseline = {"q1": 0.5}
        results = [_make_result("q1", 1.0)]
        assert detect_regressions(results, baseline) == []

    def test_new_query_not_in_baseline_is_ignored(self):
        baseline = {"q1": 1.0}
        results = [_make_result("q1", 1.0), _make_result("q2_new", 0.0)]
        assert detect_regressions(results, baseline) == []

    def test_empty_baseline_returns_no_regressions(self):
        results = [_make_result("q1", 0.0)]
        assert detect_regressions(results, {}) == []
