from pathlib import Path

import pytest

from src.config import settings
from src.models import DurableObject, ExchangeReceipt, ObjectExchange, SessionVars, WorldEvent
from src.services.consequence_objects import (
    ConsequenceDomainError,
    found_durable_object,
    place_durable_object,
)
from src.services.object_exchange import (
    accept_object_exchange,
    cancel_object_exchange,
    decline_object_exchange,
    offer_object_exchange,
    visible_object_exchanges,
)


@pytest.fixture()
def game_rules(monkeypatch):
    example = Path(__file__).resolve().parents[2] / "data" / "rulesets" / "private_constructive_game.v1.example.json"
    monkeypatch.setattr(settings, "shard_experience_path", str(example))
    monkeypatch.setattr(settings, "shard_id", "test-game-shard")


def _session(db, session_id: str, actor_id: str, location: str = "market-table") -> None:
    db.add(
        SessionVars(
            session_id=session_id,
            actor_id=actor_id,
            vars={"_v": 2, "variables": {"location": location}},
        )
    )
    db.commit()


def _found(db, *, session_id: str, key: str, name: str):
    return found_durable_object(
        db,
        session_id=session_id,
        idempotency_key=key,
        name=name,
        description=f"A durable {name.lower()} made for exchange tests.",
        object_kind="exchange_test_object",
        provenance_ref=f"test:{key}",
    )


def _two_objects(db, *, proposer_key: str = "found-cup"):
    cup = _found(db, session_id="proposer", key=proposer_key, name="Blue cup")
    token = _found(db, session_id="recipient", key="found-token", name="Wooden token")
    return cup.object["object_id"], token.object["object_id"]


def test_exact_offer_moves_nothing_until_recipient_accepts(db_session, game_rules):
    _session(db_session, "proposer", "actor-proposer")
    _session(db_session, "recipient", "actor-recipient")
    cup_id, token_id = _two_objects(db_session)

    offered = offer_object_exchange(
        db_session,
        session_id="proposer",
        recipient_session_id="recipient",
        offered_object_id=cup_id,
        requested_object_id=token_id,
        idempotency_key="offer-one",
    )
    exchange_id = offered["exchange"]["exchange_id"]

    assert db_session.get(DurableObject, cup_id).custodian_actor_id == "actor-proposer"
    assert db_session.get(DurableObject, token_id).custodian_actor_id == "actor-recipient"
    recipient_view = visible_object_exchanges(db_session, session_id="recipient")["exchanges"][0]
    assert recipient_view["can_accept"] is True
    assert recipient_view["viewer_role"] == "recipient"

    completed = accept_object_exchange(
        db_session,
        session_id="recipient",
        exchange_id=exchange_id,
        idempotency_key="accept-one",
    )
    replay = accept_object_exchange(
        db_session,
        session_id="recipient",
        exchange_id=exchange_id,
        idempotency_key="accept-one",
    )

    db_session.expire_all()
    assert completed["exchange"]["status"] == "completed"
    assert replay["replayed"] is True
    assert replay["receipt"]["receipt_id"] == completed["receipt"]["receipt_id"]
    assert db_session.get(DurableObject, cup_id).custodian_actor_id == "actor-recipient"
    assert db_session.get(DurableObject, token_id).custodian_actor_id == "actor-proposer"
    assert db_session.get(DurableObject, cup_id).revision == 2
    assert db_session.get(DurableObject, token_id).revision == 2
    assert db_session.get(ObjectExchange, exchange_id).status == "completed"
    assert [row.operation for row in db_session.query(ExchangeReceipt).order_by(ExchangeReceipt.id).all()] == [
        "object_exchange_offered",
        "object_exchange_completed",
    ]
    assert [row.event_type for row in db_session.query(WorldEvent).order_by(WorldEvent.id).all()][-2:] == [
        "object_exchange_offered",
        "object_exchange_completed",
    ]


def test_acceptance_requires_both_people_and_current_terms(db_session, game_rules):
    _session(db_session, "proposer", "actor-proposer")
    _session(db_session, "recipient", "actor-recipient")
    cup_id, token_id = _two_objects(db_session)
    offer = offer_object_exchange(
        db_session,
        session_id="proposer",
        recipient_session_id="recipient",
        offered_object_id=cup_id,
        requested_object_id=token_id,
        idempotency_key="offer-presence",
    )
    exchange_id = offer["exchange"]["exchange_id"]

    proposer = db_session.get(SessionVars, "proposer")
    proposer.vars = {"_v": 2, "variables": {"location": "far-square"}}
    db_session.commit()
    with pytest.raises(ConsequenceDomainError) as absent:
        accept_object_exchange(
            db_session,
            session_id="recipient",
            exchange_id=exchange_id,
            idempotency_key="accept-absent",
        )
    assert absent.value.code == "proposer_not_present"

    proposer.vars = {"_v": 2, "variables": {"location": "market-table"}}
    db_session.commit()
    place_durable_object(
        db_session,
        session_id="proposer",
        object_id=cup_id,
        idempotency_key="place-after-offer",
    )
    with pytest.raises(ConsequenceDomainError) as stale:
        accept_object_exchange(
            db_session,
            session_id="recipient",
            exchange_id=exchange_id,
            idempotency_key="accept-stale",
        )
    assert stale.value.code == "exchange_terms_unavailable"

    db_session.expire_all()
    assert db_session.get(ObjectExchange, exchange_id).status == "open"
    assert db_session.get(DurableObject, cup_id).location == "market-table"
    assert db_session.get(DurableObject, token_id).custodian_actor_id == "actor-recipient"
    assert db_session.query(ExchangeReceipt).count() == 1


