"""
commands/geral.py — Lógica compartilhada do comando /geral.

Módulo único importado por ambos os entry points:
  - main.py        (CLI interativo / terminal)
  - ui/chat.py     (interface Streamlit)

Garante implementação única — sem duplicação entre os dois entry points.
O caller é responsável por gerenciar o histórico e exibir a resposta.

Uso típico:
    from commands.geral import run_geral_query, build_prompt_with_history

    history.append({"role": "user", "content": user_message})
    text, metrics = await run_geral_query(user_message, history)
    if text:
        history.append({"role": "assistant", "content": text})
"""

from __future__ import annotations

import logging

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query as sdk_query,
)

from config.settings import settings

logger = logging.getLogger("data_agents.geral")

# ── System prompt ─────────────────────────────────────────────────────────────
GERAL_SYSTEM = (
    "Você é um assistente técnico especializado em Engenharia de Dados: "
    "Databricks, Microsoft Fabric, Apache Spark, Delta Lake, SQL, arquitetura Medallion "
    "e boas práticas. "
    "Responda em português brasileiro, de forma direta e objetiva. "
    "Use exemplos e code blocks quando enriquecer a resposta. "
    "Não peça aprovação, não crie documentos, não acesse arquivos externos."
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def build_geral_options() -> ClaudeAgentOptions:
    """
    ClaudeAgentOptions mínimo para /geral.

    Zero sub-agentes, zero MCP, zero hooks.
    O SDK gerencia auth internamente → mesmo mecanismo Bearer do Supervisor.
    Modelo: settings.default_model (inclui prefixo bedrock/ quando configurado).
    """
    return ClaudeAgentOptions(
        model=settings.default_model,
        system_prompt=GERAL_SYSTEM,
        allowed_tools=[],
        agents=None,
        mcp_servers={},
        max_turns=1,
        permission_mode="bypassPermissions",
    )


def build_prompt_with_history(user_message: str, history: list[dict]) -> str:
    """
    Embute histórico recente no prompt para suporte a follow-ups.

    O sdk_query() é stateless (não há API de multi-turn), então o histórico
    é prefixado como texto estruturado antes da mensagem atual.

    Args:
        user_message: Mensagem atual do usuário (deve já estar em history).
        history:      Lista completa [{role, content}] incluindo a mensagem atual.

    Returns:
        Prompt final com histórico prefixado (se houver turnos anteriores).
    """
    history_prefix = ""
    if len(history) > 1:
        lines: list[str] = []
        for msg in history[-21:-1]:  # até 10 turnos anteriores (excluindo atual)
            role = "Usuário" if msg["role"] == "user" else "Assistente"
            lines.append(f"{role}: {msg['content']}")
        if lines:
            history_prefix = "Histórico:\n" + "\n".join(lines) + "\n\n"
    return history_prefix + user_message


# ── Core async ────────────────────────────────────────────────────────────────


async def run_geral_query(
    user_message: str,
    history: list[dict],
    session_type: str = "geral",
) -> tuple[str, dict[str, float]]:
    """
    Executa consulta /geral via claude_agent_sdk.

    O caller é responsável por:
      1. Adicionar user_message ao history ANTES de chamar esta função.
      2. Adicionar response_text ao history APÓS retorno bem-sucedido.
      3. Exibir o response_text (CLI com Rich ou UI com Streamlit).

    Args:
        user_message: Mensagem atual do usuário (sem histórico embutido).
        history:      Lista [{role, content}] incluindo a mensagem atual.
        session_type: Tipo de sessão para logging (default "geral").

    Returns:
        Tuple (response_text, metrics) onde:
          - response_text: Texto da resposta (vazio se erro ou sem resposta).
          - metrics: {"cost": float, "turns": float, "duration": float}

    Raises:
        Propaga exceções do SDK — o caller deve tratar e reverter o histórico.
    """
    from hooks.session_logger import log_session_result

    prompt = build_prompt_with_history(user_message, history)
    options = build_geral_options()

    response_text = ""
    metrics: dict[str, float] = {"cost": 0.0, "turns": 1.0, "duration": 0.0}

    async for message in sdk_query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    response_text += block.text

        elif isinstance(message, ResultMessage):
            metrics["cost"] = float(message.total_cost_usd or 0)
            metrics["turns"] = float(message.num_turns or 1)
            metrics["duration"] = float(message.duration_ms or 0) / 1000
            log_session_result(
                message, prompt_preview=user_message[:100], session_type=session_type
            )
            logger.debug(
                "geral query: cost=%.5f turns=%d duration=%.1fs",
                metrics["cost"],
                int(metrics["turns"]),
                metrics["duration"],
            )

    return response_text, metrics
