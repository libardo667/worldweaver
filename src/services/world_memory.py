"""World memory service: records and queries persistent world events."""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..models import WorldEvent

logger = logging.getLogger(__name__)


def record_event(
    db: Session,
    session_id: Optional[str],
    storylet_id: Optional[int],
    event_type: str,
    summary: str,
    delta: Optional[Dict[str, Any]] = None,
) -> WorldEvent:
    """Create a WorldEvent, embed the summary, and persist it."""
    from .embedding_service import embed_text

    embedding = embed_text(summary)

    event = WorldEvent(
        session_id=session_id,
        storylet_id=storylet_id,
        event_type=event_type,
        summary=summary,
        embedding=embedding,
        world_state_delta=delta or {},
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    logger.info("Recorded world event: [%s] %s", event_type, summary[:80])
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
    vectors = [e.embedding for e in events if e.embedding]

    if not vectors:
        return None

    dim = len(vectors[0])
    avg = [0.0] * dim
    for vec in vectors:
        for i in range(dim):
            avg[i] += vec[i]
    for i in range(dim):
        avg[i] /= len(vectors)

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
