import json
from datetime import datetime, timedelta, timezone

import pytest

from src.services.clock import ControlledClock, ScheduledEventQueue, SystemClock


def test_controlled_clock_advances_without_sleeping_or_moving_backward():
    started = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
    clock = ControlledClock(started)

    assert clock.now() == started
    assert clock.advance(timedelta(days=2)) == started + timedelta(days=2)
    with pytest.raises(ValueError, match="cannot move backward"):
        clock.advance_to(started)


def test_system_clock_reports_aware_utc():
    now = SystemClock().now()

    assert now.tzinfo == timezone.utc


def test_scheduled_events_are_offered_in_deadline_then_insertion_order():
    started = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
    queue = ScheduledEventQueue(ControlledClock(started))
    second = queue.schedule_at(
        started + timedelta(hours=2), kind="inspect", payload={"order": 2}
    )
    first_a = queue.schedule_at(
        started + timedelta(hours=1), kind="inspect", payload={"order": 1}
    )
    first_b = queue.schedule_at(
        started + timedelta(hours=1), kind="inspect", payload={"order": 1.5}
    )

    offered = queue.advance_to_next()

    assert offered == (first_a, first_b)
    assert queue.clock.now() == started + timedelta(hours=1)
    queue.acknowledge(event.event_id for event in offered)
    assert queue.advance_to_next() == (second,)


def test_unacknowledged_event_is_reoffered_after_checkpoint_restore():
    started = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
    queue = ScheduledEventQueue(ControlledClock(started))
    event = queue.schedule_at(
        started + timedelta(days=2),
        kind="resident_return",
        payload={"actor_id": "actor-ivo"},
    )
    assert queue.advance_to_next() == (event,)

    restored = ScheduledEventQueue.from_payload(queue.as_payload())

    assert restored.due_events()[0].event_id == event.event_id
    restored.acknowledge((event.event_id,))
    assert restored.due_events() == ()
    assert restored.pending == ()


def test_queue_checkpoint_is_json_safe_and_preserves_future_ids():
    started = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
    queue = ScheduledEventQueue(ControlledClock(started))
    queue.schedule_at(started + timedelta(hours=1), kind="first")
    encoded = json.loads(json.dumps(queue.as_payload()))

    restored = ScheduledEventQueue.from_payload(encoded)
    second = restored.schedule_at(started + timedelta(hours=2), kind="second")

    assert second.event_id == "scheduled-00000002"


def test_queue_cancels_only_exact_pending_event_ids():
    started = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
    queue = ScheduledEventQueue(ControlledClock(started))
    first = queue.schedule_at(started + timedelta(hours=1), kind="first")
    second = queue.schedule_at(started + timedelta(hours=2), kind="second")

    assert queue.cancel((first.event_id, "missing", "")) == (first.event_id,)
    assert queue.pending == (second,)
    assert not queue.contains(first.event_id)
    assert queue.contains(second.event_id)
    assert queue.cancel((first.event_id,)) == ()


def test_queue_rejects_past_events_and_early_acknowledgement():
    started = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
    queue = ScheduledEventQueue(ControlledClock(started))
    future = queue.schedule_at(started + timedelta(hours=1), kind="inspect")

    with pytest.raises(ValueError, match="past"):
        queue.schedule_at(started - timedelta(seconds=1), kind="inspect")
    with pytest.raises(ValueError, match="currently due"):
        queue.acknowledge((future.event_id,))
