"""Main game API routes with Advanced State Management and Spatial Navigation."""

import logging
from typing import Any, Dict, List, cast
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from fastapi import Body, Query
from sqlalchemy.orm import Session

from ..database import get_db, SessionLocal
from ..models import Storylet, WorldEvent, WorldFact, WorldNode
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
    WorldHistoryResponse,
    WorldFactsResponse,
    WorldGraphFactsResponse,
    WorldGraphNeighborhoodResponse,
    WorldLocationFactsResponse,
    WorldProjectionResponse,
    ActionRequest,
    ActionResponse,
)
from ..services.game_logic import ensure_storylets, render
from ..services.spatial_navigator import DIRECTIONS
from ..services.storylet_selector import pick_storylet_enhanced
from ..services.storylet_utils import (
    find_storylet_by_location,
    normalize_choice,
    normalize_requires,
)
from ..services import session_service
from ..services.session_service import (
    get_spatial_navigator,
    get_state_manager,
    remove_cached_sessions,
    resolve_current_location,
    save_state,
)

router = APIRouter()

# Re-export shared caches for compatibility with existing tests/fixtures.
_state_managers = session_service._state_managers
_spatial_navigators = session_service._spatial_navigators


# Compatibility aliases for existing imports/tests while keeping internals in services.
save_state_to_db = save_state
_resolve_current_location = resolve_current_location


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
            ChoiceOut(**normalize_choice(c))
            for c in cast(List[Dict[str, Any]], story.choices or [])
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

        # Remove only the specific session IDs that were deleted from the database.
        removed_from_cache = remove_cached_sessions(deleted_session_ids)

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


@router.get("/spatial/navigation/{session_id}", response_model=SpatialNavigationResponse)
def get_spatial_navigation(session_id: SessionId, db: Session = Depends(get_db)):
    """Get 8-directional navigation options from current location."""
    try:
        state_manager = get_state_manager(session_id, db)
        spatial_nav = get_spatial_navigator(db)

        current_location = _resolve_current_location(state_manager, db)

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
        current_storylet = find_storylet_by_location(db, cast(str, current_location))

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
                    requires = normalize_requires(current_storylet.requires)
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
            requirements = normalize_requires(target_storylet.requires)
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


def _serialize_world_node(node: WorldNode | None) -> Dict[str, Any] | None:
    """Serialize a world graph node to API shape."""
    if node is None:
        return None
    return {
        "id": int(node.id),
        "node_type": str(node.node_type),
        "name": str(node.name),
        "normalized_name": str(node.normalized_name),
    }


def _serialize_world_facts(
    db: Session,
    facts: List[WorldFact],
) -> List[Dict[str, Any]]:
    """Serialize world facts with attached subject/location nodes."""
    node_ids: set[int] = set()
    for fact in facts:
        if fact.subject_node_id:
            node_ids.add(int(fact.subject_node_id))
        if fact.location_node_id:
            node_ids.add(int(fact.location_node_id))

    node_map: Dict[int, WorldNode] = {}
    if node_ids:
        nodes = db.query(WorldNode).filter(WorldNode.id.in_(list(node_ids))).all()
        node_map = {int(node.id): node for node in nodes}

    serialized: List[Dict[str, Any]] = []
    for fact in facts:
        subject = node_map.get(int(fact.subject_node_id))
        if subject is None:
            subject_payload = {
                "id": int(fact.subject_node_id),
                "node_type": "unknown",
                "name": "unknown",
                "normalized_name": "unknown",
            }
        else:
            subject_payload = _serialize_world_node(subject)
        location = (
            node_map.get(int(fact.location_node_id))
            if fact.location_node_id is not None
            else None
        )
        serialized.append(
            {
                "id": int(fact.id),
                "session_id": fact.session_id,
                "subject_node": subject_payload,
                "location_node": _serialize_world_node(location),
                "predicate": str(fact.predicate),
                "value": fact.value,
                "confidence": float(fact.confidence or 0.0),
                "is_active": bool(fact.is_active),
                "source_event_id": fact.source_event_id,
                "summary": str(fact.summary),
                "updated_at": fact.updated_at.isoformat() if fact.updated_at else None,
            }
        )
    return serialized


