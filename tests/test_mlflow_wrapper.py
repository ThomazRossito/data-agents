"""Testes do MLflow Wrapper."""

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
