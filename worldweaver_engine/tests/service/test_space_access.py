from pathlib import Path

import pytest

from src.config import settings
from src.models import (
    SessionVars,
    SpaceAccessGrant,
    SpaceAccessPolicy,
    SpaceAccessReceipt,
    SpaceAccessRequest,
    WorldEvent,
    WorldNode,
)
from src.services.space_access import (
    SpaceAccessError,
    access_status,
    assert_route_entry_allowed,
    found_space_policy,
    invite_to_space,
    pending_requests,
    request_space_access,
    resolve_access_request,
    revoke_space_access,
    set_space_mode,
)


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


def _place(db, name: str = "Rowan's Workshop") -> None:
    db.add(
        WorldNode(
            node_type="sublocation",
            name=name,
            normalized_name=name.lower().replace(" ", "_"),
            metadata_json={"parent_location": "Town Square", "persistence": "durable"},
        )
    )
    db.commit()


def _session(db, session_id: str, actor_id: str, location: str = "Town Square") -> None:
    db.add(
        SessionVars(
            session_id=session_id,
            actor_id=actor_id,
            vars={"_v": 2, "variables": {"location": location}},
        )
    )
    db.commit()


def test_unlisted_place_remains_public(db_session, game_rules):
    _session(db_session, "visitor", "actor-visitor")

    status = access_status(db_session, session_id="visitor", location="Town Square")
    assert status["mode"] == "public"
    assert status["can_enter"] is True
    assert status["entry_reason"] == "no_restriction"

    assert_route_entry_allowed(
        db_session, session_id="visitor", destinations=["Town Square"]
    )


def test_private_and_closed_modes_are_destination_only(db_session, game_rules):
    _place(db_session)
    _session(db_session, "controller", "actor-controller")
    _session(db_session, "visitor", "actor-visitor", location="Rowan's Workshop")
    found_space_policy(
        db_session,
        location="Rowan's Workshop",
        controller_actor_id="actor-controller",
        mode="private",
    )

    with pytest.raises(SpaceAccessError, match="need permission") as refused:
        assert_route_entry_allowed(
            db_session,
            session_id="visitor",
            destinations=["Rowan's Workshop"],
        )
    assert refused.value.code == "space_access_required"

    # The entry check has no origin argument: being inside never blocks leaving.
    assert_route_entry_allowed(
        db_session, session_id="visitor", destinations=["Town Square"]
    )
    assert_route_entry_allowed(
        db_session, session_id="controller", destinations=["Rowan's Workshop"]
    )

    set_space_mode(
        db_session,
        session_id="controller",
        location="Rowan's Workshop",
        mode="closed",
        idempotency_key="close-workshop",
    )
    with pytest.raises(SpaceAccessError) as closed:
        assert_route_entry_allowed(
            db_session,
            session_id="controller",
            destinations=["Rowan's Workshop"],
        )
    assert closed.value.code == "space_closed"
    event = db_session.query(WorldEvent).one()
    receipt = db_session.query(SpaceAccessReceipt).one()
    assert event.event_type == "space_mode_changed"
    assert event.world_state_delta["space_access"]["after_mode"] == "closed"
    assert receipt.world_event_id == event.id


def test_request_admission_and_revocation_leave_retry_safe_receipts(
    db_session, game_rules
):
    _place(db_session)
    _session(db_session, "controller", "actor-controller")
    _session(db_session, "visitor", "actor-visitor")
    found_space_policy(
        db_session,
        location="Rowan's Workshop",
        controller_actor_id="actor-controller",
        mode="requestable",
    )

    command = {
        "session_id": "visitor",
        "location": "Rowan's Workshop",
        "idempotency_key": "knock-once",
        "note": "May I look at the tools?",
    }
    first = request_space_access(db_session, **command)
    replay = request_space_access(db_session, **command)
    request_id = first["receipt"]["result"]["request"]["request_id"]

    assert replay["replayed"] is True
    assert replay["receipt"]["receipt_id"] == first["receipt"]["receipt_id"]
    assert (
        pending_requests(
            db_session,
            session_id="controller",
            location="Rowan's Workshop",
        )["count"]
        == 1
    )

    admitted = resolve_access_request(
        db_session,
        session_id="controller",
        request_id=request_id,
        decision="admitted",
        idempotency_key="admit-visitor",
    )
    assert admitted["receipt"]["result"]["request"]["status"] == "admitted"
    assert (
        access_status(
            db_session,
            session_id="visitor",
            location="Rowan's Workshop",
        )["can_enter"]
        is True
    )

    revoked = revoke_space_access(
        db_session,
        session_id="controller",
        recipient_session_id="visitor",
        location="Rowan's Workshop",
        idempotency_key="revoke-visitor",
    )
    assert revoked["receipt"]["result"]["grant"]["active"] is False
    assert (
        access_status(
            db_session,
            session_id="visitor",
            location="Rowan's Workshop",
        )["can_enter"]
        is False
    )
    assert db_session.query(SpaceAccessRequest).one().status == "admitted"
    assert db_session.query(SpaceAccessGrant).one().active is False
    assert db_session.query(SpaceAccessReceipt).count() == 3


