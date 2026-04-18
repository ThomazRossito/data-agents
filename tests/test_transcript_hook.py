"""
Testes para hooks/transcript_hook.py.

Cobre:
  - append_turn(): gravação, campos opcionais, robustez a OSError
  - load_transcript(): leitura, arquivo ausente, linhas malformadas
  - list_transcripts(): agregação por sessão, ordenação
  - build_resume_prompt_from_transcript(): formatação e truncamento
"""

import json
from pathlib import Path
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_sessions_dir(tmp_path: Path):
    """Context helper: redireciona SESSIONS_DIR para tmp_path."""
    return patch("hooks.transcript_hook.SESSIONS_DIR", tmp_path / "sessions")


# ---------------------------------------------------------------------------
# append_turn
# ---------------------------------------------------------------------------


class TestAppendTurn:
    """Testes para append_turn()."""

    def test_creates_file_on_first_append(self, tmp_path):
        with _patch_sessions_dir(tmp_path):
            from hooks.transcript_hook import append_turn, get_transcript_path

            append_turn("sess-1", "user", "oi")
            assert get_transcript_path("sess-1").exists()

    def test_entry_has_mandatory_fields(self, tmp_path):
        with _patch_sessions_dir(tmp_path):
            from hooks.transcript_hook import append_turn, get_transcript_path

            append_turn("sess-2", "user", "consulta X")
            line = get_transcript_path("sess-2").read_text(encoding="utf-8").strip()
            entry = json.loads(line)

        assert entry["session_id"] == "sess-2"
        assert entry["role"] == "user"
        assert entry["content"] == "consulta X"
        assert "timestamp" in entry

    def test_optional_fields_persisted(self, tmp_path):
        with _patch_sessions_dir(tmp_path):
            from hooks.transcript_hook import append_turn, get_transcript_path

            append_turn(
                "sess-3",
                "assistant",
                "resposta",
                tools_used=["Read", "Grep"],
                cost_usd=0.0125,
                turns=4,
                duration_ms=3200,
                metadata={"session_type": "interactive"},
            )
            line = get_transcript_path("sess-3").read_text(encoding="utf-8").strip()
            entry = json.loads(line)

        assert entry["tools_used"] == ["Read", "Grep"]
        assert entry["cost_usd"] == 0.0125
        assert entry["turns"] == 4
        assert entry["duration_ms"] == 3200
        assert entry["metadata"] == {"session_type": "interactive"}

    def test_optional_fields_omitted_when_none(self, tmp_path):
        with _patch_sessions_dir(tmp_path):
            from hooks.transcript_hook import append_turn, get_transcript_path

            append_turn("sess-4", "user", "algo")
            entry = json.loads(get_transcript_path("sess-4").read_text(encoding="utf-8").strip())

        assert "tools_used" not in entry
        assert "cost_usd" not in entry
        assert "metadata" not in entry

    def test_appends_multiple_entries(self, tmp_path):
        with _patch_sessions_dir(tmp_path):
            from hooks.transcript_hook import append_turn, get_transcript_path

            append_turn("sess-5", "user", "pergunta 1")
            append_turn("sess-5", "assistant", "resposta 1")
            append_turn("sess-5", "user", "pergunta 2")
            lines = [
                ln
                for ln in get_transcript_path("sess-5").read_text(encoding="utf-8").splitlines()
                if ln.strip()
            ]
        assert len(lines) == 3

    def test_skips_when_session_id_empty(self, tmp_path):
        with _patch_sessions_dir(tmp_path):
            from hooks.transcript_hook import append_turn

            append_turn("", "user", "oi")
        assert not (tmp_path / "sessions").exists()

    def test_skips_when_role_empty(self, tmp_path):
        with _patch_sessions_dir(tmp_path):
            from hooks.transcript_hook import append_turn, get_transcript_path

            append_turn("sess-6", "", "oi")
        assert not get_transcript_path("sess-6").exists()

    def test_handles_oserror_gracefully(self, tmp_path):
        with _patch_sessions_dir(tmp_path):
            with patch("builtins.open", side_effect=OSError("disk full")):
                with patch("os.makedirs"):
                    from hooks.transcript_hook import append_turn

                    # Não deve lançar exceção
                    append_turn("sess-7", "user", "x")


# ---------------------------------------------------------------------------
# load_transcript
# ---------------------------------------------------------------------------


