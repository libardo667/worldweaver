from pathlib import Path

import pytest

from src.config import settings
from src.models import (
    DurableObject,
    SessionVars,
    StoopObjectEntry,
    StoopReceipt,
    WorldNode,
)
from src.services.consequence_objects import found_durable_object
from src.services.world_stoops import found_world_stoop


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


def _setup(db) -> str:
    db.add(
        WorldNode(
            node_type="location",
            name="Lantern Square",
            normalized_name="lantern_square",
            metadata_json={},
        )
    )
    db.add_all(
        [
            SessionVars(
                session_id="maker",
                actor_id="actor-maker",
                vars={"_v": 2, "variables": {"location": "Lantern Square"}},
            ),
            SessionVars(
                session_id="visitor",
                actor_id="actor-visitor",
                vars={"_v": 2, "variables": {"location": "Lantern Square"}},
            ),
        ]
    )
    db.commit()
    found_world_stoop(
        db,
        stoop_id="lantern-stoop",
        title="The Lantern Stoop",
        prompt="Leave something useful or curious.",
        location="Lantern Square",
        capacity=2,
    )
    return found_durable_object(
        db,
        session_id="maker",
        idempotency_key="api-found-stoop-object",
        name="Paper lantern",
        description="A small folded paper lantern.",
        object_kind="paper_lantern",
        provenance_ref="test:paper-lantern",
    ).object["object_id"]


def test_stoop_routes_are_local_elective_and_retry_safe(client, db_session, game_rules):
    object_id = _setup(db_session)

    shells = client.get("/api/world/stoops", params={"session_id": "visitor"})
    assert shells.status_code == 200
    assert shells.json()["stoops"][0]["active_count"] == 0
    assert "entries" not in shells.json()

    leave_payload = {
        "session_id": "maker",
        "object_id": object_id,
        "idempotency_key": "api-leave-stoop-object",
    }
    left = client.post("/api/world/stoops/lantern-stoop/leave", json=leave_payload)
    replay = client.post("/api/world/stoops/lantern-stoop/leave", json=leave_payload)
    assert left.status_code == 200
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    entry_id = left.json()["entry"]["entry_id"]

    browsed = client.get(
        "/api/world/stoops/lantern-stoop",
        params={"session_id": "visitor"},
    )
    assert browsed.status_code == 200
    assert browsed.json()["entries"][0]["entry_id"] == entry_id

    take_payload = {"session_id": "visitor", "idempotency_key": "api-take-stoop-object"}
    taken = client.post(f"/api/world/stoops/entries/{entry_id}/take", json=take_payload)
    take_replay = client.post(
        f"/api/world/stoops/entries/{entry_id}/take", json=take_payload
    )
    assert taken.status_code == 200
    assert take_replay.status_code == 200
    assert take_replay.json()["replayed"] is True
    assert (
        db_session.get(DurableObject, object_id).custodian_actor_id == "actor-visitor"
    )
    assert db_session.get(StoopObjectEntry, entry_id).status == "taken"
    assert db_session.query(StoopReceipt).count() == 2


def test_sessionless_onlooker_can_browse_stoops_by_location(
    client, db_session, game_rules
):
    object_id = _setup(db_session)
    client.post(
        "/api/world/stoops/lantern-stoop/leave",
        json={
            "session_id": "maker",
            "object_id": object_id,
            "idempotency_key": "public-browse-leave",
        },
    )

    shells = client.get("/api/world/stoops", params={"location": "Lantern Square"})
    assert shells.status_code == 200
    assert shells.json()["location"] == "Lantern Square"
    assert shells.json()["stoops"][0]["active_count"] == 1

    browsed = client.get(
        "/api/world/stoops/lantern-stoop", params={"location": "Lantern Square"}
    )
    assert browsed.status_code == 200
    entry = browsed.json()["entries"][0]
    assert entry["object"]["name"] == "Paper lantern"
    # Looking is not holding: no take/withdraw affordances for onlookers,
    # and no depositor actor id in provenance.
    assert "can_take" not in entry
    assert "can_withdraw" not in entry
    assert "created_by_actor_id" not in entry["object"]["provenance"]

    elsewhere = client.get(
        "/api/world/stoops/lantern-stoop", params={"location": "Somewhere Else"}
    )
    assert elsewhere.status_code == 403

    neither = client.get("/api/world/stoops")
    assert neither.status_code == 422


def test_no_public_route_can_found_an_arbitrary_stoop(client, db_session, game_rules):
    response = client.post(
        "/api/world/stoops",
        json={
            "session_id": "someone",
            "stoop_id": "claimed-square",
            "location": "Anywhere",
        },
    )

    assert response.status_code == 405
