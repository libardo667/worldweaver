"""Spatial navigation endpoints."""

import logging
import re
from typing import Any, Dict, List, cast

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Storylet
from ...models.schemas import (
    SessionId,
    SpatialAssignResponse,
    SpatialMapResponse,
    SpatialMoveResponse,
    SpatialNavigationResponse,
)
from ...services.session_service import (
    get_spatial_navigator,
    get_state_manager,
    resolve_current_location,
    save_state,
)
from ...services.db_json import safe_json_dict
from ...services.spatial_navigator import DIRECTIONS
from ...services.storylet_utils import normalize_requires

router = APIRouter()
logger = logging.getLogger(__name__)
_SEMANTIC_MOVE_PATTERN = re.compile(
    r"^(?:toward|towards|to|find|seek|seeking|look(?:ing)? for)\s+(.+)$",
    re.IGNORECASE,
)


def _storylet_payload_by_id(db: Session, storylet_id: int) -> Dict[str, Any] | None:
    row = (
        db.execute(
            text("""
            SELECT id, title, requires, position
            FROM storylets
            WHERE id = :storylet_id
            LIMIT 1
        """),
            {"storylet_id": int(storylet_id)},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "title": str(row["title"]),
        "requires": safe_json_dict(row["requires"]),
        "position": safe_json_dict(row["position"]),
    }


def _storylet_payload_by_location(db: Session, location: str) -> Dict[str, Any] | None:
    rows = db.execute(text("""
            SELECT id, title, requires, position
            FROM storylets
            WHERE requires IS NOT NULL
        """)).mappings().all()
    normalized_location = str(location or "").strip()
    for row in rows:
        requires = safe_json_dict(row["requires"])
        row_location = requires.get("location")
        if isinstance(row_location, str) and row_location.strip() == normalized_location:
            return {
                "id": int(row["id"]),
                "title": str(row["title"]),
                "requires": requires,
                "position": safe_json_dict(row["position"]),
            }
    return None


def _extract_semantic_move_goal(raw_direction: str) -> str | None:
    text = str(raw_direction or "").strip()
    if not text:
        return None
    match = _SEMANTIC_MOVE_PATTERN.match(text)
    if not match:
        return None
    goal = match.group(1).strip(" .,!?:;-")
    return goal or None


@router.get("/spatial/navigation/{session_id}", response_model=SpatialNavigationResponse)
def get_spatial_navigation(
    session_id: SessionId,
    direction: str | None = Query(default=None),
    semantic_goal: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get 8-directional navigation options from current location."""
    try:
        from ...services import world_memory
        from ...services.semantic_selector import compute_player_context_vector

        state_manager = get_state_manager(session_id, db)
        spatial_nav = get_spatial_navigator(db)

        current_location = resolve_current_location(state_manager, db)
        current_storylet = _storylet_payload_by_location(db, current_location)
        if not current_storylet:
            logger.error(
                "No storylet found for location '%s' even after fallback",
                current_location,
            )
            raise HTTPException(status_code=404, detail="Current location not found")

        current_id = int(current_storylet["id"])
        player_vars = state_manager.get_contextual_variables()
        try:
            context_vector = compute_player_context_vector(state_manager, world_memory, db)
        except Exception:
            context_vector = None
        nav = spatial_nav.get_navigation_options(
            current_id,
            player_vars,
            context_vector=context_vector,
            preferred_direction=direction,
            semantic_goal=semantic_goal,
        )
        goal_hint = None
        if semantic_goal:
            best_hint = spatial_nav.get_semantic_goal_hint(
                current_storylet_id=current_id,
                player_vars=player_vars,
                semantic_goal=semantic_goal,
                context_vector=context_vector,
            )
            goal_hint = best_hint["hint"] if best_hint else None

        return {
            "position": nav["position"],
            "directions": nav["directions"],
            "available_directions": nav.get("available_directions", {}),
            "location_storylet": {
                "id": current_id,
                "title": str(current_storylet["title"]),
                "position": nav["position"],
            },
            "leads": nav.get("leads", []),
            "semantic_goal": semantic_goal,
            "goal_hint": goal_hint,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Spatial navigation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Navigation failed: {str(exc)}")


@router.post("/spatial/move/{session_id}", response_model=SpatialMoveResponse)
def move_in_direction(
    session_id: SessionId,
    payload: dict | None = Body(default=None),
    direction: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Move the player in a specific direction."""
    try:
        logger.info(
            "Move request: session=%s, payload=%s, direction=%s",
            session_id,
            payload,
            direction,
        )

        state_manager = get_state_manager(session_id, db)
        spatial_nav = get_spatial_navigator(db)

        if direction is None and payload is not None:
            direction = payload.get("direction")

        if direction is None:
            logger.error("No direction provided")
            raise HTTPException(status_code=400, detail="Missing 'direction'")

        direction_map = {
            "n": "north",
            "s": "south",
            "e": "east",
            "w": "west",
            "ne": "northeast",
            "nw": "northwest",
            "se": "southeast",
            "sw": "southwest",
        }
        direction_lower = direction.lower()
        original_direction = direction
        direction_full = direction_map.get(direction_lower, direction_lower)
        semantic_goal = None
        direction = direction_full if direction_full in DIRECTIONS else None

        current_location = state_manager.get_variable("location", "start")
        logger.info("Current location: %s", current_location)

        current_storylet = _storylet_payload_by_location(db, cast(str, current_location))

        if not current_storylet:
            logger.warning(
                "No storylet found for location '%s', trying any positioned storylet",
                current_location,
            )
            positioned_ids = list(spatial_nav.storylet_positions.keys())
            if positioned_ids:
                current_storylet = _storylet_payload_by_id(db, int(positioned_ids[0]))
                if current_storylet:
                    requires = normalize_requires(current_storylet.get("requires"))
                    fallback_location = requires.get("location", "unknown")
                    state_manager.set_variable("location", fallback_location)
                    save_state(state_manager, db)
                    logger.info(
                        "Using fallback storylet %s at location '%s'",
                        current_storylet["id"],
                        fallback_location,
                    )

        if not current_storylet:
            logger.error("No positioned storylets found")
            raise HTTPException(status_code=404, detail="No positioned storylets found")

        current_id = int(current_storylet["id"])
        logger.info("Current storylet: %s (%s)", current_id, current_storylet["title"])

        player_vars = state_manager.get_contextual_variables()
        if direction is None:
            semantic_goal = _extract_semantic_move_goal(str(original_direction))
            if not semantic_goal:
                logger.error("Invalid direction: %s", direction_full)
                raise HTTPException(status_code=400, detail=f"Invalid direction: {direction_full}")

            try:
                from ...services import world_memory
                from ...services.semantic_selector import compute_player_context_vector

                context_vector = compute_player_context_vector(state_manager, world_memory, db)
            except Exception:
                context_vector = None

            goal_hint = spatial_nav.get_semantic_goal_hint(
                current_storylet_id=current_id,
                player_vars=player_vars,
                semantic_goal=semantic_goal,
                context_vector=context_vector,
            )
            if not goal_hint:
                logger.error("Invalid direction: %s", direction_full)
                raise HTTPException(status_code=400, detail=f"Invalid direction: {direction_full}")
            direction = goal_hint["direction"]
            logger.info("Semantic movement '%s' resolved to %s", semantic_goal, direction)

        if not spatial_nav.can_move_to_direction(current_id, direction, player_vars):
            logger.warning("Movement blocked: %s", direction)
            raise HTTPException(status_code=403, detail="Cannot move in that direction")

        nav_options = spatial_nav.get_directional_navigation(current_id)
        target = nav_options.get(direction)

        if not target:
            logger.error("No location in direction: %s", direction)
            raise HTTPException(status_code=404, detail="No location in that direction")

        target_storylet = _storylet_payload_by_id(db, int(target["id"]))
        if target_storylet is not None and target_storylet.get("requires") is not None:
            requirements = normalize_requires(target_storylet.get("requires"))
            new_location = requirements.get("location")
            if new_location:
                state_manager.set_variable("location", new_location)
                save_state(state_manager, db)
                logger.info("Moved to: %s", new_location)

        pos = safe_json_dict(target_storylet.get("position")) if target_storylet else {}
        if "x" in pos and "y" in pos:
            new_position = {"x": pos["x"], "y": pos["y"]}
        else:
            new_position = {
                "x": target["position"]["x"],
                "y": target["position"]["y"],
            }

        return {
            "result": f"Moved {direction} to {target['title']}",
            "new_position": new_position,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Movement failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Movement failed: {str(exc)}")


@router.get("/spatial/map", response_model=SpatialMapResponse)
def get_spatial_map(db: Session = Depends(get_db)):
    """Get the full spatial map data for rendering."""
    try:
        spatial_nav = get_spatial_navigator(db)
        map_data = spatial_nav.get_spatial_map_data()
        storylets = []
        for storylet in map_data.get("storylets", []):
            storylets.append(
                {
                    "id": storylet["id"],
                    "title": storylet["title"],
                    "position": storylet["position"],
                }
            )
        return {"storylets": storylets}
    except Exception as exc:
        logger.error("Map generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Map generation failed: {str(exc)}")


@router.post("/spatial/assign-positions", response_model=SpatialAssignResponse)
def assign_spatial_positions(payload: dict = Body(...), db: Session = Depends(get_db)):
    """Assign spatial positions to all storylets."""
    try:
        positions_payload = payload.get("positions", [])
        valid_ids = {storylet.id for storylet in db.query(Storylet).all()}
        for pos in positions_payload:
            if pos["storylet_id"] not in valid_ids:
                raise HTTPException(
                    status_code=404,
                    detail=f"Storylet ID {pos['storylet_id']} not found",
                )

        spatial_nav = get_spatial_navigator(db)
        storylets = db.query(Storylet).all()
        storylet_data = []
        for storylet in storylets:
            storylet_data.append(
                {
                    "title": storylet.title,
                    "choices": cast(List[Dict[str, Any]], storylet.choices or []),
                    "requires": cast(Dict[str, Any], storylet.requires or {}),
                }
            )

        positions = spatial_nav.assign_spatial_positions(storylet_data)
        assigned = [{"storylet_id": int(storylet_id), "x": pos.x, "y": pos.y} for storylet_id, pos in positions.items()]
        return {"assigned": assigned, "assigned_count": len(assigned)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Position assignment failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Position assignment failed: {str(exc)}")
