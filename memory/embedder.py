"""
LocalEmbedder — Embeddings semânticos locais para o sistema de memória.

Backend: fastembed (ONNX runtime, sem PyTorch, sem chamada de API).
Modelo padrão: BAAI/bge-small-en-v1.5 (~25MB, 384 dimensões).
Cache: SQLite por hash de texto — evita re-computação entre sessões.

Instalação: pip install ".[memory]"

Se fastembed não estiver instalado, LocalEmbedder levanta ImportError com
instrução de instalação. ShortTermMemory usa FTS5 como fallback automático.
"""

from __future__ import annotations

import hashlib
import logging
import math
import sqlite3
import struct
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger("data_agents.memory.embedder")

_DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
_EMBEDDING_DIM = 384


# ── Utilidades de serialização ────────────────────────────────────────────────


def serialize_embedding(embedding: list[float]) -> bytes:
    """Serializa lista de floats para bytes (float32, little-endian)."""
    return struct.pack(f"<{len(embedding)}f", *embedding)


def deserialize_embedding(data: bytes) -> list[float]:
    """Deserializa bytes para lista de floats (float32, little-endian)."""
    n = len(data) // 4
    return list(struct.unpack(f"<{n}f", data))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calcula similaridade coseno entre dois vetores. Retorna 0.0 se algum for nulo."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── LocalEmbedder ─────────────────────────────────────────────────────────────


class LocalEmbedder:
    """
    Gera embeddings semânticos usando fastembed (ONNX, sem API externa).

    Cache de embeddings em SQLite por hash SHA-256 do texto.
    Thread-safe para leituras concorrentes — escrita serializada pelo SQLite.

    Args:
        cache_db_path: Path para o SQLite de cache. Criado automaticamente.
        model_name: Modelo fastembed a usar. Padrão: BAAI/bge-small-en-v1.5.

    Raises:
        ImportError: Se fastembed não estiver instalado.
    """

    def __init__(
        self,
        cache_db_path: Path,
        model_name: str = _DEFAULT_MODEL,
    ) -> None:
        try:
            from fastembed import TextEmbedding  # type: ignore[import]
        except ImportError as e:
            raise ImportError(
                "fastembed não instalado. Para habilitar embeddings semânticos:\n"
                '  pip install ".[memory]"\n'
                "  ou: pip install fastembed>=0.3"
            ) from e

        self._model_name = model_name
        self._cache_db_path = cache_db_path
        self._model: TextEmbedding | None = None  # lazy init (download na 1ª chamada)
        self._db: sqlite3.Connection | None = None
        self._init_cache_db()

    # ── Inicialização ─────────────────────────────────────────────────────────

    def _init_cache_db(self) -> None:
        """Cria o banco de cache se não existir."""
        self._cache_db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._cache_db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS embedding_cache (
                text_hash  TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                embedding  BLOB NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ec_model ON embedding_cache(model_name)")
        conn.commit()
        conn.close()

    def _get_model(self):
        """Inicializa o modelo fastembed na primeira chamada (lazy)."""
        if self._model is None:
            from fastembed import TextEmbedding  # type: ignore[import]

            logger.info(f"Carregando modelo de embeddings: {self._model_name}")
            self._model = TextEmbedding(model_name=self._model_name)
        return self._model

    # ── API pública ───────────────────────────────────────────────────────────

    def embed(self, text: str) -> list[float]:
        """
        Gera embedding para um texto.

        Verifica cache SQLite antes de chamar o modelo.
        Salva no cache após computação.
        """
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        # Cache hit
        cached = self._load_from_cache(text_hash)
        if cached is not None:
            return cached

        # Compute
        model = self._get_model()
        embeddings = list(model.embed([text]))
        if not embeddings:
            return [0.0] * _EMBEDDING_DIM
        embedding = [float(v) for v in embeddings[0]]

        # Save to cache
        self._save_to_cache(text_hash, embedding)
        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Gera embeddings para uma lista de textos.

        Verifica cache para cada texto; computa apenas os que faltam.
        """
        if not texts:
            return []

        hashes = [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in texts]
        results: list[list[float] | None] = [None] * len(texts)
        missing_indices: list[int] = []

        # Cache hits
        for i, h in enumerate(hashes):
            cached = self._load_from_cache(h)
            if cached is not None:
                results[i] = cached
            else:
                missing_indices.append(i)

        if not missing_indices:
            return [r for r in results if r is not None]

        # Compute missing
        missing_texts = [texts[i] for i in missing_indices]
        model = self._get_model()
        computed = list(model.embed(missing_texts))

        for idx, i in enumerate(missing_indices):
            embedding = [float(v) for v in computed[idx]]
            results[i] = embedding
            self._save_to_cache(hashes[i], embedding)

        return [r if r is not None else [0.0] * _EMBEDDING_DIM for r in results]

    @property
    def dimension(self) -> int:
        """Dimensão dos vetores gerados por este modelo."""
        return _EMBEDDING_DIM

    # ── Cache interno ─────────────────────────────────────────────────────────

    def _load_from_cache(self, text_hash: str) -> list[float] | None:
        try:
            conn = sqlite3.connect(str(self._cache_db_path))
            row = conn.execute(
                "SELECT embedding FROM embedding_cache WHERE text_hash=? AND model_name=?",
                (text_hash, self._model_name),
            ).fetchone()
            conn.close()
            if row:
                return deserialize_embedding(row[0])
        except sqlite3.Error:
            pass
        return None

    def _save_to_cache(self, text_hash: str, embedding: list[float]) -> None:
        import time

        try:
            conn = sqlite3.connect(str(self._cache_db_path))
            conn.execute(
                """INSERT OR REPLACE INTO embedding_cache
                   (text_hash, model_name, embedding, created_at)
                   VALUES (?, ?, ?, ?)""",
                (text_hash, self._model_name, serialize_embedding(embedding), time.time()),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.debug(f"Falha ao salvar embedding no cache: {e}")
