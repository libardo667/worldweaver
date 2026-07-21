from __future__ import annotations

from threading import Timer

from src.models import LocationChat, SessionVars
from src.services.live_signals import (
    current_live_signal_revision,
    notify_live_signal,
    read_live_signals,
    wait_for_live_signal_change,
)


def test_local_signal_notification_ends_a_wait_early():
    revision = current_live_signal_revision()
    timer = Timer(0.01, notify_live_signal)
    timer.start()
    try:
        changed = wait_for_live_signal_change(
            after_revision=revision,
            timeout=1.0,
        )
    finally:
        timer.join()

    assert changed is True


def test_live_signals_read_current_v2_session_location(db_session):
    db_session.add(
        SessionVars(
            session_id="resident-session",
            actor_id="resident-actor",
            vars={"_v": 2, "variables": {"location": "Commons Bank"}},
        )
    )
    archived = LocationChat(
        location="Commons Bank",
        session_id="archived-speaker",
        actor_id="archived-actor",
        display_name="Archived Speaker",
        message="This predates the cursor.",
    )
    db_session.add(archived)
    db_session.commit()

    established = read_live_signals(
        db_session,
        session_id="resident-session",
        after_id=None,
        cursor_shard=None,
        cursor_location=None,
        limit=10,
    )

    assert established["cursor_status"] == "established"
    assert established["cursor"]["location"] == "Commons Bank"
    assert established["cursor"]["after_id"] == archived.id
    assert established["events"] == []

    current = LocationChat(
        location="Commons Bank",
        session_id="current-speaker",
        actor_id="current-actor",
        display_name="Current Speaker",
        message="This follows the cursor.",
    )
    db_session.add(current)
    db_session.commit()

    delivered = read_live_signals(
        db_session,
        session_id="resident-session",
        after_id=established["cursor"]["after_id"],
        cursor_shard=established["cursor"]["shard_id"],
        cursor_location=established["cursor"]["location"],
        limit=10,
    )

    assert delivered["cursor_status"] == "current"
    assert delivered["cursor"]["after_id"] == current.id
    assert [event["id"] for event in delivered["events"]] == [current.id]
