from pathlib import Path

import pytest

from src.config import settings
from src.models import ConsequenceReceipt, DurableObject, SessionVars, WorldEvent
from src.services.consequence_objects import (
    ConsequenceDomainError,
    found_durable_object,
    give_durable_object,
    pick_up_durable_object,
    place_durable_object,
    visible_durable_objects,
)
from src.services.event_submission import WorldEventCommand, submit_world_event


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


def _found(db, *, session_id: str = "maker-session", key: str = "found-1"):
    return found_durable_object(
        db,
        session_id=session_id,
        idempotency_key=key,
        name="Blue clay cup",
        description="A small hand-shaped cup with an uneven rim.",
        object_kind="cup",
        provenance_ref="founding-kit:blue-cup",
        properties={"material": "clay"},
    )


def test_founded_object_has_stable_identity_provenance_and_receipt(
    db_session, game_rules
):
    _session(db_session, "maker-session", "actor-maker", "workshop-table")

    result = _found(db_session)
    object_row = db_session.get(DurableObject, result.object["object_id"])
    receipt = db_session.query(ConsequenceReceipt).one()
    event = db_session.query(WorldEvent).one()

    assert object_row is not None
    assert object_row.custodian_actor_id == "actor-maker"
    assert object_row.location is None
    assert object_row.origin_shard_id == "test-game-shard"
    assert object_row.provenance_kind == "shard_founding"
    assert object_row.provenance_event_id == event.id
    assert result.object["provenance"]["world_event_id"] == event.id
    assert receipt.world_event_id == event.id
    assert receipt.operation == "object_founded"
    assert event.event_type == "object_founded"


def test_narrative_event_cannot_create_or_mutate_canonical_objects(
    db_session, game_rules
):
    _session(db_session, "maker-session", "actor-maker", "workshop-table")
    founded = _found(db_session)
    object_id = founded.object["object_id"]

    submit_world_event(
        db_session,
        WorldEventCommand(
            session_id="maker-session",
            event_type="freeform_action",
            summary="The speaker claims a second cup appears and the first belongs elsewhere.",
            delta={
                "inventory": {"imaginary-cup": True},
                "durable_objects": {object_id: {"custodian_actor_id": "someone-else"}},
            },
        ),
    )

    object_row = db_session.get(DurableObject, object_id)
    assert db_session.query(DurableObject).count() == 1
    assert object_row is not None
    assert object_row.custodian_actor_id == "actor-maker"
    assert object_row.location is None
    assert object_row.revision == 1
    assert db_session.query(ConsequenceReceipt).count() == 1


def test_placement_is_exact_restart_safe_and_evidence_backed(db_session, game_rules):
    _session(db_session, "maker-session", "actor-maker", "quiet-window-seat")
    founded = _found(db_session)

    placed = place_durable_object(
        db_session,
        session_id="maker-session",
        object_id=founded.object["object_id"],
        idempotency_key="place-1",
    )

    db_session.expire_all()
    object_row = db_session.get(DurableObject, founded.object["object_id"])
    assert object_row is not None
    assert object_row.custodian_actor_id is None
    assert object_row.location == "quiet-window-seat"
    assert object_row.placed_by_actor_id == "actor-maker"
    assert object_row.revision == 2
    assert placed.object["attachment"] == {
        "kind": "place",
        "location": "quiet-window-seat",
    }
    assert [
        row.operation
        for row in db_session.query(ConsequenceReceipt)
        .order_by(ConsequenceReceipt.id)
        .all()
    ] == [
        "object_founded",
        "object_placed",
    ]
    assert [
        row.event_type
        for row in db_session.query(WorldEvent).order_by(WorldEvent.id).all()
    ] == [
        "object_founded",
        "object_placed",
    ]


def test_only_the_placer_can_pick_an_ordinary_object_back_up(db_session, game_rules):
    _session(db_session, "maker-session", "actor-maker", "quiet-window-seat")
    _session(db_session, "neighbor-session", "actor-neighbor", "quiet-window-seat")
    founded = _found(db_session)
    object_id = founded.object["object_id"]
    place_durable_object(
        db_session,
        session_id="maker-session",
        object_id=object_id,
        idempotency_key="place-for-pickup",
    )

    assert (
        visible_durable_objects(db_session, session_id="maker-session")[0][
            "can_pick_up"
        ]
        is True
    )
    assert (
        visible_durable_objects(db_session, session_id="neighbor-session")[0][
            "can_pick_up"
        ]
        is False
    )
    with pytest.raises(ConsequenceDomainError, match="actor who placed"):
        pick_up_durable_object(
            db_session,
            session_id="neighbor-session",
            object_id=object_id,
            idempotency_key="neighbor-pickup",
        )

    picked_up = pick_up_durable_object(
        db_session,
        session_id="maker-session",
        object_id=object_id,
        idempotency_key="maker-pickup",
    )
    replay = pick_up_durable_object(
        db_session,
        session_id="maker-session",
        object_id=object_id,
        idempotency_key="maker-pickup",
    )

    object_row = db_session.get(DurableObject, object_id)
    assert object_row.custodian_actor_id == "actor-maker"
    assert object_row.location is None
    assert object_row.placed_by_actor_id is None
    assert picked_up.object["attachment"] == {
        "kind": "custody",
        "actor_id": "actor-maker",
    }
    assert replay.replayed is True
    assert [
        row.event_type
        for row in db_session.query(WorldEvent).order_by(WorldEvent.id).all()
    ] == [
        "object_founded",
        "object_placed",
        "object_picked_up",
    ]


