"""World memory service: records and queries persistent world events."""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..models import WorldEvent

logger = logging.getLogger(__name__)

PERMANENT_EVENT_TYPE = "permanent_change"
PERMANENT_EVENT_WEIGHT = 3.0
HIGH_IMPACT_DELTA_TOKENS = (
    "bridge",
    "destroy",
    "burn",
    "broken",
    "collapse",
    "flood",
    "dead",
    "killed",
    "sealed",
    "ruin",
)
HIGH_IMPACT_KEYS = {"environment", "spatial_nodes", "location", "danger_level"}


def _normalize_delta(delta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a safe dict for world-state deltas."""
    if not isinstance(delta, dict):
        return {}
    return {str(key): value for key, value in delta.items()}


def _is_permanent_delta(delta: Dict[str, Any]) -> bool:
    """Heuristic for deltas that imply permanent world change."""
    if not delta:
        return False

    if bool(delta.get("permanent")) or bool(delta.get("_permanent")):
        return True

    for key, value in delta.items():
        key_lower = str(key).lower()
        if key_lower in HIGH_IMPACT_KEYS:
            return True
        if any(token in key_lower for token in HIGH_IMPACT_DELTA_TOKENS):
            return True
        if isinstance(value, bool) and value and any(
            token in key_lower for token in HIGH_IMPACT_DELTA_TOKENS
        ):
            return True

    return False


def infer_event_type(event_type: str, delta: Optional[Dict[str, Any]] = None) -> str:
    """Map a base event type to permanent_change when delta implies permanence."""
    normalized_delta = _normalize_delta(delta)
    if event_type == PERMANENT_EVENT_TYPE:
        return event_type
    if _is_permanent_delta(normalized_delta):
        return PERMANENT_EVENT_TYPE
    return event_type


def should_trigger_storylet(
    event_type: str, delta: Optional[Dict[str, Any]] = None
) -> bool:
    """Return True when an event should immediately trigger new narrative."""
    normalized_delta = _normalize_delta(delta)
    if event_type == PERMANENT_EVENT_TYPE:
        return True
    return _is_permanent_delta(normalized_delta)


def apply_event_delta_to_state(
    state_manager: Any, delta: Optional[Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """Apply event deltas into the active state manager."""
    normalized_delta = _normalize_delta(delta)
    if not normalized_delta:
        return {"variables": {}, "environment": {}, "spatial_nodes": {}}

    if hasattr(state_manager, "apply_world_delta"):
        return state_manager.apply_world_delta(normalized_delta)

    applied: Dict[str, Dict[str, Any]] = {
        "variables": {},
        "environment": {},
        "spatial_nodes": {},
    }
    for key, value in normalized_delta.items():
        if hasattr(state_manager, "set_variable"):
            state_manager.set_variable(key, value)
            applied["variables"][key] = value
    return applied


def record_event(
    db: Session,
    session_id: Optional[str],
    storylet_id: Optional[int],
    event_type: str,
    summary: str,
    delta: Optional[Dict[str, Any]] = None,
    state_manager: Optional[Any] = None,
) -> WorldEvent:
    """Create a WorldEvent, apply deltas, embed summary, and persist it."""
    from .embedding_service import embed_text

    normalized_delta = _normalize_delta(delta)
    resolved_event_type = infer_event_type(event_type, normalized_delta)
    if state_manager is not None and normalized_delta:
        applied = apply_event_delta_to_state(state_manager, normalized_delta)
        logger.debug("Applied world delta to state: %s", applied)

    embedding = embed_text(summary)

    event = WorldEvent(
        session_id=session_id,
        storylet_id=storylet_id,
        event_type=resolved_event_type,
        summary=summary,
        embedding=embedding,
        world_state_delta=normalized_delta,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    logger.info("Recorded world event: [%s] %s", resolved_event_type, summary[:80])
    return event


def get_world_history(
    db: Session,
    session_id: Optional[str] = None,
    limit: int = 50,
) -> List[WorldEvent]:
    """Get recent world events in reverse chronological order."""
    query = db.query(WorldEvent).order_by(desc(WorldEvent.id))
    if session_id:
        query = query.filter(WorldEvent.session_id == session_id)
    return query.limit(limit).all()


def get_world_context_vector(
    db: Session,
    session_id: Optional[str] = None,
    limit: int = 20,
) -> Optional[List[float]]:
    """Compute an average embedding of recent world events.

    Returns None if no events with embeddings exist.
    """
    events = get_world_history(db, session_id=session_id, limit=limit)
    weighted_vectors = []
    weight_total = 0.0

    for event in events:
        if not event.embedding:
            continue
        event_delta = event.world_state_delta if isinstance(event.world_state_delta, dict) else {}
        resolved_type = infer_event_type(event.event_type, event_delta)
        weight = PERMANENT_EVENT_WEIGHT if resolved_type == PERMANENT_EVENT_TYPE else 1.0
        weighted_vectors.append((event.embedding, weight))
        weight_total += weight

    if not weighted_vectors or weight_total <= 0.0:
        return None

    dim = len(weighted_vectors[0][0])
    avg = [0.0] * dim
    for vec, weight in weighted_vectors:
        for i in range(dim):
            avg[i] += vec[i] * weight
    for i in range(dim):
        avg[i] /= weight_total

    return avg


def query_world_facts(
    db: Session,
    query: str,
    session_id: Optional[str] = None,
    limit: int = 10,
) -> List[WorldEvent]:
    """Semantic search over world events by cosine similarity."""
    from .embedding_service import cosine_similarity, embed_text

    query_vector = embed_text(query)

    events = get_world_history(db, session_id=session_id, limit=200)

    scored = []
    for event in events:
        if event.embedding:
            sim = cosine_similarity(query_vector, event.embedding)
            scored.append((event, sim))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [event for event, _ in scored[:limit]]
