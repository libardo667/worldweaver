from pathlib import Path

import pytest

from src.config import settings
from src.models import SessionVars, SpaceAccessReceipt, WorldEdge, WorldEvent, WorldNode
from src.services.space_access import found_space_policy
from src.services.world_memory import seed_location_graph


@pytest.fixture()
def game_rules(monkeypatch):
    example = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "rulesets"
        / "private_constructive_game.v1.example.json"
    )
    monkeypatch.setattr(settings, "shard_experience_path", str(example))
    monkeypatch.setattr(settings, "shard_id", "test-game-shard")


def _session(db, session_id: str, actor_id: str, location: str) -> None:
    db.add(
        SessionVars(
            session_id=session_id,
            actor_id=actor_id,
            vars={"_v": 2, "variables": {"location": location}},
        )
    )
    db.commit()


def _location(db, session_id: str) -> str:
    row = db.get(SessionVars, session_id)
    return str(row.vars["variables"]["location"])


def test_access_request_opens_real_movement_and_revocation_never_traps(
    client,
    db_session,
    game_rules,
):
    seed_location_graph(
        db_session,
        [{"name": "Town Square"}, {"name": "Workshop"}],
    )
    _session(db_session, "controller", "actor-controller", "Workshop")
    _session(db_session, "visitor", "actor-visitor", "Town Square")
    found_space_policy(
        db_session,
        location="Workshop",
        controller_actor_id="actor-controller",
        mode="requestable",
        note="Please ask before entering.",
    )

    refused = client.post(
        "/api/game/move",
        json={"session_id": "visitor", "destination": "Workshop"},
    )
    assert refused.status_code == 403
    assert refused.json()["detail"]["code"] == "space_access_required"
    assert _location(db_session, "visitor") == "Town Square"
    assert db_session.query(WorldEvent).count() == 0

    requested = client.post(
        "/api/world/access/requests",
        json={
            "session_id": "visitor",
            "location": "Workshop",
            "idempotency_key": "visitor-knock-1",
            "note": "May I come in?",
        },
    )
    request_id = requested.json()["receipt"]["result"]["request"]["request_id"]
    waiting = client.get(
        "/api/world/access",
        params={"session_id": "visitor", "location": "Workshop"},
    )
    assert waiting.status_code == 200
    assert waiting.json()["access"]["request_pending"] is True
    assert waiting.json()["access"]["can_request"] is False
    reviewed = client.get(
        "/api/world/access/requests",
        params={"session_id": "controller", "location": "Workshop"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["count"] == 1
    assert reviewed.json()["requests"][0]["requester_session_id"] == "visitor"

    admitted = client.post(
        f"/api/world/access/requests/{request_id}/resolve",
        json={
            "session_id": "controller",
            "decision": "admitted",
            "idempotency_key": "controller-admit-1",
        },
    )
    assert admitted.status_code == 200
    entered = client.post(
        "/api/game/move",
        json={"session_id": "visitor", "destination": "Workshop"},
    )
    assert entered.status_code == 200
    assert _location(db_session, "visitor") == "Workshop"

    revoked = client.post(
        "/api/world/access/revoke",
        json={
            "session_id": "controller",
            "recipient_session_id": "visitor",
            "location": "Workshop",
            "idempotency_key": "controller-revoke-1",
        },
    )
    assert revoked.status_code == 200

    # Revocation changes future entry only. It never ejects the visitor or
    # prevents the next outward move.
    assert _location(db_session, "visitor") == "Workshop"
    left = client.post(
        "/api/game/move",
        json={"session_id": "visitor", "destination": "Town Square"},
    )
    assert left.status_code == 200
    blocked_again = client.post(
        "/api/game/move",
        json={"session_id": "visitor", "destination": "Workshop"},
    )
    assert blocked_again.status_code == 403
    assert _location(db_session, "visitor") == "Town Square"
    assert db_session.query(SpaceAccessReceipt).count() == 3


def test_skip_move_checks_every_door_before_changing_any_state(
    client,
    db_session,
    game_rules,
):
    seed_location_graph(
        db_session,
        [{"name": "West Gate"}, {"name": "Narrow Hall"}, {"name": "East Gate"}],
    )
    nodes = {row.name: row for row in db_session.query(WorldNode).all()}
    db_session.query(WorldEdge).delete(synchronize_session=False)
    db_session.add_all(
        [
            WorldEdge(
                source_node_id=nodes["West Gate"].id,
                target_node_id=nodes["Narrow Hall"].id,
                edge_type="path",
            ),
            WorldEdge(
                source_node_id=nodes["Narrow Hall"].id,
                target_node_id=nodes["East Gate"].id,
                edge_type="path",
            ),
        ]
    )
    db_session.commit()
    _session(db_session, "controller", "actor-controller", "East Gate")
    _session(db_session, "visitor", "actor-visitor", "West Gate")
    found_space_policy(
        db_session,
        location="Narrow Hall",
        controller_actor_id="actor-controller",
        mode="closed",
    )

    response = client.post(
        "/api/game/move",
        json={
            "session_id": "visitor",
            "destination": "East Gate",
            "skip_to_destination": True,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "space_closed"
    assert _location(db_session, "visitor") == "West Gate"
    assert db_session.query(WorldEvent).count() == 0


def test_ordinary_shard_movement_is_unchanged(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "shard_experience_path", None)
    seed_location_graph(db_session, [{"name": "One"}, {"name": "Two"}])
    _session(db_session, "legacy-session", "", "One")

    response = client.post(
        "/api/game/move",
        json={"session_id": "legacy-session", "destination": "Two"},
    )

    assert response.status_code == 200
    assert response.json()["to_location"] == "Two"
