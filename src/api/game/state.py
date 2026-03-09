"""Session state and maintenance endpoints."""

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from ...database import SessionLocal, get_db
from ...config import settings
from ...models import (
    SessionVars,
    Storylet,
    WorldEdge,
    WorldEvent,
    WorldFact,
    WorldNode,
    WorldProjection,
)
from ...models.schemas import (
    GoalMilestoneRequest,
    GoalUpdateRequest,
    NextReq,
    SessionBootstrapRequest,
    SessionBootstrapResponse,
    SessionStartResponse,
    SessionId,
    WorldSeedRequest,
    WorldSeedResponse,
)
from ...services import session_service
from ...services.session_service import (
    remove_cached_sessions,
    resolve_current_location,
    save_state,
    get_state_manager,
)
from ...services.seed_data import (
    seed_if_empty_sync,
    seed_legacy_storylets_if_empty_sync,
)
from ...services.storylet_selector import _runtime_synthesis_counts
from ...services.world_bootstrap_service import bootstrap_world_storylets
from ...services.prefetch_service import clear_prefetch_cache, clear_prefetch_cache_for_session

router = APIRouter()

# Re-export shared caches for compatibility with existing tests/fixtures.
_state_managers = session_service._state_managers
_spatial_navigators = session_service._spatial_navigators

# Compatibility aliases for existing imports/tests while keeping internals in services.
save_state_to_db = save_state
_resolve_current_location = resolve_current_location


@router.get("/state/{session_id}")
def get_state_summary(session_id: SessionId, db: Session = Depends(get_db)):
    """Get a comprehensive summary of the session state."""
    state_manager = get_state_manager(session_id, db)
    return state_manager.get_state_summary()


@router.post("/state/{session_id}/relationship")
def update_relationship(
    session_id: SessionId,
    entity_a: str,
    entity_b: str,
    changes: Dict[str, float],
    memory: str | None = None,
    db: Session = Depends(get_db),
):
    """Update a relationship between entities."""
    state_manager = get_state_manager(session_id, db)
    relationship = state_manager.update_relationship(entity_a, entity_b, changes, memory)
    save_state_to_db(state_manager, db)

    return {
        "relationship": f"{entity_a}-{entity_b}",
        "disposition": relationship.get_overall_disposition(),
        "trust": relationship.trust,
        "respect": relationship.respect,
        "interaction_count": relationship.interaction_count,
    }


@router.post("/state/{session_id}/item")
def add_item_to_inventory(
    session_id: SessionId,
    item_id: str,
    name: str,
    quantity: int = 1,
    properties: Dict[str, Any] | None = None,
    db: Session = Depends(get_db),
):
    """Add an item to the player's inventory."""
    state_manager = get_state_manager(session_id, db)
    item = state_manager.add_item(item_id, name, quantity, properties or {})
    save_state_to_db(state_manager, db)

    return {
        "item_id": item.id,
        "name": item.name,
        "quantity": item.quantity,
        "condition": item.condition,
        "available_actions": item.get_available_actions(state_manager.get_contextual_variables()),
    }


