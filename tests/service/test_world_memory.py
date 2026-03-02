"""Tests for src/services/world_memory.py."""

from src.models import WorldEvent
from src.services.world_memory import (
    get_world_context_vector,
    get_world_history,
    query_world_facts,
    record_event,
)
from src.services.embedding_service import EMBEDDING_DIMENSIONS


class TestRecordEvent:

    def test_creates_event(self, db_session):
        event = record_event(
            db_session, "sess-1", 42, "storylet_fired", "Something happened"
        )
        assert isinstance(event, WorldEvent)
        assert event.id is not None
        assert event.session_id == "sess-1"
        assert event.storylet_id == 42
        assert event.event_type == "storylet_fired"
        assert event.summary == "Something happened"

    def test_stores_embedding(self, db_session):
        event = record_event(
            db_session, "s1", None, "test", "A test event"
        )
        assert event.embedding is not None
        assert len(event.embedding) == EMBEDDING_DIMENSIONS

    def test_stores_delta(self, db_session):
        delta = {"bridge_status": "burned"}
        event = record_event(
            db_session, "s1", 1, "choice_made", "Burned the bridge", delta
        )
        assert event.world_state_delta == delta

    def test_nullable_session_and_storylet(self, db_session):
        event = record_event(
            db_session, None, None, "system", "World initialized"
        )
        assert event.session_id is None
        assert event.storylet_id is None


class TestGetWorldHistory:

    def test_returns_reverse_order(self, db_session):
        record_event(db_session, "s", 1, "t", "First")
        record_event(db_session, "s", 2, "t", "Second")
        record_event(db_session, "s", 3, "t", "Third")

        history = get_world_history(db_session)
        summaries = [e.summary for e in history]
        assert summaries == ["Third", "Second", "First"]

    def test_filters_by_session(self, db_session):
        record_event(db_session, "alice", 1, "t", "Alice event")
        record_event(db_session, "bob", 2, "t", "Bob event")

        alice_history = get_world_history(db_session, session_id="alice")
        assert len(alice_history) == 1
        assert alice_history[0].summary == "Alice event"

    def test_respects_limit(self, db_session):
        for i in range(10):
            record_event(db_session, "s", i, "t", f"Event {i}")

        history = get_world_history(db_session, limit=3)
        assert len(history) == 3

    def test_empty_db(self, db_session):
        history = get_world_history(db_session)
        assert history == []


class TestGetWorldContextVector:

    def test_returns_none_when_empty(self, db_session):
        result = get_world_context_vector(db_session)
        assert result is None

    def test_returns_vector_with_events(self, db_session):
        record_event(db_session, "s", 1, "t", "Event one")
        record_event(db_session, "s", 2, "t", "Event two")

        result = get_world_context_vector(db_session)
        # Under test env, all embeddings are zero vectors, so avg is also zero
        assert result is not None
        assert len(result) == EMBEDDING_DIMENSIONS


class TestQueryWorldFacts:

    def test_returns_events(self, db_session):
        record_event(db_session, "s", 1, "t", "The bridge was burned")
        record_event(db_session, "s", 2, "t", "The key was found")

        results = query_world_facts(db_session, "bridge")
        assert len(results) == 2  # all events returned (fallback vectors)

    def test_respects_limit(self, db_session):
        for i in range(5):
            record_event(db_session, "s", i, "t", f"Event {i}")

        results = query_world_facts(db_session, "test", limit=2)
        assert len(results) == 2

    def test_empty_db(self, db_session):
        results = query_world_facts(db_session, "anything")
        assert results == []
