"""Session lifecycle, state persistence, and cache-backed helpers."""

import logging
import os
import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterable, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..models import SessionVars
from .cache import TTLCacheMap
from .db_json import safe_json_dict
from .seed_data import DEFAULT_SESSION_VARS
from .spatial_navigator import SpatialNavigator
from .state_manager import AdvancedStateManager

logger = logging.getLogger(__name__)
_SESSION_MODE_CACHE = "cache"
_SESSION_MODE_STATELESS = "stateless"
_SESSION_MODE_SHARED_CACHE = "shared_cache"
_ALLOWED_SESSION_MODES = {
    _SESSION_MODE_CACHE,
    _SESSION_MODE_STATELESS,
    _SESSION_MODE_SHARED_CACHE,
}

_state_managers: TTLCacheMap = TTLCacheMap(
    settings.state_manager_cache_max_size,
    settings.state_manager_cache_ttl_seconds,
)
_spatial_navigators: TTLCacheMap = TTLCacheMap(
    settings.navigator_cache_max_size,
    settings.navigator_cache_ttl_seconds,
)
_session_locks: Dict[str, threading.RLock] = {}
_session_locks_guard = threading.Lock()
logger.info(
    "API cache config: state_managers(max=%d, ttl=%ds), navigators(max=%d, ttl=%ds)",
    settings.state_manager_cache_max_size,
    settings.state_manager_cache_ttl_seconds,
    settings.navigator_cache_max_size,
    settings.navigator_cache_ttl_seconds,
)


def get_session_consistency_mode() -> str:
    """Return normalized runtime session-consistency mode."""
    raw = str(getattr(settings, "session_consistency_mode", _SESSION_MODE_CACHE) or "")
    mode = raw.strip().lower()
    if mode not in _ALLOWED_SESSION_MODES:
        logger.warning(
            "Unknown WW_SESSION_CONSISTENCY_MODE='%s'; defaulting to '%s'.",
            raw,
            _SESSION_MODE_CACHE,
        )
        return _SESSION_MODE_CACHE
    return mode


def _uses_local_state_cache() -> bool:
    mode = get_session_consistency_mode()
    if mode == _SESSION_MODE_SHARED_CACHE:
        logger.debug("WW_SESSION_CONSISTENCY_MODE=shared_cache is configured but no external store is wired; " "falling back to stateless reconstruction semantics.")
        return False
    return mode == _SESSION_MODE_CACHE


def _get_or_create_session_lock(session_id: str) -> threading.RLock:
    with _session_locks_guard:
        lock = _session_locks.get(session_id)
        if lock is None:
            lock = threading.RLock()
            _session_locks[session_id] = lock
        return lock


@contextmanager
def session_mutation_lock(session_id: str):
    """Serialize same-session mutations within one process."""
    lock = _get_or_create_session_lock(session_id)
    lock.acquire()
    try:
        yield
    finally:
        lock.release()


def _get_db_cache_key(db: Session) -> str:
    """Return a stable cache key for the underlying database, not Session object id."""
    try:
        bind = db.get_bind()
        url = getattr(bind, "url", None)
        if url is not None:
            db_file = getattr(url, "database", None)
            if db_file:
                return os.path.abspath(str(db_file))
            return str(url)
    except Exception:
        pass
    return "default-db"


def get_spatial_navigator(db: Session) -> SpatialNavigator:
    """Create a per-request spatial navigator.

    SpatialNavigator keeps a live SQLAlchemy Session handle and mutable in-memory
    position maps. Reusing one navigator across requests can leak closed/foreign
    sessions under concurrent access, causing detached identity-map failures.
    """
    return SpatialNavigator(db)


def _sync_with_world_projection(
    session_id: str,
    db: Session,
    manager: AdvancedStateManager,
) -> None:
    try:
        from .world_memory import apply_projection_overlay_to_state_manager

        player_scoped_keys = set(DEFAULT_SESSION_VARS.keys()) | {"location"}
        apply_projection_overlay_to_state_manager(
            db,
            manager,
            player_scoped_variable_keys=player_scoped_keys,
            preserve_existing_player_values=True,
        )
    except Exception as e:
        logger.debug(
            "Could not apply world projection overlay for %s: %s",
            session_id,
            e,
        )


def get_state_manager(session_id: str, db: Session) -> AdvancedStateManager:
    """Get or create a state manager for the session."""
    use_local_cache = _uses_local_state_cache()
    if not use_local_cache or session_id not in _state_managers:
        manager = AdvancedStateManager(session_id)

        row = db.get(SessionVars, session_id)
        if row is not None and row.vars is not None:
            stored = cast(Dict[str, Any], row.vars)
            if stored.get("_v") == 2:
                # Full v2 payload: restore everything.
                manager.import_state(stored)
            else:
                # Legacy v1 payload: flat variable dict.
                manager.variables.update(stored)

        # Apply defaults only for keys not already present.
        for key, value in DEFAULT_SESSION_VARS.items():
            manager.variables.setdefault(key, value)

        _sync_with_world_projection(session_id, db, manager)
        if use_local_cache:
            _state_managers[session_id] = manager

    if not use_local_cache:
        return manager

    manager = _state_managers[session_id]
    _sync_with_world_projection(session_id, db, manager)
    return manager


def save_state(state_manager: AdvancedStateManager, db: Session) -> None:
    """Persist full session state as a v2 JSON payload."""
    session_id = state_manager.session_id

    row = db.get(SessionVars, session_id)
    if row is None:
        row = SessionVars(session_id=session_id, vars={})
        db.add(row)

    row.vars = state_manager.export_state()  # type: ignore
    db.commit()


def resolve_current_location(
    state_manager: AdvancedStateManager,
    db: Session,
) -> str:
    """Ensure current location matches a valid storylet location."""
    current_location = str(state_manager.get_variable("location", "start"))

    valid_locations = set()
    rows = db.execute(
        text(
            """
            SELECT requires
            FROM storylets
            WHERE requires IS NOT NULL
        """
        )
    ).fetchall()
    for row in rows:
        requires = safe_json_dict(row[0])
        location = requires.get("location")
        if isinstance(location, str) and location.strip():
            valid_locations.add(location.strip())

    if current_location not in valid_locations and valid_locations:
        new_location = sorted(valid_locations)[0]
        logger.info(
            "Invalid location '%s', setting to '%s'",
            current_location,
            new_location,
        )
        state_manager.set_variable("location", new_location)
        save_state(state_manager, db)
        return new_location

    return current_location


def remove_cached_sessions(session_ids: Iterable[str]) -> int:
    """Remove specific session ids from state-manager cache."""
    removed = 0
    for session_id in session_ids:
        if session_id in _state_managers:
            _state_managers.pop(session_id, None)
            removed += 1
        with _session_locks_guard:
            _session_locks.pop(session_id, None)
    return removed
