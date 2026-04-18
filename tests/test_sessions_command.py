"""
Testes para commands/sessions.py.

Cobre:
  - list_all_sessions(): merge transcript + checkpoint
  - render_sessions_table(): saída Rich, limite
  - render_session_details(): visualização por session_id
  - handle_sessions_command(): dispatch de subcomandos
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_settings(tmp_path: Path):
    audit = tmp_path / "logs" / "audit.log"
    m = MagicMock()
    m.audit_log_path = str(audit)
    m.max_budget_usd = 5.0
    m.default_model = "claude-opus-4-6"
    return m


@pytest.fixture
def isolated_sessions(tmp_path):
    """
    Redireciona SESSIONS_DIR do transcript e CHECKPOINT/SESSIONS_DIR do checkpoint
    para tmp_path para que os módulos escrevam/leiam em isolamento.
    """
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    settings_mock = _mock_settings(tmp_path)

    with patch("hooks.transcript_hook.SESSIONS_DIR", sessions_dir):
        with patch("hooks.checkpoint.settings", settings_mock):
            with patch("hooks.checkpoint.SESSIONS_DIR", sessions_dir):
                with patch(
                    "hooks.checkpoint.CHECKPOINT_PATH",
                    tmp_path / "logs" / "checkpoint.json",
                ):
                    yield sessions_dir


# ---------------------------------------------------------------------------
# list_all_sessions
# ---------------------------------------------------------------------------


class TestListAllSessions:
    def test_empty_when_no_sessions(self, isolated_sessions):
        from commands.sessions import list_all_sessions

        assert list_all_sessions() == []

    def test_includes_sessions_with_only_transcript(self, isolated_sessions):
        from commands.sessions import list_all_sessions
        from hooks.transcript_hook import append_turn

        append_turn("sess-only-tx", "user", "primeiro")
        append_turn("sess-only-tx", "assistant", "resposta", cost_usd=0.01)

        result = list_all_sessions()
        assert len(result) == 1
        assert result[0]["session_id"] == "sess-only-tx"
        assert result[0]["has_transcript"] is True
        assert result[0]["has_checkpoint"] is False
        assert result[0]["total_cost_usd"] == 0.01

    def test_includes_sessions_with_only_checkpoint(self, isolated_sessions):
        """Sessão antiga com checkpoint mas sem transcript deve aparecer."""
        from commands.sessions import list_all_sessions

        # Escreve checkpoint manualmente
        cp = {
            "timestamp": "2026-04-10T10:00:00+00:00",
            "session_id": "sess-legacy",
            "reason": "budget_exceeded",
            "last_prompt": "prompt antigo",
            "cost_usd": 2.5,
            "turns": 4,
        }
        (isolated_sessions / "sess-legacy.json").write_text(json.dumps(cp), encoding="utf-8")

        result = list_all_sessions()
        ids = [r["session_id"] for r in result]
        assert "sess-legacy" in ids

        entry = next(r for r in result if r["session_id"] == "sess-legacy")
        assert entry["has_transcript"] is False
        assert entry["has_checkpoint"] is True
        assert entry["reason"] == "budget_exceeded"
        assert entry["total_cost_usd"] == 2.5
        assert "prompt antigo" in entry["last_user_prompt"]

    def test_merges_transcript_and_checkpoint(self, isolated_sessions):
        from commands.sessions import list_all_sessions
        from hooks.transcript_hook import append_turn

        # Transcript
        append_turn("sess-both", "user", "prompt do transcript")
        append_turn("sess-both", "assistant", "resposta", cost_usd=0.5)
        # Checkpoint
        cp = {
            "timestamp": "2026-04-11T10:00:00+00:00",
            "session_id": "sess-both",
            "reason": "normal_exit",
            "last_prompt": "prompt do checkpoint",
            "cost_usd": 0.5,
            "turns": 1,
        }
        (isolated_sessions / "sess-both.json").write_text(json.dumps(cp), encoding="utf-8")

        result = list_all_sessions()
        entry = next(r for r in result if r["session_id"] == "sess-both")
        # Transcript tem prioridade no last_user_prompt
        assert "prompt do transcript" in entry["last_user_prompt"]
        assert entry["has_transcript"] is True
        assert entry["has_checkpoint"] is True
        assert entry["reason"] == "normal_exit"

    def test_sorted_by_last_timestamp_desc(self, isolated_sessions):
        from commands.sessions import list_all_sessions
        from hooks.transcript_hook import append_turn
        import time

        append_turn("sess-older", "user", "velho")
        time.sleep(0.01)
        append_turn("sess-newer", "user", "novo")

        result = list_all_sessions()
        assert result[0]["session_id"] == "sess-newer"
        assert result[-1]["session_id"] == "sess-older"


# ---------------------------------------------------------------------------
# render_sessions_table
# ---------------------------------------------------------------------------


class TestRenderSessionsTable:
    def test_returns_zero_when_no_sessions(self, isolated_sessions):
        from commands.sessions import render_sessions_table

        console = Console(record=True, width=120)
        n = render_sessions_table(console)
        output = console.export_text()
        assert n == 0
        assert "Nenhuma sessão" in output

    def test_renders_sessions(self, isolated_sessions):
        from commands.sessions import render_sessions_table
        from hooks.transcript_hook import append_turn

        append_turn("sess-T1", "user", "consulta sobre vendas")
        append_turn("sess-T1", "assistant", "resposta", cost_usd=0.125)

        console = Console(record=True, width=180)
        n = render_sessions_table(console)
        output = console.export_text()
        assert n == 1
        assert "sess-T1" in output
        assert "vendas" in output
        assert "$0.1250" in output

    def test_respects_limit(self, isolated_sessions):
        from commands.sessions import render_sessions_table
        from hooks.transcript_hook import append_turn
        import time

        for i in range(5):
            append_turn(f"sess-{i}", "user", f"q-{i}")
            time.sleep(0.002)

        console = Console(record=True, width=180)
        n = render_sessions_table(console, limit=3)
        output = console.export_text()
        assert n == 3
        assert "mais 2 sessões" in output

    def test_unlimited_when_limit_zero(self, isolated_sessions):
        from commands.sessions import render_sessions_table
        from hooks.transcript_hook import append_turn

        for i in range(3):
            append_turn(f"s-{i}", "user", f"q-{i}")

        console = Console(record=True, width=180)
        n = render_sessions_table(console, limit=0)
        assert n == 3


# ---------------------------------------------------------------------------
# render_session_details
# ---------------------------------------------------------------------------


class TestRenderSessionDetails:
    def test_returns_false_when_session_missing(self, isolated_sessions):
        from commands.sessions import render_session_details

        console = Console(record=True, width=120)
        ok = render_session_details(console, "ghost")
        assert ok is False
        assert "não encontrada" in console.export_text()

    def test_prints_user_and_assistant_entries(self, isolated_sessions):
        from commands.sessions import render_session_details
        from hooks.transcript_hook import append_turn

        append_turn("sess-D1", "user", "prompt A")
        append_turn(
            "sess-D1",
            "assistant",
            "resposta B",
            tools_used=["Read"],
            cost_usd=0.01,
        )

        console = Console(record=True, width=180)
        ok = render_session_details(console, "sess-D1")
        output = console.export_text()
        assert ok is True
        assert "User" in output
        assert "Assistant" in output
        assert "prompt A" in output
        assert "resposta B" in output
        assert "Read" in output

    def test_truncates_very_long_content(self, isolated_sessions):
        from commands.sessions import render_session_details
        from hooks.transcript_hook import append_turn

        big = "X" * 5000
        append_turn("sess-D2", "user", big)

        console = Console(record=True, width=180)
        render_session_details(console, "sess-D2")
        output = console.export_text()
        assert "truncado" in output


# ---------------------------------------------------------------------------
# handle_sessions_command
# ---------------------------------------------------------------------------


class TestHandleSessionsCommand:
    def test_no_arg_renders_table(self, isolated_sessions):
        from commands.sessions import handle_sessions_command
        from hooks.transcript_hook import append_turn

        append_turn("sess-H1", "user", "x")

        console = Console(record=True, width=180)
        handle_sessions_command("/sessions", console)
        assert "sess-H1" in console.export_text()

    def test_all_renders_all(self, isolated_sessions):
        from commands.sessions import handle_sessions_command
        from hooks.transcript_hook import append_turn

        for i in range(30):
            append_turn(f"s-{i:02d}", "user", f"q-{i}")

        console = Console(record=True, width=180)
        handle_sessions_command("/sessions all", console)
        output = console.export_text()
        # O "all" não deve mostrar o aviso de "mais N sessões"
        assert "mais" not in output or "mais 0" in output

    def test_session_id_renders_details(self, isolated_sessions):
        from commands.sessions import handle_sessions_command
        from hooks.transcript_hook import append_turn

        append_turn("sess-DET", "user", "detalhe teste")

        console = Console(record=True, width=180)
        handle_sessions_command("/sessions sess-DET", console)
        output = console.export_text()
        assert "detalhe teste" in output


# ---------------------------------------------------------------------------
# find_last_session_id / build_resume_prompt_for_session
# ---------------------------------------------------------------------------


class TestFindLastSessionId:
    def test_returns_none_when_no_sessions(self, isolated_sessions):
        from commands.sessions import find_last_session_id

        assert find_last_session_id() is None

    def test_returns_most_recent_by_last_timestamp(self, isolated_sessions):
        from commands.sessions import find_last_session_id
        from hooks.transcript_hook import append_turn
        import time

        append_turn("s-older", "user", "velho")
        time.sleep(0.01)
        append_turn("s-newer", "user", "novo")

        assert find_last_session_id() == "s-newer"


class TestBuildResumePromptForSession:
    def test_returns_none_when_session_missing(self, isolated_sessions):
        from commands.sessions import build_resume_prompt_for_session

        assert build_resume_prompt_for_session("ghost") is None

    def test_uses_transcript_when_available(self, isolated_sessions):
        from commands.sessions import build_resume_prompt_for_session
        from hooks.transcript_hook import append_turn

        append_turn("sess-R", "user", "prompt do transcript")
        append_turn("sess-R", "assistant", "resposta do assistente")

        prompt = build_resume_prompt_for_session("sess-R")
        assert prompt is not None
        assert "prompt do transcript" in prompt
        assert "Transcript Completo" in prompt

    def test_falls_back_to_checkpoint_when_no_transcript(self, isolated_sessions):
        """Sessão legada com checkpoint mas sem transcript usa build_resume_prompt."""
        from commands.sessions import build_resume_prompt_for_session

        cp = {
            "timestamp": "2026-04-10T10:00:00+00:00",
            "session_id": "sess-legacy",
            "reason": "user_reset",
            "last_prompt": "pergunta legada",
            "cost_usd": 0.1,
            "turns": 1,
            "output_files": [],
        }
        (isolated_sessions / "sess-legacy.json").write_text(json.dumps(cp), encoding="utf-8")

        prompt = build_resume_prompt_for_session("sess-legacy")
        assert prompt is not None
        # build_resume_prompt produz o header "Contexto da Sessão Anterior (Checkpoint Automático)"
        assert "Checkpoint Automático" in prompt
        assert "pergunta legada" in prompt

    def test_respects_context_budget_via_truncation(self, isolated_sessions):
        """O prompt não deve explodir com transcripts muito longos."""
        from commands.sessions import build_resume_prompt_for_session
        from hooks.transcript_hook import append_turn

        long_content = "Z" * 5000
        for i in range(40):
            append_turn("sess-big", "user", f"{long_content}-{i}")
            append_turn("sess-big", "assistant", long_content)

        prompt = build_resume_prompt_for_session("sess-big", max_turns=5, max_chars_per_turn=500)
        assert prompt is not None
        # Com max_turns=5 (5 pares = 10 entries) e max_chars=500, o prompt
        # deve ser bem menor que 5000 chars por turno. Teto solto: < 20k chars.
        assert len(prompt) < 20_000
