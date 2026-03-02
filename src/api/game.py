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
from ..models.schemas import NextReq, NextResp, ChoiceOut, SessionId
from ..services.game_logic import pick_storylet, render
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

    # Save enhanced state back to database
    save_state_to_db(state_manager, db)

    return out


def pick_storylet_enhanced(
    db: Session, state_manager: AdvancedStateManager
) -> Storylet | None:
    """Enhanced storylet picking using the new state manager."""
    all_storylets = db.query(Storylet).all()
    eligible = []

    for storylet in all_storylets:
        requirements = cast(Dict[str, Any], storylet.requires or {})
        if state_manager.evaluate_condition(requirements):
            eligible.append(storylet)

    if not eligible:
        return None

    # Use existing weight-based selection
    import random

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


@router.get("/spatial/navigation/{session_id}")
def get_spatial_navigation(session_id: SessionId, db: Session = Depends(get_db)):
    """Get 8-directional navigation options from current location."""
    try:
        state_manager = get_state_manager(session_id, db)
        spatial_nav = get_spatial_navigator(db)
        current_location = state_manager.get_variable("location", "start")
        logging.info(f"📍 Current location: {current_location}")
        available_storylets = (
            db.query(Storylet).filter(Storylet.requires.isnot(None)).all()
        )
        valid_locations = set()
        for s in available_storylets:
            try:
                requires_value = s.requires
                if requires_value is None:
                    continue
                if isinstance(requires_value, str):
                    req = json.loads(requires_value)
                elif isinstance(requires_value, dict):
                    req = requires_value
                else:
                    continue
                if "location" in req:
                    valid_locations.add(req["location"])
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logging.warning("Skipping storylet %s during location scan: %s", s.id, e)
        if current_location not in valid_locations and valid_locations:
            new_location = sorted(valid_locations)[0]
            logging.info(
                f"🔄 Invalid location '{current_location}', setting to '{new_location}'"
            )
            state_manager.set_variable("location", new_location)
            save_state_to_db(state_manager, db)
            current_location = new_location
        current_storylet = (
            db.query(Storylet)
            .filter(Storylet.requires.contains(f'"location": "{current_location}"'))
            .first()
        )
        if not current_storylet:
            logging.error(
                f"❌ No storylet found for location '{current_location}' even after fallback"
            )
            return {
                "error": "Current location not found",
                "directions": [],
                "position": {"x": 0, "y": 0},
            }
        current_id = cast(int, current_storylet.id)
        directions = spatial_nav.get_directional_navigation(current_id)
        player_vars = state_manager.get_contextual_variables()
        available_directions = {}
        for direction, target in directions.items():
            if target is None:
                available_directions[direction] = None
            else:
                can_access = spatial_nav.can_move_to_direction(
                    current_id, direction, player_vars
                )
                available_directions[direction] = {
                    **target,
                    "accessible": can_access,
                    "reason": "Requirements not met" if not can_access else None,
                }
        position = spatial_nav.storylet_positions.get(current_id, {"x": 0, "y": 0})
        directions_list = [d for d in available_directions.keys() if available_directions[d] is not None]
        if isinstance(position, dict):
            x = position.get("x", 0)
            y = position.get("y", 0)
        else:
            x = getattr(position, "x", 0)
            y = getattr(position, "y", 0)
        return {
            "position": {"x": x, "y": y},
            "directions": directions_list
        }
    except Exception as e:
        logging.error(f"❌ Spatial navigation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Navigation failed: {str(e)}")


class _MoveReq(BaseModel):
    direction: str


@router.post("/spatial/move/{session_id}")
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
        current_storylet = (
            db.query(Storylet)
            .filter(Storylet.requires.contains(f'"location": "{current_location}"'))
            .first()
        )

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
                    requires = cast(Dict[str, Any], current_storylet.requires or {})
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
            requirements = cast(Dict[str, Any], target_storylet.requires)
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


@router.get("/spatial/map")
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


@router.post("/spatial/assign-positions")
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
        return {"assigned": assigned}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"❌ Position assignment failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Position assignment failed: {str(e)}"
        )
