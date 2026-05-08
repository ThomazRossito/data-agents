"""
ShortTermMemory — Buffer de sessão persistente com TTL e busca.

Backend: SQLite (stdlib — zero dependências extras).
Busca: FTS5 com BM25 scoring (lexical).
       Complementado com cosine similarity quando LocalEmbedder disponível.
TTL: configurável, padrão 3 dias. Entradas expiradas são deletadas automaticamente.

Substitui o _session_buffer in-memory do memory_hook.py:
  - Sobrevive a crashes (SQLite persiste no disco)
  - TTL automático (entradas velhas não poluem buscas)
  - Pesquisável entre sessões na janela de TTL
  - Entradas com promoted=1 indicam candidatos para promoção ao LongTermMemory

Schema SQLite:
  short_term_entries: tabela principal com embedding opcional
  short_term_fts:     FTS5 virtual table para BM25 search
  Triggers:           sincronizam FTS5 com a tabela principal automaticamente
"""

from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memory.embedder import LocalEmbedder

logger = logging.getLogger("data_agents.memory.short_term")

_CREATE_MAIN_TABLE = """
CREATE TABLE IF NOT EXISTS short_term_entries (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    content     TEXT NOT NULL,
    tool_name   TEXT,
    created_at  REAL NOT NULL,
    expires_at  REAL NOT NULL,
    promoted    INTEGER NOT NULL DEFAULT 0,
    embedding   BLOB
);
"""

_CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_st_session  ON short_term_entries(session_id);
CREATE INDEX IF NOT EXISTS idx_st_expires  ON short_term_entries(expires_at);
CREATE INDEX IF NOT EXISTS idx_st_promoted ON short_term_entries(promoted);
"""

_CREATE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS short_term_fts USING fts5(
    content,
    content='short_term_entries',
    content_rowid='rowid'
);
"""

_CREATE_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS st_ai AFTER INSERT ON short_term_entries BEGIN
    INSERT INTO short_term_fts(rowid, content) VALUES (new.rowid, new.content);
END;
CREATE TRIGGER IF NOT EXISTS st_ad AFTER DELETE ON short_term_entries BEGIN
    INSERT INTO short_term_fts(short_term_fts, rowid, content)
    VALUES ('delete', old.rowid, old.content);
END;
CREATE TRIGGER IF NOT EXISTS st_au AFTER UPDATE OF content ON short_term_entries BEGIN
    INSERT INTO short_term_fts(short_term_fts, rowid, content)
    VALUES ('delete', old.rowid, old.content);
    INSERT INTO short_term_fts(rowid, content) VALUES (new.rowid, new.content);
