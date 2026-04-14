"""
Testes para hooks/context_budget_hook.py.

Cobre:
  - track_context_budget: acumulação de tokens, limiares de aviso
  - _extract_token_counts: fontes de metadados (hook_context, estimativa)
  - get_context_usage: status e campos retornados
  - reset_context_budget: reset de contadores
"""

import logging

import pytest

import hooks.context_budget_hook as budget_module
from hooks.context_budget_hook import (
    _extract_token_counts,
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
    async def test_warn_logged_at_80_percent(self, caplog):
        """WARNING deve ser emitido quando uso atinge 80% do limite."""
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
        budget_module._session_input_tokens = int(
            budget_module._INPUT_TOKEN_LIMIT * budget_module._WARN_THRESHOLD
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