@router.get("/world/graph/facts", response_model=WorldGraphFactsResponse)
def query_world_graph_facts_endpoint(
    query: str = Query(default="", min_length=0),
    session_id: Optional[str] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Semantic search over persistent world fact graph."""
    from ..services.world_memory import query_graph_facts

    facts = query_graph_facts(db, query=query, session_id=session_id, limit=limit)
    serialized = _serialize_world_facts(db, facts)
    return {"query": query, "facts": serialized, "count": len(serialized)}


@router.get("/world/graph/neighborhood", response_model=WorldGraphNeighborhoodResponse)
def get_world_graph_neighborhood_endpoint(
    node: str = Query(..., min_length=1),
    node_type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get neighboring graph structure around a node name."""
    from ..services.world_memory import get_node_neighborhood

    result = get_node_neighborhood(
        db,
        node_name=node,
        node_type=node_type,
        limit=limit,
    )
    center_node = result.get("node")
    edges_raw = result.get("edges", [])
    facts_raw = result.get("facts", [])

    edges: List[Dict[str, Any]] = []
    for edge in edges_raw:
        source_node = edge.get("source_node")
        target_node = edge.get("target_node")
        if source_node is None or target_node is None:
            continue
        edges.append(
            {
                "id": edge.get("id"),
                "edge_type": edge.get("edge_type"),
                "source_node": _serialize_world_node(source_node),
                "target_node": _serialize_world_node(target_node),
                "weight": float(edge.get("weight") or 0.0),
                "confidence": float(edge.get("confidence") or 0.0),
                "source_event_id": edge.get("source_event_id"),
                "metadata": edge.get("metadata") or {},
            }
        )

    facts = _serialize_world_facts(db, cast(List[WorldFact], facts_raw))

    return {
        "node": _serialize_world_node(cast(Optional[WorldNode], center_node)),
        "edges": edges,
        "facts": facts,
        "count": len(edges) + len(facts),
    }


@router.get("/world/graph/location/{location}", response_model=WorldLocationFactsResponse)
def get_world_graph_location_facts_endpoint(
    location: str,
    session_id: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get active graph facts associated with a location."""
    from ..services.world_memory import get_location_facts

    facts = get_location_facts(
        db,
        location=location,
        session_id=session_id,
        limit=limit,
    )
    serialized = _serialize_world_facts(db, facts)
    return {"location": location, "facts": serialized, "count": len(serialized)}


@router.get("/world/projection", response_model=WorldProjectionResponse)
def get_world_projection_endpoint(
    prefix: Optional[str] = Query(default=None),
    include_deleted: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Inspect current event-sourced world projection state."""
    from ..services.world_memory import get_world_projection

    rows = get_world_projection(
        db=db,
        prefix=prefix,
        include_deleted=include_deleted,
        limit=limit,
    )
    source_event_ids = {
        int(row.source_event_id)
        for row in rows
        if row.source_event_id is not None
    }
    event_map: Dict[int, WorldEvent] = {}
    if source_event_ids:
        source_events = db.query(WorldEvent).filter(WorldEvent.id.in_(list(source_event_ids))).all()
        event_map = {int(event.id): event for event in source_events}

    return {
        "prefix": prefix,
        "entries": [
            {
                "path": str(row.path),
                "value": row.value,
                "is_deleted": bool(row.is_deleted),
                "confidence": float(row.confidence or 0.0),
                "source_event_id": row.source_event_id,
                "source_event_type": (
                    event_map[int(row.source_event_id)].event_type
                    if row.source_event_id is not None and int(row.source_event_id) in event_map
                    else None
                ),
                "source_event_summary": (
                    event_map[int(row.source_event_id)].summary
                    if row.source_event_id is not None and int(row.source_event_id) in event_map
                    else None
                ),
                "source_event_created_at": (
                    event_map[int(row.source_event_id)].created_at.isoformat()
                    if row.source_event_id is not None
                    and int(row.source_event_id) in event_map
                    and event_map[int(row.source_event_id)].created_at
                    else None
                ),
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in rows
        ],
        "count": len(rows),
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
    current_storylet = find_storylet_by_location(db, current_location)

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

