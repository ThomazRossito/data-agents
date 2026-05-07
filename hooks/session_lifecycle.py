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
    # Reseta o contexto acumulado da sessão anterior e registra o session_id
    # para o auto-fire do summarizer localizar o transcript quando disparar.
    reset_context_budget(session_id=session_id)

    # Gera chave de sessão e registra no audit_hook para assinatura Ledger
    try:
        from hooks.audit_hook import set_current_session
        from memory.ledger import Ledger

        session_key = Ledger.generate_session_key()
        set_current_session(session_id, session_key)
        logger.debug(f"[session_start] Ledger session key gerada para sessão={session_id}")
    except Exception as e:
        logger.warning(
            f"[session_start] Falha ao inicializar Ledger (continuando sem assinatura): {e}"
        )

    # Inicializa ShortTermMemory e registra no memory_hook
    try:
        from config.settings import settings as _settings
        from memory.short_term import ShortTermMemory
        from hooks.memory_hook import init_memory_hook
        from pathlib import Path

        embedder = None
        if _settings.short_term_embedder_enabled:
            try:
                from memory.embedder import LocalEmbedder

                embedder = LocalEmbedder(
                    cache_db_path=Path(_settings.embedder_cache_db_path),
                    model_name=_settings.short_term_embedder_model,
                )
                logger.info("[session_start] LocalEmbedder carregado para short-term memory")
            except ImportError:
                logger.info(
                    "[session_start] fastembed não instalado — usando FTS5 (BM25) para short-term"
                )

        short_term = ShortTermMemory(
            db_path=Path(_settings.short_term_db_path),
            ttl_days=_settings.short_term_ttl_days,
            embedder=embedder,
        )
        short_term.expire_old_entries()
        init_memory_hook(session_id, short_term)
        logger.debug(
            f"[session_start] ShortTermMemory inicializado: ttl={_settings.short_term_ttl_days}d"
        )
    except Exception as e:
        logger.warning(
            f"[session_start] Falha ao inicializar ShortTermMemory (continuando com fallback): {e}"
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    logger.info(f"[session_start] sessão={session_id} | {now}")


def on_session_end(
    session_id: str,
    flush_memory: bool = True,
    memory_manager=None,
) -> None:
    """
    Chamado no encerramento de cada sessão (bloco finally do entry point).

    Ações:
      1. Loga estatísticas de uso do contexto.
      2. Dispara flush de memória (via memory_manager.end_session() se disponível,
         senão via flush_session_memories() direto).

    Args:
        session_id: Identificador único da sessão.
        flush_memory: Se True (padrão), dispara flush de memória.
                      Use False em testes ou quando flush manual já foi feito.
        memory_manager: Instância de MemoryManager (opcional). Se fornecida,
                        delega o flush para memory_manager.end_session(), que
                        também sincroniza o índice long-term.
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
        if memory_manager is not None:
            try:
                memory_manager.end_session()
                logger.info(
                    f"[session_end] MemoryManager.end_session() concluído para sessão={session_id}"
                )
            except Exception as e:
                logger.warning(f"[session_end] Erro em memory_manager.end_session(): {e}")
        else:
            try:
                flush_session_memories()
                logger.info(f"[session_end] Memory flush concluído para sessão={session_id}")
            except Exception as e:
                logger.warning(f"[session_end] Erro no memory flush (sessão={session_id}): {e}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    logger.info(f"[session_end] sessão={session_id} encerrada | {now}")
