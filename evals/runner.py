"""
Evals runner — executa queries canônicas e pontua com rubric determinística.

Uso:
    python -m evals.runner                      # roda todas
    python -m evals.runner --domain conceptual  # filtra por domain
    python -m evals.runner --id medallion-architecture  # uma query
    python -m evals.runner --limit 3            # primeiras N queries

    make evals

Persiste resultado em `logs/evals/<timestamp>.jsonl`.
Exit code 0 se todas passaram, 1 se alguma falhou.

Rubric (determinística):
  1.0 — must_include 100% + must_not_include 0% + length no intervalo
  0.5 — must_include ≥ 50% dos termos
  0.0 — falha crítica
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUERIES_PATH = REPO_ROOT / "evals" / "canonical_queries.yaml"

logger = logging.getLogger("data_agents.evals")


# ─── Modelos ──────────────────────────────────────────────────────────────────


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
    cost_usd: float
    duration_s: float
    failures: list[str]


# ─── Carga e parsing ─────────────────────────────────────────────────────────


def load_queries(path: Path = DEFAULT_QUERIES_PATH) -> list[Query]:
    """Carrega queries do YAML e valida campos obrigatórios."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "queries" not in data:
        raise ValueError(f"YAML inválido em {path}: esperado chave 'queries'")

    queries: list[Query] = []
    for entry in data["queries"]:
        if not isinstance(entry, dict):
            raise ValueError(f"Entrada inválida (não é dict): {entry}")
        for required in ("id", "domain", "prompt"):
            if required not in entry:
                raise ValueError(f"Query sem campo obrigatório '{required}': {entry}")
        rubric_data = entry.get("rubric") or {}
        queries.append(
            Query(
                id=entry["id"],
                domain=entry["domain"],
                prompt=entry["prompt"].strip(),
                rubric=Rubric(
                    must_include=list(rubric_data.get("must_include", [])),
                    must_not_include=list(rubric_data.get("must_not_include", [])),
                    min_length=int(rubric_data.get("min_length", 0)),
                    max_length=int(rubric_data.get("max_length", 100_000)),
                ),
            )
        )
    return queries


# ─── Scoring ─────────────────────────────────────────────────────────────────


def score_response(response: str, rubric: Rubric) -> tuple[float, bool, list[str]]:
    """
    Pontua uma resposta contra a rubric determinística.

    Returns:
        (score, passed, failures)
        - score: 0.0 | 0.5 | 1.0
        - passed: True se score == 1.0
        - failures: lista de razões para debug (vazia se passou)
    """
    failures: list[str] = []
    response_lower = response.lower()

    # 1) must_not_include — falha crítica se bater
    hits_negative = [term for term in rubric.must_not_include if term.lower() in response_lower]
    if hits_negative:
        failures.append(f"must_not_include bateu: {hits_negative}")
        return 0.0, False, failures

    # 2) length check — falha se fora do intervalo
    length = len(response)
    if length < rubric.min_length:
        failures.append(f"resposta curta demais: {length} < {rubric.min_length}")
        return 0.0, False, failures
    if length > rubric.max_length:
        failures.append(f"resposta longa demais: {length} > {rubric.max_length}")
        return 0.0, False, failures

    # 3) must_include — contagem de hits
    if not rubric.must_include:
        return 1.0, True, failures

    hits = sum(1 for term in rubric.must_include if term.lower() in response_lower)
    ratio = hits / len(rubric.must_include)

    if ratio == 1.0:
        return 1.0, True, failures
    if ratio >= 0.5:
        missing = [term for term in rubric.must_include if term.lower() not in response_lower]
        failures.append(
            f"must_include parcial ({hits}/{len(rubric.must_include)}): faltam {missing}"
        )
        return 0.5, False, failures

    missing = [term for term in rubric.must_include if term.lower() not in response_lower]
    failures.append(f"must_include falhou ({hits}/{len(rubric.must_include)}): faltam {missing}")
    return 0.0, False, failures


# ─── Execução ────────────────────────────────────────────────────────────────


