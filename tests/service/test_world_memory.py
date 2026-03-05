"""Tests for src/services/world_memory.py."""

import logging
from datetime import datetime, timedelta, timezone

from src.models import WorldEvent, WorldFact, WorldNode, WorldProjection
from src.services.state_manager import AdvancedStateManager
from src.services.world_memory import (
    EVENT_TYPE_FREEFORM_ACTION,
    EVENT_TYPE_STORYLET_FIRED,
    EVENT_TYPE_SYSTEM,
    apply_event_to_projection,
    apply_event_delta_to_state,
    apply_projection_overlay_to_state_manager,
    get_relevant_action_facts,
    get_location_facts,
    get_node_neighborhood,
    get_recent_graph_fact_summaries,
    get_world_projection,
    get_world_context_vector,
    get_world_history,
    infer_event_type,
    query_graph_facts,
    query_world_facts,
    record_event,
    rebuild_world_projection,
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

    def test_normalizes_unknown_event_type_with_safe_fallback(self, db_session, caplog):
        with caplog.at_level(logging.WARNING):
            event = record_event(
                db_session,
                "normalize-unknown",
                None,
                "custom_nonstandard_event",
                "Unknown event type should normalize safely.",
                delta={"gold": 1},
            )
        assert event.event_type == EVENT_TYPE_SYSTEM
        assert any("Unknown world event type" in record.message for record in caplog.records)

    def test_normalizes_inbound_delta_keys(self, db_session):
        event = record_event(
            db_session,
            "normalize-delta",
            None,
            EVENT_TYPE_FREEFORM_ACTION,
            "Normalize mixed key styles.",
            delta={
                "Vars": {"Quest Stage": 2},
                "Env": {"Danger-Level": 4},
                "Spatial Nodes": {"North Gate": {"Gate Status": "closed"}},
                "Bridge Status": "burned",
            },
        )
        payload = event.world_state_delta or {}
        assert payload["variables"]["quest_stage"] == 2
        assert payload["environment"]["danger_level"] == 4
        assert payload["spatial_nodes"]["north gate"]["gate_status"] == "closed"
        assert payload["bridge_status"] == "burned"

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

    def test_record_event_persists_action_metadata_without_state_mutation(self, db_session):
        sm = AdvancedStateManager("meta-session")
        event = record_event(
            db_session,
            "meta-session",
            None,
            "freeform_action",
            "Player action: I examine the rubble.",
            delta={"bridge_broken": True},
            state_manager=sm,
            metadata={"rationale": "Grounded in existing bridge facts", "confidence": 0.8},
        )
        assert sm.get_variable("bridge_broken") is True
        persisted_delta = event.world_state_delta or {}
        assert "__action_meta__" in persisted_delta
        assert sm.get_variable("__action_meta__") is None

    def test_canonical_identity_merges_entity_names(self, db_session):
        record_event(
            db_session,
            "canonical-id",
            None,
            "freeform_action",
            "The blacksmith is working.",
            delta={"spatial_nodes": {"The Blacksmith": {"status": "working"}}},
        )
        record_event(
            db_session,
            "canonical-id",
            None,
            "freeform_action",
            "A blacksmith drops his hammer.",
            delta={"spatial_nodes": {"a Blacksmith": {"status": "clumsy"}}},
        )
        
        nodes = (
            db_session.query(WorldNode)
            .filter(WorldNode.normalized_name == "blacksmith")
            .all()
        )
        assert len(nodes) == 1
        
        facts = (
            db_session.query(WorldFact)
            .filter(WorldFact.subject_node_id == nodes[0].id)
            .all()
        )
        assert len(facts) >= 2

    def test_canonical_identity_merges_rank_prefixed_aliases(self, db_session):
        record_event(
            db_session,
            "canonical-rank-id",
            None,
            "freeform_action",
            "Silas Vane is blocked.",
            delta={"spatial_nodes": {"Silas Vane": {"status": "blocked"}}},
        )
        record_event(
            db_session,
            "canonical-rank-id",
            None,
            "freeform_action",
            "Warden Silas Vane is blocked.",
            delta={"spatial_nodes": {"Warden Silas Vane": {"status": "blocked"}}},
        )

        nodes = (
            db_session.query(WorldNode)
            .filter(WorldNode.normalized_name == "silas vane")
            .all()
        )
        assert len(nodes) == 1

        canonical = get_node_neighborhood(db_session, "silas vane", limit=10)
        alias = get_node_neighborhood(db_session, "warden silas vane", limit=10)
        assert canonical["node"] is not None
        assert alias["node"] is not None
        assert canonical["node"].id == alias["node"].id

    def test_fact_string_values_auto_extract_edges(self, db_session):
        record_event(
            db_session,
            "auto-edge-id",
            None,
            "system",
            "Create companion.",
            delta={"spatial_nodes": {"The Companion": {"status": "alive"}}}
        )
        
        record_event(
            db_session,
            "auto-edge-id",
            None,
            "freeform_action",
            "Player forms a bond with the companion.",
            delta={
                "variables": {
                    "player": "happy",
                    "player.friendship": "a Companion"
                }
            }
        )
        
        # Verify WorldEdge was auto-extracted between 'player' and 'companion'
        from src.services.world_memory import get_relationships
        edges = get_relationships(
            db_session,
            subject_name="player",
            target_name="companion",
            edge_type="friendship"
        )
        assert len(edges) == 1
        assert edges[0].confidence == 0.8  # default confidence



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

    def test_get_relevant_action_facts_returns_grounding_snippets(self, db_session):
        record_event(
            db_session,
            "graph-grounding",
            None,
            "freeform_action",
            "The north gate is blocked.",
            delta={"spatial_nodes": {"north gate": {"status": "blocked"}}},
        )
        snippets = get_relevant_action_facts(
            db=db_session,
            action="inspect gate",
            session_id="graph-grounding",
            location="north gate",
            limit=6,
        )
        assert snippets
        assert any("north gate" in snippet.lower() for snippet in snippets)


class TestDeltaHooks:

    def test_infer_event_type_normalizes_existing_producer_values(self):
        assert infer_event_type("Storylet Fired", {"gold": 1}) == EVENT_TYPE_STORYLET_FIRED
        assert infer_event_type("FREEFORM_ACTION", {"gold": 1}) == EVENT_TYPE_FREEFORM_ACTION

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


class TestWorldProjection:

    def test_record_event_updates_projection_rows(self, db_session):
        record_event(
            db_session,
            "proj-1",
            None,
            "freeform_action",
            "A storm rolls in and the bridge closes.",
            delta={
                "environment": {"weather": "stormy"},
                "spatial_nodes": {"old bridge": {"status": "blocked"}},
                "bridge_broken": True,
            },
        )
        rows = get_world_projection(db_session)
        by_path = {row.path: row for row in rows}
        assert by_path["environment.weather"].value == "stormy"
        assert by_path["locations.old_bridge.status"].value == "blocked"
        assert by_path["variables.bridge_broken"].value is True

    def test_storylet_event_delta_updates_projection(self, db_session):
        record_event(
            db_session,
            "proj-storylet",
            11,
            "storylet_fired",
            "A storm storylet changes the bridge state.",
            delta={"spatial_nodes": {"bridge": {"status": "damaged"}}},
        )
        rows = get_world_projection(db_session, prefix="locations.bridge")
        assert len(rows) == 1
        assert rows[0].value == "damaged"

    def test_projection_supports_tombstones(self, db_session):
        record_event(
            db_session,
            "proj-2",
            None,
            "freeform_action",
            "The warning is cleared.",
            delta={"variables": {"warning": "high"}},
        )
        record_event(
            db_session,
            "proj-2",
            None,
            "freeform_action",
            "The warning is removed.",
            delta={"variables": {"warning": {"_delete": True}}},
        )
        active_rows = get_world_projection(db_session)
        assert "variables.warning" not in {row.path for row in active_rows}
        all_rows = get_world_projection(db_session, include_deleted=True)
        deleted = [row for row in all_rows if row.path == "variables.warning"]
        assert deleted and deleted[0].is_deleted is True

    def test_rebuild_projection_is_deterministic(self, db_session):
        record_event(
            db_session,
            "proj-3",
            None,
            "freeform_action",
            "Bridge damaged.",
            delta={"spatial_nodes": {"bridge": {"status": "damaged"}}},
        )
        record_event(
            db_session,
            "proj-3",
            None,
            "freeform_action",
            "Bridge repaired.",
            delta={"spatial_nodes": {"bridge": {"status": "repaired"}}},
        )

        first_snapshot = {
            row.path: row.value for row in get_world_projection(db_session)
        }
        stats = rebuild_world_projection(db_session, clear_existing=True)
        second_snapshot = {
            row.path: row.value for row in get_world_projection(db_session)
        }

        assert stats["events_processed"] == 2
        assert first_snapshot == second_snapshot
        assert second_snapshot["locations.bridge.status"] == "repaired"


    def test_rebuild_projection_scoped_to_session(self, db_session):
        record_event(
            db_session,
            "proj-scope-a",
            None,
            "freeform_action",
            "Session A sets warning.",
            delta={"variables": {"warning": "amber"}},
        )
        record_event(
            db_session,
            "proj-scope-b",
            None,
            "freeform_action",
            "Session B sets warning.",
            delta={"variables": {"warning": "crimson"}},
        )

        rebuild_world_projection(db_session, clear_existing=True)
        row_before = (
            db_session.query(WorldProjection)
            .filter(WorldProjection.path == "variables.warning")
            .one()
        )
        assert row_before.value == "crimson"

        event_a = (
            db_session.query(WorldEvent)
            .filter(WorldEvent.session_id == "proj-scope-a")
            .one()
        )
        db_session.query(WorldProjection).filter(
            WorldProjection.source_event_id == event_a.id
        ).delete(synchronize_session=False)
        db_session.commit()

        stats = rebuild_world_projection(
            db_session,
            clear_existing=True,
            session_id="proj-scope-a",
        )
        row_after = (
            db_session.query(WorldProjection)
            .filter(WorldProjection.path == "variables.warning")
            .one()
        )

        assert stats["events_processed"] == 1
        assert row_after.value == "amber"

    def test_projection_conflict_resolution_uses_timestamp_then_confidence(self, db_session):
        t = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        newer = WorldEvent(
            session_id="proj-conflict",
            storylet_id=None,
            event_type="freeform_action",
            summary="newer world alert",
            embedding=None,
            world_state_delta={"variables": {"world_alert": 5}},
            created_at=t + timedelta(minutes=1),
        )
        older = WorldEvent(
            session_id="proj-conflict",
            storylet_id=None,
            event_type="freeform_action",
            summary="older world alert",
            embedding=None,
            world_state_delta={"variables": {"world_alert": 1}},
            created_at=t,
        )
        db_session.add_all([older, newer])
        db_session.commit()

        # Apply out of order; newer value should remain.
        apply_event_to_projection(db_session, newer)
        apply_event_to_projection(db_session, older)
        db_session.commit()

        row = (
            db_session.query(WorldProjection)
            .filter(WorldProjection.path == "variables.world_alert")
            .one()
        )
        assert row.value == 5

        same_time_low_conf = WorldEvent(
            session_id="proj-conflict",
            storylet_id=None,
            event_type="freeform_action",
            summary="same time low confidence",
            embedding=None,
            world_state_delta={"variables": {"world_alert": {"value": 9, "confidence": 0.1}}},
            created_at=t + timedelta(minutes=1),
        )
        db_session.add(same_time_low_conf)
        db_session.commit()
        apply_event_to_projection(db_session, same_time_low_conf)
        db_session.commit()

        row_after = (
            db_session.query(WorldProjection)
            .filter(WorldProjection.path == "variables.world_alert")
            .one()
        )
        assert row_after.value == 5

    def test_overlay_applies_projection_to_new_state_manager(self, db_session):
        record_event(
            db_session,
            "proj-4",
            None,
            "freeform_action",
            "Weather turns rainy and gate closes.",
            delta={
                "environment": {"weather": "rainy"},
                "spatial_nodes": {"north gate": {"status": "closed"}},
                "variables": {"world_alarm": 2},
            },
        )

        sm = AdvancedStateManager("fresh-session")
        applied = apply_projection_overlay_to_state_manager(db_session, sm)

        assert applied["environment"] >= 1
        assert sm.environment.weather == "rainy"
        assert sm.get_variable("world_alarm") == 2
        spatial = sm.get_variable("spatial_nodes", {})
        assert spatial.get("north_gate", {}).get("status") == "closed"
        assert db_session.query(WorldProjection).count() >= 3

    def test_overlay_preserves_player_scoped_values(self, db_session):
        record_event(
            db_session,
            "proj-player",
            None,
            "freeform_action",
            "Projection includes a location update.",
            delta={"variables": {"location": "city_square", "world_alarm": 4}},
        )
        sm = AdvancedStateManager("player-one")
        sm.set_variable("location", "deep_mine")
        apply_projection_overlay_to_state_manager(
            db_session,
            sm,
            player_scoped_variable_keys={"location"},
            preserve_existing_player_values=True,
        )

        assert sm.get_variable("location") == "deep_mine"
        assert sm.get_variable("world_alarm") == 4