def test_invitation_follows_actor_identity_across_sessions(db_session, game_rules):
    _place(db_session)
    _session(db_session, "controller", "actor-controller")
    _session(db_session, "visitor-old", "actor-visitor")
    _session(db_session, "visitor-new", "actor-visitor")
    found_space_policy(
        db_session,
        location="Rowan's Workshop",
        controller_actor_id="actor-controller",
        mode="private",
    )

    invite_to_space(
        db_session,
        session_id="controller",
        recipient_session_id="visitor-old",
        location="Rowan's Workshop",
        idempotency_key="invite-visitor",
    )

    controller_view = access_status(
        db_session,
        session_id="controller",
        location="Rowan's Workshop",
    )
    assert controller_view["active_grants"] == [
        {"actor_id": "actor-visitor", "session_id": "visitor-new"}
    ]
    assert (
        access_status(
            db_session,
            session_id="visitor-new",
            location="Rowan's Workshop",
        )["can_enter"]
        is True
    )
    assert_route_entry_allowed(
        db_session,
        session_id="visitor-new",
        destinations=["Rowan's Workshop"],
    )
    assert db_session.query(WorldEvent).count() == 0


def test_public_mode_event_failure_rolls_back_policy_and_receipt(
    db_session,
    game_rules,
    monkeypatch,
):
    _place(db_session)
    _session(db_session, "controller", "actor-controller")
    found_space_policy(
        db_session,
        location="Rowan's Workshop",
        controller_actor_id="actor-controller",
        mode="private",
    )

    def fail_event(*_args, **_kwargs):
        raise RuntimeError("event store unavailable")

    monkeypatch.setattr("src.services.space_access.submit_world_event", fail_event)

    with pytest.raises(RuntimeError, match="event store unavailable"):
        set_space_mode(
            db_session,
            session_id="controller",
            location="Rowan's Workshop",
            mode="public",
            idempotency_key="open-workshop",
        )

    db_session.rollback()
    db_session.expire_all()
    assert db_session.get(SpaceAccessPolicy, "Rowan's Workshop").mode == "private"
    assert db_session.query(SpaceAccessReceipt).count() == 0
    assert db_session.query(WorldEvent).count() == 0


def test_session_cleanup_preserves_public_access_evidence(db_session, game_rules):
    from src.api.game.state import _delete_session_world_rows

    _place(db_session)
    _session(db_session, "controller", "actor-controller")
    found_space_policy(
        db_session,
        location="Rowan's Workshop",
        controller_actor_id="actor-controller",
        mode="private",
    )
    set_space_mode(
        db_session,
        session_id="controller",
        location="Rowan's Workshop",
        mode="public",
        idempotency_key="open-before-leaving",
    )

    deleted = _delete_session_world_rows(db_session, "controller")

    assert deleted["sessions"] == 1
    assert deleted["consequence_events_preserved"] == 1
    assert db_session.query(SpaceAccessReceipt).count() == 1
    assert db_session.query(WorldEvent).count() == 1


def test_ordinary_shard_cannot_create_access_machinery(db_session, monkeypatch):
    monkeypatch.setattr(settings, "shard_experience_path", None)
    _place(db_session)

    with pytest.raises(SpaceAccessError) as refused:
        found_space_policy(
            db_session,
            location="Rowan's Workshop",
            controller_actor_id="actor-controller",
        )

    assert refused.value.code == "game_capability_unavailable"
