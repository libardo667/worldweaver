"""Main game API routes with Advanced State Management and Spatial Navigation."""

import logging
import traceback
from typing import Any, Dict, List, cast
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from fastapi import Body, Query
from sqlalchemy.orm import Session
import json

from ..database import get_db, SessionLocal
from ..models import SessionVars, Storylet
from typing import Optional
from ..models.schemas import (
    NextReq,
    NextResp,
    ChoiceOut,
    SessionId,
    SpatialNavigationResponse,
    SpatialMoveResponse,
    SpatialMapResponse,
    SpatialAssignResponse,
    WorldEventOut,
    WorldHistoryResponse,
    WorldFactsResponse,
    ActionRequest,
    ActionResponse,
)
from ..services.game_logic import ensure_storylets, render
from ..services.state_manager import AdvancedStateManager
from ..services.spatial_navigator import SpatialNavigator, DIRECTIONS
from ..services.seed_data import DEFAULT_SESSION_VARS

router = APIRouter()

# Cache for state managers and spatial navigators (in production, use Redis or similar)
_state_managers: Dict[str, AdvancedStateManager] = {}
_spatial_navigators: Dict[str, SpatialNavigator] = {}


def get_spatial_navigator(db: Session) -> SpatialNavigator:
    """Get or create a spatial navigator."""
    # Use a single navigator per database connection
    db_key = str(id(db))
    if db_key not in _spatial_navigators:
        # Pass the SQLAlchemy session directly
        _spatial_navigators[db_key] = SpatialNavigator(db)
    return _spatial_navigators[db_key]


def get_state_manager(session_id: str, db: Session) -> AdvancedStateManager:
    """Get or create a state manager for the session.

    Loads a v2 full-state payload (inventory + relationships + environment)
    when available, otherwise falls back to legacy flat-variable format.
    """
    if session_id not in _state_managers:
        manager = AdvancedStateManager(session_id)

        row = db.get(SessionVars, session_id)
        if row is not None and row.vars is not None:
            stored = cast(Dict[str, Any], row.vars)
            if stored.get("_v") == 2:
                # Full v2 payload — restore everything.
                manager.import_state(stored)
            else:
                # Legacy v1 payload — flat variable dict.
                manager.variables.update(stored)

        # Apply defaults only for keys not already present.
        for key, value in DEFAULT_SESSION_VARS.items():
            manager.variables.setdefault(key, value)

        _state_managers[session_id] = manager

    return _state_managers[session_id]


def _norm_choices(c: Dict[str, Any]) -> ChoiceOut:
    """Normalize choice dictionary to ChoiceOut model."""
    label = c.get("label") or c.get("text") or "Continue"
    set_obj = c.get("set") or c.get("set_vars") or {}
    return ChoiceOut(label=label, set=set_obj)


def _parse_requires(requires_value: Any) -> Dict[str, Any]:
    """Normalize requires values stored as dict or JSON string."""
    if requires_value is None:
        return {}
    if isinstance(requires_value, dict):
        return cast(Dict[str, Any], requires_value)
    if isinstance(requires_value, str):
        try:
            parsed = json.loads(requires_value)
            if isinstance(parsed, dict):
                return cast(Dict[str, Any], parsed)
        except json.JSONDecodeError:
            return {}
    return {}


def _find_storylet_for_location(db: Session, location: str) -> Storylet | None:
    """Find the first storylet whose requires.location matches exactly."""
    for storylet in db.query(Storylet).all():
        requires = _parse_requires(storylet.requires)
        if requires.get("location") == location:
            return storylet
    return None


