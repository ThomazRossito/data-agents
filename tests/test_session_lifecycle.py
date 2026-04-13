"""
Testes para hooks/session_lifecycle.py (Ch. 12).

Cobre:
  - on_session_start: reseta context budget, loga início
  - on_session_end: loga uso de contexto, dispara memory flush
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

import hooks.context_budget_hook as budget_module
from hooks.context_budget_hook import reset_context_budget
from hooks.session_lifecycle import on_session_start, on_session_end


@pytest.fixture(autouse=True)
def clean_budget():
    reset_context_budget()
    yield
    reset_context_budget()


# ─── on_session_start ────────────────────────────────────────────────────────


class TestOnSessionStart:
    def test_resets_context_budget(self):
        """on_session_start deve zerar os contadores de tokens."""
        # Simula tokens acumulados de sessão anterior
        budget_module._session_input_tokens = 50_000
        budget_module._session_output_tokens = 10_000

        on_session_start("test-session-001")

        from hooks.context_budget_hook import get_context_usage

        usage = get_context_usage()
        assert usage["input_tokens"] == 0
        assert usage["output_tokens"] == 0

    def test_logs_session_start(self, caplog):
        """on_session_start deve emitir log de início."""
        with caplog.at_level(logging.INFO, logger="data_agents.hooks.session_lifecycle"):
            on_session_start("abc123")
        assert any("abc123" in r.message and "session_start" in r.message for r in caplog.records)

    def test_returns_none(self):
        """on_session_start não retorna valor."""
        result = on_session_start("sid-xyz")
        assert result is None

    def test_multiple_starts_each_reset(self):
        """Múltiplas chamadas de start devem cada uma resetar o budget."""
        budget_module._session_input_tokens = 100_000
        on_session_start("sess-1")

        budget_module._session_input_tokens = 80_000
        on_session_start("sess-2")

        from hooks.context_budget_hook import get_context_usage

        assert get_context_usage()["input_tokens"] == 0


# ─── on_session_end ──────────────────────────────────────────────────────────


class TestOnSessionEnd:
    def test_returns_none(self):
        """on_session_end não retorna valor."""
        with patch("hooks.session_lifecycle.flush_session_memories", MagicMock()):
            result = on_session_end("sid-xyz")
        assert result is None

    def test_calls_flush_when_enabled(self):
        """Com flush_memory=True (default), deve chamar flush_session_memories."""
        with patch("hooks.session_lifecycle.flush_session_memories") as mock_flush:
            on_session_end("session-abc", flush_memory=True)
            mock_flush.assert_called_once()

    def test_no_flush_when_disabled(self):
        """Com flush_memory=False, não deve chamar flush_session_memories."""
        with patch("hooks.session_lifecycle.flush_session_memories") as mock_flush:
            on_session_end("session-abc", flush_memory=False)
            mock_flush.assert_not_called()

    def test_logs_context_usage_on_end(self, caplog):
        """on_session_end deve logar o uso de contexto da sessão."""
        budget_module._session_input_tokens = 10_000

        with caplog.at_level(logging.INFO, logger="data_agents.hooks.session_lifecycle"):
            with patch("hooks.session_lifecycle.flush_session_memories", MagicMock()):
                on_session_end("log-test-session")

        assert any("session_end" in r.message for r in caplog.records)

    def test_flush_error_does_not_raise(self):
        """Erro no flush não deve propagar — apenas logar warning."""
        with patch(
            "hooks.session_lifecycle.flush_session_memories",
            side_effect=RuntimeError("flush falhou"),
        ):
            # Não deve levantar exceção
            on_session_end("err-session", flush_memory=True)

    def test_logs_session_end(self, caplog):
        """on_session_end deve logar o encerramento da sessão."""
        with caplog.at_level(logging.INFO, logger="data_agents.hooks.session_lifecycle"):
            with patch("hooks.session_lifecycle.flush_session_memories", MagicMock()):
                on_session_end("end-session-999")
        assert any("end-session-999" in r.message for r in caplog.records)

    def test_context_usage_error_does_not_raise(self):
        """Erro ao obter uso de contexto não deve propagar."""
        with patch(
            "hooks.session_lifecycle.get_context_usage",
            side_effect=Exception("contexto indisponível"),
        ):
            with patch("hooks.session_lifecycle.flush_session_memories", MagicMock()):
                # Não deve levantar exceção
                on_session_end("ctx-err-session", flush_memory=True)


# ─── Integração start → end ──────────────────────────────────────────────────


class TestSessionLifecycleIntegration:
    def test_start_end_cycle_resets_and_flushes(self):
        """Ciclo completo start → end reseta budget e faz flush."""
        budget_module._session_input_tokens = 30_000

        on_session_start("full-cycle-session")

        # Simula uso durante a sessão
        budget_module._session_input_tokens = 5_000

        with patch("hooks.session_lifecycle.flush_session_memories") as mock_flush:
            on_session_end("full-cycle-session")
            mock_flush.assert_called_once()
