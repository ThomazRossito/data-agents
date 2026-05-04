"""Testes para commands/eval.py — save/load/summary de avaliações de sessão."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from commands.eval import get_eval_summary, load_evals, save_eval


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def evals_path(tmp_path: Path):
    """Substitui _EVALS_PATH por um arquivo temporário durante o teste."""
    p = tmp_path / "evals.jsonl"
    with patch("commands.eval._EVALS_PATH", p):
        yield p


# ── save_eval ─────────────────────────────────────────────────────────────────


class TestSaveEval:
    def test_creates_file_and_writes_record(self, evals_path: Path):
        save_eval("sess-1", rating=4)
        assert evals_path.exists()
        records = [json.loads(line) for line in evals_path.read_text().splitlines()]
        assert len(records) == 1
        assert records[0]["session_id"] == "sess-1"
        assert records[0]["rating"] == 4

    def test_appends_multiple_records(self, evals_path: Path):
        save_eval("sess-1", rating=3)
        save_eval("sess-2", rating=5, comment="ótimo")
        records = load_evals()
        assert len(records) == 2
        assert records[1]["comment"] == "ótimo"

    def test_rounds_cost_to_6_decimals(self, evals_path: Path):
        save_eval("sess-1", rating=5, cost_usd=0.123456789)
        record = load_evals()[0]
        assert record["cost_usd"] == round(0.123456789, 6)

    def test_all_fields_persisted(self, evals_path: Path):
        save_eval(
            "sess-99",
            rating=2,
            comment="ruim",
            session_type="/sql",
            cost_usd=0.05,
            turns=7,
        )
        record = load_evals()[0]
        assert record["session_type"] == "/sql"
        assert record["turns"] == 7
        assert "timestamp" in record


# ── load_evals ────────────────────────────────────────────────────────────────


class TestLoadEvals:
    def test_returns_empty_list_when_no_file(self, evals_path: Path):
        assert not evals_path.exists()
        assert load_evals() == []

    def test_skips_malformed_lines(self, evals_path: Path):
        evals_path.parent.mkdir(parents=True, exist_ok=True)
        evals_path.write_text('{"rating": 5, "session_id": "ok"}\nnot-json\n')
        records = load_evals()
        assert len(records) == 1
        assert records[0]["rating"] == 5


# ── get_eval_summary ──────────────────────────────────────────────────────────


class TestGetEvalSummary:
    def test_empty_when_no_records(self, evals_path: Path):
        summary = get_eval_summary()
        assert summary["total"] == 0
        assert summary["avg_rating"] == 0.0
        assert summary["by_type"] == {}

    def test_correct_average(self, evals_path: Path):
        save_eval("s1", rating=4)
        save_eval("s2", rating=2)
        summary = get_eval_summary()
        assert summary["total"] == 2
        assert summary["avg_rating"] == 3.0

    def test_grouped_by_session_type(self, evals_path: Path):
        save_eval("s1", rating=5, session_type="/sql")
        save_eval("s2", rating=3, session_type="/sql")
        save_eval("s3", rating=4, session_type="interactive")
        summary = get_eval_summary()
        assert "/sql" in summary["by_type"]
        assert summary["by_type"]["/sql"]["count"] == 2
        assert summary["by_type"]["/sql"]["avg"] == 4.0
        assert "interactive" in summary["by_type"]


# ── handle_eval_command ───────────────────────────────────────────────────────


class TestHandleEvalCommand:
    def test_no_records_prints_message(self, evals_path: Path):
        from commands.eval import handle_eval_command

        console = MagicMock()
        handle_eval_command("/eval", console)
        printed = " ".join(str(c) for c in console.print.call_args_list)
        assert "Nenhuma" in printed

    def test_with_records_prints_table(self, evals_path: Path):
        from commands.eval import handle_eval_command

        save_eval("s1", rating=4, session_type="/spark")
        console = MagicMock()
        handle_eval_command("/eval", console)
        calls = [str(c) for c in console.print.call_args_list]
        # Deve ter chamado print com uma Table e com a linha de média geral
        assert any("Table" in c for c in calls)
