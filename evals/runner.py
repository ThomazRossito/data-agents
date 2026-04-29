"""
Evals runner — executa queries canônicas e pontua com rubric determinística.

Uso:
    python -m evals.runner                           # roda todas
    python -m evals.runner --domain conceptual       # filtra por domain
    python -m evals.runner --id medallion-architecture  # uma query
    python -m evals.runner --limit 5                 # primeiras N queries

    make evals

Persiste resultado em logs/evals/<timestamp>.jsonl.
Exit code 0 se todas passaram, 1 se alguma falhou.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from agents.base import BaseAgent
from agents.loader import load_all

if TYPE_CHECKING:
    from agents.supervisor import Supervisor

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUERIES_PATH = REPO_ROOT / "evals" / "canonical_queries.yaml"

logger = logging.getLogger("data_agents.evals")


# ── Modelos ──────────────────────────────────────────────────────────────────

@dataclass
class Rubric:
    must_include: list[str] = field(default_factory=list)
    must_not_include: list[str] = field(default_factory=list)
    min_length: int = 0
    max_length: int = 100_000


@dataclass
class Query:
    id: str
    domain: str
    prompt: str
    rubric: Rubric


@dataclass
class EvalResult:
    query_id: str
    domain: str
    score: float
    passed: bool
    response_chars: int
    cost_tokens: int
    failures: list[str]


# ── Carga e parsing ──────────────────────────────────────────────────────────

def load_queries(path: Path = DEFAULT_QUERIES_PATH) -> list[Query]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "queries" not in data:
        raise ValueError(f"YAML inválido em {path}: esperado chave 'queries'")

    queries: list[Query] = []
    for entry in data["queries"]:
        if not isinstance(entry, dict):
            raise ValueError(f"Entrada inválida: {entry}")
        for required in ("id", "domain", "prompt"):
            if required not in entry:
                raise ValueError(f"Query sem campo '{required}': {entry}")
        rubric_data = entry.get("rubric") or {}
        queries.append(
            Query(
                id=entry["id"],
                domain=entry["domain"],
                prompt=entry["prompt"].strip(),
                rubric=Rubric(
                    must_include=list(rubric_data.get("must_include", [])),
                    must_not_include=list(
                        rubric_data.get("must_not_include", [])
                    ),
                    min_length=int(rubric_data.get("min_length", 0)),
                    max_length=int(rubric_data.get("max_length", 100_000)),
                ),
            )
        )
    return queries


# ── Scoring ──────────────────────────────────────────────────────────────────

def score_response(
    response: str, rubric: Rubric
) -> tuple[float, bool, list[str]]:
    """
    Pontua uma resposta contra a rubric determinística.

    Returns:
        (score, passed, failures)
        - score: 0.0 | 0.5 | 1.0
        - passed: True se score == 1.0
        - failures: razões (vazia se passou)
    """
    failures: list[str] = []
    response_lower = response.lower()

    # must_not_include — falha crítica
    hits_negative = [
        term
        for term in rubric.must_not_include
        if term.lower() in response_lower
    ]
    if hits_negative:
        failures.append(f"must_not_include bateu: {hits_negative}")
        return 0.0, False, failures

    # length check
    length = len(response)
    if length < rubric.min_length:
        failures.append(
            f"resposta curta demais: {length} < {rubric.min_length}"
        )
        return 0.0, False, failures
    if length > rubric.max_length:
        failures.append(
            f"resposta longa demais: {length} > {rubric.max_length}"
        )
        return 0.0, False, failures

    # must_include
    if not rubric.must_include:
        return 1.0, True, failures

    hits = sum(
        1 for term in rubric.must_include if term.lower() in response_lower
    )
    ratio = hits / len(rubric.must_include)

    if ratio == 1.0:
        return 1.0, True, failures
    if ratio >= 0.5:
        missing = [
            t for t in rubric.must_include if t.lower() not in response_lower
        ]
        failures.append(
            f"must_include parcial ({hits}/{len(rubric.must_include)}): "
            f"faltam {missing}"
        )
        return 0.5, False, failures

    missing = [
        t for t in rubric.must_include if t.lower() not in response_lower
    ]
    failures.append(
        f"must_include falhou ({hits}/{len(rubric.must_include)}): "
        f"faltam {missing}"
    )
    return 0.0, False, failures


# ── Execução ─────────────────────────────────────────────────────────────────

def run_query(query: Query, agent: BaseAgent) -> EvalResult:
    """Executa uma query via agente direto e pontua."""
    try:
        result = agent.run(query.prompt)
        response = result.content
        tokens = result.tokens_used
    except Exception as e:
        return EvalResult(
            query_id=query.id,
            domain=query.domain,
            score=0.0,
            passed=False,
            response_chars=0,
            cost_tokens=0,
            failures=[f"exception: {type(e).__name__}: {e}"],
        )

    score, passed, failures = score_response(response, query.rubric)
    return EvalResult(
        query_id=query.id,
        domain=query.domain,
        score=score,
        passed=passed,
        response_chars=len(response),
        cost_tokens=tokens,
        failures=failures,
    )


def run_query_routed(query: Query, supervisor: Supervisor) -> EvalResult:
    """Executa uma query via Supervisor.route() — usa roteamento real por domínio."""
    try:
        result = supervisor.route(query.prompt)
        response = result.content
        tokens = result.tokens_used
    except Exception as e:
        return EvalResult(
            query_id=query.id,
            domain=query.domain,
            score=0.0,
            passed=False,
            response_chars=0,
            cost_tokens=0,
            failures=[f"exception: {type(e).__name__}: {e}"],
        )

    score, passed, failures = score_response(response, query.rubric)
    return EvalResult(
        query_id=query.id,
        domain=query.domain,
        score=score,
        passed=passed,
        response_chars=len(response),
        cost_tokens=tokens,
        failures=failures,
    )


def run_all(queries: list[Query], agent: BaseAgent) -> list[EvalResult]:
    results: list[EvalResult] = []
    for i, query in enumerate(queries, 1):
        print(f"  [{i}/{len(queries)}] {query.id}...", flush=True)
        result = run_query(query, agent)
        _print_query_result(result)
        results.append(result)
    return results


def run_all_routed(queries: list[Query], supervisor: Supervisor) -> list[EvalResult]:
    """Executa todas as queries via Supervisor.route() — roteamento real por domínio."""
    results: list[EvalResult] = []
    for i, query in enumerate(queries, 1):
        print(f"  [{i}/{len(queries)}] {query.id} [routed]...", flush=True)
        result = run_query_routed(query, supervisor)
        _print_query_result(result)
        results.append(result)
    return results


def _print_query_result(result: EvalResult) -> None:
    status = "✅" if result.passed else ("◐" if result.score == 0.5 else "❌")
    print(f"      {status} score={result.score} tokens={result.cost_tokens}")
    for failure in result.failures:
        print(f"      ↳ {failure}")


# ── Persistência ─────────────────────────────────────────────────────────────

def _persist_results(results: list[EvalResult]) -> Path:
    evals_dir = REPO_ROOT / "logs" / "evals"
    evals_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = evals_dir / f"{ts}.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(
                json.dumps(
                    {
                        "query_id": r.query_id,
                        "domain": r.domain,
                        "score": r.score,
                        "passed": r.passed,
                        "response_chars": r.response_chars,
                        "cost_tokens": r.cost_tokens,
                        "failures": r.failures,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    return path


def _print_summary(results: list[EvalResult], log_path: Path) -> int:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    partial = sum(1 for r in results if r.score == 0.5)
    failed = sum(1 for r in results if r.score == 0.0)
    total_tokens = sum(r.cost_tokens for r in results)

    print("\n" + "━" * 60)
    print(" Sumário")
    print("━" * 60)
    print(f"  Total:     {total}")
    print(f"  ✅ Passed:  {passed} ({passed / total * 100:.0f}%)")
    print(f"  ◐ Partial: {partial}")
    print(f"  ❌ Failed:  {failed}")
    print(f"  🔢 Tokens:  {total_tokens}")
    print(f"  📄 Log:     {log_path.relative_to(REPO_ROOT)}")
    print()

    return 0 if failed == 0 and partial == 0 else 1


# ── CLI ──────────────────────────────────────────────────────────────────────

def _filter_queries(
    queries: list[Query],
    domain: str | None,
    query_id: str | None,
    limit: int | None,
) -> list[Query]:
    filtered = queries
    if domain:
        filtered = [q for q in filtered if q.domain == domain]
    if query_id:
        filtered = [q for q in filtered if q.id == query_id]
    if limit and limit > 0:
        filtered = filtered[:limit]
    return filtered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="data-agents-copilot — Evals runner"
    )
    parser.add_argument(
        "--domain",
        help="Filtrar por domain (ex: conceptual, sql, spark)",
    )
    parser.add_argument("--id", help="Executar só a query com este id")
    parser.add_argument(
        "--limit", type=int, help="Limitar às N primeiras queries"
    )
    parser.add_argument(
        "--queries-path",
        type=Path,
        default=DEFAULT_QUERIES_PATH,
        help="Caminho do YAML de queries",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida queries e rubric sem chamar o agente (não requer GITHUB_TOKEN)",
    )
    parser.add_argument(
        "--use-supervisor",
        action="store_true",
        help="Roteia queries via Supervisor.route() em vez de usar agente geral direto",
    )
    args = parser.parse_args(argv)

    print("━" * 60)
    print(" data-agents-copilot — Evals Runner")
    print("━" * 60)

    try:
        queries = load_queries(args.queries_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"\n❌ Erro ao carregar queries: {e}")
        return 2

    queries = _filter_queries(queries, args.domain, args.id, args.limit)
    if not queries:
        print("\n⚠️  Nenhuma query casou com os filtros.")
        return 2

    if args.dry_run:
        print(f"\n[dry-run] {len(queries)} query(ies) carregada(s) e válida(s):\n")
        for q in queries:
            mi = len(q.rubric.must_include)
            mn = len(q.rubric.must_not_include)
            print(
                f"  • {q.id} [{q.domain}] "
                f"must_include={mi} must_not_include={mn} "
                f"len=[{q.rubric.min_length}, {q.rubric.max_length}]"
            )
        print("\n✅ Estrutura OK. Use sem --dry-run para executar contra o agente.")
        return 0

    if args.use_supervisor:
        print(f"\nExecutando {len(queries)} query(ies) via Supervisor.route() (roteamento real):\n")
        from agents.supervisor import Supervisor
        supervisor = Supervisor()
        results = run_all_routed(queries, supervisor)
    else:
        print(f"\nExecutando {len(queries)} query(ies) via agente geral (T3):\n")
        agents = load_all()
        geral_agent = agents.get("geral")
        if geral_agent is None:
            print("❌ Agente 'geral' não encontrado no registry.")
            return 2
        results = run_all(queries, geral_agent)
    log_path = _persist_results(results)
    return _print_summary(results, log_path)


if __name__ == "__main__":
    sys.exit(main())