@router.post("/state/{session_id}/environment")
def update_environment(
    session_id: SessionId,
    changes: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """Update environmental conditions."""
    state_manager = get_state_manager(session_id, db)
    state_manager.update_environment(changes)
    save_state_to_db(state_manager, db)

    return {
        "environment": {
            "time_of_day": state_manager.environment.time_of_day,
            "weather": state_manager.environment.weather,
            "danger_level": state_manager.environment.danger_level,
            "mood_modifiers": state_manager.environment.get_mood_modifier(),
        }
    }


@router.post("/state/{session_id}/goal")
def update_goal_state(
    session_id: SessionId,
    payload: GoalUpdateRequest,
    db: Session = Depends(get_db),
):
    """Create or update primary goal and goal signals for a session."""
    state_manager = get_state_manager(session_id, db)
    if payload.primary_goal is None and payload.subgoals is None and payload.urgency is None and payload.complication is None:
        raise HTTPException(status_code=422, detail="Goal update payload is empty.")

    goal = state_manager.set_goal_state(
        primary_goal=payload.primary_goal,
        subgoals=payload.subgoals,
        urgency=payload.urgency,
        complication=payload.complication,
        note=payload.note,
        source="api",
    )
    save_state_to_db(state_manager, db)
    return {"goal": goal, "arc_timeline": state_manager.get_arc_timeline(limit=20)}


@router.post("/state/{session_id}/goal/milestone")
def add_goal_milestone(
    session_id: SessionId,
    payload: GoalMilestoneRequest,
    db: Session = Depends(get_db),
):
    """Append a goal milestone and update urgency/complication signals."""
    state_manager = get_state_manager(session_id, db)
    goal = state_manager.mark_goal_milestone(
        payload.title,
        status=payload.status,
        note=str(payload.note or ""),
        source="api",
        urgency_delta=payload.urgency_delta,
        complication_delta=payload.complication_delta,
    )
    save_state_to_db(state_manager, db)
    return {"goal": goal, "arc_timeline": state_manager.get_arc_timeline(limit=20)}


def _seed_if_test_db() -> None:
    """Seed legacy test database file when running spatial tests."""
    try:
        if os.getenv("DW_DB_PATH") == "test_database.db":
            db = SessionLocal()
            seed_legacy_storylets_if_empty_sync(db)
            db.commit()
            db.close()
    except Exception:
        pass


_seed_if_test_db()


def _bootstrap_input_hash(payload: SessionBootstrapRequest) -> str:
    canonical_payload = {
        "world_theme": payload.world_theme,
        "player_role": payload.player_role,
        "description": payload.description or "",
        "key_elements": payload.key_elements,
        "tone": payload.tone,
        "storylet_count": payload.storylet_count,
        "bootstrap_source": payload.bootstrap_source,
    }
    encoded = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _clear_runtime_caches() -> None:
    _state_managers.clear()
    _spatial_navigators.clear()
    _runtime_synthesis_counts.clear()
    clear_prefetch_cache()


def _clear_runtime_session_caches(session_id: str) -> None:
    safe_session_id = str(session_id or "").strip()
    if not safe_session_id:
        return
    remove_cached_sessions([safe_session_id])
    _spatial_navigators.pop(safe_session_id, None)
    _runtime_synthesis_counts.pop(safe_session_id, None)
    clear_prefetch_cache_for_session(safe_session_id)


def _delete_session_world_rows(db: Session, session_id: str) -> Dict[str, int]:
    safe_session_id = str(session_id or "").strip()
    if not safe_session_id:
        return {
            "sessions": 0,
            "world_events": 0,
            "world_facts": 0,
            "world_edges": 0,
            "world_projection": 0,
        }

    session_event_ids = [int(row[0]) for row in db.query(WorldEvent.id).filter(WorldEvent.session_id == safe_session_id).all() if row[0] is not None]

    projection_rows_deleted = 0
    edge_rows_deleted = 0
    if session_event_ids:
        projection_rows_deleted = db.query(WorldProjection).filter(WorldProjection.source_event_id.in_(session_event_ids)).delete(synchronize_session=False)
        edge_rows_deleted = db.query(WorldEdge).filter(WorldEdge.source_event_id.in_(session_event_ids)).delete(synchronize_session=False)

    fact_filter = WorldFact.session_id == safe_session_id
    if session_event_ids:
        fact_filter = or_(fact_filter, WorldFact.source_event_id.in_(session_event_ids))
    world_facts_deleted = db.query(WorldFact).filter(fact_filter).delete(synchronize_session=False)

    world_events_deleted = db.query(WorldEvent).filter(WorldEvent.session_id == safe_session_id).delete(synchronize_session=False)
    sessions_deleted = db.query(SessionVars).filter(SessionVars.session_id == safe_session_id).delete(synchronize_session=False)
    db.commit()

    return {
        "sessions": int(sessions_deleted),
        "world_events": int(world_events_deleted),
        "world_facts": int(world_facts_deleted),
        "world_edges": int(edge_rows_deleted),
        "world_projection": int(projection_rows_deleted),
    }


def _delete_all_world_rows(db: Session) -> Dict[str, int]:
    world_facts_deleted = db.query(WorldFact).delete(synchronize_session=False)
    world_edges_deleted = db.query(WorldEdge).delete(synchronize_session=False)
    projection_rows_deleted = db.query(WorldProjection).delete(synchronize_session=False)
    world_nodes_deleted = db.query(WorldNode).delete(synchronize_session=False)
    world_events_deleted = db.query(WorldEvent).delete(synchronize_session=False)
    sessions_deleted = db.query(SessionVars).delete(synchronize_session=False)
    storylets_deleted = db.query(Storylet).delete(synchronize_session=False)
    db.commit()
    return {
        "storylets": int(storylets_deleted),
        "sessions": int(sessions_deleted),
        "world_events": int(world_events_deleted),
        "world_nodes": int(world_nodes_deleted),
        "world_edges": int(world_edges_deleted),
        "world_facts": int(world_facts_deleted),
        "world_projection": int(projection_rows_deleted),
    }


def _reset_storylet_sequences(db: Session) -> None:
    try:
        db.execute(text("DELETE FROM sqlite_sequence WHERE name IN ('storylets', 'world_events')"))
        db.commit()
    except Exception:
        db.rollback()


_WORLD_ID_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "world_id.txt")


