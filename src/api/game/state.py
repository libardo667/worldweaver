"""Session state and maintenance endpoints."""

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
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
    SessionBootstrapRequest,
    SessionBootstrapResponse,
    SessionId,
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
    if (
        payload.primary_goal is None
        and payload.subgoals is None
        and payload.urgency is None
        and payload.complication is None
    ):
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


@router.post("/session/bootstrap", response_model=SessionBootstrapResponse)
def bootstrap_session_world(
    payload: SessionBootstrapRequest,
    db: Session = Depends(get_db),
):
    """Initialize world content + onboarding vars before first /api/next turn."""
    try:
        world_theme = payload.world_theme.strip()
        player_role = payload.player_role.strip()
        if not world_theme:
            raise HTTPException(status_code=422, detail="world_theme must not be blank.")
        if not player_role:
            raise HTTPException(status_code=422, detail="player_role must not be blank.")

        raw_description = (payload.description or "").strip()
        description = raw_description or (
            f"A living world shaped by {world_theme}, viewed through the life of a {player_role}."
        )
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
        save_state(state_manager, db)

        contextual_vars = state_manager.get_contextual_variables()
        return SessionBootstrapResponse(
            success=True,
            message=str(world_result.get("message", "Session bootstrap complete.")),
            session_id=payload.session_id,
            vars=contextual_vars,
            storylets_created=int(world_result.get("storylets_created", 0)),
            theme=world_theme,
            player_role=player_role,
            bootstrap_state="completed",
        )
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logging.error("Session bootstrap failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Session bootstrap failed: {str(exc)}")


@router.post("/cleanup-sessions")
def cleanup_old_sessions(db: Session = Depends(get_db)):
    """Clean up sessions older than 24 hours."""
    try:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)

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
        world_facts_deleted = db.query(WorldFact).delete(synchronize_session=False)
        world_edges_deleted = db.query(WorldEdge).delete(synchronize_session=False)
        projection_rows_deleted = db.query(WorldProjection).delete(synchronize_session=False)
        world_nodes_deleted = db.query(WorldNode).delete(synchronize_session=False)
        world_events_deleted = db.query(WorldEvent).delete(synchronize_session=False)
        sessions_deleted = db.query(SessionVars).delete(synchronize_session=False)
        storylets_deleted = db.query(Storylet).delete(synchronize_session=False)
        db.commit()

        should_seed_legacy = bool(include_legacy_seed or settings.enable_legacy_test_seeds)
        storylets_seeded = 0
        if should_seed_legacy:
            storylets_seeded = seed_if_empty_sync(db, allow_legacy_seed=True)
            db.commit()

        _state_managers.clear()
        _spatial_navigators.clear()
        _runtime_synthesis_counts.clear()

        return {
            "success": True,
            "message": "World reset complete.",
            "deleted": {
                "storylets": int(storylets_deleted),
                "sessions": int(sessions_deleted),
                "world_events": int(world_events_deleted),
                "world_nodes": int(world_nodes_deleted),
                "world_edges": int(world_edges_deleted),
                "world_facts": int(world_facts_deleted),
                "world_projection": int(projection_rows_deleted),
            },
            "storylets_seeded": int(storylets_seeded),
            "legacy_seed_mode": should_seed_legacy,
        }
    except Exception as exc:
        db.rollback()
        logging.error("Session reset failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Session reset failed: {str(exc)}")