@router.post("/next", response_model=NextResp)
def api_next(payload: NextReq, db: Session = Depends(get_db)):
    """Get the next storylet for a session with Advanced State Management."""
    # Get the advanced state manager
    state_manager = get_state_manager(payload.session_id, db)

    # Update state with any new variables from client
    for key, value in (payload.vars or {}).items():
        state_manager.set_variable(key, value)

    # Get full contextual variables for storylet evaluation
    contextual_vars = state_manager.get_contextual_variables()

    # Ensure we have enough eligible storylets (generates via LLM if needed)
    ensure_storylets(db, contextual_vars)

    # Pick a storylet using enhanced condition evaluation
    story = pick_storylet_enhanced(db, state_manager)

    if story is None:
        text = "🕯️ The tunnel is quiet. Nothing compelling meets the eye."
        choices = [ChoiceOut(label="Wait", set={})]

        # Add some contextual flavor based on state
        if state_manager.environment.danger_level > 3:
            text = "⚠️ The air feels heavy with danger. Perhaps it's wise to wait and listen."
        elif state_manager.environment.time_of_day == "night":
            text = "🌙 The darkness is deep. Something stirs in the shadows, but nothing approaches."

        out = NextResp(text=text, choices=choices, vars=contextual_vars)
    else:
        # Render text with full contextual variables
        text = render(cast(str, story.text_template), contextual_vars)
        choices = [
            _norm_choices(c) for c in cast(List[Dict[str, Any]], story.choices or [])
        ]
        out = NextResp(text=text, choices=choices, vars=contextual_vars)

        # Record world event
        try:
            from ..services.world_memory import record_event

            record_event(
                db=db,
                session_id=payload.session_id,
                storylet_id=cast(int, story.id),
                event_type="storylet_fired",
                summary=f"Storylet '{story.title}' fired",
                delta={},
            )
        except Exception as e:
            logging.warning("Failed to record storylet event: %s", e)

    # Save enhanced state back to database
    save_state_to_db(state_manager, db)

    return out


def pick_storylet_enhanced(
    db: Session, state_manager: AdvancedStateManager
) -> Storylet | None:
    """Enhanced storylet picking: semantic selection when embeddings exist,
    weight-based fallback otherwise."""
    import random

    all_storylets = db.query(Storylet).all()
    eligible = []

    for storylet in all_storylets:
        requirements = cast(Dict[str, Any], storylet.requires or {})
        if state_manager.evaluate_condition(requirements):
            eligible.append(storylet)

    if not eligible:
        return None

    # Try semantic selection if any eligible storylets have embeddings
    embedded = [s for s in eligible if s.embedding]
    if embedded:
        try:
            from ..services.semantic_selector import (
                compute_player_context_vector,
                score_storylets,
                select_storylet,
            )
            from ..services import world_memory

            recent_storylet_ids = []
            try:
                recent_events = world_memory.get_world_history(
                    db, session_id=state_manager.session_id, limit=5
                )
                recent_storylet_ids = [
                    e.storylet_id for e in recent_events if e.storylet_id
                ]
            except Exception:
                pass

            context_vector = compute_player_context_vector(
                state_manager, world_memory, db
            )
            scored = score_storylets(
                context_vector, embedded, recent_storylet_ids
            )
            result = select_storylet(scored)
            if result:
                return result
        except Exception as e:
            logging.warning("Semantic selection failed, falling back: %s", e)

    # Fallback: weight-based random selection
    weights = [max(0.0, cast(float, s.weight or 0.0)) for s in eligible]
    return random.choices(eligible, weights=weights, k=1)[0]


def save_state_to_db(state_manager: AdvancedStateManager, db: Session):
    """Save the full session state (variables, inventory, relationships,
    environment) to the database as a v2 JSON payload."""
    session_id = state_manager.session_id

    row = db.get(SessionVars, session_id)
    if row is None:
        row = SessionVars(session_id=session_id, vars={})
        db.add(row)

    row.vars = state_manager.export_state()  # type: ignore
    db.commit()


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
    relationship = state_manager.update_relationship(
        entity_a, entity_b, changes, memory
    )
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
        "available_actions": item.get_available_actions(
            state_manager.get_contextual_variables()
        ),
    }


