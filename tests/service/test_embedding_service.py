"""Tests for src/services/embedding_service.py."""

import pytest
from unittest.mock import patch

from src.models import Storylet
from src.services.embedding_service import (
    build_composite_text,
    cosine_similarity,
    embed_all_storylets,
    embed_storylet,
    embed_text,
    EMBEDDING_DIMENSIONS,
    reembed_storylets,
)
from src.services.world_memory import record_event, reembed_world_events


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


class TestReembedMaintenance:

    def test_reembed_storylets_survives_single_row_failure(self, db_session):
        s1 = Storylet(title="R1", text_template="Alpha", requires={}, choices=[], weight=1.0)
        s2 = Storylet(title="R2", text_template="Beta", requires={}, choices=[], weight=1.0)
        s3 = Storylet(title="R3", text_template="Gamma", requires={}, choices=[], weight=1.0)
        db_session.add_all([s1, s2, s3])
        db_session.commit()

        def _fake_embed(storylet):
            if storylet.title == "R2":
                raise RuntimeError("embed failure")
            return [0.1] * EMBEDDING_DIMENSIONS

        with patch("src.services.embedding_service.embed_storylet", side_effect=_fake_embed):
            stats = reembed_storylets(db_session, batch_size=2)

        assert stats == {"scanned": 3, "updated": 2, "failed": 1}
        refreshed = {s.title: s for s in db_session.query(Storylet).all()}
        assert refreshed["R1"].embedding is not None
        assert refreshed["R2"].embedding is None
        assert refreshed["R3"].embedding is not None

    def test_reembed_world_events_survives_single_row_failure(self, db_session):
        e1 = record_event(db_session, "reemb-ev", None, "system", "alpha event")
        e2 = record_event(db_session, "reemb-ev", None, "system", "beta event")
        assert e1.id is not None and e2.id is not None

        def _fake_embed(text: str):
            if "beta event" in text:
                raise RuntimeError("event embed failure")
            return [0.2] * EMBEDDING_DIMENSIONS

        with patch("src.services.embedding_service.embed_text", side_effect=_fake_embed):
            stats = reembed_world_events(db_session, batch_size=1)

        assert stats == {"scanned": 2, "updated": 1, "failed": 1}

    def test_dry_run_reports_counts_without_mutation(self, db_session):
        storylet = Storylet(
            title="DryRun Storylet",
            text_template="Stable text",
            requires={},
            choices=[],
            weight=1.0,
            embedding=[1.0] * EMBEDDING_DIMENSIONS,
        )
        db_session.add(storylet)
        db_session.commit()
        event = record_event(db_session, "dry-run-session", None, "system", "dry run event")
        event.embedding = [3.0] * EMBEDDING_DIMENSIONS
        db_session.add(event)
        db_session.commit()

        storylet_stats = reembed_storylets(db_session, dry_run=True)
        event_stats = reembed_world_events(db_session, dry_run=True)

        assert storylet_stats == {"scanned": 1, "updated": 0, "failed": 0}
        assert event_stats["scanned"] >= 1
        assert event_stats["updated"] == 0
        assert event_stats["failed"] == 0

        refreshed_storylet = db_session.get(Storylet, storylet.id)
        refreshed_event = db_session.get(type(event), event.id)
        assert refreshed_storylet is not None
        assert refreshed_storylet.embedding == [1.0] * EMBEDDING_DIMENSIONS
        assert refreshed_event is not None
        assert refreshed_event.embedding == [3.0] * EMBEDDING_DIMENSIONS

    def test_reembed_can_run_repeatedly_without_corruption(self, db_session):
        storylet = Storylet(
            title="Repeat Storylet",
            text_template="Repeat text",
            requires={},
            choices=[],
            weight=1.0,
        )
        db_session.add(storylet)
        db_session.commit()
        event = record_event(db_session, "repeat-session", None, "system", "repeat event")

        first_storylet_stats = reembed_storylets(db_session, batch_size=1)
        second_storylet_stats = reembed_storylets(db_session, batch_size=1)
        first_event_stats = reembed_world_events(db_session, batch_size=1)
        second_event_stats = reembed_world_events(db_session, batch_size=1)

        assert first_storylet_stats["failed"] == 0
        assert second_storylet_stats["failed"] == 0
        assert first_event_stats["failed"] == 0
        assert second_event_stats["failed"] == 0

        refreshed_storylet = db_session.get(Storylet, storylet.id)
        refreshed_event = db_session.get(type(event), event.id)
        assert refreshed_storylet is not None and refreshed_storylet.embedding is not None
        assert refreshed_event is not None and refreshed_event.embedding is not None
        assert len(refreshed_storylet.embedding) == EMBEDDING_DIMENSIONS
        assert len(refreshed_event.embedding) == EMBEDDING_DIMENSIONS
