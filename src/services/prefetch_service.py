"""Background frontier prefetch for low-latency storylet selection."""

import logging
import threading
import time
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, cast

from sqlalchemy import or_
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings
from ..database import SessionLocal
from ..models import Storylet
from .storylet_utils import find_storylet_by_location, normalize_choice, storylet_location

logger = logging.getLogger(__name__)

_session_frontier_cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_last_schedule_at: Dict[str, float] = {}
_inflight_sessions: set[str] = set()
_cache_lock = threading.Lock()


def _cache_capacity() -> int:
    return max(1, int(settings.state_manager_cache_max_size))


def _ttl_seconds() -> int:
    return max(1, int(settings.prefetch_ttl_seconds))


def _stub_cap_per_session() -> int:
    return max(0, int(settings.prefetch_max_per_session))


def _schedule_window_seconds() -> int:
    return max(1, int(settings.prefetch_idle_trigger_seconds))


def _now_mono() -> float:
    return time.monotonic()


def _safe_session_id(session_id: Any) -> str:
    return str(session_id or "").strip()


def _purge_expired_locked(now: float) -> None:
    expired = [session_id for session_id, payload in _session_frontier_cache.items() if float(payload.get("expires_at_mono", 0.0)) <= now]
    for session_id in expired:
        _session_frontier_cache.pop(session_id, None)


def _store_frontier_locked(
    session_id: str,
    stubs: List[Dict[str, Any]],
    directional_leads: List[Dict[str, Any]],
    context_summary: Dict[str, Any],
    now: float,
) -> Dict[str, Any]:
    expires_at = now + _ttl_seconds()
    stub_cap = _stub_cap_per_session()
    trimmed_stubs = stubs[:stub_cap] if stub_cap > 0 else []
    payload = {
        "session_id": session_id,
        "stubs": trimmed_stubs,
        "directional_leads": directional_leads[:stub_cap] if stub_cap > 0 else [],
        "context_summary": dict(context_summary),
        "created_at_mono": now,
        "expires_at_mono": expires_at,
    }

    if session_id in _session_frontier_cache:
        _session_frontier_cache.pop(session_id, None)
    _session_frontier_cache[session_id] = payload
    while len(_session_frontier_cache) > _cache_capacity():
        _session_frontier_cache.popitem(last=False)
    return payload


def _copy_frontier(payload: Optional[Dict[str, Any]], now: float) -> Optional[Dict[str, Any]]:
    if not payload:
        return None
    ttl_remaining = max(0, int(round(float(payload.get("expires_at_mono", now)) - now)))
    return {
        "session_id": str(payload.get("session_id", "")),
        "stubs": [dict(item) for item in cast(List[Dict[str, Any]], payload.get("stubs", []))],
        "directional_leads": [dict(item) for item in cast(List[Dict[str, Any]], payload.get("directional_leads", []))],
        "context_summary": dict(cast(Dict[str, Any], payload.get("context_summary", {}))),
        "expires_in_seconds": ttl_remaining,
    }


def clear_prefetch_cache() -> None:
    """Reset all in-memory prefetch cache and scheduling metadata."""
    with _cache_lock:
        _session_frontier_cache.clear()
        _last_schedule_at.clear()
        _inflight_sessions.clear()


def get_frontier_status(session_id: str) -> Dict[str, int]:
    """Return current cached frontier count + TTL for one session."""
    safe_session_id = _safe_session_id(session_id)
    if not safe_session_id:
        return {"stubs_cached": 0, "expires_in_seconds": 0}

    now = _now_mono()
    with _cache_lock:
        _purge_expired_locked(now)
        payload = _session_frontier_cache.get(safe_session_id)
        if payload is None:
            return {"stubs_cached": 0, "expires_in_seconds": 0}
        ttl_remaining = max(0, int(round(float(payload.get("expires_at_mono", now)) - now)))
        return {
            "stubs_cached": len(cast(List[Dict[str, Any]], payload.get("stubs", []))),
            "expires_in_seconds": ttl_remaining,
        }


