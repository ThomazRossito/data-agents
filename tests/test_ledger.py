"""
Testes para memory/ledger.py.

Cobre:
  - generate_session_key: 32 bytes, aleatório
  - sign_entry: determinístico, exclui ledger_entry_hash ao assinar
  - verify_entry: pass/fail; hash ausente; tamper detectado
  - load_range: filtra por session_id; ignora malformados; verify opcional
  - list_sessions: ordem de primeira aparição; sem duplicatas; arquivo ausente
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from memory.ledger import Ledger


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def key() -> bytes:
    return Ledger.generate_session_key()


@pytest.fixture
def ledger(tmp_path: Path) -> Ledger:
    return Ledger(log_path=tmp_path / "audit.jsonl")


@pytest.fixture
def ledger_with_log(tmp_path: Path) -> tuple[Ledger, Path]:
    log = tmp_path / "audit.jsonl"
    return Ledger(log_path=log), log


def _write_entries(log: Path, entries: list[dict]) -> None:
    with open(log, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


# ─── generate_session_key ─────────────────────────────────────────────────────


class TestGenerateSessionKey:
    def test_returns_32_bytes(self):
        key = Ledger.generate_session_key()
        assert len(key) == 32

    def test_is_random(self):
        k1 = Ledger.generate_session_key()
        k2 = Ledger.generate_session_key()
        assert k1 != k2


# ─── sign_entry ───────────────────────────────────────────────────────────────


class TestSignEntry:
    def test_returns_hex_string(self, ledger, key):
        entry = {"tool_name": "Bash", "timestamp": "2026-01-01"}
        sig = ledger.sign_entry(entry, key)
        assert isinstance(sig, str)
        assert len(sig) == 64  # SHA-256 hex = 64 chars

    def test_deterministic(self, ledger, key):
        entry = {"tool_name": "Read", "session_id": "s1"}
        assert ledger.sign_entry(entry, key) == ledger.sign_entry(entry, key)

    def test_different_keys_different_hash(self, ledger):
        entry = {"tool_name": "Write"}
        k1 = Ledger.generate_session_key()
        k2 = Ledger.generate_session_key()
        assert ledger.sign_entry(entry, k1) != ledger.sign_entry(entry, k2)

    def test_excludes_ledger_entry_hash_field(self, ledger, key):
        entry = {"tool_name": "Bash"}
        entry_with_hash = {**entry, "ledger_entry_hash": "abc123"}
        # Assinar com ou sem o campo hash deve produzir o mesmo resultado
        assert ledger.sign_entry(entry, key) == ledger.sign_entry(entry_with_hash, key)

    def test_sensitive_to_content_change(self, ledger, key):
        e1 = {"tool_name": "Bash", "session_id": "s1"}
        e2 = {"tool_name": "Bash", "session_id": "s2"}
        assert ledger.sign_entry(e1, key) != ledger.sign_entry(e2, key)


# ─── verify_entry ─────────────────────────────────────────────────────────────


class TestVerifyEntry:
    def test_valid_signature_passes(self, ledger, key):
        entry = {"tool_name": "Read", "session_id": "s1"}
        entry["ledger_entry_hash"] = ledger.sign_entry(entry, key)
        assert ledger.verify_entry(entry, key) is True

    def test_missing_hash_fails(self, ledger, key):
        entry = {"tool_name": "Read"}
        assert ledger.verify_entry(entry, key) is False

    def test_empty_hash_fails(self, ledger, key):
        entry = {"tool_name": "Read", "ledger_entry_hash": ""}
        assert ledger.verify_entry(entry, key) is False

    def test_tampered_content_fails(self, ledger, key):
        entry = {"tool_name": "Read", "session_id": "s1"}
        entry["ledger_entry_hash"] = ledger.sign_entry(entry, key)
        entry["session_id"] = "s2"  # tamper
        assert ledger.verify_entry(entry, key) is False

    def test_wrong_key_fails(self, ledger):
        k1 = Ledger.generate_session_key()
        k2 = Ledger.generate_session_key()
        entry = {"tool_name": "Read"}
        entry["ledger_entry_hash"] = ledger.sign_entry(entry, k1)
        assert ledger.verify_entry(entry, k2) is False

    def test_round_trip(self, ledger, key):
        entry = {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "event": "tool_call",
            "tool_name": "mcp__databricks__execute_sql",
            "session_id": "sess-abc",
            "agent_name": "databricks-engineer",
            "result_type": "success",
        }
        entry["ledger_entry_hash"] = ledger.sign_entry(entry, key)
        assert ledger.verify_entry(entry, key) is True


# ─── load_range ───────────────────────────────────────────────────────────────


class TestLoadRange:
    def test_returns_empty_for_missing_file(self, ledger):
        assert ledger.load_range("sess-1") == []

    def test_filters_by_session_id(self, ledger_with_log):
        ledger, log = ledger_with_log
        _write_entries(
            log,
            [
                {"session_id": "s1", "tool_name": "Read"},
                {"session_id": "s2", "tool_name": "Write"},
                {"session_id": "s1", "tool_name": "Bash"},
            ],
        )
        results = ledger.load_range("s1")
        assert len(results) == 2
        assert all(e["session_id"] == "s1" for e in results)

    def test_returns_empty_for_unknown_session(self, ledger_with_log):
        ledger, log = ledger_with_log
        _write_entries(log, [{"session_id": "s1", "tool_name": "Read"}])
        assert ledger.load_range("unknown") == []

    def test_ignores_malformed_lines(self, ledger_with_log):
        ledger, log = ledger_with_log
        with open(log, "w") as f:
            f.write('{"session_id": "s1", "tool_name": "Read"}\n')
            f.write("not-json\n")
            f.write('{"session_id": "s1", "tool_name": "Bash"}\n')
        results = ledger.load_range("s1")
        assert len(results) == 2

    def test_verify_valid_entries_passes(self, ledger_with_log, key):
        ledger, log = ledger_with_log
        entry = {"session_id": "s1", "tool_name": "Read"}
        entry["ledger_entry_hash"] = ledger.sign_entry(entry, key)
        _write_entries(log, [entry])
        results = ledger.load_range("s1", verify=True, session_key=key)
        assert len(results) == 1

    def test_verify_tampered_entry_logs_warning(self, ledger_with_log, key, caplog):
        import logging

        ledger, log = ledger_with_log
        entry = {"session_id": "s1", "tool_name": "Read"}
        entry["ledger_entry_hash"] = "invalid_hash_tampered"
        _write_entries(log, [entry])
        with caplog.at_level(logging.WARNING, logger="data_agents.memory.ledger"):
            results = ledger.load_range("s1", verify=True, session_key=key)
        assert len(results) == 1  # entrada ainda retornada
        assert any("inválido" in r.message for r in caplog.records)

    def test_preserves_chronological_order(self, ledger_with_log):
        ledger, log = ledger_with_log
        entries = [
            {"session_id": "s1", "tool_name": "A", "timestamp": "2026-01-01T10:00:00"},
            {"session_id": "s1", "tool_name": "B", "timestamp": "2026-01-01T10:01:00"},
            {"session_id": "s1", "tool_name": "C", "timestamp": "2026-01-01T10:02:00"},
        ]
        _write_entries(log, entries)
        results = ledger.load_range("s1")
        assert [r["tool_name"] for r in results] == ["A", "B", "C"]


# ─── list_sessions ────────────────────────────────────────────────────────────


class TestListSessions:
    def test_returns_empty_for_missing_file(self, ledger):
        assert ledger.list_sessions() == []

    def test_returns_unique_session_ids(self, ledger_with_log):
        ledger, log = ledger_with_log
        _write_entries(
            log,
            [
                {"session_id": "s1", "tool_name": "A"},
                {"session_id": "s2", "tool_name": "B"},
                {"session_id": "s1", "tool_name": "C"},
                {"session_id": "s3", "tool_name": "D"},
            ],
        )
        sessions = ledger.list_sessions()
        assert sessions == ["s1", "s2", "s3"]

    def test_preserves_first_appearance_order(self, ledger_with_log):
        ledger, log = ledger_with_log
        _write_entries(
            log,
            [
                {"session_id": "c", "tool_name": "X"},
                {"session_id": "a", "tool_name": "Y"},
                {"session_id": "b", "tool_name": "Z"},
            ],
        )
        assert ledger.list_sessions() == ["c", "a", "b"]

    def test_ignores_entries_without_session_id(self, ledger_with_log):
        ledger, log = ledger_with_log
        _write_entries(
            log,
            [
                {"tool_name": "A"},  # sem session_id
                {"session_id": "s1", "tool_name": "B"},
                {"session_id": None, "tool_name": "C"},  # session_id None
            ],
        )
        assert ledger.list_sessions() == ["s1"]

    def test_ignores_malformed_lines(self, ledger_with_log):
        ledger, log = ledger_with_log
        with open(log, "w") as f:
            f.write('{"session_id": "s1"}\n')
            f.write("not-json\n")
            f.write('{"session_id": "s2"}\n')
        assert ledger.list_sessions() == ["s1", "s2"]

    def test_empty_log_returns_empty(self, ledger_with_log):
        ledger, log = ledger_with_log
        log.write_text("")
        assert ledger.list_sessions() == []
