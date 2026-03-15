"""Tests for src/services/session_service.py and shared cache behavior."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from unittest.mock import Mock

from src.models import SessionVars, Storylet
from src.services.cache import TTLCacheMap
from src.services.session_service import (
    _session_locks,
    _state_managers,
    get_session_consistency_mode,
    get_state_manager,
    remove_cached_sessions,
    resolve_current_location,
    save_state,
    session_mutation_lock,
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
    _session_locks.clear()
    _state_managers.update({"a": Mock(), "b": Mock(), "orphan": Mock()})
    with session_mutation_lock("a"):
        pass
    with session_mutation_lock("b"):
        pass

    removed = remove_cached_sessions(["a", "b", "missing"])

    assert removed == 2
    assert "a" not in _state_managers
    assert "b" not in _state_managers
    assert "orphan" in _state_managers
    assert "a" not in _session_locks
    assert "b" not in _session_locks


def test_new_session_defaults_are_neutral_and_no_pickaxe(db_session):
    _state_managers.clear()
    session_id = "neutral-defaults"

    manager = get_state_manager(session_id, db_session)

    assert manager.get_variable("name") == "Adventurer"
    assert manager.get_variable("danger") == 0
    assert manager.get_variable("has_pickaxe") is None


def test_session_consistency_mode_defaults_to_cache(monkeypatch):
    monkeypatch.setattr("src.services.session_service.settings.session_consistency_mode", "cache")
    assert get_session_consistency_mode() == "cache"


def test_stateless_mode_reconstructs_manager_each_call(monkeypatch, db_session):
    _state_managers.clear()
    session_id = "stateless-reconstruct"
    monkeypatch.setattr("src.services.session_service.settings.session_consistency_mode", "stateless")

    first = get_state_manager(session_id, db_session)
    first.set_variable("gold", 3)
    save_state(first, db_session)
    second = get_state_manager(session_id, db_session)

    assert first is not second
    assert second.get_variable("gold") == 3
    assert session_id not in _state_managers


def test_session_mutation_lock_serializes_same_session_calls():
    events = []
    events_lock = Lock()

    def _work(tag: str):
        with session_mutation_lock("same-session"):
            with events_lock:
                events.append(f"{tag}-start")
            time.sleep(0.05)
            with events_lock:
                events.append(f"{tag}-end")

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(_work, "a")
        b = pool.submit(_work, "b")
        a.result(timeout=2)
        b.result(timeout=2)

    assert events in (
        ["a-start", "a-end", "b-start", "b-end"],
        ["b-start", "b-end", "a-start", "a-end"],
    )


