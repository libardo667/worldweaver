"""Spatial navigation endpoints."""

import logging
from typing import Any, Dict, List, cast

from fastapi import APIRouter, Body, Depends, HTTPException, Query
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
from ...services.storylet_utils import find_storylet_by_location, normalize_requires

router = APIRouter()


@router.get("/spatial/navigation/{session_id}", response_model=SpatialNavigationResponse)
def get_spatial_navigation(session_id: SessionId, db: Session = Depends(get_db)):
    """Get 8-directional navigation options from current location."""
    try:
        state_manager = get_state_manager(session_id, db)
        spatial_nav = get_spatial_navigator(db)

        current_location = resolve_current_location(state_manager, db)
        current_storylet = find_storylet_by_location(db, current_location)
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
    except Exception as exc:
        logging.error("Spatial navigation failed: %s", exc)
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
        logging.info(
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
            logging.error("No direction provided")
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
        direction_full = direction_map.get(direction_lower, direction_lower)

        if direction_full not in DIRECTIONS:
            logging.error("Invalid direction: %s", direction)
            raise HTTPException(status_code=400, detail=f"Invalid direction: {direction}")
        direction = direction_full

        current_location = state_manager.get_variable("location", "start")
        logging.info("Current location: %s", current_location)

        current_storylet = find_storylet_by_location(db, cast(str, current_location))

        if not current_storylet:
            logging.warning(
                "No storylet found for location '%s', trying any positioned storylet",
                current_location,
            )
            positioned_ids = list(spatial_nav.storylet_positions.keys())
            if positioned_ids:
                current_storylet = db.query(Storylet).filter(Storylet.id.in_(positioned_ids)).first()
                if current_storylet:
                    requires = normalize_requires(current_storylet.requires)
                    fallback_location = requires.get("location", "unknown")
                    state_manager.set_variable("location", fallback_location)
                    save_state(state_manager, db)
                    logging.info(
                        "Using fallback storylet %s at location '%s'",
                        current_storylet.id,
                        fallback_location,
                    )

        if not current_storylet:
            logging.error("No positioned storylets found")
            raise HTTPException(status_code=404, detail="No positioned storylets found")

        current_id = cast(int, current_storylet.id)
        logging.info("Current storylet: %s (%s)", current_id, current_storylet.title)

        player_vars = state_manager.get_contextual_variables()
        if not spatial_nav.can_move_to_direction(current_id, direction, player_vars):
            logging.warning("Movement blocked: %s", direction)
            raise HTTPException(status_code=403, detail="Cannot move in that direction")

        nav_options = spatial_nav.get_directional_navigation(current_id)
        target = nav_options.get(direction)

        if not target:
            logging.error("No location in direction: %s", direction)
            raise HTTPException(status_code=404, detail="No location in that direction")

        target_storylet = db.get(Storylet, target["id"])
        if target_storylet is not None and target_storylet.requires is not None:
            requirements = normalize_requires(target_storylet.requires)
            new_location = requirements.get("location")
            if new_location:
                state_manager.set_variable("location", new_location)
                save_state(state_manager, db)
                logging.info("Moved to: %s", new_location)

        pos = safe_json_dict(getattr(target_storylet, "position", None)) if target_storylet else {}
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
        logging.error("Movement failed: %s", exc)
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
        logging.error("Map generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Map generation failed: {str(exc)}")


@router.post("/spatial/assign-positions", response_model=SpatialAssignResponse)
def assign_spatial_positions(payload: dict = Body(...), db: Session = Depends(get_db)):
    """Assign spatial positions to all storylets."""
    try:
        positions_payload = payload.get("positions", [])
        valid_ids = {storylet.id for storylet in db.query(Storylet).all()}
        for pos in positions_payload:
            if pos["storylet_id"] not in valid_ids:
                raise HTTPException(status_code=404, detail=f"Storylet ID {pos['storylet_id']} not found")

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
        assigned = [
            {"storylet_id": int(storylet_id), "x": pos.x, "y": pos.y}
            for storylet_id, pos in positions.items()
        ]
        return {"assigned": assigned, "assigned_count": len(assigned)}
    except HTTPException:
        raise
    except Exception as exc:
        logging.error("Position assignment failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Position assignment failed: {str(exc)}")
