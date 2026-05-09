#!/usr/bin/env python3
"""
Smoke test para o pipeline LESSON_LEARNED.

Simula 3 triggers em sequência e verifica se as lessons são criadas,
injetadas no prompt e deduplicadas corretamente.

Uso:
    python scripts/smoke_lesson_learned.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Garante imports do projeto
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Helpers ──────────────────────────────────────────────────────────────────


def _section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print("─" * 60)


def _ok(msg: str) -> None:
    print(f"  ✅  {msg}")


def _fail(msg: str) -> None:
    print(f"  ❌  {msg}")


def _info(msg: str) -> None:
    print(f"  ℹ   {msg}")


# ── Fase 1: trigger error ─────────────────────────────────────────────────────


async def test_error_trigger() -> None:
    _section("FASE 1 — trigger: error (execute_sql com tabela inexistente)")

    from hooks.memory_hook import _maybe_capture_lesson, reset_lesson_state

    reset_lesson_state()

    input_data = {
        "tool_name": "mcp__databricks__execute_sql",
        "tool_input": {
            "statement": "SELECT * FROM silver.clientes_xyz_inexistente",
            "warehouse_id": "abc123",
        },
        "tool_output": (
            "AnalysisException: Table or view not found: "
            "silver.clientes_xyz_inexistente. Check catalog/schema."
        ),
        "tool_error": "Table or view not found: silver.clientes_xyz_inexistente",
    }

    await _maybe_capture_lesson(
        tool_name="mcp__databricks__execute_sql",
        tool_input=input_data["tool_input"],
        tool_output=input_data["tool_output"],
        tool_use_id="smoke_error_001",
        input_data=input_data,
    )

    lesson_dir = Path("memory/data/lesson_learned")
    files = list(lesson_dir.iterdir()) if lesson_dir.exists() else []

    if files:
        _ok(f"{len(files)} lesson(s) criada(s) em memory/data/lesson_learned/")
        f = files[0]
        content = f.read_text(encoding="utf-8")
        _info(f"Arquivo: {f.name}")
        # Preview do frontmatter
        lines = content.splitlines()
        for ln in lines[:15]:
            print(f"    {ln}")
        if len(lines) > 15:
            print(f"    ... ({len(lines) - 15} linhas omitidas)")
    else:
        _fail("Nenhuma lesson criada — verifique MEMORY_ENABLED e ANTHROPIC_API_KEY")


# ── Fase 2: trigger high_cost ─────────────────────────────────────────────────


async def test_high_cost_trigger() -> None:
    _section("FASE 2 — trigger: high_cost (6 chamadas a run_job_now)")

    from hooks.memory_hook import (
        _HIGH_COST_THRESHOLD,
        _maybe_capture_lesson,
        _track_lesson_state,
        reset_lesson_state,
    )

    reset_lesson_state()

    # Simula _HIGH_COST_THRESHOLD + 1 chamadas HIGH para ativar o trigger
    for i in range(_HIGH_COST_THRESHOLD + 1):
        _track_lesson_state(
            tool_name="mcp__databricks__run_job_now",
            tool_input={"job_id": f"job_{i}"},
            tool_use_id=f"smoke_hc_{i:03}",
        )

    # A última chamada deve disparar high_cost
    input_data = {
        "tool_name": "mcp__databricks__run_job_now",
        "tool_input": {"job_id": "job_final"},
        "tool_output": "Job submitted successfully. run_id=98765",
        "tool_error": "",
    }

    await _maybe_capture_lesson(
        tool_name="mcp__databricks__run_job_now",
        tool_input=input_data["tool_input"],
        tool_output=input_data["tool_output"],
        tool_use_id="smoke_hc_final",
        input_data=input_data,
    )

    lesson_dir = Path("memory/data/lesson_learned")
    files = list(lesson_dir.iterdir()) if lesson_dir.exists() else []
    _ok(f"Total de lessons no store: {len(files)}")


# ── Fase 3: deduplicação ──────────────────────────────────────────────────────


def test_deduplication() -> None:
    _section("FASE 3 — deduplicação de lessons similares")

    from memory.compiler import deduplicate_lessons
    from memory.store import MemoryStore

    store = MemoryStore()
    metrics = deduplicate_lessons(store)
    _ok(f"Merged: {metrics['merged']}  |  Unchanged: {metrics['unchanged']}")


# ── Fase 4: injeção no prompt ─────────────────────────────────────────────────


def test_injection() -> None:
    _section("FASE 4 — injeção no system prompt")

    from memory.retrieval import format_memories_for_injection
    from memory.store import MemoryStore
    from memory.types import MemoryType

    store = MemoryStore()
    lessons = store.list_all(memory_type=MemoryType.LESSON_LEARNED, active_only=True)

    if not lessons:
        _fail("Nenhuma lesson ativa no store — fase 1 ou 2 pode ter falhado")
        return

    injected = format_memories_for_injection(lessons)
    if "Lições Aprendidas" in injected:
        _ok("Seção '### Lições Aprendidas' presente no bloco injetado")
        # Mostra o bloco completo
        for ln in injected.splitlines():
            print(f"    {ln}")
    else:
        _fail("Seção 'Lições Aprendidas' ausente — verificar memory/retrieval.py")


# ── Fase 5: listagem final ────────────────────────────────────────────────────


def show_summary() -> None:
    _section("RESUMO FINAL")

    from memory.store import MemoryStore
    from memory.types import MemoryType

    store = MemoryStore()
    lessons = store.list_all(memory_type=MemoryType.LESSON_LEARNED, active_only=False)

    _info(f"Total de lessons gravadas: {len(lessons)}")
    for lesson in lessons:
        status = "ativo" if lesson.is_active() else "superseded"
        print(
            f"    [{status}] {lesson.id[:8]}  "
            f"trigger={lesson.metadata.get('trigger', '?')}  "
            f"agent={lesson.metadata.get('agent', '?')}  "
            f"conf={lesson.confidence:.2f}"
        )


# ── Main ──────────────────────────────────────────────────────────────────────


async def main() -> None:
    print("\n🧪 SMOKE TEST — LESSON_LEARNED pipeline\n")
    print("  Triggers testados: error, high_cost")
    print("  Fases: capture → dedup → injection")

    await test_error_trigger()
    await test_high_cost_trigger()
    test_deduplication()
    test_injection()
    show_summary()

    print(f"\n{'─' * 60}")
    print("  Arquivos criados em memory/data/lesson_learned/")
    print("─" * 60)


if __name__ == "__main__":
    asyncio.run(main())