def _read_world_id() -> str:
    try:
        with open(_WORLD_ID_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def _write_world_id(world_id: str) -> None:
    os.makedirs(os.path.dirname(_WORLD_ID_FILE), exist_ok=True)
    with open(_WORLD_ID_FILE, "w", encoding="utf-8") as f:
        f.write(world_id)


@router.post("/world/seed", response_model=WorldSeedResponse)
def seed_world(
    payload: WorldSeedRequest,
    db: Session = Depends(get_db),
):
    """Seed the world once before any agents bootstrap.

    This is an admin-only operation. It generates a unique world_id, creates the
    world bible and initial storylets, and stores the world_id server-side so all
    agents can discover it via GET /api/world/id without depending on any character
    workspace.

    Requires WW_ENABLE_DEV_RESET=true (default in dev).
    """
    if not settings.enable_dev_reset:
        raise HTTPException(status_code=404, detail="Not found.")

    import uuid
    from datetime import datetime as _dt, timezone as _tz

    world_id = f"world-{_dt.now(_tz.utc).strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8]}"
    raw_description = (payload.description or "").strip()
    description = raw_description or (
        f"A persistent world shaped by its inhabitants — {payload.world_theme}."
    )
    tone = payload.tone.strip() or "grounded, observational"

    try:
        world_result = bootstrap_world_storylets(
            db,
            description=description,
            theme=payload.world_theme,
            player_role=payload.player_role,
            key_elements=payload.key_elements,
            tone=tone,
            storylet_count=payload.storylet_count,
            replace_existing=True,
            improvement_trigger="world-seed",
            run_improvements=False,
        )

        state_manager = get_state_manager(world_id, db)
        state_manager.set_variable("world_theme", payload.world_theme)
        state_manager.set_variable("player_role", payload.player_role)
        state_manager.set_variable("world_tone", tone)
        state_manager.set_variable("_bootstrap_state", "completed")
        state_manager.set_variable("_bootstrap_source", "world-seed")

        world_bible = world_result.get("world_bible")
        if world_bible and isinstance(world_bible, dict):
            state_manager.set_world_bible(world_bible)
            bible_locations = world_bible.get("locations", [])
            if bible_locations and isinstance(bible_locations[0], dict):
                entry_location = str(bible_locations[0].get("name", "")).strip()
                if entry_location:
                    state_manager.set_variable("location", entry_location)
            if bible_locations:
                from ...services.world_memory import seed_location_graph
                seed_location_graph(db, bible_locations)
        save_state(state_manager, db)

        _write_world_id(world_id)

        return WorldSeedResponse(
            success=True,
            world_id=world_id,
            storylets_created=int(world_result.get("storylets_created", 0)),
            world_bible_generated=bool(world_bible),
            seeded_at=_dt.now(_tz.utc).isoformat(),
            message=f"World seeded. All agents can now join via world_id={world_id}",
        )
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logging.error("World seed failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"World seed failed: {str(exc)}")


@router.get("/world/id")
def get_world_id():
    """Return the current server-side world_id.

    All agents call this on first setup to discover the world_id without
    depending on any character workspace path.
    """
    wid = _read_world_id()
    return {"world_id": wid, "seeded": bool(wid)}


@router.post("/session/bootstrap", response_model=SessionBootstrapResponse)
def bootstrap_session_world(
    payload: SessionBootstrapRequest,
    db: Session = Depends(get_db),
):
    """Initialize world content + onboarding vars before first /api/next turn.

    If ``payload.world_id`` is supplied the session joins an existing shared
    world instead of creating a new one.  World storylets and the world bible
    are inherited from the world session; only resident-private state is
    initialised here.
    """
    try:
        deleted = _delete_session_world_rows(db, payload.session_id)
        _clear_runtime_session_caches(payload.session_id)
        if any(int(count) > 0 for count in deleted.values()):
            logging.info(
                "Bootstrap freshness purge for session %s removed: %s",
                payload.session_id,
                deleted,
            )

        world_theme = payload.world_theme.strip()
        player_role = payload.player_role.strip()
        if not world_theme:
            raise HTTPException(status_code=422, detail="world_theme must not be blank.")
        if not player_role:
            raise HTTPException(status_code=422, detail="player_role must not be blank.")

        joining_world_id = str(payload.world_id).strip() if payload.world_id else None

        if joining_world_id:
            # ── Resident join flow ──────────────────────────────────────────
            # Inherit the world bible from the host world session so the
            # resident narrator has full context immediately.
            host_state = get_state_manager(joining_world_id, db)
            inherited_bible = host_state.get_world_bible()

            state_manager = get_state_manager(payload.session_id, db)
            bootstrap_completed_at = datetime.now(timezone.utc).isoformat()
            state_manager.set_world_id(joining_world_id)
            state_manager.set_variable("world_theme", world_theme)
            state_manager.set_variable("player_role", player_role)
            state_manager.set_variable("character_profile", player_role)
            tone = payload.tone.strip() or "adventure"
            state_manager.set_variable("world_tone", tone)
            if payload.key_elements:
                state_manager.set_variable(
                    "world_key_elements",
                    [str(item).strip() for item in payload.key_elements if str(item).strip()][:20],
                )
            state_manager.set_variable("_bootstrap_state", "completed")
            state_manager.set_variable("_bootstrap_source", payload.bootstrap_source)
            state_manager.set_variable("_bootstrap_completed_at", bootstrap_completed_at)
            # Determine entry location: explicit > bible default
            resolved_location: str = ""
            if payload.entry_location:
                resolved_location = str(payload.entry_location).strip()
            if inherited_bible:
                state_manager.set_world_bible(inherited_bible)
                if not resolved_location:
                    bible_locations = inherited_bible.get("locations", [])
                    if bible_locations and isinstance(bible_locations[0], dict):
                        resolved_location = str(bible_locations[0].get("name", "")).strip()
            if resolved_location:
                state_manager.set_variable("location", resolved_location)
            save_state(state_manager, db)

            # Log a WorldEvent so the digest roster can show the player's location immediately
            bootstrap_event = WorldEvent(
                session_id=payload.session_id,
                event_type="session_bootstrap",
                summary=f"{player_role} arrived at {resolved_location or 'the world'}.",
                world_state_delta={"location": resolved_location} if resolved_location else {},
            )
            db.add(bootstrap_event)
            db.commit()

            contextual_vars = state_manager.get_contextual_variables()
            return SessionBootstrapResponse(
                success=True,
                message=f"Resident session joined world {joining_world_id}.",
                session_id=payload.session_id,
                vars=contextual_vars,
                storylets_created=0,
                theme=world_theme,
                player_role=player_role,
                bootstrap_state="completed",
                bootstrap_diagnostics={
                    "bootstrap_mode": "resident_join",
                    "world_id": joining_world_id,
                    "world_bible_inherited": bool(inherited_bible),
                    "bootstrap_source": str(payload.bootstrap_source),
                },
            )

        # ── No world_id supplied — world must be seeded first ──────────────
        # In V4, the world is seeded once via POST /api/world/seed (admin operation).
        # All characters join as residents. There is no founder.
        raise HTTPException(
            status_code=422,
            detail=(
                "world_id is required. Seed the world first via POST /api/world/seed, "
                "then pass the returned world_id here."
            ),
        )
        raw_description = (payload.description or "").strip()
        description = raw_description or (f"A living world shaped by {world_theme}, viewed through the life of a {player_role}.")
        tone = payload.tone.strip() or "adventure"

        world_result = bootstrap_world_storylets(
            db,
            description=description,
            theme=world_theme,
            player_role=player_role,
            key_elements=payload.key_elements,
            tone=tone,
            storylet_count=payload.storylet_count,
            replace_existing=True,
            improvement_trigger="session-bootstrap",
            run_improvements=False,
        )

        state_manager = get_state_manager(payload.session_id, db)
        bootstrap_completed_at = datetime.now(timezone.utc).isoformat()
        state_manager.set_variable("world_theme", world_theme)
        state_manager.set_variable("player_role", player_role)
        state_manager.set_variable("character_profile", player_role)
        state_manager.set_variable("world_tone", tone)
        if payload.key_elements:
            state_manager.set_variable(
                "world_key_elements",
                [str(item).strip() for item in payload.key_elements if str(item).strip()][:20],
            )
        state_manager.set_variable("_bootstrap_state", "completed")
        state_manager.set_variable("_bootstrap_source", payload.bootstrap_source)
        state_manager.set_variable("_bootstrap_completed_at", bootstrap_completed_at)
        state_manager.set_variable("_bootstrap_input_hash", _bootstrap_input_hash(payload))
        state_manager.set_variable(
            "_bootstrap_storylets_created",
            int(world_result.get("storylets_created", 0)),
        )
        # Persist world bible into session state so the JIT beat path in
        # api_next can find it via state_manager.get_world_bible().
        world_bible = world_result.get("world_bible")
        if world_bible and isinstance(world_bible, dict):
            state_manager.set_world_bible(world_bible)
            # Seed `location` from the world bible's first location so that
            # storylet requires blocks that gate on location are satisfiable
            # from turn 1.  Without this the var is absent and every
            # location-gated storylet fails the missing-key gate immediately.
            bible_locations = world_bible.get("locations", [])
            if bible_locations and isinstance(bible_locations[0], dict):
                entry_location = str(bible_locations[0].get("name", "")).strip()
                if entry_location:
                    state_manager.set_variable("location", entry_location)
            logging.info(
                "World bible stored in session %s (%d locations, %d NPCs)",
                payload.session_id,
                len(world_bible.get("locations", [])),
                len(world_bible.get("npcs", [])),
            )
        save_state(state_manager, db)

        contextual_vars = state_manager.get_contextual_variables()
        bootstrap_diag = {
            "bootstrap_mode": str(world_result.get("bootstrap_mode", "classic")),
            "seeding_path": str(world_result.get("seeding_path", "bootstrap_world_storylets")),
            "world_bible_generated": bool(world_result.get("world_bible")),
            "world_bible_fallback": bool(world_result.get("world_bible_fallback", False)),
            "storylets_created": int(world_result.get("storylets_created", 0)),
            "fallback_active": bool(world_result.get("fallback_active", False)),
            "bootstrap_source": str(payload.bootstrap_source),
        }
        return SessionBootstrapResponse(
            success=True,
            message=str(world_result.get("message", "Session bootstrap complete.")),
            session_id=payload.session_id,
            vars=contextual_vars,
            storylets_created=int(world_result.get("storylets_created", 0)),
            theme=world_theme,
            player_role=player_role,
            bootstrap_state="completed",
            bootstrap_diagnostics=bootstrap_diag,
        )
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logging.error("Session bootstrap failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Session bootstrap failed: {str(exc)}")


@router.post("/session/start", response_model=SessionStartResponse)
def session_start(
    payload: SessionBootstrapRequest,
    db: Session = Depends(get_db),
):
    """Bootstrap world content and return the first playable turn in a single call.

    Equivalent to POST /session/bootstrap followed by POST /next with empty vars,
    but atomic under a single DB session and session-mutation lock. Existing
    /session/bootstrap + /next clients remain fully compatible.
    """
    import time as _time

    try:
        # ── 1. Bootstrap (same path as /session/bootstrap) ──────────────────
        deleted = _delete_session_world_rows(db, payload.session_id)
        _clear_runtime_session_caches(payload.session_id)
        if any(int(count) > 0 for count in deleted.values()):
            logging.info(
                "session/start freshness purge for session %s removed: %s",
                payload.session_id,
                deleted,
            )

        world_theme = payload.world_theme.strip()
        player_role = payload.player_role.strip()
        if not world_theme:
            raise HTTPException(status_code=422, detail="world_theme must not be blank.")
        if not player_role:
            raise HTTPException(status_code=422, detail="player_role must not be blank.")

        raw_description = (payload.description or "").strip()
        description = raw_description or (f"A living world shaped by {world_theme}, viewed through the life of a {player_role}.")
        tone = payload.tone.strip() or "adventure"

        world_result = bootstrap_world_storylets(
            db,
            description=description,
            theme=world_theme,
            player_role=player_role,
            key_elements=payload.key_elements,
            tone=tone,
            storylet_count=payload.storylet_count,
            replace_existing=True,
            improvement_trigger="session-start",
            run_improvements=False,
        )

        state_manager = get_state_manager(payload.session_id, db)
        bootstrap_completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        state_manager.set_variable("world_theme", world_theme)
        state_manager.set_variable("player_role", player_role)
        state_manager.set_variable("character_profile", player_role)
        state_manager.set_variable("world_tone", tone)
        if payload.key_elements:
            state_manager.set_variable(
                "world_key_elements",
                [str(item).strip() for item in payload.key_elements if str(item).strip()][:20],
            )
        state_manager.set_variable("_bootstrap_state", "completed")
        state_manager.set_variable("_bootstrap_source", payload.bootstrap_source)
        state_manager.set_variable("_bootstrap_completed_at", bootstrap_completed_at)
        state_manager.set_variable("_bootstrap_input_hash", _bootstrap_input_hash(payload))
        state_manager.set_variable(
            "_bootstrap_storylets_created",
            int(world_result.get("storylets_created", 0)),
        )
        world_bible = world_result.get("world_bible")
        if world_bible and isinstance(world_bible, dict):
            state_manager.set_world_bible(world_bible)
            bible_locations = world_bible.get("locations", [])
            if bible_locations and isinstance(bible_locations[0], dict):
                entry_location = str(bible_locations[0].get("name", "")).strip()
                if entry_location:
                    state_manager.set_variable("location", entry_location)
            logging.info(
                "World bible stored in session %s (%d locations, %d NPCs)",
                payload.session_id,
                len(world_bible.get("locations", [])),
                len(world_bible.get("npcs", [])),
            )
        save_state(state_manager, db)

        contextual_vars = state_manager.get_contextual_variables()
        storylets_created = int(world_result.get("storylets_created", 0))

        # ── 2. First turn — same pipeline as /next with no prior choice ──────
        first_turn = None
        first_turn_duration_ms = None
        first_turn_error = None
        first_turn_started = _time.perf_counter()
        try:
            first_turn_payload = NextReq(session_id=payload.session_id, vars={})
            from .orchestration_adapters import run_next_turn_orchestration

            first_turn_result = run_next_turn_orchestration(
                db=db,
                payload=first_turn_payload,
                timings_ms={},
                debug_scores=False,
                use_session_lock=True,
            )
            first_turn = first_turn_result.get("response")
        except Exception as exc:
            first_turn_error = str(exc)
            logging.warning(
                "session/start first-turn failed for session %s (bootstrap succeeded): %s",
                payload.session_id,
                exc,
            )
        finally:
            first_turn_duration_ms = round((_time.perf_counter() - first_turn_started) * 1000.0, 1)

        bootstrap_diag = {
            "bootstrap_mode": str(world_result.get("bootstrap_mode", "classic")),
            "seeding_path": str(world_result.get("seeding_path", "bootstrap_world_storylets")),
            "world_bible_generated": bool(world_result.get("world_bible")),
            "world_bible_fallback": bool(world_result.get("world_bible_fallback", False)),
            "storylets_created": int(world_result.get("storylets_created", 0)),
            "fallback_active": bool(world_result.get("fallback_active", False)),
            "bootstrap_source": str(payload.bootstrap_source),
        }
        return SessionStartResponse(
            success=True,
            message=str(world_result.get("message", "Session start complete.")),
            session_id=payload.session_id,
            vars=contextual_vars,
            storylets_created=storylets_created,
            theme=world_theme,
            player_role=player_role,
            bootstrap_state="completed",
            bootstrap_diagnostics=bootstrap_diag,
            first_turn=first_turn,
            first_turn_duration_ms=first_turn_duration_ms,
            first_turn_error=first_turn_error,
            startup_source="unified",
        )
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logging.error("session/start failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Session start failed: {str(exc)}")


@router.post("/cleanup-sessions")
def cleanup_old_sessions(db: Session = Depends(get_db)):
    """Clean up sessions older than 24 hours."""
    try:
        cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=24)).replace(tzinfo=None)

        sessions_to_delete_result = db.execute(
            text("SELECT session_id FROM session_vars WHERE updated_at < :cutoff"),
            {"cutoff": cutoff_time},
        ).fetchall()

        deleted_session_ids = [row[0] for row in sessions_to_delete_result]
        sessions_to_delete_count = len(deleted_session_ids)

        db.execute(
            text("DELETE FROM session_vars WHERE updated_at < :cutoff"),
            {"cutoff": cutoff_time},
        )
        db.commit()

        removed_from_cache = remove_cached_sessions(deleted_session_ids)
        logging.info(
            "Cleaned up %s old sessions (%s removed from cache)",
            sessions_to_delete_count,
            removed_from_cache,
        )

        return {
            "success": True,
            "sessions_removed": sessions_to_delete_count,
            "cache_entries_removed": removed_from_cache,
            "message": f"Cleaned up {sessions_to_delete_count} sessions older than 24 hours",
        }
    except Exception as exc:
        db.rollback()
        logging.error("Session cleanup failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Session cleanup failed: {str(exc)}")


