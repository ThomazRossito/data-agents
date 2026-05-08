"""
LongTermMemory — Índice SQLite persistente de memórias de longo prazo.

Backend: SQLite (stdlib) + FTS5 com BM25 scoring.
Busca híbrida: BM25 lexical (sempre) + cosine similarity (quando fastembed disponível).
Sem TTL — entradas sobrevivem indefinidamente (decay via campo `confidence`).

Schema:
  long_term_memories: tabela principal (espelha Memory dataclass)
  long_term_fts:      FTS5 virtual table sobre summary + content + tags
  Triggers:           sincronizam FTS5 automaticamente

Relação com MemoryStore:
  MemoryStore é a fonte de verdade (arquivos .md em memory/data/).
  LongTermMemory é o índice de busca sobre esse acervo.
  migrate_from_store() sincroniza o índice a partir do MemoryStore.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from memory.types import Memory, MemoryType

if TYPE_CHECKING:
    from memory.embedder import LocalEmbedder
    from memory.store import MemoryStore

logger = logging.getLogger("data_agents.memory.long_term")

_CREATE_MAIN_TABLE = """
CREATE TABLE IF NOT EXISTS long_term_memories (
    id            TEXT PRIMARY KEY,
    type          TEXT NOT NULL,
    summary       TEXT NOT NULL,
    content       TEXT NOT NULL,
    tags          TEXT NOT NULL DEFAULT '[]',
    confidence    REAL NOT NULL DEFAULT 1.0,
    source_session TEXT NOT NULL DEFAULT '',
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL,
    active        INTEGER NOT NULL DEFAULT 1,
    superseded_by TEXT,
    embedding     BLOB
);
"""

_CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_lt_type       ON long_term_memories(type);
CREATE INDEX IF NOT EXISTS idx_lt_active     ON long_term_memories(active);
CREATE INDEX IF NOT EXISTS idx_lt_confidence ON long_term_memories(confidence);
"""

_CREATE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS long_term_fts USING fts5(
    summary,
    content,
    tags,
    content='long_term_memories',
    content_rowid='rowid'
);
"""

_CREATE_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS lt_ai AFTER INSERT ON long_term_memories BEGIN
    INSERT INTO long_term_fts(rowid, summary, content, tags)
    VALUES (new.rowid, new.summary, new.content, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS lt_ad AFTER DELETE ON long_term_memories BEGIN
    INSERT INTO long_term_fts(long_term_fts, rowid, summary, content, tags)
    VALUES ('delete', old.rowid, old.summary, old.content, old.tags);
END;
CREATE TRIGGER IF NOT EXISTS lt_au AFTER UPDATE OF summary, content, tags ON long_term_memories BEGIN
    INSERT INTO long_term_fts(long_term_fts, rowid, summary, content, tags)
    VALUES ('delete', old.rowid, old.summary, old.content, old.tags);
    INSERT INTO long_term_fts(rowid, summary, content, tags)
    VALUES (new.rowid, new.summary, new.content, new.tags);
END;
"""


