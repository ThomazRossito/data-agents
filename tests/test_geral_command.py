"""Testes para commands/geral.py — _geral_model(), build_prompt_with_history() e run_geral_query()."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── _geral_model ──────────────────────────────────────────────────────────────


class TestGeralModel:
    def test_default_is_haiku_alias(self):
        """Sem tier_model_map, retorna claude-haiku-4-5."""
        from commands.geral import _geral_model

        with patch("commands.geral.settings") as mock_settings:
            mock_settings.tier_model_map = {}
            assert _geral_model() == "claude-haiku-4-5"

    def test_t0_override_respected(self):
        """Se T0 estiver no tier_map (raro, mas possível), usa o valor configurado."""
        from commands.geral import _geral_model

        with patch("commands.geral.settings") as mock_settings:
            mock_settings.tier_model_map = {"T0": "claude-sonnet-4-6"}
            assert _geral_model() == "claude-sonnet-4-6"

    def test_t1_t2_t3_in_tier_map_does_not_affect_geral(self):
        """T1/T2/T3 no tier_map não afetam /geral — T0 não está no mapa por padrão."""
        from commands.geral import _geral_model

        with patch("commands.geral.settings") as mock_settings:
            mock_settings.tier_model_map = {
                "T1": "claude-opus-4-6",
                "T2": "claude-sonnet-4-6",
                "T3": "claude-sonnet-4-6",
            }
            # T0 ausente → fallback para Haiku
            assert _geral_model() == "claude-haiku-4-5"

    def test_none_tier_map_uses_haiku(self):
        """tier_model_map None é tratado como {}."""
        from commands.geral import _geral_model

        with patch("commands.geral.settings") as mock_settings:
            mock_settings.tier_model_map = None
            assert _geral_model() == "claude-haiku-4-5"


# ── build_prompt_with_history ─────────────────────────────────────────────────


class TestBuildPromptWithHistory:
    def test_no_history_returns_message_as_is(self):
        from commands.geral import build_prompt_with_history

        result = build_prompt_with_history("Olá", [{"role": "user", "content": "Olá"}])
        assert result == "Olá"

    def test_single_prior_turn_prefixed(self):
        from commands.geral import build_prompt_with_history

        history = [
            {"role": "user", "content": "O que é Delta Lake?"},
            {"role": "assistant", "content": "Delta Lake é um formato de storage..."},
            {"role": "user", "content": "E Iceberg?"},
        ]
        result = build_prompt_with_history("E Iceberg?", history)
        assert "Histórico:" in result
        assert "O que é Delta Lake?" in result
        assert "Delta Lake é um formato" in result
        assert result.endswith("E Iceberg?")

    def test_roles_labeled_correctly(self):
        from commands.geral import build_prompt_with_history

        history = [
            {"role": "user", "content": "pergunta"},
            {"role": "assistant", "content": "resposta"},
            {"role": "user", "content": "nova pergunta"},
        ]
        result = build_prompt_with_history("nova pergunta", history)
        assert "Usuário: pergunta" in result
        assert "Assistente: resposta" in result

    def test_limits_to_20_prior_messages(self):
        from commands.geral import build_prompt_with_history

        # 25 mensagens anteriores + 1 atual = 26 mensagens no history
        # history[-21:-1] pega os 20 anteriores à mensagem atual
        history = []
        for i in range(25):
            role = "user" if i % 2 == 0 else "assistant"
            history.append({"role": role, "content": f"msg-{i}"})
        history.append({"role": "user", "content": "atual"})

        result = build_prompt_with_history("atual", history)
        # history[-21:-1] = history[5:25] → msg-5 a msg-24
        # msg-0 a msg-4 ficam fora da janela
        assert "msg-0" not in result
        assert "msg-4" not in result
        # msg-5 em diante deve estar presente
        assert "msg-5" in result
        assert "msg-24" in result

    def test_current_message_always_at_end(self):
        from commands.geral import build_prompt_with_history

        history = [
            {"role": "user", "content": "anterior"},
            {"role": "assistant", "content": "resposta anterior"},
            {"role": "user", "content": "mensagem atual"},
        ]
        result = build_prompt_with_history("mensagem atual", history)
        assert result.endswith("mensagem atual")


# ── run_geral_query ───────────────────────────────────────────────────────────


def _make_usage(input_tokens: int = 100, output_tokens: int = 50) -> MagicMock:
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    return usage


class TestRunGeralQuery:
    @pytest.mark.asyncio
    async def test_non_streaming_returns_text_and_metrics(self):
        from commands.geral import run_geral_query

        fake_block = MagicMock()
        fake_block.text = "Delta Lake is a storage layer."
        fake_message = MagicMock()
        fake_message.content = [fake_block]
        fake_message.usage = _make_usage(input_tokens=80, output_tokens=30)

        with (
            patch("commands.geral.settings") as mock_settings,
            patch("commands.geral.anthropic.AsyncAnthropic") as mock_client_cls,
        ):
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.tier_model_map = {}
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=fake_message)
            mock_client_cls.return_value = mock_client

            history = [{"role": "user", "content": "O que é Delta Lake?"}]
            text, metrics = await run_geral_query("O que é Delta Lake?", history)

        assert "Delta Lake" in text
        assert metrics["cost"] > 0
        assert metrics["input_tokens"] == 80
        assert metrics["output_tokens"] == 30

    @pytest.mark.asyncio
    async def test_streaming_calls_token_callback(self):
        from commands.geral import run_geral_query

        chunks_received: list[str] = []

        async def token_cb(chunk: str) -> None:
            chunks_received.append(chunk)

        # Build a mock stream context manager
        fake_final = MagicMock()
        fake_final.usage = _make_usage(input_tokens=60, output_tokens=20)

        async def fake_text_stream():
            for word in ["Hello", " world", "!"]:
                yield word

        mock_stream = MagicMock()
        mock_stream.text_stream = fake_text_stream()
        mock_stream.get_final_message = AsyncMock(return_value=fake_final)

        @asynccontextmanager
        async def fake_stream_ctx(*args, **kwargs):
            yield mock_stream

        with (
            patch("commands.geral.settings") as mock_settings,
            patch("commands.geral.anthropic.AsyncAnthropic") as mock_client_cls,
        ):
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.tier_model_map = {}
            mock_client = MagicMock()
            mock_client.messages.stream = fake_stream_ctx
            mock_client_cls.return_value = mock_client

            history = [{"role": "user", "content": "hi"}]
            text, metrics = await run_geral_query("hi", history, token_callback=token_cb)

        assert text == "Hello world!"
        assert chunks_received == ["Hello", " world", "!"]
        assert metrics["input_tokens"] == 60
        assert metrics["output_tokens"] == 20

    @pytest.mark.asyncio
    async def test_streaming_full_text_accumulated(self):
        from commands.geral import run_geral_query

        received: list[str] = []

        async def token_cb(chunk: str) -> None:
            received.append(chunk)

        fake_final = MagicMock()
        fake_final.usage = _make_usage()

        async def fake_text_stream():
            for c in ["A", "B", "C"]:
                yield c

        mock_stream = MagicMock()
        mock_stream.text_stream = fake_text_stream()
        mock_stream.get_final_message = AsyncMock(return_value=fake_final)

        @asynccontextmanager
        async def fake_stream_ctx(*args, **kwargs):
            yield mock_stream

        with (
            patch("commands.geral.settings") as mock_settings,
            patch("commands.geral.anthropic.AsyncAnthropic") as mock_client_cls,
        ):
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.tier_model_map = {}
            mock_client = MagicMock()
            mock_client.messages.stream = fake_stream_ctx
            mock_client_cls.return_value = mock_client

            history = [{"role": "user", "content": "test"}]
            text, _ = await run_geral_query("test", history, token_callback=token_cb)

        assert text == "ABC"
        assert received == ["A", "B", "C"]

    @pytest.mark.asyncio
    async def test_non_streaming_used_when_no_callback(self):
        from commands.geral import run_geral_query

        fake_block = MagicMock()
        fake_block.text = "response"
        fake_message = MagicMock()
        fake_message.content = [fake_block]
        fake_message.usage = _make_usage()

        with (
            patch("commands.geral.settings") as mock_settings,
            patch("commands.geral.anthropic.AsyncAnthropic") as mock_client_cls,
        ):
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.tier_model_map = {}
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=fake_message)
            mock_client.messages.stream = MagicMock()
            mock_client_cls.return_value = mock_client

            history = [{"role": "user", "content": "test"}]
            text, _ = await run_geral_query("test", history)

        # stream should NOT have been called — only create()
        mock_client.messages.stream.assert_not_called()
        assert text == "response"
