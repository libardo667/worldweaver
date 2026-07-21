from __future__ import annotations

from threading import Timer

from src.services.live_signals import (
    current_live_signal_revision,
    notify_live_signal,
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
