from pathlib import Path

import pytest

from src.config import settings
from src.models import ConsequenceReceipt, DurableObject, SessionVars, WorldEvent
from src.services.consequence_objects import found_durable_object


@pytest.fixture()
def game_rules(monkeypatch):
    example = Path(__file__).resolve().parents[2] / "data" / "rulesets" / "private_constructive_game.v1.example.json"
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


def _found(db):
    return found_durable_object(
        db,
        session_id="maker-session",
        idempotency_key="api-found-1",
        name="Wooden token",
        description="A smooth token cut from a fallen branch.",
        object_kind="token",
        provenance_ref="founding-kit:wooden-token",
        properties={"material": "wood"},
    )


def test_shared_object_routes_list_place_and_give(client, db_session, game_rules):
    _session(db_session, "maker-session", "actor-maker", "maker-bench")
    _session(db_session, "neighbor-session", "actor-neighbor", "maker-bench")
    founded = _found(db_session)
    object_id = founded.object["object_id"]

    carried = client.get("/api/world/objects", params={"session_id": "maker-session"})
    assert carried.status_code == 200
    assert carried.json()["objects"][0]["relation"] == "carried"

    placed = client.post(
        f"/api/world/objects/{object_id}/place",
        json={"session_id": "maker-session", "idempotency_key": "api-place-1"},
    )
    assert placed.status_code == 200
    assert placed.json()["object"]["attachment"] == {"kind": "place", "location": "maker-bench"}

    visible_to_neighbor = client.get("/api/world/objects", params={"session_id": "neighbor-session"})
    assert visible_to_neighbor.status_code == 200
    assert visible_to_neighbor.json()["objects"][0]["relation"] == "here"

    # A placed object cannot be silently claimed. Give operates only from custody.
    rejected = client.post(
        f"/api/world/objects/{object_id}/give",
        json={
            "session_id": "maker-session",
            "recipient_session_id": "neighbor-session",
            "idempotency_key": "api-give-while-placed",
        },
    )
    assert rejected.status_code == 403
    assert rejected.json()["detail"]["code"] == "not_custodian"


def test_give_route_is_atomic_and_retry_safe(client, db_session, game_rules):
    _session(db_session, "maker-session", "actor-maker", "maker-bench")
    _session(db_session, "neighbor-session", "actor-neighbor", "maker-bench")
    founded = _found(db_session)
    object_id = founded.object["object_id"]
    payload = {
        "session_id": "maker-session",
        "recipient_session_id": "neighbor-session",
        "idempotency_key": "api-give-1",
    }

    first = client.post(f"/api/world/objects/{object_id}/give", json=payload)
    retry = client.post(f"/api/world/objects/{object_id}/give", json=payload)

    assert first.status_code == 200
    assert retry.status_code == 200
    assert retry.json()["replayed"] is True
    assert first.json()["receipt"]["receipt_id"] == retry.json()["receipt"]["receipt_id"]
    assert db_session.get(DurableObject, object_id).custodian_actor_id == "actor-neighbor"
    assert db_session.query(ConsequenceReceipt).count() == 2
    assert db_session.query(WorldEvent).count() == 2


def test_public_api_has_no_arbitrary_object_creation_route(client, db_session, game_rules):
    _session(db_session, "maker-session", "actor-maker", "maker-bench")

    response = client.post(
        "/api/world/objects",
        json={"session_id": "maker-session", "name": "Narrated crown"},
    )

    assert response.status_code == 405
    assert db_session.query(DurableObject).count() == 0
    assert db_session.query(ConsequenceReceipt).count() == 0


def test_ordinary_shard_object_route_fails_closed(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "shard_experience_path", None)
    _session(db_session, "ordinary-session", "ordinary-actor", "ordinary-place")

    response = client.get("/api/world/objects", params={"session_id": "ordinary-session"})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "game_capability_unavailable"


def test_session_cleanup_preserves_consequence_history(db_session, game_rules):
    from src.api.game.state import _delete_session_world_rows

    _session(db_session, "maker-session", "actor-maker", "maker-bench")
    founded = _found(db_session)

    deleted = _delete_session_world_rows(db_session, "maker-session")

    assert deleted["sessions"] == 1
    assert deleted["consequence_events_preserved"] == 1
    assert db_session.get(DurableObject, founded.object["object_id"]) is not None
    assert db_session.query(ConsequenceReceipt).count() == 1
    assert db_session.query(WorldEvent).count() == 1