@router.post("/reset-session")
def reset_session_world(
    include_legacy_seed: bool = False,
    db: Session = Depends(get_db),
):
    """Hard-reset world/session data; optionally reseed legacy test storylets."""
    try:
        deleted = _delete_all_world_rows(db)

        # Legacy seeding is isolated behind explicit request + feature flag.
        should_seed_legacy = bool(include_legacy_seed and settings.enable_legacy_test_seeds)
        storylets_seeded = 0
        if should_seed_legacy:
            storylets_seeded = seed_if_empty_sync(db, allow_legacy_seed=True)
            db.commit()

        _clear_runtime_caches()

        return {
            "success": True,
            "message": "World reset complete.",
            "deleted": deleted,
            "storylets_seeded": int(storylets_seeded),
            "legacy_seed_mode": should_seed_legacy,
        }
    except Exception as exc:
        db.rollback()
        logging.error("Session reset failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Session reset failed: {str(exc)}")


@router.post("/dev/hard-reset")
def dev_hard_reset_world(db: Session = Depends(get_db)):
    """Developer-only hard reset: wipe world data and reset local id sequences."""
    if not settings.enable_dev_reset:
        raise HTTPException(status_code=404, detail="Not found")

    try:
        deleted = _delete_all_world_rows(db)
        _reset_storylet_sequences(db)
        _clear_runtime_caches()
        return {
            "success": True,
            "message": "Development hard reset complete. Database world state fully wiped.",
            "deleted": deleted,
            "storylets_seeded": 0,
            "legacy_seed_mode": False,
        }
    except Exception as exc:
        db.rollback()
        logging.error("Development hard reset failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Development hard reset failed: {str(exc)}")


