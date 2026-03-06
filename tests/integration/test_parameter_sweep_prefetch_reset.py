from __future__ import annotations

from playtest_harness.long_run_harness import (
    _is_reset_clean,
    _prefetch_status_complete,
    _resolve_prefetch_wait_timeout_seconds,
)


def test_prefetch_status_complete_uses_stable_shape_fields() -> None:
    assert _prefetch_status_complete({"stubs_cached": 1, "expires_in_seconds": 0}) is True
    assert _prefetch_status_complete({"stubs_cached": 0, "expires_in_seconds": 10}) is True
    assert _prefetch_status_complete({"stubs_cached": 0, "expires_in_seconds": 0}) is False


def test_prefetch_status_complete_honors_legacy_field_when_present() -> None:
    assert _prefetch_status_complete({"prefetch_complete": True}) is True
    assert _prefetch_status_complete({"prefetch_complete": False, "stubs_cached": 99, "expires_in_seconds": 99}) is False


def test_resolve_prefetch_wait_timeout_defaults_by_policy() -> None:
    assert _resolve_prefetch_wait_timeout_seconds(policy="off", configured=None) == 0.0
    assert _resolve_prefetch_wait_timeout_seconds(policy="bounded", configured=None) > 0.0
    assert _resolve_prefetch_wait_timeout_seconds(policy="strict", configured=None) >= 10.0
    assert _resolve_prefetch_wait_timeout_seconds(policy="bounded", configured=2.5) == 2.5


def test_is_reset_clean_requires_all_zero_counters() -> None:
    assert (
        _is_reset_clean(
            {
                "world_history_count": 0,
                "world_projection_count": 0,
                "storylet_count": 0,
                "prefetch_stubs_cached": 0,
            }
        )
        is True
    )
    assert (
        _is_reset_clean(
            {
                "world_history_count": 1,
                "world_projection_count": 0,
                "storylet_count": 0,
                "prefetch_stubs_cached": 0,
            }
        )
        is False
    )