def test_giving_requires_current_custody_and_exact_colocation(db_session, game_rules):
    _session(db_session, "maker-session", "actor-maker", "maker-bench")
    _session(db_session, "neighbor-session", "actor-neighbor", "maker-bench")
    founded = _found(db_session)

    given = give_durable_object(
        db_session,
        session_id="maker-session",
        recipient_session_id="neighbor-session",
        object_id=founded.object["object_id"],
        idempotency_key="give-1",
    )

    assert given.object["attachment"] == {
        "kind": "custody",
        "actor_id": "actor-neighbor",
    }
    assert visible_durable_objects(db_session, session_id="maker-session") == []
    assert (
        visible_durable_objects(db_session, session_id="neighbor-session")[0][
            "relation"
        ]
        == "carried"
    )

    with pytest.raises(ConsequenceDomainError, match="current custodian"):
        give_durable_object(
            db_session,
            session_id="maker-session",
            recipient_session_id="neighbor-session",
            object_id=founded.object["object_id"],
            idempotency_key="give-again",
        )

    assert db_session.query(ConsequenceReceipt).count() == 2
    assert db_session.query(WorldEvent).count() == 2


def test_failed_give_changes_nothing(db_session, game_rules):
    _session(db_session, "maker-session", "actor-maker", "maker-bench")
    _session(db_session, "far-session", "actor-far", "distant-square")
    founded = _found(db_session)

    with pytest.raises(ConsequenceDomainError, match="same exact location"):
        give_durable_object(
            db_session,
            session_id="maker-session",
            recipient_session_id="far-session",
            object_id=founded.object["object_id"],
            idempotency_key="failed-give",
        )

    object_row = db_session.get(DurableObject, founded.object["object_id"])
    assert object_row is not None
    assert object_row.custodian_actor_id == "actor-maker"
    assert object_row.revision == 1
    assert db_session.query(ConsequenceReceipt).count() == 1
    assert db_session.query(WorldEvent).count() == 1


def test_event_failure_rolls_back_custody_and_receipt(
    db_session, game_rules, monkeypatch
):
    _session(db_session, "maker-session", "actor-maker", "maker-bench")
    _session(db_session, "neighbor-session", "actor-neighbor", "maker-bench")
    founded = _found(db_session)

    def fail_event(*_args, **_kwargs):
        raise RuntimeError("event store unavailable")

    monkeypatch.setattr(
        "src.services.consequence_objects.submit_world_event", fail_event
    )

    with pytest.raises(RuntimeError, match="event store unavailable"):
        give_durable_object(
            db_session,
            session_id="maker-session",
            recipient_session_id="neighbor-session",
            object_id=founded.object["object_id"],
            idempotency_key="failed-event-give",
        )

    db_session.expire_all()
    object_row = db_session.get(DurableObject, founded.object["object_id"])
    assert object_row is not None
    assert object_row.custodian_actor_id == "actor-maker"
    assert object_row.revision == 1
    assert db_session.query(ConsequenceReceipt).count() == 1
    assert db_session.query(WorldEvent).count() == 1


def test_idempotent_retry_does_not_duplicate_object_or_evidence(db_session, game_rules):
    _session(db_session, "maker-session", "actor-maker", "workshop-table")

    first = _found(db_session)
    retry = _found(db_session)

    assert retry.replayed is True
    assert retry.object["object_id"] == first.object["object_id"]
    assert db_session.query(DurableObject).count() == 1
    assert db_session.query(ConsequenceReceipt).count() == 1
    assert db_session.query(WorldEvent).count() == 1


def test_ordinary_shard_cannot_use_game_object_domain(db_session, monkeypatch):
    monkeypatch.setattr(settings, "shard_experience_path", None)
    _session(db_session, "ordinary-session", "ordinary-actor", "ordinary-place")

    with pytest.raises(ConsequenceDomainError) as caught:
        visible_durable_objects(db_session, session_id="ordinary-session")

    assert caught.value.code == "game_capability_unavailable"
    assert db_session.query(DurableObject).count() == 0
