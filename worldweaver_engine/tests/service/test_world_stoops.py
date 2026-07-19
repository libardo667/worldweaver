from pathlib import Path

import pytest

from src.config import settings
from src.models import (
    DurableObject,
    SessionVars,
    StoopObjectEntry,
    StoopReceipt,
    WorldEvent,
    WorldNode,
    WorldStoop,
)
from src.services.consequence_objects import ConsequenceDomainError, found_durable_object, visible_durable_objects
from src.services.world_stoops import (
    browse_world_stoop,
    found_world_stoop,
    leave_object_on_stoop,
    local_stoops,
    take_stoop_object,
    withdraw_stoop_object,
)


@pytest.fixture()
def game_rules(monkeypatch):
    example = Path(__file__).resolve().parents[2] / "data" / "rulesets" / "private_constructive_game.v1.example.json"
    monkeypatch.setattr(settings, "shard_experience_path", str(example))
    monkeypatch.setattr(settings, "shard_id", "test-game-shard")


def _place(db) -> None:
    db.add(
        WorldNode(
            node_type="location",
            name="Lantern Square",
            normalized_name="lantern_square",
            metadata_json={},
        )
    )
    db.commit()


def _session(db, session_id: str, actor_id: str, location: str = "Lantern Square") -> None:
    db.add(
        SessionVars(
            session_id=session_id,
            actor_id=actor_id,
            vars={"_v": 2, "variables": {"location": location}},
        )
    )
    db.commit()


def _found(db, *, session_id: str, key: str, name: str) -> str:
    return found_durable_object(
        db,
        session_id=session_id,
        idempotency_key=key,
        name=name,
        description=f"A {name.lower()} deliberately made to share.",
        object_kind="stoop_test_object",
        provenance_ref=f"test:{key}",
    ).object["object_id"]


def _stoop(db, capacity: int = 3) -> WorldStoop:
    return found_world_stoop(
        db,
        stoop_id="lantern-stoop",
        title="The Lantern Stoop",
        prompt="Leave something useful or curious for whoever comes next.",
        location="Lantern Square",
        capacity=capacity,
    )


def test_leave_is_voluntary_and_take_is_first_claim_atomic(db_session, game_rules):
    _place(db_session)
    _session(db_session, "maker", "actor-maker")
    _session(db_session, "visitor", "actor-visitor")
    _stoop(db_session)
    object_id = _found(db_session, session_id="maker", key="found-lantern", name="Paper lantern")

    left = leave_object_on_stoop(
        db_session,
        session_id="maker",
        stoop_id="lantern-stoop",
        object_id=object_id,
        idempotency_key="leave-lantern",
    )
    entry_id = left["entry"]["entry_id"]

    object_row = db_session.get(DurableObject, object_id)
    assert object_row.custodian_actor_id is None
    assert object_row.location == "Lantern Square"
    assert left["entry"]["can_withdraw"] is True
    assert "left_by_actor_id" not in left["entry"]
    assert visible_durable_objects(db_session, session_id="maker") == []
    assert visible_durable_objects(db_session, session_id="visitor") == []

    browsed = browse_world_stoop(db_session, session_id="visitor", stoop_id="lantern-stoop")
    assert browsed["count"] == 1
    assert browsed["entries"][0]["can_take"] is True
    assert "created_by_actor_id" not in browsed["entries"][0]["object"]["provenance"]

    taken = take_stoop_object(
        db_session,
        session_id="visitor",
        entry_id=entry_id,
        idempotency_key="take-lantern",
    )
    replay = take_stoop_object(
        db_session,
        session_id="visitor",
        entry_id=entry_id,
        idempotency_key="take-lantern",
    )

    db_session.expire_all()
    assert taken["entry"]["status"] == "taken"
    assert replay["replayed"] is True
    assert db_session.get(DurableObject, object_id).custodian_actor_id == "actor-visitor"
    assert db_session.get(StoopObjectEntry, entry_id).status == "taken"
    assert visible_durable_objects(db_session, session_id="visitor")[0]["relation"] == "carried"
    assert db_session.query(StoopReceipt).count() == 2
    assert [row.event_type for row in db_session.query(WorldEvent).order_by(WorldEvent.id).all()][-2:] == [
        "stoop_object_left",
        "stoop_object_taken",
    ]


def test_capacity_refuses_property_instead_of_composting_it(db_session, game_rules):
    _place(db_session)
    _session(db_session, "maker", "actor-maker")
    _stoop(db_session, capacity=1)
    first_id = _found(db_session, session_id="maker", key="found-first", name="First token")
    second_id = _found(db_session, session_id="maker", key="found-second", name="Second token")
    leave_object_on_stoop(
        db_session,
        session_id="maker",
        stoop_id="lantern-stoop",
        object_id=first_id,
        idempotency_key="leave-first",
    )

    with pytest.raises(ConsequenceDomainError) as full:
        leave_object_on_stoop(
            db_session,
            session_id="maker",
            stoop_id="lantern-stoop",
            object_id=second_id,
            idempotency_key="leave-second",
        )

    assert full.value.code == "stoop_full"
    assert db_session.get(DurableObject, first_id).location == "Lantern Square"
    assert db_session.get(DurableObject, second_id).custodian_actor_id == "actor-maker"
    assert db_session.query(StoopObjectEntry).filter(StoopObjectEntry.status == "active").count() == 1
    assert local_stoops(db_session, session_id="maker")["stoops"][0]["space_remaining"] == 0


