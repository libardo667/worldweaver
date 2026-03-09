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

_INTERNAL_SESSION_PREFIXES = ("world-", "_", "player-", "agent-")


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
    session_id: Optional[str] = Query(default=None),
    events_limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Human-readable snapshot of the current world state, scoped to the player's location.

    When session_id is provided the roster and timeline are filtered to events
    visible from the player's current location. known_agents lists agents the
    player can write to (co-located or have already mailed the player).
    No LLM — pure aggregation.
    """
    from ...services.world_memory import get_world_history
    from ..game.state import _read_world_id

    world_id = _read_world_id()

    # ── Recent events ────────────────────────────────────────────────────────
    # Use a larger window for location tracking so agents don't show "unknown"
    # if their last location-stamped event is older than the timeline window.
    _LOCATION_SCAN_LIMIT = max(events_limit, 200)
    location_scan_events = get_world_history(db, limit=_LOCATION_SCAN_LIMIT)
    events = location_scan_events[:events_limit]
    full_timeline = [
        {
            "ts": (e.created_at.isoformat() if e.created_at else None),
            "who": e.session_id,
            "summary": (e.summary or "")[:120],
            "location": (e.world_state_delta or {}).get("location"),
        }
        for e in events
    ]

    # Derive per-session location from the most recent event that sets it.
    # Scan the full location_scan_events window (not just the display window)
    # so sessions that haven't acted recently still show their last known location.
    session_last_location: Dict[str, str] = {}
    session_last_seen: Dict[str, str] = {}
    for e in reversed(location_scan_events):  # oldest first so later events overwrite
        sid = e.session_id or ""
        if not sid:
            continue
        ts = e.created_at.isoformat() if e.created_at else None
        session_last_seen[sid] = ts or ""
        loc = (e.world_state_delta or {}).get("location")
        if loc:
            session_last_location[sid] = str(loc)

    # Player's current location (used to scope the digest)
    player_location: Optional[str] = None
    if session_id and _is_player_session(session_id):
        player_location = session_last_location.get(session_id)

    # ── Timeline — filtered by player location ───────────────────────────────
    if player_location:
        timeline = [
            e for e in full_timeline
            if e["location"] == player_location or e["who"] == session_id
        ]
    else:
        timeline = full_timeline

    # Build roster — player sessions only
    from ...services.session_service import get_state_manager

    all_session_ids = list(session_last_seen.keys())
    full_roster = []
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
        full_roster.append({
            "session_id": sid,
            "location": session_last_location.get(sid, "unknown"),
            "last_seen": session_last_seen.get(sid),
            "player_name": player_name,
        })
    full_roster.sort(key=lambda r: r["last_seen"] or "", reverse=True)

    # Filter roster to the player's location (always include the player themselves)
    if player_location:
        roster = [
            r for r in full_roster
            if r["location"] == player_location or r["session_id"] == session_id
        ]
    else:
        roster = full_roster

    # ── Location population count (based on full roster) ────────────────────
    location_counts: Dict[str, int] = {}
    for r in full_roster:
        loc = r["location"]
        if loc and loc != "unknown":
            location_counts[loc] = location_counts.get(loc, 0) + 1

    # ── Known agents: co-located agents + agents who have mailed the player ──
    # Discover all available agents from workspace directories
    available_agents: List[str] = []
    if _OPENCLAW_ROOT.exists():
        for ws in _OPENCLAW_ROOT.iterdir():
            if ws.is_dir() and ws.name.startswith("workspace-"):
                name = ws.name[len("workspace-"):]
                if _SAFE_NAME_RE.match(name):
                    available_agents.append(name)
    available_agents.sort()

    # Agent last-known locations from event history.
    # Agent session IDs follow the pattern "{agentname}-{YYYYMMDD-HHMMSS}".
    agent_last_location: Dict[str, str] = {}
    for sid, loc in session_last_location.items():
        for agent_name in available_agents:
            if sid == agent_name or sid.startswith(agent_name + "-"):
                agent_last_location[agent_name] = loc
                break

    known_agents: List[str] = []
    if player_location:
        known_agents = [a for a in available_agents if agent_last_location.get(a) == player_location]
    # Always add agents who have already mailed this player (regardless of location)
    if session_id and _SAFE_SESSION_RE.match(session_id):
        inbox = _player_inbox(session_id)
        if inbox.exists():
            import re as _re
            for p in inbox.glob("from_*.md"):
                # Filename pattern: from_{agent}_{YYYYMMDD-HHMMSS}.md
                m = _re.match(r"^from_([a-z][a-z0-9_-]*)_\d{8}-\d{6}\.md$", p.name)
                if m:
                    agent_from_inbox = m.group(1)
                    if agent_from_inbox in available_agents and agent_from_inbox not in known_agents:
                        known_agents.append(agent_from_inbox)

    return {
        "world_id": world_id or None,
        "seeded": bool(world_id),
        "active_sessions": len(roster),
        "roster": roster,
        "location_population": location_counts,
        "timeline": timeline,
        "events_shown": len(timeline),
        "known_agents": known_agents,
        "player_location": player_location,
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

    # Known locations: prefer world bible (always available after seed), fall back to event history
    bible_locations: List[str] = []
    if world_id:
        from ...services.session_service import get_state_manager as _gsm
        try:
            world_bible = _gsm(world_id, db).get_world_bible()
            if world_bible and isinstance(world_bible, dict):
                bible_locations = [
                    str(loc.get("name", "")).strip()
                    for loc in world_bible.get("locations", [])
                    if isinstance(loc, dict) and loc.get("name")
                ]
        except Exception:
            pass

    event_locations = sorted({
        str((e.world_state_delta or {}).get("location"))
        for e in events
        if (e.world_state_delta or {}).get("location")
    })

    known_locations = bible_locations if bible_locations else event_locations

    result = generate_entry_cards(
        event_summaries=event_summaries,
        fact_summaries=fact_summaries,
        existing_session_labels=existing,
        world_name="Oakhaven Lows",
        known_locations=known_locations,
    )

    return {
        "world_id": world_id,
        "snapshot": result.get("snapshot", ""),
        "cards": result.get("cards", []),
        "locations": known_locations,
    }


# ---------------------------------------------------------------------------
# Player ↔ Agent letter system
# ---------------------------------------------------------------------------

_OPENCLAW_ROOT = Path(__file__).parents[3] / ".openclaw"
_PLAYER_INBOX_ROOT = Path(__file__).parents[3] / "data" / "player_inboxes"
_SAFE_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_SAFE_SESSION_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _agent_inbox(agent_name: str) -> Path:
    return _OPENCLAW_ROOT / f"workspace-{agent_name}" / "worldweaver_runs" / agent_name / "letters" / "inbox"


def _player_inbox(session_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", session_id)[:64]
    return _PLAYER_INBOX_ROOT / safe


def _valid_agent(agent_name: str) -> bool:
    if not _SAFE_NAME_RE.match(agent_name):
        return False
    workspace = _OPENCLAW_ROOT / f"workspace-{agent_name}"
    return workspace.is_dir()


class SendLetterRequest(BaseModel):
    to_agent: str = Field(..., min_length=1, max_length=32)
    from_name: str = Field(..., min_length=1, max_length=60)
    body: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = Field(default=None, max_length=64)


class AgentReplyRequest(BaseModel):
    from_agent: str = Field(..., min_length=1, max_length=32)
    to_session_id: str = Field(..., min_length=1, max_length=64)
    body: str = Field(..., min_length=1, max_length=4000)


@router.post("/world/letter")
def send_letter(payload: SendLetterRequest, db: Session = Depends(get_db)):
    """Drop a player letter into an agent's inbox directory.

    The agent will find it on their next heartbeat, read it, and let it
    influence their next in-world action. If session_id is provided it is
    embedded in the letter so the agent can reply.
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

    reply_header = ""
    if payload.session_id and _SAFE_SESSION_RE.match(payload.session_id):
        reply_header = f"Reply-To-Session: {payload.session_id}\n"

    letter_path.write_text(
        f"# Letter from {payload.from_name}\n{reply_header}\n{payload.body}\n",
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


@router.post("/world/letter/reply")
def agent_reply_letter(payload: AgentReplyRequest, db: Session = Depends(get_db)):
    """Drop an agent reply into a player's inbox.

    Called by agent heartbeats when they want to write back to a player.
    The to_session_id comes from the Reply-To-Session header in received letters.
    """
    agent = payload.from_agent.lower().strip()
    if not _valid_agent(agent):
        raise HTTPException(status_code=404, detail=f"No agent workspace found for '{agent}'.")

    if not _SAFE_SESSION_RE.match(payload.to_session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")

    inbox = _player_inbox(payload.to_session_id)
    inbox.mkdir(parents=True, exist_ok=True)

    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    filename = f"from_{agent}_{ts}.md"
    letter_path = inbox / filename

    letter_path.write_text(
        f"# Letter from {agent.capitalize()}\n\n{payload.body}\n",
        encoding="utf-8",
    )

    # Log to world timeline
    from ..game.state import _read_world_id
    world_id = _read_world_id()
    if world_id:
        event = WorldEvent(
            session_id=f"agent-{agent}",
            event_type="agent_letter",
            summary=f"{agent.capitalize()} sent a reply to a player.",
            world_state_delta={},
        )
        db.add(event)
        db.commit()

    return {"success": True, "letter_id": filename, "from_agent": agent}


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


@router.get("/world/letters/my-inbox/{session_id}")
def get_player_inbox(session_id: str):
    """Return unread letters in a player's inbox, deposited by agents."""
    if not _SAFE_SESSION_RE.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")

    inbox = _player_inbox(session_id)
    if not inbox.exists():
        return {"session_id": session_id, "letters": [], "count": 0}

    letters = []
    for p in sorted(inbox.glob("*.md")):
        try:
            letters.append({"filename": p.name, "body": p.read_text(encoding="utf-8")})
        except Exception:
            pass

    return {"session_id": session_id, "letters": letters, "count": len(letters)}