def get_cached_frontier(session_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a session frontier cache snapshot when present and not expired."""
    safe_session_id = _safe_session_id(session_id)
    if not safe_session_id:
        return None

    now = _now_mono()
    with _cache_lock:
        _purge_expired_locked(now)
        payload = _session_frontier_cache.get(safe_session_id)
        return _copy_frontier(payload, now)


def set_prefetched_stubs_for_session(
    session_id: str,
    stubs: Sequence[Dict[str, Any]],
    context_summary: Optional[Dict[str, Any]] = None,
    directional_leads: Optional[Sequence[Dict[str, Any]]] = None,
) -> None:
    """Directly seed prefetch cache for tests/debug flows."""
    safe_session_id = _safe_session_id(session_id)
    if not safe_session_id:
        return

    now = _now_mono()
    with _cache_lock:
        _purge_expired_locked(now)
        _store_frontier_locked(
            safe_session_id,
            [dict(item) for item in stubs],
            [dict(item) for item in (directional_leads or [])],
            dict(context_summary or {}),
            now,
        )


def _active_storylets(db: Session) -> List[Storylet]:
    now_utc = datetime.now(UTC).replace(tzinfo=None)
    return db.query(Storylet).filter(or_(Storylet.expires_at.is_(None), Storylet.expires_at > now_utc)).all()


def _compact_text(text: Any, max_len: int = 180) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[: max_len - 3].rstrip()}..."


def _normalize_stub_choices(raw_choices: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(raw_choices, list):
        return out
    for raw in raw_choices[:3]:
        if isinstance(raw, dict):
            out.append(normalize_choice(raw))
    return out


def _resolve_position(storylet: Storylet) -> Optional[Dict[str, int]]:
    position = storylet.position if isinstance(storylet.position, dict) else None
    if isinstance(position, dict) and "x" in position and "y" in position:
        try:
            return {"x": int(position["x"]), "y": int(position["y"])}
        except (TypeError, ValueError):
            return None
    return None


def _collect_storylet_positions(storylets: Iterable[Storylet]) -> Dict[int, Dict[str, int]]:
    out: Dict[int, Dict[str, int]] = {}
    for storylet in storylets:
        if storylet.id is None:
            continue
        position = _resolve_position(storylet)
        if position is not None:
            out[int(storylet.id)] = position
    return out


def _direction_from_delta(dx: int, dy: int) -> str:
    if dx == 0 and dy == 0:
        return "here"
    vertical = ""
    horizontal = ""
    if dy < 0:
        vertical = "north"
    elif dy > 0:
        vertical = "south"
    if dx > 0:
        horizontal = "east"
    elif dx < 0:
        horizontal = "west"
    if vertical and horizontal:
        return f"{vertical}{horizontal}"
    return vertical or horizontal or "here"


def _build_directional_leads(
    selected_storylets: Sequence[Storylet],
    current_position: Optional[Dict[str, int]],
) -> List[Dict[str, Any]]:
    if current_position is None:
        return []
    leads: List[Dict[str, Any]] = []
    for storylet in selected_storylets:
        if storylet.id is None:
            continue
        position = _resolve_position(storylet)
        if position is None:
            continue
        dx = int(position["x"]) - int(current_position["x"])
        dy = int(position["y"]) - int(current_position["y"])
        leads.append(
            {
                "storylet_id": int(storylet.id),
                "direction": _direction_from_delta(dx, dy),
                "x": int(position["x"]),
                "y": int(position["y"]),
                "title": str(storylet.title),
            }
        )
    return leads


def _select_prefetch_storylets(
    db: Session,
    state_manager: Any,
    trigger: str,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    from . import world_memory
    from .semantic_selector import compute_player_context_vector, score_storylets
    from .storylet_selector import _synthesize_runtime_storylets

    current_location = str(state_manager.get_variable("location", "start") or "start")
    eligible: List[Storylet] = []
    for storylet in _active_storylets(db):
        requires = cast(Dict[str, Any], storylet.requires or {})
        if state_manager.evaluate_condition(requires):
            eligible.append(storylet)

    stub_cap = _stub_cap_per_session()
    if stub_cap <= 0 or not eligible:
        return (
            [],
            [],
            {
                "trigger": trigger,
                "location": current_location,
                "eligible_count": len(eligible),
                "cached_count": 0,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

    location_target = min(max(1, stub_cap // 2), stub_cap)
    semantic_target = max(0, stub_cap - location_target)
    selected: List[Storylet] = []
    selected_ids: set[int] = set()
    semantic_scores: Dict[int, float] = {}

    for storylet in eligible:
        if len(selected) >= location_target:
            break
        if storylet_location(storylet) == current_location and storylet.id is not None:
            selected.append(storylet)
            selected_ids.add(int(storylet.id))

    if semantic_target > 0:
        semantic_candidates = [storylet for storylet in eligible if storylet.embedding and storylet.id is not None and int(storylet.id) not in selected_ids]
        if semantic_candidates:
            try:
                context_vector = compute_player_context_vector(
                    state_manager=state_manager,
                    world_memory_module=world_memory,
                    db=db,
                )
                scored = score_storylets(
                    context_vector,
                    semantic_candidates,
                    recent_storylet_ids=[],
                    active_beats=state_manager.get_active_narrative_beats(),
                    storylet_positions=_collect_storylet_positions(semantic_candidates),
                )
                scored_sorted = sorted(scored, key=lambda item: float(item[1]), reverse=True)
                for storylet, score in scored_sorted:
                    if len(selected) >= stub_cap:
                        break
                    if storylet.id is None:
                        continue
                    storylet_id = int(storylet.id)
                    if storylet_id in selected_ids:
                        continue
                    selected.append(storylet)
                    selected_ids.add(storylet_id)
                    semantic_scores[storylet_id] = float(score)
                    if len(semantic_scores) >= semantic_target:
                        break
            except Exception as exc:
                logger.debug("Prefetch semantic lead scoring failed: %s", exc)

    if len(selected) < stub_cap:
        for storylet in eligible:
            if len(selected) >= stub_cap:
                break
            if storylet.id is None:
                continue
            storylet_id = int(storylet.id)
            if storylet_id in selected_ids:
                continue
            selected.append(storylet)
            selected_ids.add(storylet_id)

    stubs: List[Dict[str, Any]] = []
    for storylet in selected[:stub_cap]:
        if storylet.id is None:
            continue
        storylet_id = int(storylet.id)
        stubs.append(
            {
                "storylet_id": storylet_id,
                "title": str(storylet.title),
                "premise": _compact_text(storylet.text_template),
                "requires": cast(Dict[str, Any], storylet.requires or {}),
                "choices": _normalize_stub_choices(storylet.choices),
                "location": storylet_location(storylet),
                "position": _resolve_position(storylet),
                "semantic_score": semantic_scores.get(storylet_id),
                "source": str(storylet.source or "authored"),
            }
        )

    # Trigger runtime synthesis for sparse contexts
    if len(stubs) < stub_cap and settings.enable_runtime_storylet_synthesis:
        try:
            synthesized = _synthesize_runtime_storylets(db, state_manager)
            for storylet in synthesized:
                if len(stubs) >= stub_cap:
                    break
                # Transient stubs don't have an ID yet, use a negative ID placeholder
                temp_id = -(len(stubs) + 1)
                stubs.append(
                    {
                        "storylet_id": temp_id,
                        "is_stub": True,
                        "title": str(storylet.title),
                        "premise": _compact_text(storylet.text_template),
                        "requires": cast(Dict[str, Any], storylet.requires or {}),
                        "choices": _normalize_stub_choices(storylet.choices),
                        "location": storylet_location(storylet),
                        "position": _resolve_position(storylet),
                        "semantic_score": None,  # Stubs aren't semantically scored yet
                        "source": str(storylet.source or "runtime_synthesis"),
                        "raw_storylet": storylet,  # Stash the full object
                    }
                )
        except Exception as exc:
            logger.warning("Prefetch runtime synthesis failed: %s", exc)

    current_storylet = find_storylet_by_location(db, current_location)
    current_position = _resolve_position(current_storylet) if current_storylet is not None else None
    directional_leads = _build_directional_leads(selected, current_position)

    context_summary: Dict[str, Any] = {
        "trigger": trigger,
        "location": current_location,
        "eligible_count": len(eligible),
        "cached_count": len(stubs),
        "generated_at": datetime.now(UTC).isoformat(),
    }
    return stubs, directional_leads, context_summary


def refresh_frontier_for_session(
    session_id: str,
    trigger: str = "manual",
    db: Optional[Session] = None,
    bind: Any = None,
) -> Optional[Dict[str, Any]]:
    """Build and cache prefetch artifacts for one session (read-only)."""
    safe_session_id = _safe_session_id(session_id)
    if not safe_session_id or not settings.enable_frontier_prefetch:
        return None

    from .session_service import get_state_manager

    owns_db = False
    active_db = db
    if active_db is None:
        owns_db = True
        if bind is None:
            active_db = SessionLocal()
        else:
            scoped = sessionmaker(bind=bind, autocommit=False, autoflush=False)
            active_db = scoped()

    started = time.perf_counter()
    try:
        state_manager = get_state_manager(safe_session_id, cast(Session, active_db))
        stubs, directional_leads, context_summary = _select_prefetch_storylets(
            cast(Session, active_db),
            state_manager,
            trigger,
        )
        now = _now_mono()
        with _cache_lock:
            _purge_expired_locked(now)
            payload = _store_frontier_locked(
                safe_session_id,
                stubs,
                directional_leads,
                context_summary,
                now,
            )
            out = _copy_frontier(payload, now)
        logger.info(
            "Prefetch refreshed for session=%s trigger=%s cached=%d duration_ms=%.3f",
            safe_session_id,
            trigger,
            len(stubs),
            (time.perf_counter() - started) * 1000.0,
        )
        return out
    except Exception as exc:
        logger.debug("Prefetch refresh failed for session=%s: %s", safe_session_id, exc)
        return None
    finally:
        if owns_db and active_db is not None:
            active_db.close()


def _finish_inflight(session_id: str) -> None:
    with _cache_lock:
        _inflight_sessions.discard(session_id)


def _run_prefetch_job(session_id: str, trigger: str, bind: Any = None) -> None:
    try:
        refresh_frontier_for_session(session_id=session_id, trigger=trigger, bind=bind)
    finally:
        _finish_inflight(session_id)


def schedule_frontier_prefetch(
    session_id: str,
    trigger: str = "unknown",
    bind: Any = None,
) -> bool:
    """Schedule a best-effort background prefetch without blocking requests."""
    safe_session_id = _safe_session_id(session_id)
    if not safe_session_id or not settings.enable_frontier_prefetch:
        return False

    now = _now_mono()
    with _cache_lock:
        _purge_expired_locked(now)
        if safe_session_id in _inflight_sessions:
            return False
        min_gap = _schedule_window_seconds()
        last = float(_last_schedule_at.get(safe_session_id, 0.0))
        if now - last < float(min_gap):
            return False
        _last_schedule_at[safe_session_id] = now
        _inflight_sessions.add(safe_session_id)

    worker = threading.Thread(
        target=_run_prefetch_job,
        args=(safe_session_id, trigger, bind),
        daemon=True,
        name=f"ww-prefetch-{safe_session_id[:12]}",
    )
    try:
        worker.start()
        return True
    except Exception:
        _finish_inflight(safe_session_id)
        return False


def select_prefetched_storylet(
    session_id: str,
    eligible_storylets: Sequence[Storylet],
    current_location: str,
    recent_storylet_ids: Optional[Sequence[int]] = None,
) -> Optional[Storylet]:
    """Return one eligible cached storylet, preferring location + non-recent items."""
    safe_session_id = _safe_session_id(session_id)
    if not safe_session_id or not settings.enable_frontier_prefetch:
        return None

    frontier = get_cached_frontier(safe_session_id)
    if not frontier:
        return None

    by_id: Dict[int, Storylet] = {}
    for storylet in eligible_storylets:
        if storylet.id is not None:
            by_id[int(storylet.id)] = storylet

    if not by_id:
        return None

    current_location_text = str(current_location or "").strip()
    recent_ids = {int(item) for item in (recent_storylet_ids or [])}
    ranked: List[tuple[tuple[int, int, float, int], Storylet]] = []
    stubs = cast(List[Dict[str, Any]], frontier.get("stubs", []))
    for idx, stub in enumerate(stubs):
        # Handle transient stubs
        if stub.get("is_stub"):
            storylet = stub.get("raw_storylet")
            if not isinstance(storylet, Storylet):
                continue
            stub_location = str(stub.get("location") or "").strip()
            location_miss = 0 if stub_location and stub_location == current_location_text else 1
            # Ranking: Not recent (0), location miss, semantic score prioritizes stubs slightly
            rank = (0, location_miss, -1.0, idx)
            ranked.append((rank, storylet))
            continue

        raw_storylet_id = stub.get("storylet_id")
        if raw_storylet_id is None:
            continue
        try:
            storylet_id = int(raw_storylet_id)
        except (TypeError, ValueError):
            continue
        storylet = by_id.get(storylet_id)
        if storylet is None:
            continue
        stub_location = str(stub.get("location") or "").strip()
        location_miss = 0 if stub_location and stub_location == current_location_text else 1
        is_recent = 1 if storylet_id in recent_ids else 0
        semantic_score = float(stub.get("semantic_score") or 0.0)
        rank = (is_recent, location_miss, -semantic_score, idx)
        ranked.append((rank, storylet))

    if not ranked:
        return None

    ranked.sort(key=lambda pair: pair[0])
    return ranked[0][1]
