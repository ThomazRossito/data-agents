"""
Wrapper PyFunc para implantação do Data Agent em Model Serving do Databricks
via MLflow (Mosaic AI Agent Framework).

Implementa:
  - asyncio.run() compatível com Python 3.12+ (sem get_event_loop depreciado)
  - load_context() com validação de dependências e credenciais
  - Logging estruturado para diagnóstico em produção
  - Tratamento de erros granular com mensagens descritivas
"""

import asyncio
import logging
import os
from typing import Any

import mlflow

logger = logging.getLogger("data_agents.mlflow")


class ClaudeDataAgent(mlflow.pyfunc.PythonModel):
    """
    Wrapper PyFunc para implantação do Data Agent em Model Serving do Databricks
    via MLflow (Mosaic AI Agent Framework).

    O endpoint recebe payloads no formato OpenAI Messages e retorna
    respostas no mesmo formato, compatível com Databricks AI Gateway.
    """

    def load_context(self, context) -> None:
        """
        Inicialização disparada quando o endpoint de model serving sobe.

        Valida dependências, credenciais e pré-carrega módulos para
        reduzir latência na primeira chamada.
        """
        self._ready = False
        self._init_error: str | None = None

        # Validar dependências críticas
        try:
            import claude_agent_sdk  # noqa: F401
            from agents.supervisor import build_supervisor_options  # noqa: F401

            logger.info("Dependências do Data Agent carregadas com sucesso.")
        except ImportError as e:
            self._init_error = (
                f"Dependência ausente no ambiente MLflow: {e}. "
                f"Verifique se 'claude-agent-sdk' e o pacote 'data-agents' "
                f"estão listados no conda_env do modelo."
            )
            logger.error(self._init_error)
            return

        # Validar credenciais mínimas
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key or api_key.startswith("sk-ant-..."):
            self._init_error = (
                "ANTHROPIC_API_KEY não configurada no ambiente de serving. "
                "Configure como secret no Databricks Model Serving."
            )
            logger.error(self._init_error)
            return

        self._ready = True
        logger.info("ClaudeDataAgent inicializado e pronto para servir.")

    def predict(self, context, model_input) -> dict[str, Any]:
        """
        Ponto de entrada do Databricks Model Serving.

        Recebe payload compatível com OpenAI Messages:
            { "messages": [{"role": "user", "content": "Analise a tabela X"}] }

        Retorna resposta no mesmo formato para compatibilidade com AI Gateway.
        """
        # Verificar se o modelo foi inicializado corretamente
        if not getattr(self, "_ready", False):
            return self._format_response(
                f"Erro de inicialização: {getattr(self, '_init_error', None) or 'Motivo desconhecido'}",
                is_error=True,
            )

        # Extrair prompt do payload
        prompt = self._extract_prompt(model_input)

        if not prompt.strip():
            return self._format_response(
                "Nenhum prompt foi recebido. Envie no formato: "
                '{"messages": [{"role": "user", "content": "sua pergunta"}]}',
                is_error=True,
            )

        # Executar query via Claude SDK — usa asyncio.run() (Python 3.12+ compatível)
        try:
            result = asyncio.run(self._run_query(prompt))
            return self._format_response(result)
        except Exception as e:
            error_msg = f"Erro durante execução: {type(e).__name__}: {e}"
            logger.error(error_msg, exc_info=True)
            return self._format_response(error_msg, is_error=True)

    def _extract_prompt(self, model_input: Any) -> str:
        """
        Extrai o prompt do payload de entrada, suportando múltiplos formatos.

        Formatos suportados:
          - OpenAI Messages: {"messages": [{"role": "user", "content": "..."}]}
          - Lista simples: [{"prompt": "..."}]
          - String direta: "..."
        """
        # Formato OpenAI Messages (padrão Databricks AI Gateway)
        if hasattr(model_input, "get") and "messages" in model_input:
            messages = model_input["messages"]
            if messages:
                return messages[-1].get("content", "")

        # Formato lista de dicts
        if isinstance(model_input, list) and len(model_input) > 0:
            item = model_input[0]
            if isinstance(item, dict):
                return item.get("prompt", item.get("content", str(item)))
            return str(item)

        # Fallback: string direta
        return str(model_input)

    def _format_response(self, text: str, is_error: bool = False) -> dict[str, Any]:
        """
        Formata a saída para compatibilidade com APIs de Chat (Databricks + OpenAI).

        Args:
            text: Conteúdo da resposta.
            is_error: Se True, inclui metadata de erro para observabilidade.
        """
        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": text,
                    }
                }
            ]
        }

        if is_error:
            response["error"] = {"message": text, "type": "agent_error"}

        return response

    async def _run_query(self, prompt: str) -> str:
        """
        Executa o fluxo interno do sistema via Claude SDK.

        Inicializa o supervisor com ferramentas MCP e processa a query
        através do pipeline multi-agente completo.

        Registra métricas de custo/turns/duração no MLflow Run ativo (se houver),
        permitindo rastreamento de custos diretamente no experimento MLflow.
        """
        from claude_agent_sdk import query, AssistantMessage, TextBlock, ResultMessage
        from agents.supervisor import build_supervisor_options

        options = build_supervisor_options()
        final_text = ""

        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock) and block.text.strip():
                        final_text += block.text + "\n"

            elif isinstance(message, ResultMessage):
                # Loga métricas de uso no MLflow Run ativo (se houver)
                self._log_result_metrics(message)

        return final_text if final_text else "Processamento concluído sem resposta textual."

    def _log_result_metrics(self, result) -> None:
        """
        Loga métricas do ResultMessage no MLflow Run ativo.

        Métricas registradas:
          - agent.cost_usd: custo total em dólares
          - agent.num_turns: número de turns executados
          - agent.duration_ms: duração total em milissegundos

        Se não houver um Run MLflow ativo, apenas loga via logger (não falha).
        """
        try:
            run = mlflow.active_run()
            if run is None:
                # Sem run ativo — apenas loga no logger para diagnóstico
                logger.info(
                    "ResultMessage (sem MLflow run ativo): cost=%.4f turns=%s duration_ms=%s",
                    result.total_cost_usd or 0.0,
                    result.num_turns or 0,
                    result.duration_ms or 0,
                )
                return

            metrics: dict[str, float] = {}
            if result.total_cost_usd is not None:
                metrics["agent.cost_usd"] = result.total_cost_usd
            if result.num_turns is not None:
                metrics["agent.num_turns"] = float(result.num_turns)
            if result.duration_ms is not None:
                metrics["agent.duration_ms"] = float(result.duration_ms)

            if metrics:
                mlflow.log_metrics(metrics)
                logger.info("Métricas do agente logadas no MLflow: %s", metrics)

        except Exception as e:
            # Falhas de logging nunca devem interromper a resposta ao usuário
            logger.warning("Falha ao logar métricas no MLflow: %s", e)


# ═══════════════════════════════════════════════════════════════════
# Snippet de Código para Registro Manual
# Copie as linhas abaixo para um Databricks Notebook para logar
# esta classe e registrá-la em Unity Catalog.
# ═══════════════════════════════════════════════════════════════════
"""
import mlflow
from agents.mlflow_wrapper import ClaudeDataAgent

# Definir as dependências do ambiente
conda_env = mlflow.pyfunc.get_default_conda_env()
conda_env["dependencies"][-1]["pip"].extend([
    "claude-agent-sdk>=0.1.48",
    "databricks-sdk>=0.20.0",
    "pydantic-settings>=2.0.0",
])

# Log in Unity Catalog
mlflow.set_registry_uri("databricks-uc")
with mlflow.start_run():
    mlflow.pyfunc.log_model(
        artifact_path="data_agent",
        python_model=ClaudeDataAgent(),
        registered_model_name="main.data_agents.claude_supervisor",
        conda_env=conda_env,
    )
"""
