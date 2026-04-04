import asyncio
import mlflow

class ClaudeDataAgent(mlflow.pyfunc.PythonModel):
    """
    Wrapper PyFunc para implantação do Data Agent em Model Serving do Databricks 
    via MLflow (Mosaic AI Agent Framework).
    """

    def load_context(self, context):
        """
        Inicialização disparada quando o endpoint de model serving sobe.
        Aqui são feitas configurações globais ou validação das credenciais.
        """
        pass

    def predict(self, context, model_input):
        """
        Ponto de entrada do Databricks Model Serving.
        
        É arquitetado para receber um Payload compatível com chamadas REST de Chat.
        Exemplo: { "messages": [{"role": "user", "content": "Analise a tabela X"}] }
        """
        prompt = ""
        
        # Tratar a entrada caso venha do endpoint Model Serving no formato OpenAI Messages
        if hasattr(model_input, "get") and "messages" in model_input:
            messages = model_input["messages"]
            if messages:
                prompt = messages[-1].get("content", "")
        # Tratamento de fallback
        elif isinstance(model_input, list) and len(model_input) > 0:
            item = model_input[0]
            if isinstance(item, dict):
                prompt = item.get("prompt", str(item))
            else:
                prompt = str(item)
        else:
            prompt = str(model_input)

        if not prompt.strip():
            return self._format_response("Nenhum prompt foi recebido no backend.")

        # Rodando a camada assíncrona do Claude SDK dentro de um ambiente síncrono (endpoint de Serving)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        result = loop.run_until_complete(self._run_query(prompt))
        
        return self._format_response(result)

    def _format_response(self, text: str) -> dict:
        """Formata a saída para bater com o contrato de APIs de Chat do Databricks e OpenAI."""
        return {
             "choices": [
                  {
                       "message": {
                            "role": "assistant",
                            "content": text
                       }
                  }
             ]
        }

    async def _run_query(self, prompt: str) -> str:
        """
        Reusa o fluxo interno do sistema, inicializando o supervisor com ferramentas (tools).
        """
        try:
            from claude_agent_sdk import query, AssistantMessage, TextBlock
            # Utilizamos o builder do próprio projeto apontando para recursos Databricks
            from agents.supervisor import build_supervisor_options
        except ImportError as e:
            return f"Erro de Importação: Módulo do data-agents não listado nos requirements do MLflow: {e}"
            
        options = build_supervisor_options()
        final_text = ""
        
        # Executa a query no runtime do Claude via protocolo MCP (que baterá no Databricks Workspace)
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock) and block.text.strip():
                        final_text += block.text + "\n"
                        
        return final_text if final_text else "Aguardando resposta do agente."

# === Snippet de Código para Registro Manual ===
# Copie as linhas abaixo para um Databricks Notebook caso queira logar esta classe e registrá-la em Unity Catalog.
"""
import mlflow
from agents.mlflow_wrapper import ClaudeDataAgent

# Definir as dependências do ambiente
conda_env = mlflow.pyfunc.get_default_conda_env()
conda_env["dependencies"][-1]["pip"].extend([
    "claude-agent-sdk>=0.1.48",
    "databricks-sdk>=0.20.0"
])

# Log in Unity Catalog
mlflow.set_registry_uri("databricks-uc")
with mlflow.start_run():
    mlflow.pyfunc.log_model(
        artifact_path="data_agent",
        python_model=ClaudeDataAgent(),
        registered_model_name="main.data_agents.claude_supervisor",
        conda_env=conda_env
    )
"""
