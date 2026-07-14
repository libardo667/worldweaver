"""Tests for src/services/embedding_service.py."""

import pytest

from src.services.embedding_service import EMBEDDING_DIMENSIONS, cosine_similarity, embed_text


class TestCosineSimlarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector(self):
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        assert cosine_similarity(a, b) == 0.0

    def test_length_mismatch(self):
        with pytest.raises(ValueError, match="length mismatch"):
            cosine_similarity([1.0, 2.0], [1.0])

    def test_similar_vectors(self):
        a = [1.0, 1.0, 0.0]
        b = [1.0, 1.0, 0.1]
        assert cosine_similarity(a, b) > 0.95


class TestEmbedText:
    def test_returns_fallback_vector(self):
        """Under PYTEST_CURRENT_TEST, embed_text returns the fallback zero vector."""
        result = embed_text("hello world")
        assert isinstance(result, list)
        assert len(result) == EMBEDDING_DIMENSIONS
        assert all(v == 0.0 for v in result)

    def test_returns_new_list_each_call(self):
        a = embed_text("a")
        b = embed_text("b")
        assert a is not b
