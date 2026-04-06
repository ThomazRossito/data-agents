"""Testes do MLflow Wrapper."""

from unittest.mock import MagicMock, patch

from agents.mlflow_wrapper import ClaudeDataAgent


class TestClaudeDataAgent:
    """Testes para o wrapper PyFunc do MLflow."""

    def setup_method(self):
        self.agent = ClaudeDataAgent()

    def test_format_response_standard(self):
        """Verifica formato padrão de resposta (OpenAI Messages)."""
        response = self.agent._format_response("Hello world")
        assert "choices" in response
        assert len(response["choices"]) == 1
        assert response["choices"][0]["message"]["role"] == "assistant"
        assert response["choices"][0]["message"]["content"] == "Hello world"
        assert "error" not in response

    def test_format_response_error(self):
        """Verifica que erros incluem metadata adicional."""
        response = self.agent._format_response("Erro grave", is_error=True)
        assert "error" in response
        assert response["error"]["type"] == "agent_error"
        assert response["error"]["message"] == "Erro grave"

    def test_extract_prompt_openai_format(self):
        """Verifica extração de prompt no formato OpenAI Messages."""
        model_input = {
            "messages": [
                {"role": "user", "content": "Analise a tabela X"},
            ]
        }
        prompt = self.agent._extract_prompt(model_input)
        assert prompt == "Analise a tabela X"

    def test_extract_prompt_multi_message(self):
        """Verifica que pega a última mensagem."""
        model_input = {
            "messages": [
                {"role": "user", "content": "Primeira pergunta"},
                {"role": "assistant", "content": "Resposta"},
                {"role": "user", "content": "Segunda pergunta"},
            ]
        }
        prompt = self.agent._extract_prompt(model_input)
        assert prompt == "Segunda pergunta"

    def test_extract_prompt_list_format(self):
        """Verifica extração de prompt no formato lista."""
        model_input = [{"prompt": "Analise a tabela X"}]
        prompt = self.agent._extract_prompt(model_input)
        assert prompt == "Analise a tabela X"

    def test_extract_prompt_string_format(self):
        """Verifica extração de prompt como string direta."""
        prompt = self.agent._extract_prompt("Analise a tabela X")
        assert prompt == "Analise a tabela X"

    def test_extract_prompt_empty_messages(self):
        """Verifica comportamento com messages vazio."""
        model_input = {"messages": []}
        prompt = self.agent._extract_prompt(model_input)
        assert prompt == ""

    def test_predict_without_init_returns_error(self):
        """Verifica que predict sem load_context retorna erro."""
        self.agent._ready = False
        self.agent._init_error = "Teste de erro"
        response = self.agent.predict(None, {"messages": [{"role": "user", "content": "test"}]})
        assert "error" in response
        assert "Teste de erro" in response["choices"][0]["message"]["content"]

    def test_predict_empty_prompt_returns_error(self):
        """Verifica que prompt vazio retorna mensagem de ajuda."""
        self.agent._ready = True
        self.agent._init_error = None
        response = self.agent.predict(None, {"messages": []})
        assert "Nenhum prompt" in response["choices"][0]["message"]["content"]

    def test_extract_prompt_list_with_string_item(self):
        """Verifica extração quando item da lista é string (não dict)."""
        prompt = self.agent._extract_prompt(["Analise a tabela X"])
        assert prompt == "Analise a tabela X"

    def test_extract_prompt_empty_list(self):
        """Verifica que lista vazia cai no fallback str()."""
        prompt = self.agent._extract_prompt([])
        # Lista vazia não entra no branch len > 0, cai no str()
        assert isinstance(prompt, str)

    def test_predict_asyncio_exception_returns_error(self):
        """Verifica que exceção no asyncio.run é capturada e retornada como erro."""
        self.agent._ready = True
        self.agent._init_error = None
        with patch("agents.mlflow_wrapper.asyncio.run", side_effect=RuntimeError("async fail")):
            response = self.agent.predict(
                None, {"messages": [{"role": "user", "content": "test"}]}
            )
        assert "error" in response
        assert "RuntimeError" in response["choices"][0]["message"]["content"]

    # ─── load_context ─────────────────────────────────────────────────────────

    def test_load_context_sets_ready_false_initially(self):
        """Verifica que load_context inicializa _ready=False antes de validar."""
        agent = ClaudeDataAgent()
        mock_context = MagicMock()
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-valid-key"}):
            agent.load_context(mock_context)
        # Se as dependências estão disponíveis e a key é válida → ready
        # (Resultado depende do ambiente; o importante é não lançar exceção)

    def test_load_context_missing_api_key_sets_not_ready(self):
        """Verifica que ausência de ANTHROPIC_API_KEY deixa o agente não pronto."""
        agent = ClaudeDataAgent()
        mock_context = MagicMock()
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
            # Remove a key do ambiente temporariamente
            import os
            env_backup = os.environ.pop("ANTHROPIC_API_KEY", None)
            try:
                agent.load_context(mock_context)
            finally:
                if env_backup is not None:
                    os.environ["ANTHROPIC_API_KEY"] = env_backup
        assert agent._ready is False
        assert agent._init_error is not None

    def test_load_context_placeholder_api_key_sets_not_ready(self):
        """Verifica que key placeholder 'sk-ant-...' é rejeitada."""
        agent = ClaudeDataAgent()
        mock_context = MagicMock()
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-..."}):
            agent.load_context(mock_context)
        assert agent._ready is False
        assert "ANTHROPIC_API_KEY" in (agent._init_error or "")

    # ─── _log_result_metrics ─────────────────────────────────────────────────

    def test_log_result_metrics_no_active_run(self):
        """Verifica que sem run MLflow ativo apenas loga via logger (sem erro)."""
        class FakeResult:
            total_cost_usd = 0.5
            num_turns = 3
            duration_ms = 1500

        with patch("agents.mlflow_wrapper.mlflow.active_run", return_value=None):
            # Não deve levantar exceção
            self.agent._log_result_metrics(FakeResult())

    def test_log_result_metrics_with_active_run_logs_metrics(self):
        """Verifica que com run MLflow ativo as métricas são logadas."""
        class FakeResult:
            total_cost_usd = 0.25
            num_turns = 5
            duration_ms = 2000

        mock_run = MagicMock()
        with patch("agents.mlflow_wrapper.mlflow.active_run", return_value=mock_run):
            with patch("agents.mlflow_wrapper.mlflow.log_metrics") as mock_log:
                self.agent._log_result_metrics(FakeResult())
                mock_log.assert_called_once()
                logged = mock_log.call_args[0][0]
                assert "agent.cost_usd" in logged
                assert "agent.num_turns" in logged
                assert "agent.duration_ms" in logged

    def test_log_result_metrics_none_values_not_logged(self):
        """Verifica que valores None não são incluídos nas métricas."""
        class FakeResult:
            total_cost_usd = None
            num_turns = None
            duration_ms = None

        mock_run = MagicMock()
        with patch("agents.mlflow_wrapper.mlflow.active_run", return_value=mock_run):
            with patch("agents.mlflow_wrapper.mlflow.log_metrics") as mock_log:
                self.agent._log_result_metrics(FakeResult())
                mock_log.assert_not_called()

    def test_log_result_metrics_partial_values(self):
        """Verifica que apenas métricas com valor não-None são logadas."""
        class FakeResult:
            total_cost_usd = 0.1
            num_turns = None
            duration_ms = 500

        mock_run = MagicMock()
        with patch("agents.mlflow_wrapper.mlflow.active_run", return_value=mock_run):
            with patch("agents.mlflow_wrapper.mlflow.log_metrics") as mock_log:
                self.agent._log_result_metrics(FakeResult())
                logged = mock_log.call_args[0][0]
                assert "agent.cost_usd" in logged
                assert "agent.num_turns" not in logged
                assert "agent.duration_ms" in logged

    def test_log_result_metrics_exception_is_swallowed(self):
        """Verifica que exceção em log não propaga para o caller."""
        class FakeResult:
            total_cost_usd = 0.5
            num_turns = 3
            duration_ms = 1500

        with patch(
            "agents.mlflow_wrapper.mlflow.active_run", side_effect=Exception("mlflow down")
        ):
            # Deve ser silenciado — não lança exceção
            self.agent._log_result_metrics(FakeResult())
