"""
Tests for S4 Selective Relaxation — Phase 5 coverage.

Tests:
  - Settings has s4_autonomous_mode=False by default
  - Settings has s4_auto_approval_min_clarity_score=4 and s4_auto_approval_max_cost_usd=0.10
  - log_s4_decision writes correct event to workflows.jsonl
  - S4-AUTO fields are documented in constitution.md
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path


# ── Settings defaults ─────────────────────────────────────────────────────────


def test_s4_autonomous_mode_default_off() -> None:
    from config.settings import Settings

    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.s4_autonomous_mode is False


def test_s4_min_clarity_score_default() -> None:
    from config.settings import Settings

    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.s4_auto_approval_min_clarity_score == 4


def test_s4_max_cost_default() -> None:
    from config.settings import Settings

    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.s4_auto_approval_max_cost_usd == 0.10


# ── log_s4_decision ───────────────────────────────────────────────────────────


def test_log_s4_decision_writes_event(tmp_path: Path, monkeypatch) -> None:
    from workflow import tracker

    log_file = tmp_path / "workflows.jsonl"
    monkeypatch.setattr(tracker, "WORKFLOWS_LOG_PATH", log_file)

    tracker.log_s4_decision(
        mode="autonomous",
        clarity_score=5,
        approved=True,
        reason="read_only",
        agents=["databricks-engineer"],
    )

    assert log_file.exists()
    line = log_file.read_text(encoding="utf-8").strip()
    event = json.loads(line)
    assert event["event"] == "s4_decision"
    assert event["mode"] == "autonomous"
    assert event["clarity_score"] == 5
    assert event["approved"] is True
    assert event["reason"] == "read_only"
    assert "databricks-engineer" in event["agents"]
    assert event["s4_autonomous_mode"] is False  # default OFF


def test_log_s4_decision_blocked_scenario(tmp_path: Path, monkeypatch) -> None:
    from workflow import tracker

    log_file = tmp_path / "workflows.jsonl"
    monkeypatch.setattr(tracker, "WORKFLOWS_LOG_PATH", log_file)

    tracker.log_s4_decision(
        mode="required",
        clarity_score=3,
        approved=False,
        reason="low_clarity",
    )

    line = log_file.read_text(encoding="utf-8").strip()
    event = json.loads(line)
    assert event["event"] == "s4_decision"
    assert event["approved"] is False
    assert event["reason"] == "low_clarity"


# ── Constitution S4 clause ───────────────────────────────────────────────────


def test_constitution_has_s4_auto_clause() -> None:
    constitution = Path("kb/constitution.md")
    if not constitution.exists():
        pytest.skip("kb/constitution.md not found")

    content = constitution.read_text(encoding="utf-8")
    assert "S4-AUTO" in content
    assert "s4_autonomous_mode" in content.lower() or "S4_AUTONOMOUS_MODE" in content


def test_supervisor_prompt_has_s4_auto() -> None:
    from agents.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

    assert "S4-AUTO" in SUPERVISOR_SYSTEM_PROMPT
    assert "s4_decision" in SUPERVISOR_SYSTEM_PROMPT


# ── tracker has log_s4_decision function ─────────────────────────────────────


def test_tracker_exports_log_s4_decision() -> None:
    from workflow import tracker

    assert hasattr(tracker, "log_s4_decision")
    assert callable(tracker.log_s4_decision)
