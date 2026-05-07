"""
Tests for memory.embedder — serialize/deserialize, cosine_similarity, LocalEmbedder.

LocalEmbedder tests are skipped when fastembed is not installed
(matches the optional [memory] extra in pyproject.toml).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from memory.embedder import (
    serialize_embedding,
    deserialize_embedding,
    cosine_similarity,
)


# ── serialize / deserialize ───────────────────────────────────────────────────


class TestSerializeDeserialize:
    def test_round_trip(self) -> None:
        vec = [0.1, 0.2, 0.3, 0.4, 0.5]
        data = serialize_embedding(vec)
        recovered = deserialize_embedding(data)
        assert len(recovered) == len(vec)
        for a, b in zip(vec, recovered):
            assert abs(a - b) < 1e-6

    def test_returns_bytes(self) -> None:
        data = serialize_embedding([1.0, 2.0])
        assert isinstance(data, bytes)

    def test_size_is_4_bytes_per_float(self) -> None:
        vec = [0.0] * 10
        data = serialize_embedding(vec)
        assert len(data) == 10 * 4  # float32 = 4 bytes

    def test_empty_vector(self) -> None:
        data = serialize_embedding([])
        assert data == b""
        assert deserialize_embedding(b"") == []

    def test_single_element(self) -> None:
        data = serialize_embedding([3.14])
        recovered = deserialize_embedding(data)
        assert len(recovered) == 1
        assert abs(recovered[0] - 3.14) < 1e-5

    def test_large_vector(self) -> None:
        vec = [float(i) / 1000.0 for i in range(384)]  # bge-small-en size
        data = serialize_embedding(vec)
        recovered = deserialize_embedding(data)
        assert len(recovered) == 384
        assert abs(recovered[0] - vec[0]) < 1e-6


# ── cosine_similarity ─────────────────────────────────────────────────────────


class TestCosineSimilarity:
    def test_identical_vectors_return_one(self) -> None:
        vec = [1.0, 0.0, 0.0]
        assert abs(cosine_similarity(vec, vec) - 1.0) < 1e-6

    def test_orthogonal_vectors_return_zero(self) -> None:
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert abs(cosine_similarity(a, b)) < 1e-6

    def test_opposite_vectors_return_minus_one(self) -> None:
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert abs(cosine_similarity(a, b) - (-1.0)) < 1e-6

    def test_zero_vector_returns_zero(self) -> None:
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        assert cosine_similarity(a, b) == 0.0

    def test_symmetry(self) -> None:
        a = [1.0, 2.0, 3.0]
        b = [4.0, 5.0, 6.0]
        assert abs(cosine_similarity(a, b) - cosine_similarity(b, a)) < 1e-9

    def test_normalized_result_in_range(self) -> None:
        a = [0.1, 0.5, 0.9, 0.3]
        b = [0.9, 0.1, 0.4, 0.7]
        sim = cosine_similarity(a, b)
        assert -1.0 <= sim <= 1.0


# ── LocalEmbedder ─────────────────────────────────────────────────────────────

fastembed = pytest.importorskip("fastembed", reason="fastembed not installed — skip embedder tests")


class TestLocalEmbedder:
    @pytest.fixture
    def embedder(self, tmp_path: Path):
        from memory.embedder import LocalEmbedder

        return LocalEmbedder(
            cache_db_path=tmp_path / "embed_cache.db",
            model_name="BAAI/bge-small-en-v1.5",
        )

    def test_embed_returns_list(self, embedder) -> None:
        result = embedder.embed("hello world")
        assert isinstance(result, list)
        assert all(isinstance(x, float) for x in result)

    def test_embed_dimension(self, embedder) -> None:
        result = embedder.embed("test sentence")
        assert len(result) == embedder.dimension

    def test_dimension_property(self, embedder) -> None:
        assert embedder.dimension == 384

    def test_embed_cache_hit(self, embedder) -> None:
        text = "repeated query to test cache"
        first = embedder.embed(text)
        second = embedder.embed(text)
        assert first == second

    def test_embed_batch_returns_list_of_lists(self, embedder) -> None:
        texts = ["sentence one", "sentence two", "sentence three"]
        results = embedder.embed_batch(texts)
        assert len(results) == 3
        assert all(len(r) == embedder.dimension for r in results)

    def test_similar_texts_higher_score(self, embedder) -> None:
        base = embedder.embed("data pipeline in databricks")
        similar = embedder.embed("ETL pipeline on databricks platform")
        unrelated = embedder.embed("weather forecast sunny day")
        sim_high = cosine_similarity(base, similar)
        sim_low = cosine_similarity(base, unrelated)
        assert sim_high > sim_low
