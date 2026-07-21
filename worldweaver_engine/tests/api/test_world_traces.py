"""Physical trace commons: local, attributed, expiring, and narrator-free."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from src.api.game.world import (
    LeaveWorldTraceRequest,
    _active_world_traces,
    get_agent_scene,
    post_world_trace,
)
from src.api.game.state import _delete_all_world_rows
from src.models import SessionVars, WorldEvent, WorldTrace
from src.services.clock import SystemClock


def _session(session_id: str, location: str = "Chinatown") -> SessionVars:
    return SessionVars(
        session_id=session_id,
        vars={"location": location},
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )


def test_trace_derives_author_and_location_without_entering_event_feed(db_session):
    author_id = "test_resident-20260714-120000"
    viewer_id = "test_resident_two-20260714-120000"
    db_session.add_all([_session(author_id), _session(viewer_id)])
    db_session.commit()

    receipt = post_world_trace(
        LeaveWorldTraceRequest(
            session_id=author_id,
            body="three blue chalk lines",
            target="the bakery lintel",
        ),
        db_session,
        world_clock=SystemClock(),
    )

    trace = receipt["trace"]
    assert trace["trace_id"].startswith("trace:")
    assert trace["author_name"] == "Test Resident"
    assert trace["location"] == "Chinatown"
    assert trace["target"] == "the bakery lintel"
    assert trace["source_id"] == trace["trace_id"]
    assert trace["provenance"] == "physical_trace"
    assert trace["freshness"] == "active"
    assert trace["locality"] == "Chinatown"
    assert trace["visibility"] == "local"
    assert trace["selection_mode"] == "embodied_local"
    assert db_session.query(WorldEvent).count() == 0

    scene = get_agent_scene(viewer_id, db_session, world_clock=SystemClock())
    assert scene["traces_here"] == [trace]
    assert (
        get_agent_scene(
            author_id,
            db_session,
            world_clock=SystemClock(),
        )["traces_here"]
        == []
    )


def test_human_trace_view_uses_the_same_local_marks_without_session_ids(
    client, db_session
):
    author_id = "test_resident-20260714-120000"
    viewer_id = "human_player-20260719-120000"
    db_session.add_all([_session(author_id), _session(viewer_id)])
    db_session.commit()

    posted = client.post(
        "/api/world/traces",
        json={
            "session_id": author_id,
            "body": "three blue chalk lines",
            "target": "the bakery lintel",
        },
    )
    assert posted.status_code == 200

    response = client.get("/api/world/traces", params={"session_id": viewer_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["location"] == "Chinatown"
    assert payload["count"] == 1
    assert payload["traces"][0]["body"] == "three blue chalk lines"
    assert payload["traces"][0]["target"] == "the bakery lintel"
    assert "author_session_id" not in payload["traces"][0]

    own_view = client.get("/api/world/traces", params={"session_id": author_id})
    assert own_view.status_code == 200
    assert own_view.json()["traces"] == []


def test_trace_visibility_is_location_bounded_and_expiry_bounded(db_session):
    author_id = "test_resident-20260714-120000"
    viewer_id = "test_resident_two-20260714-120000"
    elsewhere_id = "third_resident-20260714-120000"
    db_session.add_all(
        [
            _session(author_id, "Chinatown"),
            _session(viewer_id, "Chinatown"),
            _session(elsewhere_id, "Mission"),
        ]
    )
    db_session.commit()
    post_world_trace(
        LeaveWorldTraceRequest(
            session_id=author_id, body="a paper crane", target="the sill"
        ),
        db_session,
        world_clock=SystemClock(),
    )

    assert (
        len(
            _active_world_traces(
                db_session, location="Chinatown", viewer_session_id=viewer_id
            )
        )
        == 1
    )
    assert (
        _active_world_traces(
            db_session, location="Mission", viewer_session_id=elsewhere_id
        )
        == []
    )

    row = db_session.query(WorldTrace).one()
    row.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
        seconds=1
    )
    db_session.commit()
    assert (
        _active_world_traces(
            db_session, location="Chinatown", viewer_session_id=viewer_id
        )
        == []
    )
    assert (
        db_session.query(WorldTrace).count() == 1
    )  # decay hides history; it does not rewrite it


def test_trace_requires_canonical_session_location(db_session):
    session_id = "test_resident-20260714-120000"
    db_session.add(_session(session_id, ""))
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        post_world_trace(
            LeaveWorldTraceRequest(session_id=session_id, body="a mark"),
            db_session,
            world_clock=SystemClock(),
        )

    assert exc_info.value.status_code == 409
    assert db_session.query(WorldTrace).count() == 0


def test_hard_world_reset_clears_trace_store(db_session):
    session_id = "test_resident-20260714-120000"
    db_session.add(_session(session_id))
    db_session.commit()
    post_world_trace(
        LeaveWorldTraceRequest(session_id=session_id, body="a temporary chalk spiral"),
        db_session,
        world_clock=SystemClock(),
    )

    receipt = _delete_all_world_rows(db_session)

    assert receipt["world_traces"] == 1
    assert db_session.query(WorldTrace).count() == 0