class LongTermMemory:
    """
    Índice SQLite de busca sobre as memórias persistentes do MemoryStore.

    Não substitui o MemoryStore — apenas oferece busca eficiente sem
    chamar um LLM lateral. Chame migrate_from_store() para sincronizar
    o índice com o acervo de arquivos .md.

    Args:
        db_path: Path do arquivo SQLite. Criado automaticamente se não existir.
        embedder: LocalEmbedder opcional para busca vetorial.
                  Quando None, usa somente FTS5 (BM25).
    """

    def __init__(
        self,
        db_path: Path,
        embedder: LocalEmbedder | None = None,
    ) -> None:
        self._db_path = db_path
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

    # ── Serialização ──────────────────────────────────────────────────────────

    @staticmethod
    def _memory_to_row(memory: Memory) -> dict:
        return {
            "id": memory.id,
            "type": memory.type.value,
            "summary": memory.summary,
            "content": memory.content,
            "tags": json.dumps(memory.tags),
            "confidence": memory.confidence,
            "source_session": memory.source_session,
            "created_at": memory.created_at.timestamp(),
            "updated_at": memory.updated_at.timestamp(),
            "active": 1 if memory.is_active() else 0,
            "superseded_by": memory.superseded_by,
        }

    @staticmethod
    def _row_to_memory(row: sqlite3.Row) -> Memory:
        tags_raw = row["tags"] or "[]"
        try:
            tags = json.loads(tags_raw)
        except (json.JSONDecodeError, TypeError):
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

        return Memory(
            id=row["id"],
            type=MemoryType(row["type"]),
            summary=row["summary"],
            content=row["content"],
            tags=tags,
            confidence=float(row["confidence"]),
            source_session=row["source_session"] or "",
            created_at=datetime.fromtimestamp(row["created_at"], tz=timezone.utc),
            updated_at=datetime.fromtimestamp(row["updated_at"], tz=timezone.utc),
            superseded_by=row["superseded_by"],
        )

    # ── Escrita ───────────────────────────────────────────────────────────────

    def upsert(self, memory: Memory) -> None:
        """
        Insere ou atualiza uma memória no índice.

        Gera embedding se LocalEmbedder disponível.
        """
        row = self._memory_to_row(memory)

        embedding_bytes: bytes | None = None
        if self._embedder is not None:
            try:
                from memory.embedder import serialize_embedding

                text_for_embed = f"{memory.summary} {memory.content[:500]}"
                emb = self._embedder.embed(text_for_embed)
                embedding_bytes = serialize_embedding(emb)
            except Exception as e:
                logger.debug(f"Embedding falhou para {memory.id}: {e}")

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM long_term_memories WHERE id=?", (row["id"],)
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE long_term_memories
                       SET type=?, summary=?, content=?, tags=?, confidence=?,
                           source_session=?, updated_at=?, active=?, superseded_by=?,
                           embedding=COALESCE(?, embedding)
                       WHERE id=?""",
                    (
                        row["type"],
                        row["summary"],
                        row["content"],
                        row["tags"],
                        row["confidence"],
                        row["source_session"],
                        row["updated_at"],
                        row["active"],
                        row["superseded_by"],
                        embedding_bytes,
                        row["id"],
                    ),
                )
            else:
                conn.execute(
                    """INSERT INTO long_term_memories
                       (id, type, summary, content, tags, confidence, source_session,
                        created_at, updated_at, active, superseded_by, embedding)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        row["id"],
                        row["type"],
                        row["summary"],
                        row["content"],
                        row["tags"],
                        row["confidence"],
                        row["source_session"],
                        row["created_at"],
                        row["updated_at"],
                        row["active"],
                        row["superseded_by"],
                        embedding_bytes,
                    ),
                )

    def delete(self, memory_id: str) -> None:
        """Remove uma memória do índice pelo ID."""
        try:
            with self._connect() as conn:
                conn.execute("DELETE FROM long_term_memories WHERE id=?", (memory_id,))
        except sqlite3.Error as e:
            logger.warning(f"delete falhou para {memory_id}: {e}")

    # ── Migração ──────────────────────────────────────────────────────────────

    def migrate_from_store(self, store: MemoryStore) -> int:
        """
        Sincroniza o índice com o MemoryStore (arquivos .md).

        Upserta todas as memórias (ativas e inativas) para manter
        o índice completo. Idempotente — seguro de chamar repetidamente.

        Returns:
            Número de memórias indexadas.
        """
        memories = store.list_all(active_only=False)
        if not memories:
            logger.debug("migrate_from_store: nenhuma memória no store.")
            return 0

        for mem in memories:
            try:
                self.upsert(mem)
            except Exception as e:
                logger.warning(f"migrate_from_store: falha ao upsert {mem.id}: {e}")

        logger.info(f"LongTermMemory: {len(memories)} memórias indexadas do MemoryStore.")
        return len(memories)

    # ── Busca ─────────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        limit: int = 8,
        include_types: list[MemoryType] | None = None,
        min_confidence: float = 0.1,
    ) -> list[Memory]:
        """
        Busca memórias relevantes usando FTS5 (BM25).

        Se LocalEmbedder disponível, re-rankeia por cosine similarity.

        Args:
            query: Texto de busca.
            limit: Máximo de resultados.
            include_types: Filtra por tipos específicos. None = todos.
            min_confidence: Exclui memórias abaixo deste threshold.

        Returns:
            Memórias ativas ordenadas por relevância (score desc).
        """
        if not query or not query.strip():
            return []

        # Mantém apenas word chars (\w) e espaços — whitelist que cobre todos os operadores
        # FTS5 problemáticos sem precisar enumerá-los individualmente.
        import re

        query = re.sub(r"[^\w\s]", " ", query)
        query = re.sub(r"\s+", " ", query).strip()
        if not query:
            return []

        type_filter = ""
        params: list = [query, min_confidence]
        if include_types:
            placeholders = ",".join("?" * len(include_types))
            type_filter = f"AND m.type IN ({placeholders})"
            params.extend(t.value for t in include_types)
        params.append(limit * 3)

        sql = f"""
            SELECT m.id, m.type, m.summary, m.content, m.tags, m.confidence,
                   m.source_session, m.created_at, m.updated_at, m.active,
                   m.superseded_by, m.embedding, -f.rank AS bm25_score
            FROM long_term_fts f
            JOIN long_term_memories m ON m.rowid = f.rowid
            WHERE long_term_fts MATCH ?
              AND m.active = 1
              AND m.confidence >= ?
              AND m.superseded_by IS NULL
              {type_filter}
            ORDER BY f.rank
            LIMIT ?
        """

        try:
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as e:
            logger.warning(f"LongTermMemory.search FTS falhou: {e}")
            return []

        memories = [self._row_to_memory(row) for row in rows]

        # Re-rankear com cosine similarity se embedder disponível
        if self._embedder is not None and memories:
            memories = self._rerank_by_similarity(query, memories, rows)

        return memories[:limit]

    def _rerank_by_similarity(
        self,
        query: str,
        memories: list[Memory],
        rows: list[sqlite3.Row],
    ) -> list[Memory]:
        """Re-rankeia candidatos BM25 por cosine similarity."""
        try:
            from memory.embedder import deserialize_embedding, cosine_similarity

            query_emb = self._embedder.embed(query)
            scored: list[tuple[float, Memory]] = []

            for mem, row in zip(memories, rows):
                emb_blob = row["embedding"]
                if emb_blob:
                    emb = deserialize_embedding(emb_blob)
                    score = cosine_similarity(query_emb, emb)
                else:
                    score = float(row["bm25_score"] or 0.0) / 10.0  # normaliza BM25
                scored.append((score, mem))

            scored.sort(key=lambda t: t[0], reverse=True)
            return [m for _, m in scored]
        except Exception as e:
            logger.debug(f"Re-rank por embedding falhou (mantendo BM25): {e}")
            return memories

    # ── Leitura ───────────────────────────────────────────────────────────────

    def list_all(self, active_only: bool = True) -> list[Memory]:
        """Retorna todas as memórias do índice."""
        try:
            with self._connect() as conn:
                if active_only:
                    rows = conn.execute(
                        "SELECT * FROM long_term_memories WHERE active=1 AND superseded_by IS NULL"
                    ).fetchall()
                else:
                    rows = conn.execute("SELECT * FROM long_term_memories").fetchall()
            return [self._row_to_memory(row) for row in rows]
        except sqlite3.Error as e:
            logger.warning(f"list_all falhou: {e}")
            return []

    def get_stats(self) -> dict:
        """Retorna estatísticas do índice."""
        try:
            with self._connect() as conn:
                total = conn.execute("SELECT COUNT(*) FROM long_term_memories").fetchone()[0]
                active = conn.execute(
                    "SELECT COUNT(*) FROM long_term_memories WHERE active=1 AND superseded_by IS NULL"
                ).fetchone()[0]
                by_type_rows = conn.execute(
                    """SELECT type, COUNT(*) as n
                       FROM long_term_memories
                       WHERE active=1 AND superseded_by IS NULL
                       GROUP BY type"""
                ).fetchall()
            return {
                "total": total,
                "active": active,
                "by_type": {row["type"]: row["n"] for row in by_type_rows},
            }
        except sqlite3.Error:
            return {"total": 0, "active": 0, "by_type": {}}
