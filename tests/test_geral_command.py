"""Testes para commands/geral.py — _geral_model() e build_prompt_with_history()."""

from __future__ import annotations

from unittest.mock import patch


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