async def run_query(query: Query) -> EvalResult:
    """Executa uma query via run_geral_query e pontua."""
    from commands.geral import run_geral_query

    history = [{"role": "user", "content": query.prompt}]
    response = ""
    cost = 0.0
    duration = 0.0

    try:
        response, metrics = await run_geral_query(query.prompt, history, session_type="eval")
        cost = float(metrics.get("cost", 0.0))
        duration = float(metrics.get("duration", 0.0))
    except Exception as e:
        return EvalResult(
            query_id=query.id,
            domain=query.domain,
            score=0.0,
            passed=False,
            response_chars=0,
            cost_usd=0.0,
            duration_s=0.0,
            failures=[f"exception: {type(e).__name__}: {e}"],
        )

    score, passed, failures = score_response(response, query.rubric)
    return EvalResult(
        query_id=query.id,
        domain=query.domain,
        score=score,
        passed=passed,
        response_chars=len(response),
        cost_usd=cost,
        duration_s=duration,
        failures=failures,
    )


async def run_all(queries: list[Query]) -> list[EvalResult]:
    """Executa todas as queries sequencialmente (Haiku é rápido e barato)."""
    results: list[EvalResult] = []
    for i, query in enumerate(queries, 1):
        print(f"  [{i}/{len(queries)}] {query.id}...", flush=True)
        result = await run_query(query)
        status = "✅" if result.passed else ("◐" if result.score == 0.5 else "❌")
        print(
            f"      {status} score={result.score} ${result.cost_usd:.5f} {result.duration_s:.1f}s"
        )
        if result.failures:
            for failure in result.failures:
                print(f"      ↳ {failure}")
        results.append(result)
    return results


# ─── Persistência e relatório ────────────────────────────────────────────────


def _persist_results(results: list[EvalResult]) -> Path:
    """Grava resultados em logs/evals/<timestamp>.jsonl."""
    evals_dir = REPO_ROOT / "logs" / "evals"
    evals_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
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
                        "cost_usd": r.cost_usd,
                        "duration_s": r.duration_s,
                        "failures": r.failures,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    return path


def _print_summary(results: list[EvalResult], log_path: Path) -> int:
    """Imprime sumário e retorna exit code."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    partial = sum(1 for r in results if r.score == 0.5)
    failed = sum(1 for r in results if r.score == 0.0)
    total_cost = sum(r.cost_usd for r in results)
    total_duration = sum(r.duration_s for r in results)

    print("\n" + "━" * 60)
    print(" Sumário")
    print("━" * 60)
    print(f"  Total:      {total}")
    print(f"  ✅ Passed:  {passed} ({passed / total * 100:.0f}%)")
    print(f"  ◐ Partial: {partial}")
    print(f"  ❌ Failed:  {failed}")
    print(f"  💰 Custo:   ${total_cost:.4f}")
    print(f"  ⏱ Duração: {total_duration:.1f}s")
    print(f"  📄 Log:     {log_path.relative_to(REPO_ROOT)}")
    print()

    return 0 if failed == 0 and partial == 0 else 1


# ─── CLI ─────────────────────────────────────────────────────────────────────


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
    parser = argparse.ArgumentParser(description="Data Agents — Evals runner")
    parser.add_argument("--domain", help="Filtra por domain (ex: conceptual, sql, spark)")
    parser.add_argument("--id", help="Executa só a query com esse id")
    parser.add_argument("--limit", type=int, help="Limita ao N primeiras queries")
    parser.add_argument(
        "--queries-path",
        type=Path,
        default=DEFAULT_QUERIES_PATH,
        help="Caminho do YAML de queries (default: evals/canonical_queries.yaml)",
    )
    args = parser.parse_args(argv)

    print("━" * 60)
    print(" Data Agents — Evals Runner")
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

    print(f"\nExecutando {len(queries)} query(ies) via /geral (Haiku 4.5):\n")

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    try:
        results = asyncio.run(run_all(queries))
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrompido pelo usuário.")
        return 130

    log_path = _persist_results(results)
    return _print_summary(results, log_path)


if __name__ == "__main__":
    sys.exit(main())