def test_acceptance_event_failure_rolls_back_both_objects(db_session, game_rules, monkeypatch):
    _session(db_session, "proposer", "actor-proposer")
    _session(db_session, "recipient", "actor-recipient")
    cup_id, token_id = _two_objects(db_session)
    offer = offer_object_exchange(
        db_session,
        session_id="proposer",
        recipient_session_id="recipient",
        offered_object_id=cup_id,
        requested_object_id=token_id,
        idempotency_key="offer-before-failure",
    )

    def fail_event(*_args, **_kwargs):
        raise RuntimeError("event store unavailable")

    monkeypatch.setattr("src.services.object_exchange.submit_world_event", fail_event)
    with pytest.raises(RuntimeError, match="event store unavailable"):
        accept_object_exchange(
            db_session,
            session_id="recipient",
            exchange_id=offer["exchange"]["exchange_id"],
            idempotency_key="accept-fails",
        )

    db_session.expire_all()
    assert db_session.get(DurableObject, cup_id).custodian_actor_id == "actor-proposer"
    assert db_session.get(DurableObject, token_id).custodian_actor_id == "actor-recipient"
    assert db_session.get(ObjectExchange, offer["exchange"]["exchange_id"]).status == "open"
    assert db_session.query(ExchangeReceipt).count() == 1


def test_decline_and_cancel_leave_custody_unchanged(db_session, game_rules):
    _session(db_session, "proposer", "actor-proposer")
    _session(db_session, "recipient", "actor-recipient")
    cup_id, token_id = _two_objects(db_session)

    first = offer_object_exchange(
        db_session,
        session_id="proposer",
        recipient_session_id="recipient",
        offered_object_id=cup_id,
        requested_object_id=token_id,
        idempotency_key="offer-decline",
    )
    declined = decline_object_exchange(
        db_session,
        session_id="recipient",
        exchange_id=first["exchange"]["exchange_id"],
        idempotency_key="decline-one",
    )
    assert declined["exchange"]["status"] == "declined"

    second = offer_object_exchange(
        db_session,
        session_id="proposer",
        recipient_session_id="recipient",
        offered_object_id=cup_id,
        requested_object_id=token_id,
        idempotency_key="offer-cancel",
    )
    cancelled = cancel_object_exchange(
        db_session,
        session_id="proposer",
        exchange_id=second["exchange"]["exchange_id"],
        idempotency_key="cancel-one",
    )

    assert cancelled["exchange"]["status"] == "cancelled"
    assert db_session.get(DurableObject, cup_id).custodian_actor_id == "actor-proposer"
    assert db_session.get(DurableObject, token_id).custodian_actor_id == "actor-recipient"


def test_structural_event_retry_keys_are_namespaced_by_command(db_session, game_rules):
    _session(db_session, "proposer", "actor-proposer")
    _session(db_session, "recipient", "actor-recipient")
    cup_id, token_id = _two_objects(db_session, proposer_key="same-caller-key")

    result = offer_object_exchange(
        db_session,
        session_id="proposer",
        recipient_session_id="recipient",
        offered_object_id=cup_id,
        requested_object_id=token_id,
        idempotency_key="same-caller-key",
    )

    assert result["exchange"]["status"] == "open"
    assert db_session.query(WorldEvent).count() == 3
    keys = [row.world_state_delta["__action_meta__"]["idempotency_key"] for row in db_session.query(WorldEvent).order_by(WorldEvent.id).all()]
    assert len(keys) == len(set(keys))


def test_session_cleanup_preserves_exchange_evidence(db_session, game_rules):
    from src.api.game.state import _delete_session_world_rows

    _session(db_session, "proposer", "actor-proposer")
    _session(db_session, "recipient", "actor-recipient")
    cup_id, token_id = _two_objects(db_session)
    offer_object_exchange(
        db_session,
        session_id="proposer",
        recipient_session_id="recipient",
        offered_object_id=cup_id,
        requested_object_id=token_id,
        idempotency_key="offer-before-leave",
    )

    deleted = _delete_session_world_rows(db_session, "proposer")

    assert deleted["sessions"] == 1
    assert deleted["consequence_events_preserved"] == 2
    assert db_session.query(ObjectExchange).count() == 1
    assert db_session.query(ExchangeReceipt).count() == 1
    assert db_session.query(WorldEvent).count() == 3


def test_full_development_reset_deletes_exchange_before_objects(db_session, game_rules):
    from src.api.game.state import _delete_all_world_rows

    _session(db_session, "proposer", "actor-proposer")
    _session(db_session, "recipient", "actor-recipient")
    cup_id, token_id = _two_objects(db_session)
    offer_object_exchange(
        db_session,
        session_id="proposer",
        recipient_session_id="recipient",
        offered_object_id=cup_id,
        requested_object_id=token_id,
        idempotency_key="offer-before-reset",
    )

    deleted = _delete_all_world_rows(db_session)

    assert deleted["exchange_receipts"] == 1
    assert deleted["object_exchanges"] == 1
    assert deleted["durable_objects"] == 2
    assert db_session.query(ExchangeReceipt).count() == 0
    assert db_session.query(ObjectExchange).count() == 0
    assert db_session.query(DurableObject).count() == 0


def test_ordinary_shard_cannot_use_exchange_domain(db_session, monkeypatch):
    monkeypatch.setattr(settings, "shard_experience_path", None)
    _session(db_session, "ordinary", "ordinary-actor")

    with pytest.raises(ConsequenceDomainError) as refused:
        visible_object_exchanges(db_session, session_id="ordinary")

    assert refused.value.code == "game_capability_unavailable"
