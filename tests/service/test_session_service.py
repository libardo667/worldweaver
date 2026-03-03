"""Tests for src/services/session_service.py and shared cache behavior."""

import time
from unittest.mock import Mock, patch

from src.models import SessionVars, Storylet
from src.services.cache import TTLCacheMap
from src.services.session_service import (
    _spatial_navigators,
    _state_managers,
    get_spatial_navigator,
    get_state_manager,
    remove_cached_sessions,
    resolve_current_location,
    save_state,
)


def test_ttl_cache_map_evicts_oldest_when_over_capacity():
    cache = TTLCacheMap(max_size=2, ttl_seconds=60)
    cache["a"] = 1
    cache["b"] = 2
    cache["c"] = 3

    assert len(cache) == 2
    assert "a" not in cache
    assert "b" in cache
    assert "c" in cache


def test_ttl_cache_map_expires_entries():
    cache = TTLCacheMap(max_size=2, ttl_seconds=1)
    cache["short"] = "lived"
    time.sleep(1.1)

    assert "short" not in cache
    assert len(cache) == 0


def test_save_state_persists_v2_payload(db_session):
    _state_managers.clear()
    session_id = "session-save-v2"

    manager = get_state_manager(session_id, db_session)
    manager.set_variable("gold", 42)
    save_state(manager, db_session)

    row = db_session.get(SessionVars, session_id)
    assert row is not None
    assert row.vars.get("_v") == 2
    assert row.vars["variables"]["gold"] == 42


def test_resolve_current_location_updates_invalid_location_and_persists(db_session):
    _state_managers.clear()
    session_id = "location-fallback"

    db_session.add(
        Storylet(
            title="Only Valid Location",
            text_template="You can only be here.",
            requires={"location": "cave"},
            choices=[{"label": "Stay", "set": {}}],
            weight=1.0,
            position={"x": 0, "y": 0},
        )
    )
    db_session.commit()

    manager = get_state_manager(session_id, db_session)
    manager.set_variable("location", "invalid-location")
    save_state(manager, db_session)

    resolved = resolve_current_location(manager, db_session)
    row = db_session.get(SessionVars, session_id)

    assert resolved == "cave"
    assert row is not None
    assert row.vars["variables"]["location"] == "cave"


def test_remove_cached_sessions_only_removes_requested_keys():
    _state_managers.clear()
    _state_managers.update({"a": Mock(), "b": Mock(), "orphan": Mock()})

    removed = remove_cached_sessions(["a", "b", "missing"])

    assert removed == 2
    assert "a" not in _state_managers
    assert "b" not in _state_managers
    assert "orphan" in _state_managers


def test_new_session_defaults_are_neutral_and_no_pickaxe(db_session):
    _state_managers.clear()
    session_id = "neutral-defaults"

    manager = get_state_manager(session_id, db_session)

    assert manager.get_variable("name") == "Adventurer"
    assert manager.get_variable("danger") == 0
    assert manager.get_variable("has_pickaxe") is None


@patch("src.services.session_service.SpatialNavigator")
def test_spatial_navigator_is_created_per_request_session(mock_navigator_cls):
    _spatial_navigators.clear()
    db_a = Mock()
    db_b = Mock()

    first = Mock()
    second = Mock()
    mock_navigator_cls.side_effect = [first, second]

    nav_a = get_spatial_navigator(db_a)
    nav_b = get_spatial_navigator(db_b)

    assert nav_a is first
    assert nav_b is second
    assert nav_a is not nav_b
    assert mock_navigator_cls.call_count == 2
