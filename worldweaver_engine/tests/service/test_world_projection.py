"""Tests for world projection determinism and rebuild mechanics."""

from src.models import WorldEvent, WorldProjection
from src.services.world_memory import rebuild_world_projection


def test_projection_rebuild_is_deterministic(db_session):
    """Verify that rebuilding projection from events produces consistent results."""
    event1 = WorldEvent(
        session_id="test-session",
        event_type="test",
        summary="Event 1",
        world_state_delta={"variables": {"test_var": 1}},
    )
    db_session.add(event1)
    db_session.flush()

    event2 = WorldEvent(
        session_id="test-session",
        event_type="test",
        summary="Event 2",
        world_state_delta={"variables": {"test_var": 2}},
    )
    db_session.add(event2)
    db_session.commit()

    metrics1 = rebuild_world_projection(db_session, session_id="test-session")

    projections1 = db_session.query(WorldProjection).filter(WorldProjection.path == "variables.test_var").all()
    assert len(projections1) == 1
    assert projections1[0].value == 2
    assert projections1[0].source_event_id == event2.id

    metrics2 = rebuild_world_projection(db_session, session_id="test-session")

    projections2 = db_session.query(WorldProjection).filter(WorldProjection.path == "variables.test_var").all()
    assert len(projections2) == 1
    assert projections2[0].value == 2
    assert projections2[0].source_event_id == event2.id

    assert metrics1["events_processed"] == metrics2["events_processed"]


def test_projection_surfaces_lineage(db_session):
    """Verify that projection rows retain source event ID and metadata."""
    event = WorldEvent(
        session_id="lineage-session",
        event_type="discovery",
        summary="Found a sword",
        world_state_delta={"variables": {"has_sword": True}},
    )
    db_session.add(event)
    db_session.commit()

    rebuild_world_projection(db_session, session_id="lineage-session")

    projection = db_session.query(WorldProjection).filter(WorldProjection.path == "variables.has_sword").first()
    assert projection is not None
    assert projection.source_event_id == event.id
    assert projection.metadata_json.get("source_event_type") == "discovery"
