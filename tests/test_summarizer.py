"""
Testes para utils/summarizer.py.

Cobre:
  - should_summarize(): lógica do threshold
  - _format_transcript(): truncamento e seleção dos últimos turns
  - _estimate_cost_usd(): cálculo de custo Haiku
  - summarize_session(): chamada mockada ao Anthropic, extração do resumo,
    tratamento de transcript vazio e API key ausente.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# should_summarize
# ---------------------------------------------------------------------------


class TestShouldSummarize:
    def test_below_threshold(self):
        from utils.summarizer import should_summarize

        assert should_summarize(0.5) is False
        assert should_summarize(0.64) is False

    def test_at_or_above_threshold(self):
        from utils.summarizer import should_summarize

        assert should_summarize(0.65) is True
        assert should_summarize(0.80) is True
        assert should_summarize(1.0) is True

    def test_custom_threshold(self):
        from utils.summarizer import should_summarize

        assert should_summarize(0.50, threshold=0.50) is True
        assert should_summarize(0.49, threshold=0.50) is False


# ---------------------------------------------------------------------------
# _format_transcript
# ---------------------------------------------------------------------------


class TestFormatTranscript:
    def test_empty_returns_empty_string(self):
        from utils.summarizer import _format_transcript

        assert _format_transcript([], 10, 100) == ""

    def test_labels_user_and_assistant(self):
        from utils.summarizer import _format_transcript

        entries = [
            {"role": "user", "content": "pergunta"},
            {"role": "assistant", "content": "resposta"},
        ]
        out = _format_transcript(entries, 10, 100)
        assert "USER" in out
        assert "ASSISTANT" in out
        assert "pergunta" in out
        assert "resposta" in out

    def test_truncates_per_turn(self):
        from utils.summarizer import _format_transcript

        entries = [{"role": "user", "content": "X" * 5000}]
        out = _format_transcript(entries, 10, 100)
        # O conteúdo foi truncado em 100 chars
        assert "X" * 200 not in out

    def test_keeps_only_tail(self):
        from utils.summarizer import _format_transcript

        entries = []
        for i in range(20):
            entries.append({"role": "user", "content": f"pergunta-{i}"})
            entries.append({"role": "assistant", "content": f"resposta-{i}"})

        out = _format_transcript(entries, max_turns=2, max_chars_per_turn=200)
        # Só as últimas 2*2=4 entries devem estar presentes
        assert "pergunta-0" not in out
        assert "pergunta-19" in out


# ---------------------------------------------------------------------------
# _estimate_cost_usd
# ---------------------------------------------------------------------------


class TestEstimateCost:
    def test_zero_tokens(self):
        from utils.summarizer import _estimate_cost_usd

        assert _estimate_cost_usd(0, 0) == 0.0

    def test_haiku_pricing(self):
        """Haiku 4.5: $1/Mtok input + $5/Mtok output."""
        from utils.summarizer import _estimate_cost_usd

        # 1M input + 0 output = $1.00
        assert _estimate_cost_usd(1_000_000, 0) == 1.0
        # 0 input + 1M output = $5.00
        assert _estimate_cost_usd(0, 1_000_000) == 5.0

    def test_rounded_to_six_decimals(self):
        from utils.summarizer import _estimate_cost_usd

        result = _estimate_cost_usd(1234, 567)
        # Check it's a finite float rounded at 6 decimal places
        assert isinstance(result, float)
        assert len(str(result).split(".")[-1]) <= 6


# ---------------------------------------------------------------------------
# summarize_session
# ---------------------------------------------------------------------------


def _make_fake_response(text: str, in_tok: int = 500, out_tok: int = 200):
    """Cria um mock do response.messages.create do anthropic SDK."""
    response = MagicMock()
    block = MagicMock()
    block.text = text
    response.content = [block]
    response.usage = MagicMock(input_tokens=in_tok, output_tokens=out_tok)
    return response


class TestSummarizeSession:
    @pytest.mark.asyncio
    async def test_empty_transcript_raises(self):
        from utils.summarizer import summarize_session

        with pytest.raises(ValueError, match="Transcript vazio"):
            await summarize_session([])

    @pytest.mark.asyncio
    async def test_missing_api_key_raises(self):
        from utils.summarizer import summarize_session

        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = ""
        with patch("config.settings.settings", mock_settings):
            with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
                await summarize_session([{"role": "user", "content": "oi"}], api_key=None)

    @pytest.mark.asyncio
    async def test_happy_path_returns_summary_and_cost(self):
        from utils.summarizer import summarize_session

        fake_client = MagicMock()
        fake_client.messages.create = AsyncMock(
            return_value=_make_fake_response("## Objetivo\nTeste", 100, 50)
        )
        with patch("anthropic.AsyncAnthropic", return_value=fake_client):
            result = await summarize_session(
                [
                    {"role": "user", "content": "fazer X"},
                    {"role": "assistant", "content": "fiz X"},
                ],
                api_key="sk-test",
            )

        assert "Objetivo" in result["summary"]
        assert result["input_tokens"] == 100
        assert result["output_tokens"] == 50
        # Haiku: 100/1M * $1 + 50/1M * $5 = $0.00035
        assert result["cost_usd"] == pytest.approx(0.00035, abs=1e-6)
        assert result["model"]
        assert result["turns_summarized"] == 2

    @pytest.mark.asyncio
    async def test_api_error_raises_runtime_error(self):
        from utils.summarizer import summarize_session

        fake_client = MagicMock()
        fake_client.messages.create = AsyncMock(side_effect=Exception("rate limited"))
        with patch("anthropic.AsyncAnthropic", return_value=fake_client):
            with pytest.raises(RuntimeError, match="Summarizer falhou"):
                await summarize_session([{"role": "user", "content": "x"}], api_key="sk-test")

    @pytest.mark.asyncio
    async def test_system_prompt_contains_seven_fields(self):
        """Verifica que o prompt declara os 7 campos GAPS G3."""
        from utils.summarizer import _SYSTEM_PROMPT

        for field in [
            "Objetivo",
            "Decisões",
            "Artefatos",
            "Pendências",
            "Próximos passos",
            "Contexto técnico",
            "Descobertas-chave",
        ]:
            assert field in _SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_system_prompt_forbids_hallucination(self):
        from utils.summarizer import _SYSTEM_PROMPT

        # Deve instruir explicitamente a não inventar
        assert "Nunca invente" in _SYSTEM_PROMPT or "nunca invente" in _SYSTEM_PROMPT