def test_only_depositor_can_withdraw_an_available_entry(db_session, game_rules):
    _place(db_session)
    _session(db_session, "maker", "actor-maker")
    _session(db_session, "visitor", "actor-visitor")
    _stoop(db_session)
    object_id = _found(db_session, session_id="maker", key="found-withdraw", name="Folded map")
    entry_id = leave_object_on_stoop(
        db_session,
        session_id="maker",
        stoop_id="lantern-stoop",
        object_id=object_id,
        idempotency_key="leave-map",
    )[
        "entry"
    ]["entry_id"]

    with pytest.raises(ConsequenceDomainError) as refused:
        withdraw_stoop_object(
            db_session,
            session_id="visitor",
            entry_id=entry_id,
            idempotency_key="visitor-withdraw",
        )
    assert refused.value.code == "not_stoop_depositor"

    withdrawn = withdraw_stoop_object(
        db_session,
        session_id="maker",
        entry_id=entry_id,
        idempotency_key="maker-withdraw",
    )
    assert withdrawn["entry"]["status"] == "withdrawn"
    assert db_session.get(DurableObject, object_id).custodian_actor_id == "actor-maker"
    assert visible_durable_objects(db_session, session_id="maker")[0]["relation"] == "carried"


def test_stoop_requires_exact_location_for_browse_and_commands(db_session, game_rules):
    _place(db_session)
    _session(db_session, "maker", "actor-maker", location="Elsewhere")
    _stoop(db_session)

    with pytest.raises(ConsequenceDomainError) as refused:
        browse_world_stoop(db_session, session_id="maker", stoop_id="lantern-stoop")

    assert refused.value.code == "stoop_not_here"
    assert local_stoops(db_session, session_id="maker")["stoops"] == []


def test_take_event_failure_rolls_back_entry_and_object(db_session, game_rules, monkeypatch):
    _place(db_session)
    _session(db_session, "maker", "actor-maker")
    _session(db_session, "visitor", "actor-visitor")
    _stoop(db_session)
    object_id = _found(db_session, session_id="maker", key="found-failure", name="Carved bird")
    entry_id = leave_object_on_stoop(
        db_session,
        session_id="maker",
        stoop_id="lantern-stoop",
        object_id=object_id,
        idempotency_key="leave-before-failure",
    )[
        "entry"
    ]["entry_id"]

    def fail_event(*_args, **_kwargs):
        raise RuntimeError("event store unavailable")

    monkeypatch.setattr("src.services.world_stoops.submit_world_event", fail_event)
    with pytest.raises(RuntimeError, match="event store unavailable"):
        take_stoop_object(
            db_session,
            session_id="visitor",
            entry_id=entry_id,
            idempotency_key="take-fails",
        )

    db_session.expire_all()
    assert db_session.get(StoopObjectEntry, entry_id).status == "active"
    assert db_session.get(DurableObject, object_id).custodian_actor_id is None
    assert db_session.get(DurableObject, object_id).location == "Lantern Square"
    assert db_session.query(StoopReceipt).count() == 1


def test_session_cleanup_preserves_stoop_evidence(db_session, game_rules):
    from src.api.game.state import _delete_session_world_rows

    _place(db_session)
    _session(db_session, "maker", "actor-maker")
    _stoop(db_session)
    object_id = _found(db_session, session_id="maker", key="found-cleanup", name="Small bell")
    leave_object_on_stoop(
        db_session,
        session_id="maker",
        stoop_id="lantern-stoop",
        object_id=object_id,
        idempotency_key="leave-before-cleanup",
    )

    deleted = _delete_session_world_rows(db_session, "maker")

    assert deleted["consequence_events_preserved"] == 2
    assert db_session.query(StoopReceipt).count() == 1
    assert db_session.query(StoopObjectEntry).count() == 1
    assert db_session.query(WorldEvent).count() == 2


def test_full_reset_deletes_stoop_history_before_objects(db_session, game_rules):
    from src.api.game.state import _delete_all_world_rows

    _place(db_session)
    _session(db_session, "maker", "actor-maker")
    _stoop(db_session)
    object_id = _found(db_session, session_id="maker", key="found-reset", name="Small bell")
    leave_object_on_stoop(
        db_session,
        session_id="maker",
        stoop_id="lantern-stoop",
        object_id=object_id,
        idempotency_key="leave-before-reset",
    )

    deleted = _delete_all_world_rows(db_session)

    assert deleted["stoop_receipts"] == 1
    assert deleted["stoop_entries"] == 1
    assert deleted["world_stoops"] == 1
    assert db_session.query(StoopReceipt).count() == 0
    assert db_session.query(StoopObjectEntry).count() == 0
    assert db_session.query(WorldStoop).count() == 0


def test_ordinary_shard_cannot_use_stoop_domain(db_session, monkeypatch):
    monkeypatch.setattr(settings, "shard_experience_path", None)
    _session(db_session, "ordinary", "ordinary-actor")

    with pytest.raises(ConsequenceDomainError) as refused:
        local_stoops(db_session, session_id="ordinary")

    assert refused.value.code == "game_capability_unavailable"
