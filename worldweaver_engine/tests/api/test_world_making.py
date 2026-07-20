from pathlib import Path

import pytest

from src.config import settings
from src.models import DurableObject, MaterialPool, SessionVars


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


def _session(db, location: str = "Alderbank Workshop") -> None:
    db.add(
        SessionVars(
            session_id="maker-session",
            actor_id="actor-maker",
            vars={"_v": 2, "variables": {"location": location}},
        )
    )
    db.commit()


def test_making_routes_are_local_structured_and_retry_safe(
    client, db_session, game_rules
):
    _session(db_session)

    catalog = client.get("/api/world/making", params={"session_id": "maker-session"})
    assert catalog.status_code == 200
    assert catalog.json()["location"] == "Alderbank Workshop"
    assert catalog.json()["recipes"][0]["can_make"] is True

    payload = {
        "session_id": "maker-session",
        "recipe_id": "small_clay_cup",
        "idempotency_key": "api-make-cup-1",
    }
    made = client.post("/api/world/make", json=payload)
    retry = client.post("/api/world/make", json=payload)

    assert made.status_code == 200
    assert made.json()["object"]["provenance"]["kind"] == "recipe"
    assert retry.status_code == 200
    assert retry.json()["replayed"] is True
    assert retry.json()["object"]["object_id"] == made.json()["object"]["object_id"]
    assert db_session.query(DurableObject).count() == 1
    assert (
        db_session.query(MaterialPool)
        .filter(MaterialPool.material_id == "reclaimed_clay")
        .one()
        .available_units
        == 6
    )


def test_making_route_rejects_recipe_at_wrong_location(client, db_session, game_rules):
    _session(db_session, location="quiet-square")

    response = client.post(
        "/api/world/make",
        json={
            "session_id": "maker-session",
            "recipe_id": "small_clay_cup",
            "idempotency_key": "wrong-location",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "recipe_not_available_here"
    assert db_session.query(DurableObject).count() == 0


def test_ordinary_shard_making_route_fails_closed(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "shard_experience_path", None)
    _session(db_session)

    response = client.get("/api/world/making", params={"session_id": "maker-session"})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "game_capability_unavailable"
    assert db_session.query(MaterialPool).count() == 0


def test_development_reset_clears_game_materials_and_objects(
    client, db_session, game_rules
):
    _session(db_session)
    assert (
        client.get(
            "/api/world/making", params={"session_id": "maker-session"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/world/make",
            json={
                "session_id": "maker-session",
                "recipe_id": "wooden_token",
                "idempotency_key": "make-before-reset",
            },
        ).status_code
        == 200
    )

    response = client.post("/api/dev/hard-reset")

    assert response.status_code == 200
    assert response.json()["deleted"]["material_pools"] == 2
    assert response.json()["deleted"]["durable_objects"] == 1
    assert db_session.query(MaterialPool).count() == 0
    assert db_session.query(DurableObject).count() == 0
