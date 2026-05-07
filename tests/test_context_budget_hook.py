"""
Testes para hooks/context_budget_hook.py.

Cobre:
  - track_context_budget: acumulação de tokens, limiares de aviso
  - _extract_token_counts: fontes de metadados (hook_context, estimativa)
  - get_context_usage: status e campos retornados
  - reset_context_budget: reset de contadores
  - _schedule_compaction / check_and_consume_compaction: compactação autônoma
"""

import logging

import pytest

import hooks.context_budget_hook as budget_module
from hooks.context_budget_hook import (
    _extract_token_counts,
    check_and_consume_compaction,
    get_context_usage,
    reset_context_budget,
    track_context_budget,
)


# ── Helper: monta input_data no formato SDK ────────────────────────────────────


def _input(tool_name: str, tool_input=None, tool_output=None) -> dict:
    return {"tool_name": tool_name, "tool_input": tool_input or {}, "tool_output": tool_output}


@pytest.fixture(autouse=True)
def reset_budget():
    """Reseta os contadores antes e depois de cada teste."""
    reset_context_budget()
    yield
    reset_context_budget()


# ─── track_context_budget ────────────────────────────────────────────────────


class TestTrackContextBudget:
    """Testes para a função principal do hook."""

    @pytest.mark.asyncio
    async def test_returns_empty_dict_always(self):
        """O hook não deve modificar o output — sempre retorna {}."""
        result = await track_context_budget(_input("Write", {}, "output de teste"), None, None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_accumulates_tokens_across_calls(self):
        """Tokens devem acumular entre chamadas."""
        await track_context_budget(_input("Write", {"content": "abc"}, "ok"), None, None)
        await track_context_budget(
            _input("Read", {"path": "file.py"}, "conteúdo do arquivo"), None, None
        )
        usage = get_context_usage()
        assert usage["input_tokens"] > 0
        assert usage["output_tokens"] > 0

    @pytest.mark.asyncio
    async def test_no_crash_on_none_input_output(self):
        """Input e output None não devem causar erro."""
        result = await track_context_budget(_input("SomeTool", None, None), None, None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_warn_logged_at_warn_threshold(self, caplog):
        """WARNING deve ser emitido quando uso atinge o limiar de aviso."""
        with caplog.at_level(logging.WARNING, logger="data_agents.hooks.context_budget"):
            budget_module._session_input_tokens = int(
                budget_module._INPUT_TOKEN_LIMIT * budget_module._WARN_THRESHOLD
            )
            await track_context_budget(_input("Write", {"x": "y"}, "z"), None, None)
        assert any("CONTEXT ALTO" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_error_logged_at_95_percent(self, caplog):
        """ERROR deve ser emitido quando uso atinge 95% do limite."""
        with caplog.at_level(logging.ERROR, logger="data_agents.hooks.context_budget"):
            budget_module._session_input_tokens = int(
                budget_module._INPUT_TOKEN_LIMIT * budget_module._CRITICAL_THRESHOLD
            )
            # Marca como já disparado para não tentar _schedule_compaction
            budget_module._compaction_fired_for_session = True
            await track_context_budget(_input("Write", {"x": "y"}, "z"), None, None)
        assert any("CONTEXT CRÍTICO" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_uses_sdk_token_counts_when_available(self):
        """Com metadados do SDK no context, usa os valores exatos."""
        hook_ctx = {"usage": {"input_tokens": 500, "output_tokens": 100}}
        await track_context_budget(_input("Agent", {}, "resp"), None, hook_ctx)
        usage = get_context_usage()
        assert usage["input_tokens"] == 500
        assert usage["output_tokens"] == 100


# ─── _extract_token_counts ───────────────────────────────────────────────────


class TestExtractTokenCounts:
    """Testes para a extração de contagens de tokens."""

    def test_returns_sdk_input_tokens(self):
        ctx = {"usage": {"input_tokens": 1000, "output_tokens": 200}}
        inp, out = _extract_token_counts({}, "resp", ctx)
        assert inp == 1000
        assert out == 200

    def test_accepts_prompt_tokens_key(self):
        """Compatibilidade com chave 'prompt_tokens' (formato OpenAI-like)."""
        ctx = {"usage": {"prompt_tokens": 300, "completion_tokens": 50}}
        inp, out = _extract_token_counts({}, "", ctx)
        assert inp == 300
        assert out == 50

    def test_falls_back_to_char_estimate_without_context(self):
        """Sem hook_context, estima por número de caracteres."""
        big_input = {"data": "x" * 400}  # ~100 tokens estimados
        big_output = "y" * 800  # ~200 tokens estimados
        inp, out = _extract_token_counts(big_input, big_output, None)
        assert inp > 0
        assert out > 0

    def test_empty_input_output_returns_zeros(self):
        inp, out = _extract_token_counts(None, None, None)
        assert inp == 0
        assert out == 0

    def test_sdk_takes_precedence_over_estimate(self):
        """SDK deve ter prioridade sobre a estimativa por caracteres."""
        ctx = {"usage": {"input_tokens": 42, "output_tokens": 7}}
        big_input = {"data": "x" * 10_000}  # estimativa seria muito maior
        inp, out = _extract_token_counts(big_input, "out", ctx)
        assert inp == 42
        assert out == 7


# ─── get_context_usage ───────────────────────────────────────────────────────


class TestGetContextUsage:
    """Testes para get_context_usage."""

    def test_returns_expected_keys(self):
        usage = get_context_usage()
        expected_keys = {
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "limit",
            "usage_ratio",
            "remaining_tokens",
            "status",
        }
        assert expected_keys.issubset(usage.keys())

    def test_status_ok_when_low_usage(self):
        usage = get_context_usage()
        assert usage["status"] == "ok"

    def test_status_warning_at_threshold(self):
        # +1 para garantir que o ratio >= threshold mesmo com arredondamento float
        budget_module._session_input_tokens = (
            int(budget_module._INPUT_TOKEN_LIMIT * budget_module._WARN_THRESHOLD) + 1
        )
        usage = get_context_usage()
        assert usage["status"] == "warning"

    def test_status_critical_at_threshold(self):
        budget_module._session_input_tokens = int(
            budget_module._INPUT_TOKEN_LIMIT * budget_module._CRITICAL_THRESHOLD
        )
        usage = get_context_usage()
        assert usage["status"] == "critical"

    def test_total_tokens_is_sum(self):
        budget_module._session_input_tokens = 1000
        budget_module._session_output_tokens = 250
        usage = get_context_usage()
        assert usage["total_tokens"] == 1250

    def test_remaining_tokens_not_negative(self):
        """remaining_tokens nunca deve ser negativo."""
        budget_module._session_input_tokens = budget_module._INPUT_TOKEN_LIMIT + 5000
        usage = get_context_usage()
        assert usage["remaining_tokens"] == 0


# ─── reset_context_budget ────────────────────────────────────────────────────


class TestResetContextBudget:
    """Testes para reset_context_budget."""

    def test_reset_zeroes_counters(self):
        budget_module._session_input_tokens = 50_000
        budget_module._session_output_tokens = 10_000
        reset_context_budget()
        usage = get_context_usage()
        assert usage["input_tokens"] == 0
        assert usage["output_tokens"] == 0

    def test_reset_status_becomes_ok(self):
        budget_module._session_input_tokens = int(budget_module._INPUT_TOKEN_LIMIT * 0.9)
        reset_context_budget()
        assert get_context_usage()["status"] == "ok"

    def test_reset_idempotent(self):
        reset_context_budget()
        reset_context_budget()
        assert get_context_usage()["input_tokens"] == 0

    def test_reset_records_session_id(self):
        reset_context_budget(session_id="cli-abcd1234")
        assert budget_module._active_session_id == "cli-abcd1234"

    def test_reset_without_session_id_clears_it(self):
        budget_module._active_session_id = "stale-id"
        reset_context_budget()
        assert budget_module._active_session_id is None

    def test_reset_clears_compaction_state(self):
        """reset_context_budget deve limpar flags de compactação."""
        budget_module._compaction_fired_for_session = True
        budget_module._compaction_pending = True
        budget_module._compaction_summary = "some summary"
        reset_context_budget()
        assert budget_module._compaction_fired_for_session is False
        assert budget_module._compaction_pending is False
        assert budget_module._compaction_summary == ""


# ─── Compactação autônoma (_schedule_compaction) ──────────────────────────────


class TestScheduleCompaction:
    """Testes para o disparo automático de compactação em ≥80%."""

    @pytest.mark.asyncio
    async def test_does_not_fire_below_threshold(self, monkeypatch):
        """Abaixo de 80% não deve disparar compactação."""
        called = {"count": 0}

        async def fake_schedule(ratio):
            called["count"] += 1

        monkeypatch.setattr(budget_module, "_schedule_compaction", fake_schedule)
        reset_context_budget(session_id="cli-test")
        # 60% → abaixo do threshold (80%)
        budget_module._session_input_tokens = int(budget_module._INPUT_TOKEN_LIMIT * 0.60)
        await track_context_budget(_input("Write", {"x": "y"}, "z"), None, None)
        assert called["count"] == 0
        assert budget_module._compaction_fired_for_session is False

    @pytest.mark.asyncio
    async def test_fires_once_at_threshold(self, monkeypatch):
        """Ao cruzar 80% deve disparar uma vez; chamadas subsequentes não re-disparam."""
        calls: list[float] = []

        async def fake_schedule(ratio):
            calls.append(ratio)

        monkeypatch.setattr(budget_module, "_schedule_compaction", fake_schedule)
        reset_context_budget(session_id="cli-test")
        budget_module._session_input_tokens = int(budget_module._INPUT_TOKEN_LIMIT * 0.80)
        await track_context_budget(_input("Write", {"x": "y"}, "z"), None, None)
        assert len(calls) == 1
        # Segunda tool call no mesmo patamar não deve redisparar
        await track_context_budget(_input("Write", {"x": "y"}, "z"), None, None)
        assert len(calls) == 1
        assert budget_module._compaction_fired_for_session is True

    @pytest.mark.asyncio
    async def test_schedule_sets_compaction_pending(self, monkeypatch, tmp_path):
        """_schedule_compaction deve setar _compaction_pending e _compaction_summary."""
        from utils import summarizer as summarizer_module

        monkeypatch.setattr(budget_module.settings, "audit_log_path", str(tmp_path / "audit.jsonl"))

        def fake_load(_sid):
            return [
                {"role": "user", "content": "fazer X"},
                {"role": "assistant", "content": "ok"},
            ]

        async def fake_summarize(transcript, **kwargs):
            return {
                "summary": "## Objetivo\nTeste\n",
                "input_tokens": 100,
                "output_tokens": 40,
                "cost_usd": 0.00012,
                "model": "claude-haiku-4-5-20251001",
                "turns_summarized": len(transcript),
            }

        import hooks.transcript_hook as transcript_hook

        monkeypatch.setattr(transcript_hook, "load_transcript", fake_load)
        monkeypatch.setattr(summarizer_module, "summarize_session", fake_summarize)

        reset_context_budget(session_id="cli-pending")
        await budget_module._schedule_compaction(0.80)

        assert budget_module._compaction_pending is True
        assert "## Objetivo" in budget_module._compaction_summary

    @pytest.mark.asyncio
    async def test_schedule_persists_summary_file(self, monkeypatch, tmp_path):
        """_schedule_compaction deve gravar logs/summaries/<sid>.md com o resumo."""
        from utils import summarizer as summarizer_module

        monkeypatch.setattr(budget_module.settings, "audit_log_path", str(tmp_path / "audit.jsonl"))

        def fake_load(_sid):
            return [
                {"role": "user", "content": "fazer X"},
                {"role": "assistant", "content": "ok"},
            ]

        async def fake_summarize(transcript, **kwargs):
            return {
                "summary": "## Objetivo\nTeste\n",
                "input_tokens": 100,
                "output_tokens": 40,
                "cost_usd": 0.00012,
                "model": "claude-haiku-4-5-20251001",
                "turns_summarized": len(transcript),
            }

        import hooks.transcript_hook as transcript_hook

        monkeypatch.setattr(transcript_hook, "load_transcript", fake_load)
        monkeypatch.setattr(summarizer_module, "summarize_session", fake_summarize)

        reset_context_budget(session_id="cli-persist")
        await budget_module._schedule_compaction(0.80)

        summary_file = tmp_path / "summaries" / "cli-persist.md"
        assert summary_file.exists()
        content = summary_file.read_text(encoding="utf-8")
        assert "Session Summary — cli-persist" in content
        assert "80%" in content
        assert "## Objetivo" in content
        assert "claude-haiku-4-5-20251001" in content

    @pytest.mark.asyncio
    async def test_schedule_skipped_without_session_id(self, monkeypatch, caplog):
        """Sem session_id, _schedule_compaction loga INFO e retorna sem chamar o modelo."""
        from utils import summarizer as summarizer_module

        async def should_not_be_called(*args, **kwargs):
            raise AssertionError("summarize_session não deveria rodar sem session_id")

        monkeypatch.setattr(summarizer_module, "summarize_session", should_not_be_called)
        reset_context_budget(session_id=None)
        with caplog.at_level(logging.INFO, logger="data_agents.hooks.context_budget"):
            await budget_module._schedule_compaction(0.80)
        assert any("session_id desconhecido" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_schedule_skipped_when_transcript_empty(self, monkeypatch, tmp_path, caplog):
        """Transcript vazio → _schedule_compaction pula sem persistir nem chamar modelo."""
        from utils import summarizer as summarizer_module

        monkeypatch.setattr(budget_module.settings, "audit_log_path", str(tmp_path / "audit.jsonl"))

        import hooks.transcript_hook as transcript_hook

        monkeypatch.setattr(transcript_hook, "load_transcript", lambda _sid: [])

        async def should_not_be_called(*args, **kwargs):
            raise AssertionError("summarize_session não deveria rodar com transcript vazio")

        monkeypatch.setattr(summarizer_module, "summarize_session", should_not_be_called)
        reset_context_budget(session_id="cli-empty")
        with caplog.at_level(logging.INFO, logger="data_agents.hooks.context_budget"):
            await budget_module._schedule_compaction(0.80)
        assert any("transcript vazio" in r.message for r in caplog.records)
        assert not (tmp_path / "summaries" / "cli-empty.md").exists()

    @pytest.mark.asyncio
    async def test_schedule_graceful_on_summarize_error(self, monkeypatch, tmp_path, caplog):
        """Se summarize_session levantar, o hook loga WARNING e não propaga."""
        from utils import summarizer as summarizer_module

        monkeypatch.setattr(budget_module.settings, "audit_log_path", str(tmp_path / "audit.jsonl"))

        import hooks.transcript_hook as transcript_hook

        monkeypatch.setattr(
            transcript_hook,
            "load_transcript",
            lambda _sid: [{"role": "user", "content": "x"}],
        )

        async def raise_runtime(*args, **kwargs):
            raise RuntimeError("API down")

        monkeypatch.setattr(summarizer_module, "summarize_session", raise_runtime)
        reset_context_budget(session_id="cli-err")
        with caplog.at_level(logging.WARNING, logger="data_agents.hooks.context_budget"):
            await budget_module._schedule_compaction(0.80)
        assert any("auto falhou" in r.message for r in caplog.records)


# ─── check_and_consume_compaction ─────────────────────────────────────────────


class TestCheckAndConsumeCompaction:
    """Testes para check_and_consume_compaction."""

    def test_returns_none_when_no_compaction(self):
        """Sem compactação pendente, retorna None."""
        assert check_and_consume_compaction() is None

    def test_returns_summary_and_clears_flag(self):
        """Quando pendente, retorna o summary e limpa o estado."""
        budget_module._compaction_pending = True
        budget_module._compaction_summary = "## Contexto\nresumo aqui"
        result = check_and_consume_compaction()
        assert result == "## Contexto\nresumo aqui"
        assert budget_module._compaction_pending is False
        assert budget_module._compaction_summary == ""

    def test_consuming_twice_returns_none_second_time(self):
        """Flag é consumível uma única vez."""
        budget_module._compaction_pending = True
        budget_module._compaction_summary = "summary"
        first = check_and_consume_compaction()
        second = check_and_consume_compaction()
        assert first == "summary"
        assert second is None

    def test_returns_none_on_empty_summary(self):
        """Summary vazio com flag True → retorna None (sem reconexão desnecessária)."""
        budget_module._compaction_pending = True
        budget_module._compaction_summary = ""
        result = check_and_consume_compaction()
        assert result is None
