"""
MemoryManager — Façade unificada para o sistema de memória.

API única sobre as 3 camadas:
  inject_context()  → long_term.search() (FTS5) + cache TTL 60s
  flush_session()   → flush_session_memories() + sync long_term
  apply_decay()     → memory.decay.apply_decay()
  end_session()     → flush_session() + reset de estado
  sync_long_term()  → migrate_from_store() → reindexação do MemoryStore
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memory.store import MemoryStore
    from memory.long_term import LongTermMemory
    from config.settings import Settings

logger = logging.getLogger("data_agents.memory.manager")

_RETRIEVAL_CACHE_TTL = 60.0  # segundos


class MemoryManager:
    """
    Ponto único de entrada para todas as operações de memória.

    Instanciar uma vez por processo (em main.py ou chainlit_app.py).
    Chamar start_session() no início de cada sessão interativa.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        if settings is None:
            from config.settings import settings as _s

            settings = _s
        self._settings = settings
        self._store: MemoryStore | None = None
        self._long_term: LongTermMemory | None = None
        self._session_id: str = ""
        self._decay_applied: bool = False
        self._long_term_synced: bool = False
        # {query_hash: (enriched_prompt, timestamp)} — evita retrieval redundante
        self._retrieval_cache: dict[str, tuple[str, float]] = {}

    # ── Propriedades lazy ─────────────────────────────────────────────────────

    @property
    def store(self) -> MemoryStore:
        """MemoryStore lazy-initialized."""
        if self._store is None:
            from memory.store import MemoryStore

            self._store = MemoryStore()
        return self._store

    @property
    def long_term(self) -> LongTermMemory:
        """LongTermMemory lazy-initialized."""
        if self._long_term is None:
            from memory.long_term import LongTermMemory
            from pathlib import Path

            embedder = None
            if self._settings.long_term_embedder_enabled:
                try:
                    from memory.embedder import LocalEmbedder
                    from pathlib import Path as _Path

                    embedder = LocalEmbedder(
                        cache_db_path=_Path(self._settings.embedder_cache_db_path),
                        model_name=self._settings.short_term_embedder_model,
                    )
                except ImportError:
                    pass

            self._long_term = LongTermMemory(
                db_path=Path(self._settings.long_term_db_path),
                embedder=embedder,
            )
        return self._long_term

    # ── Ciclo de vida da sessão ───────────────────────────────────────────────

    def start_session(self, session_id: str) -> None:
        """Inicializa o estado da sessão. Chamar uma vez por conversa.

        Deve ser chamado APÓS on_session_start() do session_lifecycle,
        que inicializa o ShortTermMemory e dispara expire_old_entries().
        """
        self._session_id = session_id
        self._decay_applied = False
        self._long_term_synced = False
        self._retrieval_cache.clear()
        logger.info(f"MemoryManager: sessão iniciada — {session_id!r}")

    def end_session(self) -> None:
        """Encerra a sessão: persiste memórias capturadas e reseta estado."""
        if self._settings.memory_enabled:
            count = self.flush_session()
            logger.info(f"MemoryManager: sessão encerrada — {count} memórias persistidas")
        self._session_id = ""
        self._decay_applied = False
        self._long_term_synced = False

    # ── Sincronização do índice ───────────────────────────────────────────────

    def sync_long_term(self) -> int:
        """
        Sincroniza o LongTermMemory com o MemoryStore.

        Idempotente — seguro de chamar repetidamente.
        Chamado automaticamente na primeira query de inject_context().

        Returns:
            Número de memórias indexadas.
        """
        try:
            count = self.long_term.migrate_from_store(self.store)
            self._long_term_synced = True
            return count
        except Exception as e:
            logger.warning(f"sync_long_term falhou: {e}")
            return 0

    # ── Operações principais ──────────────────────────────────────────────────

    def inject_context(self, query: str, system_prompt: str) -> str:
        """
        Injeta memórias relevantes no system_prompt do Supervisor.

        Caminho:
          1. Cache hit → retorna imediatamente (TTL 60s)
          2. Apply decay (1x por sessão)
          3. Sync long_term (1x por sessão)
          4. long_term.search(query) → memórias persistentes
          5. Formata e injeta no system_prompt
        """
        if not self._settings.memory_enabled or not self._settings.memory_retrieval_enabled:
            return system_prompt

        try:
            query_hash = hashlib.md5(query[:200].encode(), usedforsecurity=False).hexdigest()
            cached = self._retrieval_cache.get(query_hash)
            if cached and (time.monotonic() - cached[1]) < _RETRIEVAL_CACHE_TTL:
                logger.debug("Memory retrieval: cache hit.")
                return cached[0]

            # Apply decay 1x por sessão
            if not self._decay_applied:
                self.apply_decay()

            # Sync index 1x por sessão
            if not self._long_term_synced:
                self.sync_long_term()

            # Busca no LongTermMemory (FTS5 — sem custo LLM)
            from memory.retrieval import format_memories_for_injection

            memories = self.long_term.search(
                query=query,
                limit=self._settings.long_term_search_limit,
            )

            if not memories:
                return system_prompt

            memory_context = format_memories_for_injection(memories)
            enriched = system_prompt + memory_context

            self._retrieval_cache[query_hash] = (enriched, time.monotonic())
            logger.debug(
                f"Memory injection: {len(memories)} memórias (+{len(memory_context)} chars)"
            )
            return enriched

        except Exception as e:
            logger.warning(f"MemoryManager.inject_context falhou (continuando sem memória): {e}")
            return system_prompt

    def flush_session(self) -> int:
        """
        Processa o buffer da sessão, persiste memórias e sincroniza o índice.

        Returns:
            Número de memórias extraídas e salvas.
        """
        if not self._settings.memory_enabled or not self._settings.memory_capture_enabled:
            return 0

        try:
            from hooks.memory_hook import flush_session_memories

            count = flush_session_memories(session_id=self._session_id)

            # Sincroniza o índice com as novas memórias salvas
            if count > 0:
                self._long_term_synced = False
                self.sync_long_term()

            return count

        except Exception as e:
            logger.warning(f"MemoryManager.flush_session falhou: {e}")
            return 0

    def apply_decay(self) -> None:
        """Aplica decay temporal às memórias ativas (1x por sessão)."""
        try:
            from memory.decay import apply_decay as _apply_decay

            memories = self.store.list_all(active_only=False)
            if memories:
                _apply_decay(memories, save_fn=self.store.save)
            self._decay_applied = True

        except Exception as e:
            logger.warning(f"MemoryManager.apply_decay falhou: {e}")
