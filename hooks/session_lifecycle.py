"""
Session Lifecycle Hooks — Inicialização e encerramento de sessão (Ch. 12).

Inspirado no capítulo 12 de "Claude Code from Source": hooks que disparam no
início e no fim de cada sessão para manter o estado do sistema limpo e
garantir que a memória seja persistida corretamente.

Responsabilidades:
  - on_session_start: reseta contadores de contexto, prepara buffer de memória
  - on_session_end:   dispara flush de memória, loga estatísticas de uso

Integração:
  Chame on_session_start() no início de main.py (ou equivalent entry point)
  antes de iniciar o loop de agente, e on_session_end() no bloco finally.

  Exemplo:
      session_id = uuid.uuid4().hex[:8]
      on_session_start(session_id)
      try:
          result = query(agent_options, message)
      finally:
          on_session_end(session_id)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from hooks.context_budget_hook import get_context_usage, reset_context_budget
from hooks.memory_hook import flush_session_memories

logger = logging.getLogger("data_agents.hooks.session_lifecycle")


def on_session_start(session_id: str) -> None:
    """
    Chamado no início de cada sessão antes do loop de agente.

    Ações:
      1. Reseta o context budget counter (acumulado da sessão anterior).
      2. Loga o início com timestamp para rastreamento.

    Args:
        session_id: Identificador único da sessão (ex: uuid hex).
    """
    # Reseta o contexto acumulado da sessão anterior
    reset_context_budget()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    logger.info(f"[session_start] sessão={session_id} | {now}")


def on_session_end(
    session_id: str,
    flush_memory: bool = True,
) -> None:
    """
    Chamado no encerramento de cada sessão (bloco finally do entry point).

    Ações:
      1. Dispara flush de memória para persistir o contexto acumulado.
      2. Loga estatísticas de uso do contexto.

    Args:
        session_id: Identificador único da sessão.
        flush_memory: Se True (padrão), dispara flush_session_memories().
                      Use False em testes ou quando flush manual já foi feito.
    """
    # Loga uso final do contexto antes do flush
    try:
        usage = get_context_usage()
        logger.info(
            f"[session_end] sessão={session_id} | "
            f"input={usage['input_tokens']:,} output={usage['output_tokens']:,} "
            f"tokens | {usage['usage_ratio']:.1%} do limite"
        )
    except Exception as e:
        logger.warning(f"[session_end] Erro ao obter uso de contexto: {e}")

    # Flush de memória: persiste o contexto acumulado da sessão
    if flush_memory:
        try:
            flush_session_memories()
            logger.info(f"[session_end] Memory flush concluído para sessão={session_id}")
        except Exception as e:
            logger.warning(f"[session_end] Erro no memory flush (sessão={session_id}): {e}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    logger.info(f"[session_end] sessão={session_id} encerrada | {now}")
