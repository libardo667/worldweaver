from pathlib import Path

import pytest

from src.config import settings
from src.models import DurableObject, ExchangeReceipt, SessionVars
from src.services.consequence_objects import found_durable_object


@pytest.fixture()
def game_rules(monkeypatch):
    example = Path(__file__).resolve().parents[2] / "data" / "rulesets" / "private_constructive_game.v1.example.json"
    monkeypatch.setattr(settings, "shard_experience_path", str(example))
    monkeypatch.setattr(settings, "shard_id", "test-game-shard")


def _session(db, session_id: str, actor_id: str) -> None:
    db.add(
        SessionVars(
            session_id=session_id,
            actor_id=actor_id,
            vars={"_v": 2, "variables": {"location": "market-table"}},
        )
    )
    db.commit()


def _object(db, session_id: str, key: str, name: str) -> str:
    return found_durable_object(
        db,
        session_id=session_id,
        idempotency_key=key,
        name=name,
        description=f"A {name.lower()} for an API exchange.",
        object_kind="api_exchange_object",
        provenance_ref=f"test:{key}",
    ).object["object_id"]


def test_exchange_routes_offer_list_and_atomically_accept(client, db_session, game_rules):
    _session(db_session, "proposer", "actor-proposer")
    _session(db_session, "recipient", "actor-recipient")
    cup_id = _object(db_session, "proposer", "api-cup", "Blue cup")
    token_id = _object(db_session, "recipient", "api-token", "Wooden token")

    offered = client.post(
        "/api/world/exchanges",
        json={
            "session_id": "proposer",
            "recipient_session_id": "recipient",
            "offered_object_id": cup_id,
            "requested_object_id": token_id,
            "idempotency_key": "api-offer",
        },
    )
    assert offered.status_code == 200
    exchange_id = offered.json()["exchange"]["exchange_id"]

    listed = client.get("/api/world/exchanges", params={"session_id": "recipient"})
    assert listed.status_code == 200
    assert listed.json()["exchanges"][0]["can_accept"] is True

    payload = {"session_id": "recipient", "idempotency_key": "api-accept"}
    accepted = client.post(f"/api/world/exchanges/{exchange_id}/accept", json=payload)
    replay = client.post(f"/api/world/exchanges/{exchange_id}/accept", json=payload)

    assert accepted.status_code == 200
    assert accepted.json()["exchange"]["status"] == "completed"
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert db_session.get(DurableObject, cup_id).custodian_actor_id == "actor-recipient"
    assert db_session.get(DurableObject, token_id).custodian_actor_id == "actor-proposer"
    assert db_session.query(ExchangeReceipt).count() == 2


def test_exchange_offer_rejects_absent_recipient(client, db_session, game_rules):
    _session(db_session, "proposer", "actor-proposer")
    _session(db_session, "recipient", "actor-recipient")
    recipient = db_session.get(SessionVars, "recipient")
    recipient.vars = {"_v": 2, "variables": {"location": "elsewhere"}}
    db_session.commit()
    cup_id = _object(db_session, "proposer", "api-cup", "Blue cup")
    token_id = _object(db_session, "recipient", "api-token", "Wooden token")

    response = client.post(
        "/api/world/exchanges",
        json={
            "session_id": "proposer",
            "recipient_session_id": "recipient",
            "offered_object_id": cup_id,
            "requested_object_id": token_id,
            "idempotency_key": "api-absent-offer",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "recipient_not_present"
    assert db_session.query(ExchangeReceipt).count() == 0