@router.post("/state/{session_id}/environment")
def update_environment(
    session_id: SessionId, changes: Dict[str, Any], db: Session = Depends(get_db)
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


# Seed test DB if empty to support spatial tests
def _seed_if_test_db():
    try:
        import os

        if os.getenv("DW_DB_PATH") == "test_database.db":
            db = SessionLocal()
            from ..services.seed_data import seed_if_empty_sync

            seed_if_empty_sync(db)
            db.close()
    except Exception:
        pass


_seed_if_test_db()


@router.post("/cleanup-sessions")
def cleanup_old_sessions(db: Session = Depends(get_db)):
    """Clean up sessions older than 24 hours."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import text

    try:
        # Calculate cutoff time (24 hours ago)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)

        # Get session IDs that will be deleted (for precise cache cleanup)
        sessions_to_delete_result = db.execute(
            text("SELECT session_id FROM session_vars WHERE updated_at < :cutoff"),
            {"cutoff": cutoff_time},
        ).fetchall()

        # Extract the actual session IDs
        deleted_session_ids = [row[0] for row in sessions_to_delete_result]
        sessions_to_delete_count = len(deleted_session_ids)

        # Delete old sessions
        result = db.execute(
            text("DELETE FROM session_vars WHERE updated_at < :cutoff"),
            {"cutoff": cutoff_time},
        )

        db.commit()

        # Clear state manager cache for deleted sessions (precise matching)
        global _state_managers
        removed_from_cache = 0

        # Remove only the specific session IDs that were deleted from the database
        for session_id in deleted_session_ids:
            if session_id in _state_managers:
                _state_managers.pop(session_id, None)
                removed_from_cache += 1

        logging.info(
            f"🧹 Cleaned up {sessions_to_delete_count} old sessions ({removed_from_cache} removed from cache)"
        )

        return {
            "success": True,
            "sessions_removed": sessions_to_delete_count,
            "cache_entries_removed": removed_from_cache,
            "message": f"Cleaned up {sessions_to_delete_count} sessions older than 24 hours",
        }

    except Exception as e:
        db.rollback()
        logging.error(f"❌ Session cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Session cleanup failed: {str(e)}")


def _resolve_current_location(
    state_manager: AdvancedStateManager, db: Session
) -> str:
    """Ensure the player's current location matches a valid storylet.

    Returns the (possibly corrected) location string.
    """
    current_location = str(state_manager.get_variable("location", "start"))

    available_storylets = db.query(Storylet).filter(Storylet.requires.isnot(None)).all()
    valid_locations = set()
    for storylet in available_storylets:
        location = _parse_requires(storylet.requires).get("location")
        if isinstance(location, str):
            valid_locations.add(location)

    if current_location not in valid_locations and valid_locations:
        new_location = sorted(valid_locations)[0]
        logging.info(
            "Invalid location '%s', setting to '%s'",
            current_location,
            new_location,
        )
        state_manager.set_variable("location", new_location)
        save_state_to_db(state_manager, db)
        return new_location

    return current_location


@router.get("/spatial/navigation/{session_id}", response_model=SpatialNavigationResponse)
def get_spatial_navigation(session_id: SessionId, db: Session = Depends(get_db)):
    """Get 8-directional navigation options from current location."""
    try:
        state_manager = get_state_manager(session_id, db)
        spatial_nav = get_spatial_navigator(db)

        current_location = _resolve_current_location(state_manager, db)

        current_storylet = _find_storylet_for_location(db, current_location)
        if not current_storylet:
            logging.error(
                "No storylet found for location '%s' even after fallback",
                current_location,
            )
            raise HTTPException(status_code=404, detail="Current location not found")

        current_id = cast(int, current_storylet.id)
        player_vars = state_manager.get_contextual_variables()
        nav = spatial_nav.get_navigation_options(current_id, player_vars)

        return {
            "position": nav["position"],
            "directions": nav["directions"],
            "location_storylet": {
                "id": current_id,
                "title": cast(str, current_storylet.title),
                "position": nav["position"],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error("Spatial navigation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Navigation failed: {str(e)}")


class _MoveReq(BaseModel):
    direction: str


@router.post("/spatial/move/{session_id}", response_model=SpatialMoveResponse)
def move_in_direction(
    session_id: SessionId,
    payload: dict | None = Body(default=None),
    direction: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Move the player in a specific direction."""
    try:
        logging.info(
            f"🎯 Move request: session={session_id}, payload={payload}, direction={direction}"
        )

        state_manager = get_state_manager(session_id, db)
        spatial_nav = get_spatial_navigator(db)

        # Validate direction from either JSON or query
        if direction is None and payload is not None:
            direction = payload.get("direction")

        if direction is None:
            logging.error("❌ No direction provided")
            raise HTTPException(status_code=400, detail="Missing 'direction'")

        # Normalize direction input
        direction_map = {
            "n": "north", "s": "south", "e": "east", "w": "west",
            "ne": "northeast", "nw": "northwest", "se": "southeast", "sw": "southwest"
        }
        direction_lower = direction.lower()
        direction_full = direction_map.get(direction_lower, direction_lower)

        if direction_full not in DIRECTIONS:
            logging.error(f"❌ Invalid direction: {direction}")
            raise HTTPException(
                status_code=400, detail=f"Invalid direction: {direction}"
            )
        direction = direction_full

        # Get current storylet - try multiple approaches
        current_location = state_manager.get_variable("location", "start")
        logging.info(f"📍 Current location: {current_location}")

        # First try: exact location match
        current_storylet = _find_storylet_for_location(db, cast(str, current_location))

        # Second try: any storylet if we can't find location-based ones
        if not current_storylet:
            logging.warning(
                f"❌ No storylet found for location '{current_location}', trying any positioned storylet"
            )
            positioned_ids = list(spatial_nav.storylet_positions.keys())
            if positioned_ids:
                current_storylet = (
                    db.query(Storylet).filter(Storylet.id.in_(positioned_ids)).first()
                )
                if current_storylet:
                    # Update the session to match this storylet's location
                    requires = _parse_requires(current_storylet.requires)
                    fallback_location = requires.get("location", "unknown")
                    state_manager.set_variable("location", fallback_location)
                    save_state_to_db(state_manager, db)
                    logging.info(
                        f"🔄 Using fallback storylet {current_storylet.id} at location '{fallback_location}'"
                    )

        if not current_storylet:
            logging.error(f"❌ No positioned storylets found")
            raise HTTPException(status_code=404, detail="No positioned storylets found")

        current_id = cast(int, current_storylet.id)
        logging.info(f"🎯 Current storylet: {current_id} ({current_storylet.title})")

        # Check if movement is allowed
        player_vars = state_manager.get_contextual_variables()
        if not spatial_nav.can_move_to_direction(current_id, direction, player_vars):
            logging.warning(f"⛔ Movement blocked: {direction}")
            raise HTTPException(status_code=403, detail="Cannot move in that direction")

        # Get target storylet
        nav_options = spatial_nav.get_directional_navigation(current_id)
        target = nav_options.get(direction)

        if not target:
            logging.error(f"❌ No location in direction: {direction}")
            raise HTTPException(status_code=404, detail="No location in that direction")

        # Update player location
        target_storylet = db.get(Storylet, target["id"])
        if target_storylet is not None and target_storylet.requires is not None:
            requirements = _parse_requires(target_storylet.requires)
            new_location = requirements.get("location")
            if new_location:
                state_manager.set_variable("location", new_location)
                save_state_to_db(state_manager, db)
                logging.info(f"✅ Moved to: {new_location}")

        # Use position field for new position
        # Defensive: SQLAlchemy Column can shadow instance value, so check type
        pos = getattr(target_storylet, "position", None) if target_storylet else None
        if isinstance(pos, dict) and "x" in pos and "y" in pos:
            new_position = {
                "x": pos["x"],
                "y": pos["y"]
            }
        else:
            new_position = {
                "x": target["position"]["x"],
                "y": target["position"]["y"]
            }
        return {
            "result": f"Moved {direction} to {target['title']}",
            "new_position": new_position
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"❌ Movement failed: {e}")
        raise HTTPException(status_code=500, detail=f"Movement failed: {str(e)}")


@router.get("/spatial/map", response_model=SpatialMapResponse)
def get_spatial_map(db: Session = Depends(get_db)):
    """Get the full spatial map data for rendering."""
    try:
        spatial_nav = get_spatial_navigator(db)
        map_data = spatial_nav.get_spatial_map_data()
        storylets = []
        for s in map_data.get("storylets", []):
            storylets.append({
                "id": s["id"],
                "title": s["title"],
                "position": s["position"]
            })
        return {"storylets": storylets}
    except Exception as e:
        logging.error(f"❌ Map generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Map generation failed: {str(e)}")


@router.post("/spatial/assign-positions", response_model=SpatialAssignResponse)
def assign_spatial_positions(payload: dict = Body(...), db: Session = Depends(get_db)):
    """Assign spatial positions to all storylets (useful after world generation)."""
    try:
        positions_payload = payload.get("positions", [])
        valid_ids = {s.id for s in db.query(Storylet).all()}
        for pos in positions_payload:
            if pos["storylet_id"] not in valid_ids:
                raise HTTPException(status_code=404, detail=f"Storylet ID {pos['storylet_id']} not found")
        spatial_nav = get_spatial_navigator(db)
        storylets = db.query(Storylet).all()
        storylet_data = []
        for s in storylets:
            storylet_data.append(
                {
                    "title": s.title,
                    "choices": cast(List[Dict[str, Any]], s.choices or []),
                    "requires": cast(Dict[str, Any], s.requires or {}),
                }
            )
        positions = spatial_nav.assign_spatial_positions(storylet_data)
        assigned = [
            {"storylet_id": int(storylet_id), "x": pos.x, "y": pos.y}
            for storylet_id, pos in positions.items()
        ]
        return {"assigned": assigned, "assigned_count": len(assigned)}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"❌ Position assignment failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Position assignment failed: {str(e)}"
        )