END;
"""


@dataclass
class ShortTermEntry:
    """Uma entrada do buffer de sessão."""

    id: str
    session_id: str
    content: str
    tool_name: str | None
    created_at: float
    expires_at: float
    promoted: bool = False
    score: float = 0.0  # score de busca (BM25 rank ou cosine similarity)


class ShortTermMemory:
    """
    Buffer de sessão persistente em SQLite com TTL e busca FTS5.

    Args:
        db_path: Path do arquivo SQLite. Criado automaticamente se não existir.
        ttl_days: Dias até uma entrada expirar. Padrão: 3 dias.
        embedder: Instância opcional de LocalEmbedder para busca vetorial.
                  Quando None, usa somente FTS5 (BM25 lexical).
    """

    def __init__(
        self,
        db_path: Path,
        ttl_days: float = 3.0,
        embedder: LocalEmbedder | None = None,
    ) -> None:
        self._db_path = db_path
        self._ttl_seconds = ttl_days * 86_400
        self._embedder = embedder
        self._init_db()

    # ── Inicialização ─────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(_CREATE_MAIN_TABLE)
            conn.executescript(_CREATE_INDEXES)
            conn.execute(_CREATE_FTS)
            conn.executescript(_CREATE_TRIGGERS)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    # ── Escrita ───────────────────────────────────────────────────────────────

    def append(
        self,
        content: str,
        session_id: str,
        tool_name: str | None = None,
    ) -> str:
        """
        Adiciona uma entrada ao buffer.

        Gera embedding se LocalEmbedder disponível.
        Retorna o ID da entrada criada.
        """
        if not content or not content.strip():
            return ""

        entry_id = uuid.uuid4().hex[:12]
        now = time.time()
        expires_at = now + self._ttl_seconds

        embedding_bytes: bytes | None = None
        if self._embedder is not None:
            try:
                emb = self._embedder.embed(content)
                from memory.embedder import serialize_embedding

                embedding_bytes = serialize_embedding(emb)
            except Exception as e:
                logger.debug(f"Embedding falhou (sem vetor): {e}")

        with self._connect() as conn:
            conn.execute(
                """INSERT INTO short_term_entries
                   (id, session_id, content, tool_name, created_at, expires_at, promoted, embedding)
                   VALUES (?, ?, ?, ?, ?, ?, 0, ?)""",
                (entry_id, session_id, content, tool_name, now, expires_at, embedding_bytes),
            )

        return entry_id

    # ── Busca ─────────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        limit: int = 10,
        session_id: str | None = None,
    ) -> list[ShortTermEntry]:
        """
        Busca entradas relevantes usando FTS5 (BM25).

        Se LocalEmbedder disponível, re-rankeia os resultados por
        cosine similarity entre o embedding da query e os das entradas.

        Args:
            query: Texto de busca.
            limit: Número máximo de resultados.
            session_id: Se fornecido, restringe à sessão específica.

        Returns:
            Entradas ordenadas por relevância (score desc).
        """
        if not query or not query.strip():
            return []

        # FTS5 trata ?  " * ( ) - ^ ~ como operadores; remove-os para evitar syntax error
        import re

        query = re.sub(r'[?"*()^\-~]', " ", query).strip()
        if not query:
            return []

        now = time.time()
        session_filter = "AND e.session_id = ?" if session_id else ""
        params: list = [query, now]
        if session_id:
            params.append(session_id)
        params.append(limit * 3)  # busca mais para re-rankear com embeddings

        sql = f"""
            SELECT e.id, e.session_id, e.content, e.tool_name,
                   e.created_at, e.expires_at, e.promoted, e.embedding,
                   -rank AS bm25_score
            FROM short_term_fts f
            JOIN short_term_entries e ON e.rowid = f.rowid
            WHERE short_term_fts MATCH ?
              AND e.expires_at > ?
              {session_filter}
            ORDER BY rank
            LIMIT ?
        """

        try:
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as e:
            logger.warning(f"ShortTermMemory.search FTS falhou: {e}")
            return []

        entries = [
            ShortTermEntry(
                id=row["id"],
                session_id=row["session_id"],
                content=row["content"],
                tool_name=row["tool_name"],
                created_at=row["created_at"],
                expires_at=row["expires_at"],
                promoted=bool(row["promoted"]),
                score=float(row["bm25_score"] or 0.0),
            )
            for row in rows
        ]

        # Re-rankear com cosine similarity se embedder disponível
        if self._embedder is not None and entries:
            entries = self._rerank_by_similarity(query, entries)

        return entries[:limit]

    def _rerank_by_similarity(
        self,
        query: str,
        candidates: list[ShortTermEntry],
    ) -> list[ShortTermEntry]:
        """Re-rankeia candidatos BM25 usando cosine similarity."""
        try:
            from memory.embedder import deserialize_embedding, cosine_similarity

            query_emb = self._embedder.embed(query)

            with self._connect() as conn:
                for entry in candidates:
                    row = conn.execute(
                        "SELECT embedding FROM short_term_entries WHERE id=?", (entry.id,)
                    ).fetchone()
                    if row and row["embedding"]:
                        entry_emb = deserialize_embedding(row["embedding"])
                        entry.score = cosine_similarity(query_emb, entry_emb)
                    # Entradas sem embedding mantém score BM25 normalizado

            candidates.sort(key=lambda e: e.score, reverse=True)
        except Exception as e:
            logger.debug(f"Re-rank por embedding falhou (mantendo BM25): {e}")

        return candidates

    # ── Leitura de sessão ─────────────────────────────────────────────────────

    def get_session_buffer(self, session_id: str) -> str:
        """
        Retorna o conteúdo acumulado da sessão como texto.

        Usado pelo extractor para processar a conversa no flush.
        Retorna entradas não-expiradas em ordem cronológica.
        """
        now = time.time()
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """SELECT content FROM short_term_entries
                       WHERE session_id=? AND expires_at > ?
                       ORDER BY created_at ASC""",
                    (session_id, now),
                ).fetchall()
            return "\n\n---\n\n".join(row["content"] for row in rows)
        except sqlite3.Error as e:
            logger.warning(f"get_session_buffer falhou: {e}")
            return ""

    def get_stats(self, session_id: str | None = None) -> dict:
        """Retorna estatísticas do buffer."""
        now = time.time()
        try:
            with self._connect() as conn:
                if session_id:
                    total = conn.execute(
                        "SELECT COUNT(*) FROM short_term_entries WHERE session_id=?",
                        (session_id,),
                    ).fetchone()[0]
                    active = conn.execute(
                        "SELECT COUNT(*) FROM short_term_entries WHERE session_id=? AND expires_at>?",
                        (session_id, now),
                    ).fetchone()[0]
                else:
                    total = conn.execute("SELECT COUNT(*) FROM short_term_entries").fetchone()[0]
                    active = conn.execute(
                        "SELECT COUNT(*) FROM short_term_entries WHERE expires_at>?",
                        (now,),
                    ).fetchone()[0]
            return {"total": total, "active": active, "expired": total - active}
        except sqlite3.Error:
            return {"total": 0, "active": 0, "expired": 0}

    # ── Manutenção ────────────────────────────────────────────────────────────

    def expire_old_entries(self) -> int:
        """
        Remove entradas com TTL expirado.

        Retorna o número de entradas removidas.
        Seguro para chamar a qualquer momento — não afeta entradas ativas.
        """
        now = time.time()
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM short_term_entries WHERE expires_at <= ?", (now,)
                )
                removed = cursor.rowcount
            if removed:
                logger.info(f"ShortTermMemory: {removed} entradas expiradas removidas")
            return removed
        except sqlite3.Error as e:
            logger.warning(f"expire_old_entries falhou: {e}")
            return 0

    def mark_promoted(self, entry_id: str) -> None:
        """Marca uma entrada como promovida para long-term memory."""
        try:
            with self._connect() as conn:
                conn.execute("UPDATE short_term_entries SET promoted=1 WHERE id=?", (entry_id,))
        except sqlite3.Error as e:
            logger.warning(f"mark_promoted falhou para {entry_id}: {e}")
