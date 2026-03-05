"""World memory and projection endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import WorldEvent, WorldFact, WorldNode
from ...models.schemas import (
    WorldFactsResponse,
    WorldGraphFactsResponse,
    WorldGraphNeighborhoodResponse,
    WorldHistoryResponse,
    WorldLocationFactsResponse,
    WorldProjectionResponse,
)

router = APIRouter()


@router.get("/world/history", response_model=WorldHistoryResponse)
def get_world_history_endpoint(
    session_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    event_type: Optional[str] = Query(default=None, min_length=1),
    since: Optional[datetime] = Query(default=None),
    until: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get recent world events."""
    from ...services.world_memory import get_world_history

    normalized_event_type = event_type.strip() if event_type else None
    active_filters: Dict[str, str] = {}
    if normalized_event_type:
        active_filters["event_type"] = normalized_event_type
    if since is not None:
        active_filters["since"] = since.isoformat()
    if until is not None:
        active_filters["until"] = until.isoformat()

    events = get_world_history(
        db,
        session_id=session_id,
        limit=limit,
        event_type=normalized_event_type,
        since=since,
        until=until,
    )
    return {
        "events": [
            {
                "id": event.id,
                "session_id": event.session_id,
                "storylet_id": event.storylet_id,
                "event_type": event.event_type,
                "summary": event.summary,
                "world_state_delta": event.world_state_delta or {},
                "created_at": event.created_at.isoformat() if event.created_at else None,
            }
            for event in events
        ],
        "count": len(events),
        "filters": active_filters,
    }


@router.get("/world/facts", response_model=WorldFactsResponse)
def query_world_facts_endpoint(
    query: str = Query(..., min_length=1),
    session_id: Optional[str] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Semantic search over world history."""
    from ...services.world_memory import query_world_facts

    facts = query_world_facts(db, query, session_id=session_id, limit=limit)
    return {
        "query": query,
        "facts": [
            {
                "id": event.id,
                "session_id": event.session_id,
                "storylet_id": event.storylet_id,
                "event_type": event.event_type,
                "summary": event.summary,
                "world_state_delta": event.world_state_delta or {},
                "created_at": event.created_at.isoformat() if event.created_at else None,
            }
            for event in facts
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


def _serialize_world_facts(db: Session, facts: List[WorldFact]) -> List[Dict[str, Any]]:
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

        location = node_map.get(int(fact.location_node_id)) if fact.location_node_id is not None else None
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
    from ...services.world_memory import query_graph_facts

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
    from ...services.world_memory import get_node_neighborhood

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
    from ...services.world_memory import get_location_facts

    facts = get_location_facts(db, location=location, session_id=session_id, limit=limit)
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
    from ...services.world_memory import get_world_projection

    rows = get_world_projection(
        db=db,
        prefix=prefix,
        include_deleted=include_deleted,
        limit=limit,
    )
    source_event_ids = {int(row.source_event_id) for row in rows if row.source_event_id is not None}
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
                "source_event_type": (event_map[int(row.source_event_id)].event_type if row.source_event_id is not None and int(row.source_event_id) in event_map else None),
                "source_event_summary": (event_map[int(row.source_event_id)].summary if row.source_event_id is not None and int(row.source_event_id) in event_map else None),
                "source_event_created_at": (event_map[int(row.source_event_id)].created_at.isoformat() if row.source_event_id is not None and int(row.source_event_id) in event_map and event_map[int(row.source_event_id)].created_at else None),
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in rows
        ],
        "count": len(rows),
    }