# ---------------------------------------------------------------------------
# World Memory Endpoints
# ---------------------------------------------------------------------------


@router.get("/world/history", response_model=WorldHistoryResponse)
def get_world_history_endpoint(
    session_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Get recent world events."""
    from ..services.world_memory import get_world_history

    events = get_world_history(db, session_id=session_id, limit=limit)
    return {
        "events": [
            {
                "id": e.id,
                "session_id": e.session_id,
                "storylet_id": e.storylet_id,
                "event_type": e.event_type,
                "summary": e.summary,
                "world_state_delta": e.world_state_delta or {},
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
        "count": len(events),
    }


@router.get("/world/facts", response_model=WorldFactsResponse)
def query_world_facts_endpoint(
    query: str = Query(..., min_length=1),
    session_id: Optional[str] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Semantic search over world history."""
    from ..services.world_memory import query_world_facts

    facts = query_world_facts(db, query, session_id=session_id, limit=limit)
    return {
        "query": query,
        "facts": [
            {
                "id": e.id,
                "session_id": e.session_id,
                "storylet_id": e.storylet_id,
                "event_type": e.event_type,
                "summary": e.summary,
                "world_state_delta": e.world_state_delta or {},
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in facts
        ],
        "count": len(facts),
    }


# ---------------------------------------------------------------------------
# Freeform Action Endpoint
# ---------------------------------------------------------------------------


@router.post("/action", response_model=ActionResponse)
def api_freeform_action(payload: ActionRequest, db: Session = Depends(get_db)):
    """Interpret a freeform player action using natural language."""
    from ..services.command_interpreter import interpret_action
    from ..services import world_memory

    state_manager = get_state_manager(payload.session_id, db)

    current_location = str(state_manager.get_variable("location", "start"))
    current_storylet = _find_storylet_for_location(db, current_location)

    result = interpret_action(
        action=payload.action,
        state_manager=state_manager,
        world_memory_module=world_memory,
        current_storylet=current_storylet,
        db=db,
    )

    event_type = world_memory.infer_event_type("freeform_action", result.state_deltas)

    # Record as world event
    try:
        world_memory.record_event(
            db=db,
            session_id=payload.session_id,
            storylet_id=cast(int, current_storylet.id) if current_storylet else None,
            event_type=event_type,
            summary=f"Player action: {payload.action}. Result: {result.narrative_text[:200]}",
            delta=result.state_deltas,
            state_manager=state_manager,
        )
    except Exception as e:
        logging.warning("Failed to record action event: %s", e)
        if result.state_deltas:
            world_memory.apply_event_delta_to_state(state_manager, result.state_deltas)

    save_state_to_db(state_manager, db)

    # Optionally trigger a storylet
    triggered_text = None
    should_trigger = result.should_trigger_storylet or world_memory.should_trigger_storylet(
        event_type, result.state_deltas
    )
    if should_trigger:
        contextual_vars = state_manager.get_contextual_variables()
        triggered = pick_storylet_enhanced(db, state_manager)
        if triggered:
            triggered_text = render(
                cast(str, triggered.text_template), contextual_vars
            )

    response = {
        "narrative": result.narrative_text,
        "state_changes": result.state_deltas,
        "choices": [
            {"label": c.get("label", "Continue"), "set": c.get("set", {})}
            for c in result.follow_up_choices
        ],
        "plausible": result.plausible,
        "vars": state_manager.get_contextual_variables(),
    }

    if triggered_text:
        response["triggered_storylet"] = triggered_text

    return response
