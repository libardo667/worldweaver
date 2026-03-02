"""Tests for src/services/world_memory.py."""

from src.models import WorldEvent, WorldFact, WorldNode
from src.services.state_manager import AdvancedStateManager
from src.services.world_memory import (
    apply_event_delta_to_state,
    get_location_facts,
    get_node_neighborhood,
    get_recent_graph_fact_summaries,
    get_world_context_vector,
    get_world_history,
    infer_event_type,
    query_graph_facts,
    query_world_facts,
    record_event,
    should_trigger_storylet,
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

    def test_applies_delta_to_state_manager(self, db_session):
        sm = AdvancedStateManager("sess-delta")
        event = record_event(
            db_session,
            "sess-delta",
            7,
            "freeform_action",
            "The bridge collapses in flames",
            delta={
                "bridge_broken": True,
                "environment": {"weather": "stormy"},
                "spatial_nodes": {"bridge": {"status": "destroyed"}},
            },
            state_manager=sm,
        )
        assert event.event_type == "permanent_change"
        assert sm.get_variable("bridge_broken") is True
        assert sm.environment.weather == "stormy"
        spatial_nodes = sm.get_variable("spatial_nodes", {})
        assert spatial_nodes.get("bridge", {}).get("status") == "destroyed"

    def test_creates_graph_nodes_and_facts_from_delta(self, db_session):
        record_event(
            db_session,
            "graph-1",
            3,
            "freeform_action",
            "The bridge is destroyed.",
            delta={"bridge_broken": True},
        )
        nodes = db_session.query(WorldNode).all()
        facts = db_session.query(WorldFact).all()
        assert len(nodes) >= 1
        assert len(facts) >= 1
        assert any(f.predicate == "broken" for f in facts)

    def test_repeated_events_merge_node_identity(self, db_session):
        record_event(
            db_session,
            "graph-2",
            None,
            "freeform_action",
            "The bridge burns.",
            delta={"bridge_broken": True},
        )
        record_event(
            db_session,
            "graph-2",
            None,
            "freeform_action",
            "The bridge remains broken.",
            delta={"bridge_broken": True},
        )
        bridge_nodes = (
            db_session.query(WorldNode)
            .filter(WorldNode.normalized_name == "bridge")
            .all()
        )
        assert len(bridge_nodes) == 1

    def test_summary_only_event_extracts_entity_and_location_fact(self, db_session):
        record_event(
            db_session,
            "graph-summary-1",
            None,
            "freeform_action",
            "The bridge was destroyed in the old town.",
            delta={},
        )

        bridge_node = (
            db_session.query(WorldNode)
            .filter(
                WorldNode.node_type == "entity",
                WorldNode.normalized_name == "bridge",
            )
            .one_or_none()
        )
        assert bridge_node is not None

        facts = (
            db_session.query(WorldFact)
            .filter(
                WorldFact.session_id == "graph-summary-1",
                WorldFact.subject_node_id == bridge_node.id,
                WorldFact.is_active.is_(True),
            )
            .all()
        )
        assert any(f.predicate == "status" and f.value == "destroyed" for f in facts)

        location_facts = get_location_facts(
            db_session,
            "old town",
            session_id="graph-summary-1",
        )
        assert any(f.subject_node_id == bridge_node.id for f in location_facts)

    def test_player_action_summary_merges_identity_and_updates_fact(self, db_session):
        record_event(
            db_session,
            "graph-summary-2",
            None,
            "freeform_action",
            "Player action: I destroy the bridge supports. Result: The wood splinters.",
            delta={},
        )
        record_event(
            db_session,
            "graph-summary-2",
            None,
            "freeform_action",
            "Player action: I damaged the bridge supports. Result: Cracks spread.",
            delta={},
        )

        support_nodes = (
            db_session.query(WorldNode)
            .filter(
                WorldNode.node_type == "entity",
                WorldNode.normalized_name == "bridge supports",
            )
            .all()
        )
        assert len(support_nodes) == 1

        active_status_facts = (
            db_session.query(WorldFact)
            .filter(
                WorldFact.session_id == "graph-summary-2",
                WorldFact.subject_node_id == support_nodes[0].id,
                WorldFact.predicate == "status",
                WorldFact.is_active.is_(True),
            )
            .all()
        )
        assert len(active_status_facts) == 1
        assert active_status_facts[0].value == "damaged"


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

    def test_permanent_change_is_weighted_more_heavily(self, db_session):
        # Use tiny custom vectors so weighted averaging is easy to verify.
        event_regular = WorldEvent(
            session_id="s",
            storylet_id=1,
            event_type="storylet_fired",
            summary="regular",
            embedding=[1.0, 0.0],
            world_state_delta={},
        )
        event_permanent = WorldEvent(
            session_id="s",
            storylet_id=2,
            event_type="permanent_change",
            summary="permanent",
            embedding=[0.0, 1.0],
            world_state_delta={"bridge_broken": True},
        )
        db_session.add(event_regular)
        db_session.add(event_permanent)
        db_session.commit()

        result = get_world_context_vector(db_session, session_id="s", limit=5)
        assert result is not None
        # Weighted average with permanent weight 3.0:
        # x = (1*1 + 0*3) / 4 = 0.25, y = (0*1 + 1*3) / 4 = 0.75
        assert result[1] > result[0]


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


class TestGraphQueries:

    def test_query_graph_facts_returns_matches(self, db_session):
        record_event(
            db_session,
            "graph-q1",
            None,
            "freeform_action",
            "The bridge is broken.",
            delta={"bridge_broken": True},
        )
        results = query_graph_facts(db_session, "bridge", session_id="graph-q1", limit=5)
        assert len(results) >= 1
        assert isinstance(results[0], WorldFact)

    def test_location_facts_include_spatial_node_deltas(self, db_session):
        record_event(
            db_session,
            "graph-loc",
            None,
            "freeform_action",
            "The old bridge is now blocked.",
            delta={"spatial_nodes": {"old bridge": {"status": "blocked"}}},
        )
        facts = get_location_facts(db_session, "old bridge", session_id="graph-loc")
        assert len(facts) >= 1
        assert any(f.predicate == "status" for f in facts)

    def test_node_neighborhood_returns_edges_and_facts(self, db_session):
        record_event(
            db_session,
            "graph-nb",
            None,
            "freeform_action",
            "The bridge is damaged.",
            delta={"spatial_nodes": {"bridge": {"status": "damaged"}}},
        )
        neighborhood = get_node_neighborhood(db_session, "bridge", limit=10)
        assert neighborhood["node"] is not None
        assert isinstance(neighborhood["facts"], list)
        assert isinstance(neighborhood["edges"], list)

    def test_recent_graph_fact_summaries(self, db_session):
        record_event(
            db_session,
            "graph-sum",
            None,
            "freeform_action",
            "A merchant gains influence in town.",
            delta={"merchant_influence": 5},
        )
        summaries = get_recent_graph_fact_summaries(
            db_session,
            session_id="graph-sum",
            limit=3,
        )
        assert len(summaries) >= 1
        assert isinstance(summaries[0], str)


class TestDeltaHooks:

    def test_infer_event_type_promotes_permanent_change(self):
        assert infer_event_type("freeform_action", {"bridge_broken": True}) == "permanent_change"
        assert infer_event_type("freeform_action", {"gold": 1}) == "freeform_action"

    def test_should_trigger_storylet_for_high_impact(self):
        assert should_trigger_storylet("freeform_action", {"bridge_broken": True}) is True
        assert should_trigger_storylet("freeform_action", {"gold": 1}) is False

    def test_apply_event_delta_to_state_fallback(self):
        sm = AdvancedStateManager("s-fallback")
        applied = apply_event_delta_to_state(sm, {"variables": {"quest_stage": 2}})
        assert applied["variables"]["quest_stage"] == 2
        assert sm.get_variable("quest_stage") == 2
