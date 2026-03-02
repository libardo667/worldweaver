"""Tests for src/services/embedding_service.py."""

import pytest

from src.models import Storylet
from src.services.embedding_service import (
    build_composite_text,
    cosine_similarity,
    embed_all_storylets,
    embed_storylet,
    embed_text,
    EMBEDDING_DIMENSIONS,
)


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


class TestBuildCompositeText:

    def test_includes_title_and_template(self):
        s = Storylet(title="Forest Path", text_template="A dark forest.", requires={}, choices=[], weight=1.0)
        text = build_composite_text(s)
        assert "Forest Path" in text
        assert "A dark forest." in text

    def test_includes_choice_labels(self):
        s = Storylet(
            title="T", text_template="T",
            requires={}, weight=1.0,
            choices=[{"label": "Go north", "set": {}}, {"label": "Go south", "set": {}}],
        )
        text = build_composite_text(s)
        assert "Go north" in text
        assert "Go south" in text

    def test_includes_requires_keys(self):
        s = Storylet(
            title="T", text_template="T", weight=1.0,
            choices=[],
            requires={"location": "cave", "has_torch": True},
        )
        text = build_composite_text(s)
        assert "location=cave" in text
        assert "has_torch=True" in text

    def test_handles_empty_fields(self):
        s = Storylet(title="", text_template="", requires={}, choices=[], weight=1.0)
        text = build_composite_text(s)
        assert isinstance(text, str)


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


class TestEmbedStorylet:

    def test_returns_vector(self):
        s = Storylet(title="Test", text_template="Text.", requires={}, choices=[], weight=1.0)
        result = embed_storylet(s)
        assert isinstance(result, list)
        assert len(result) == EMBEDDING_DIMENSIONS


class TestEmbedAllStorylets:

    def test_fills_null_embeddings(self, db_session):
        s1 = Storylet(title="A", text_template="A.", requires={}, choices=[], weight=1.0)
        s2 = Storylet(title="B", text_template="B.", requires={}, choices=[], weight=1.0)
        db_session.add_all([s1, s2])
        db_session.commit()

        count = embed_all_storylets(db_session)
        assert count == 2

        refreshed = db_session.query(Storylet).all()
        for s in refreshed:
            assert s.embedding is not None
            assert len(s.embedding) == EMBEDDING_DIMENSIONS

    def test_skips_existing_embeddings(self, db_session):
        existing_vec = [1.0] * EMBEDDING_DIMENSIONS
        s = Storylet(
            title="Pre-embedded", text_template="T.",
            requires={}, choices=[], weight=1.0,
            embedding=existing_vec,
        )
        db_session.add(s)
        db_session.commit()

        count = embed_all_storylets(db_session)
        assert count == 0

        refreshed = db_session.query(Storylet).first()
        assert refreshed.embedding == existing_vec

    def test_returns_zero_when_none_needed(self, db_session):
        count = embed_all_storylets(db_session)
        assert count == 0
