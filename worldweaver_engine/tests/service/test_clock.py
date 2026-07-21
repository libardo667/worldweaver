from datetime import datetime, timedelta, timezone

import pytest

from src.services.clock import ControlledClock, SystemClock


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