@router.get("/world/{world_id}/events")
def get_world_events(
    world_id: SessionId,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Return recent events for a shared world — readable by all residents.

    Any resident or observer can call this to perceive what other residents
    have done in the shared world.  Pass ``limit`` to control how many events
    are returned (default 50, max 200).
    """
    from ...services import world_memory

    limit = max(1, min(int(limit), 200))
    try:
        events = world_memory.get_world_history(db, session_id=str(world_id), limit=limit)
        return {
            "world_id": str(world_id),
            "event_count": len(events),
            "events": [
                {
                    "id": e.id,
                    "session_id": e.session_id,
                    "event_type": e.event_type,
                    "summary": e.summary,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in events
            ],
        }
    except Exception as exc:
        logging.error("get_world_events failed for world_id=%s: %s", world_id, exc)
        raise HTTPException(status_code=500, detail=f"Failed to fetch world events: {str(exc)}")


@router.get("/dev/jit-test")
def dev_jit_test(
    theme: str = "solarpunk",
    player_role: str = "local troublemaker",
    tone: str = "adventure",
):
    """Developer-only: call generate_world_bible directly and return raw result or error."""
    if not settings.enable_dev_reset:
        raise HTTPException(status_code=404, detail="Not found")

    import os
    import traceback
    from ...services.llm_service import generate_world_bible
    from ...services.llm_client import get_llm_client, get_model, is_ai_disabled, get_api_key

    # Inline diagnostics
    diag = {
        "is_ai_disabled": is_ai_disabled(),
        "get_model": get_model(),
        "get_api_key_prefix": (get_api_key() or "NONE")[:20],
        "client_is_none": get_llm_client() is None,
        "llm_timeout": settings.llm_timeout_seconds,
        "v3_runtime": settings.get_v3_runtime_settings(),
        "DW_DISABLE_AI": os.getenv("DW_DISABLE_AI"),
        "DW_FAST_TEST": os.getenv("DW_FAST_TEST"),
        "PYTEST_CURRENT_TEST": os.getenv("PYTEST_CURRENT_TEST"),
    }

    try:
        bible = generate_world_bible(
            description=f"A {tone} world in a {theme} setting.",
            theme=theme,
            player_role=player_role,
            tone=tone,
        )
        return {
            "success": True,
            "world_bible": bible,
            "locations_count": len(bible.get("locations", [])),
            "npcs_count": len(bible.get("npcs", [])),
            "_diag": diag,
        }
    except Exception as exc:
        return {
            "success": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "_diag": diag,
        }