class TestLoadTranscript:
    """Testes para load_transcript()."""

    def test_returns_empty_when_no_file(self, tmp_path):
        with _patch_sessions_dir(tmp_path):
            from hooks.transcript_hook import load_transcript

            assert load_transcript("ghost") == []

    def test_returns_entries_in_order(self, tmp_path):
        with _patch_sessions_dir(tmp_path):
            from hooks.transcript_hook import append_turn, load_transcript

            append_turn("sess-8", "user", "A")
            append_turn("sess-8", "assistant", "B")
            append_turn("sess-8", "user", "C")
            entries = load_transcript("sess-8")

        assert [e["content"] for e in entries] == ["A", "B", "C"]

    def test_skips_malformed_lines(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        path = sessions_dir / "sess-9.jsonl"
        path.write_text(
            json.dumps({"role": "user", "content": "ok"})
            + "\n"
            + "linha quebrada\n"
            + json.dumps({"role": "assistant", "content": "fine"})
            + "\n",
            encoding="utf-8",
        )
        with _patch_sessions_dir(tmp_path):
            from hooks.transcript_hook import load_transcript

            entries = load_transcript("sess-9")
        assert len(entries) == 2

    def test_handles_oserror_gracefully(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        (sessions_dir / "sess-10.jsonl").write_text("{}\n", encoding="utf-8")
        with _patch_sessions_dir(tmp_path):
            with patch("builtins.open", side_effect=OSError("boom")):
                from hooks.transcript_hook import load_transcript

                assert load_transcript("sess-10") == []


# ---------------------------------------------------------------------------
# list_transcripts
# ---------------------------------------------------------------------------


class TestListTranscripts:
    """Testes para list_transcripts()."""

    def test_returns_empty_when_dir_missing(self, tmp_path):
        with _patch_sessions_dir(tmp_path):
            from hooks.transcript_hook import list_transcripts

            assert list_transcripts() == []

    def test_aggregates_per_session(self, tmp_path):
        with _patch_sessions_dir(tmp_path):
            from hooks.transcript_hook import append_turn, list_transcripts

            append_turn("sess-A", "user", "primeiro prompt")
            append_turn("sess-A", "assistant", "resposta", cost_usd=0.1)
            append_turn("sess-A", "user", "segundo prompt")
            append_turn("sess-B", "user", "outra sessão")

            result = list_transcripts()

        by_id = {r["session_id"]: r for r in result}
        assert by_id["sess-A"]["turn_count"] == 2  # 2 prompts do usuário
        assert by_id["sess-A"]["total_cost_usd"] == 0.1
        assert by_id["sess-A"]["last_user_prompt"] == "segundo prompt"
        assert by_id["sess-B"]["turn_count"] == 1

    def test_orders_by_last_timestamp_desc(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        (sessions_dir / "older.jsonl").write_text(
            json.dumps(
                {
                    "role": "user",
                    "content": "velho",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (sessions_dir / "newer.jsonl").write_text(
            json.dumps(
                {
                    "role": "user",
                    "content": "novo",
                    "timestamp": "2026-04-17T00:00:00+00:00",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        with _patch_sessions_dir(tmp_path):
            from hooks.transcript_hook import list_transcripts

            result = list_transcripts()

        assert result[0]["session_id"] == "newer"
        assert result[1]["session_id"] == "older"

    def test_skips_empty_transcript_files(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        (sessions_dir / "empty.jsonl").write_text("", encoding="utf-8")
        with _patch_sessions_dir(tmp_path):
            from hooks.transcript_hook import list_transcripts

            assert list_transcripts() == []


# ---------------------------------------------------------------------------
# build_resume_prompt_from_transcript
# ---------------------------------------------------------------------------


class TestBuildResumePromptFromTranscript:
    """Testes para build_resume_prompt_from_transcript()."""

    def test_returns_none_when_no_transcript(self, tmp_path):
        with _patch_sessions_dir(tmp_path):
            from hooks.transcript_hook import build_resume_prompt_from_transcript

            assert build_resume_prompt_from_transcript("ghost") is None

    def test_prompt_contains_user_and_assistant_turns(self, tmp_path):
        with _patch_sessions_dir(tmp_path):
            from hooks.transcript_hook import (
                append_turn,
                build_resume_prompt_from_transcript,
            )

            append_turn("sess-R1", "user", "analisar vendas Q1")
            append_turn("sess-R1", "assistant", "vendas foram X", tools_used=["Read"])

            prompt = build_resume_prompt_from_transcript("sess-R1")

        assert "analisar vendas Q1" in prompt
        assert "vendas foram X" in prompt
        assert "Usuário" in prompt
        assert "Assistente" in prompt

    def test_limits_to_max_turns(self, tmp_path):
        with _patch_sessions_dir(tmp_path):
            from hooks.transcript_hook import (
                append_turn,
                build_resume_prompt_from_transcript,
            )

            for i in range(20):
                append_turn("sess-R2", "user", f"pergunta-{i}")
                append_turn("sess-R2", "assistant", f"resposta-{i}")

            prompt = build_resume_prompt_from_transcript("sess-R2", max_turns=3)

        # Deve conter apenas as 3 últimas interações (3*2 = 6 entries)
        assert "pergunta-0" not in prompt
        assert "pergunta-19" in prompt

    def test_truncates_content_per_turn(self, tmp_path):
        with _patch_sessions_dir(tmp_path):
            from hooks.transcript_hook import (
                append_turn,
                build_resume_prompt_from_transcript,
            )

            long_content = "A" * 10000
            append_turn("sess-R3", "user", long_content)

            prompt = build_resume_prompt_from_transcript("sess-R3", max_chars_per_turn=100)

        # Não deve conter a string completa
        assert "A" * 200 not in prompt

    def test_includes_tools_used_line(self, tmp_path):
        with _patch_sessions_dir(tmp_path):
            from hooks.transcript_hook import (
                append_turn,
                build_resume_prompt_from_transcript,
            )

            append_turn("sess-R4", "user", "x")
            append_turn("sess-R4", "assistant", "y", tools_used=["Read", "Grep"])

            prompt = build_resume_prompt_from_transcript("sess-R4")

        assert "Tools usadas" in prompt
        assert "Read" in prompt
