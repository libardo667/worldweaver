"""World memory and projection endpoints."""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
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

_INTERNAL_SESSION_PREFIXES = ("world-", "_")


def _is_player_session(session_id: str) -> bool:
    """Return True if this looks like a player/agent session rather than a world admin session."""
    if not session_id:
        return False
    for prefix in _INTERNAL_SESSION_PREFIXES:
        if session_id.startswith(prefix):
            return False
    return True

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


@router.get("/world/digest")
def get_world_digest(
    events_limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Human-readable snapshot of the current world state.

    Returns active sessions with their last known location, a compact event
    timeline, and a location population summary. No LLM — pure aggregation.
    """
    from ...services.world_memory import get_world_history, get_world_projection
    from ..game.state import _read_world_id

    world_id = _read_world_id()

    # ── Recent events ────────────────────────────────────────────────────────
    events = get_world_history(db, limit=events_limit)
    timeline = [
        {
            "ts": (e.created_at.isoformat() if e.created_at else None),
            "who": e.session_id,
            "summary": (e.summary or "")[:120],
            "location": (e.world_state_delta or {}).get("location"),
        }
        for e in events
    ]

    # ── Session roster from projection (location key per session) ────────────
    projection_rows = get_world_projection(db, limit=1000)

    # Collect the last known location for each session from projection
    session_locations: Dict[str, str] = {}
    for row in projection_rows:
        path = str(row.path or "")
        # Projection paths look like "session_id.location" or bare "location"
        # We want per-session location keys if they exist, otherwise fall back
        # to the bare world-level "location" key per session from events
        if path == "location" or path.endswith(".location"):
            pass  # handled via event scan below

    # Derive per-session location from the most recent event that sets it
    session_last_location: Dict[str, str] = {}
    session_last_seen: Dict[str, str] = {}
    for e in reversed(events):  # oldest first so later events overwrite
        sid = e.session_id or ""
        if not sid:
            continue
        ts = e.created_at.isoformat() if e.created_at else None
        session_last_seen[sid] = ts or ""
        loc = (e.world_state_delta or {}).get("location")
        if loc:
            session_last_location[sid] = str(loc)

    # Build roster — player sessions only
    from ...services.session_service import get_state_manager

    all_session_ids = list(session_last_seen.keys())
    roster = []
    for sid in all_session_ids:
        if not _is_player_session(sid):
            continue
        # Look up character name from session state vars
        player_name: Optional[str] = None
        try:
            sm = get_state_manager(sid, db)
            player_role = sm.get_variable("player_role") or ""
            if player_role:
                # player_role format is "Name — role description"; extract just the name
                name_part = player_role.split(" — ")[0].strip() if " — " in player_role else player_role.strip()
                player_name = name_part or None
        except Exception:
            pass
        roster.append({
            "session_id": sid,
            "location": session_last_location.get(sid, "unknown"),
            "last_seen": session_last_seen.get(sid),
            "player_name": player_name,
        })
    roster.sort(key=lambda r: r["last_seen"] or "", reverse=True)

    # ── Location population count ────────────────────────────────────────────
    location_counts: Dict[str, int] = {}
    for r in roster:
        loc = r["location"]
        if loc and loc != "unknown":
            location_counts[loc] = location_counts.get(loc, 0) + 1

    return {
        "world_id": world_id or None,
        "seeded": bool(world_id),
        "active_sessions": len(roster),
        "roster": roster,
        "location_population": location_counts,
        "timeline": timeline,
        "events_shown": len(timeline),
    }


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


@router.get("/world/entry")
def get_world_entry(
    db: Session = Depends(get_db),
):
    """Generate entry cards + world snapshot for the player entry screen.

    Queries recent events and graph facts, then uses the narrator LLM to
    generate an atmospheric world snapshot and 4 role cards for a new player
    to choose from.
    """
    from ...services.world_memory import get_world_history, query_graph_facts
    from ...services.llm_service import generate_entry_cards
    from ..game.state import _read_world_id

    world_id = _read_world_id()

    # Recent event summaries
    events = get_world_history(db, limit=30)
    event_summaries = [
        f"[{e.session_id or 'world'}] {e.summary}"
        for e in events
        if e.summary
    ]

    # Graph facts about named characters
    facts = query_graph_facts(db, query="character person NPC inhabitant named", limit=20)
    fact_summaries = [f.summary for f in facts if f.summary]

    # Existing session labels (so cards don't duplicate active characters)
    existing = list({e.session_id for e in events if e.session_id and _is_player_session(e.session_id)})

    result = generate_entry_cards(
        event_summaries=event_summaries,
        fact_summaries=fact_summaries,
        existing_session_labels=existing,
        world_name="Oakhaven Lows",
    )

    return {
        "world_id": world_id,
        "snapshot": result.get("snapshot", ""),
        "cards": result.get("cards", []),
    }


# ---------------------------------------------------------------------------
# Player ↔ Agent letter system
# ---------------------------------------------------------------------------

_OPENCLAW_ROOT = Path(__file__).parents[3] / ".openclaw"
_SAFE_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


def _agent_inbox(agent_name: str) -> Path:
    return _OPENCLAW_ROOT / f"workspace-{agent_name}" / "worldweaver_runs" / agent_name / "letters" / "inbox"


def _valid_agent(agent_name: str) -> bool:
    if not _SAFE_NAME_RE.match(agent_name):
        return False
    workspace = _OPENCLAW_ROOT / f"workspace-{agent_name}"
    return workspace.is_dir()


class SendLetterRequest(BaseModel):
    to_agent: str = Field(..., min_length=1, max_length=32)
    from_name: str = Field(..., min_length=1, max_length=60)
    body: str = Field(..., min_length=1, max_length=4000)


@router.post("/world/letter")
def send_letter(payload: SendLetterRequest, db: Session = Depends(get_db)):
    """Drop a player letter into an agent's inbox directory.

    The agent will find it on their next heartbeat, read it, and let it
    influence their next in-world action.
    """
    agent = payload.to_agent.lower().strip()
    if not _valid_agent(agent):
        raise HTTPException(status_code=404, detail=f"No agent workspace found for '{agent}'.")

    inbox = _agent_inbox(agent)
    inbox.mkdir(parents=True, exist_ok=True)

    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    safe_from = re.sub(r"[^a-zA-Z0-9_-]", "_", payload.from_name)[:20]
    filename = f"from_{safe_from}_{ts}.md"
    letter_path = inbox / filename

    letter_path.write_text(
        f"# Letter from {payload.from_name}\n\n{payload.body}\n",
        encoding="utf-8",
    )

    # Log to world timeline so it shows up in the digest
    from ..game.state import _read_world_id
    world_id = _read_world_id()
    if world_id:
        event = WorldEvent(
            session_id=f"player-{safe_from}",
            event_type="player_letter",
            summary=f"{payload.from_name} sent a letter to {agent}.",
            world_state_delta={},
        )
        db.add(event)
        db.commit()

    return {"success": True, "letter_id": filename, "delivered_to": agent}


@router.get("/world/letters/inbox/{agent}")
def get_agent_inbox(agent: str):
    """List unread letters waiting in an agent's inbox."""
    agent = agent.lower().strip()
    if not _valid_agent(agent):
        raise HTTPException(status_code=404, detail=f"No agent workspace found for '{agent}'.")

    inbox = _agent_inbox(agent)
    if not inbox.exists():
        return {"agent": agent, "letters": [], "count": 0}

    letters = []
    for p in sorted(inbox.glob("*.md")):
        try:
            letters.append({"filename": p.name, "body": p.read_text(encoding="utf-8")})
        except Exception:
            pass

    return {"agent": agent, "letters": letters, "count": len(letters)}
