"""World memory and projection endpoints."""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import WorldEvent, WorldFact, WorldNode
from ...models import LocationChat
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
    _PLAYER_ACTION_RE = re.compile(r"^Player action:.*?Result:\s*", re.DOTALL)
    full_timeline = [
        {
            "ts": (e.created_at.isoformat() if e.created_at else None),
            "who": e.session_id,
            "display_name": None,  # enriched below after roster is built
            "summary": e.summary or "",
            "narrative": _PLAYER_ACTION_RE.sub("", e.summary or "").strip() or None,
            "location": (e.world_state_delta or {}).get("location"),
            "destination": (e.world_state_delta or {}).get("destination"),
            "is_movement": e.event_type == "movement",
        }
        for e in events
    ]

    # Derive per-session location from the most recent event that sets it.
    # For movement events, "destination" is where the session ended up;
    # "location" is the origin (departure stamp). Prefer "destination" for tracking.
    session_last_location: Dict[str, str] = {}
    session_last_seen: Dict[str, str] = {}
    for e in reversed(location_scan_events):  # oldest first so later events overwrite
        sid = e.session_id or ""
        if not sid:
            continue
        ts = e.created_at.isoformat() if e.created_at else None
        session_last_seen[sid] = ts or ""
        delta = e.world_state_delta or {}
        loc = delta.get("destination") or delta.get("location")
        if loc:
            session_last_location[sid] = str(loc)

    # Player's current location (used to scope the digest)
    player_location: Optional[str] = None
    if session_id and _is_player_session(session_id):
        player_location = session_last_location.get(session_id)

    # ── Timeline — filtered by player location ───────────────────────────────
    # Show events that happened at the player's location (including departures
    # stamped at origin) and arrivals at this location (destination == here).
    if player_location:
        timeline = [e for e in full_timeline if e["location"] == player_location or e.get("destination") == player_location or e["who"] == session_id]
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
        # Derive a short display name: prefer explicit player_name (human players),
        # otherwise extract the agent slug from the session ID.
        import re as _re3

        _agent_name = _slug_display_name(sid)
        if _agent_name:
            # Agent session: "fei_fei-20260312-..." → "Fei Fei"
            display_name = _agent_name
        elif player_name:
            # Human player with a real name (e.g. "Levi")
            display_name = player_name
        else:
            display_name = sid[:12]

        full_roster.append(
            {
                "session_id": sid,
                "location": session_last_location.get(sid, "unknown"),
                "last_seen": session_last_seen.get(sid),
                "player_name": player_name,
                "display_name": display_name,
            }
        )
    full_roster.sort(key=lambda r: r["last_seen"] or "", reverse=True)

    # Deduplicate by display_name — keep only the most recently seen session per character.
    # This prevents stale sessions from old world runs appearing alongside current ones.
    _seen_display_names: set = set()
    deduped_roster = []
    for r in full_roster:
        dn = r["display_name"].lower()
        if dn not in _seen_display_names:
            _seen_display_names.add(dn)
            deduped_roster.append(r)
    full_roster = deduped_roster

    # Filter roster to the player's location (always include the player themselves)
    if player_location:
        roster = [r for r in full_roster if r["location"] == player_location or r["session_id"] == session_id]
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
                name = ws.name[len("workspace-") :]
                if _SAFE_NAME_RE.match(name):
                    available_agents.append(name)
    if _WW_AGENT_RESIDENTS.exists():
        for res in _WW_AGENT_RESIDENTS.iterdir():
            if res.is_dir() and not res.name.startswith("_") and _SAFE_NAME_RE.match(res.name):
                if res.name not in available_agents:
                    available_agents.append(res.name)
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

    # Build session → display_name lookup from the full roster.
    # For human players: use player_name ("Levi").
    # For agents: extract the agent slug from the session ID ("casper-20260309-..." → "casper").
    # Fallback: first 12 chars of session_id.
    def _display_name_for(sid: Optional[str]) -> Optional[str]:
        if not sid:
            return None
        # Agent sessions always use the slug as display name
        agent_name = _slug_display_name(sid)
        if agent_name:
            return agent_name
        # Human player — look up their entered name from the roster
        for r in full_roster:
            if r["session_id"] == sid and r["player_name"]:
                return r["player_name"]
        return sid[:12]

    for entry in timeline:
        entry["display_name"] = _display_name_for(entry["who"])

    # ── Location graph for the map view ─────────────────────────────────────
    from ...services.world_memory import get_location_graph

    # Count tethered agents per location
    agent_location_counts: Dict[str, int] = {}
    for loc in agent_last_location.values():
        agent_location_counts[loc] = agent_location_counts.get(loc, 0) + 1

    raw_graph = get_location_graph(db)
    location_graph = {
        "nodes": [
            {
                "key": n["key"],
                "name": n["name"],
                "count": location_counts.get(n["name"], 0),
                "agent_count": agent_location_counts.get(n["name"], 0),
                "is_player": n["name"] == player_location,
                "lat": n.get("lat"),
                "lon": n.get("lon"),
            }
            for n in raw_graph.get("nodes", [])
        ],
        "edges": raw_graph.get("edges", []),
    }

    # ── Location chat snapshot ────────────────────────────────────────────────
    location_chat: List[Dict[str, Any]] = []
    if player_location:
        chat_rows = db.query(LocationChat).filter(LocationChat.location == player_location).order_by(LocationChat.created_at.desc()).limit(30).all()
        location_chat = [
            {
                "id": r.id,
                "session_id": r.session_id,
                "display_name": r.display_name,
                "message": r.message,
                "ts": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reversed(chat_rows)
        ]

    return {
        "world_id": world_id or None,
        "seeded": bool(world_id),
        "active_sessions": len(roster),
        "roster": roster,
        "location_population": location_counts,
        "location_graph": location_graph,
        "timeline": timeline,
        "events_shown": len(timeline),
        "known_agents": known_agents,
        "player_location": player_location,
        "location_chat": location_chat,
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
    event_summaries = [f"[{e.session_id or 'world'}] {e.summary}" for e in events if e.summary]

    # Graph facts about named characters
    facts = query_graph_facts(db, query="character person NPC inhabitant named", limit=20)
    fact_summaries = [f.summary for f in facts if f.summary]

    # Existing session labels (so cards don't duplicate active characters)
    existing = list({e.session_id for e in events if e.session_id and _is_player_session(e.session_id)})

    # Known locations: prefer location graph (seeded from world bible), fall back to event history
    from ...services.world_memory import get_location_graph

    graph = get_location_graph(db)
    graph_locations = [n["name"] for n in graph["nodes"]]

    if not graph_locations:
        graph_locations = sorted({str((e.world_state_delta or {}).get("location")) for e in events if (e.world_state_delta or {}).get("location")})

    result = generate_entry_cards(
        event_summaries=event_summaries,
        fact_summaries=fact_summaries,
        existing_session_labels=existing,
        world_name="Oakhaven Lows",
        known_locations=graph_locations,
    )

    # Entry nodes: city-pack locations + landmarks (landmarks stitched to path
    # graph by repair_graph.py, so both types are fully navigable)
    cp_entry_nodes = (
        db.query(WorldNode)
        .filter(WorldNode.node_type.in_(["location", "landmark"]))
        .all()
    )
    entry_nodes = [
        {
            "name": n.name,
            "key": f"{n.node_type}:{n.normalized_name}",
            "lat": (n.metadata_json or {}).get("lat"),
            "lon": (n.metadata_json or {}).get("lon"),
        }
        for n in cp_entry_nodes
        if (n.metadata_json or {}).get("source") == "city_pack"
    ]

    # Dropdown locations: use entry nodes (city-pack + landmarks with coords) if available,
    # otherwise fall back to graph locations. Deduplicate while preserving order.
    if entry_nodes:
        seen: set[str] = set()
        dropdown_locations: list[str] = []
        for n in entry_nodes:
            if n["name"] not in seen:
                seen.add(n["name"])
                dropdown_locations.append(n["name"])
    else:
        seen = set()
        dropdown_locations = []
        for loc in graph_locations:
            if loc not in seen:
                seen.add(loc)
                dropdown_locations.append(loc)

    return {
        "world_id": world_id,
        "snapshot": result.get("snapshot", ""),
        "cards": result.get("cards", []),
        "locations": dropdown_locations,
        "entry_nodes": entry_nodes,
    }


@router.get("/world/{world_id}/locations/graph")
def get_world_location_graph(
    world_id: str,
    db: Session = Depends(get_db),
):
    """Return the location graph for a world: nodes (places) and edges (paths between them).

    The graph is seeded from the world bible at creation time and grows as agents
    explore and the LLM narrates new places.
    """
    from ...services.world_memory import get_location_graph

    graph = get_location_graph(db)
    return {"world_id": world_id, **graph}


# ---------------------------------------------------------------------------
# Map-based movement — graph-traversal, no LLM
# ---------------------------------------------------------------------------


class MapMoveRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    destination: str = Field(..., min_length=1, max_length=200)


@router.post("/game/move")
def map_move(payload: MapMoveRequest, db: Session = Depends(get_db)):
    """Move one hop toward destination along the shortest graph path.

    Bypasses LLM — pure graph traversal over 'path' edges.
    Each call advances one hop. Call repeatedly to continue transit.
    Returns the new location, the full planned route, and remaining hops.
    """
    from ...services.session_service import get_state_manager, save_state
    from ...services.world_memory import find_route

    session_id = payload.session_id
    if not _SAFE_SESSION_RE.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")

    sm = get_state_manager(session_id, db)
    current_location = sm.get_variable("location") or ""

    if not current_location:
        raise HTTPException(status_code=400, detail="Session has no current location set.")

    destination = payload.destination.strip()
    route = find_route(db, current_location, destination)

    snapped = False
    if not route:
        # If routing failed because current_location is a narrative sublocation that isn't
        # in the graph (e.g. "The Bakery Stall"), snap the agent directly to the destination
        # as a one-time recovery move. This re-anchors orphaned agents without stranding them.
        dest_route = find_route(db, destination, destination)
        if dest_route and current_location != destination:
            # current_location is the bad node; destination is valid — snap there.
            route = [current_location, destination]
            snapped = True
        else:
            raise HTTPException(
                status_code=404,
                detail=f"No route from '{current_location}' to '{destination}'.",
            )

    if len(route) == 1:
        # Already at destination
        return {
            "moved": False,
            "from_location": current_location,
            "to_location": current_location,
            "route": route,
            "route_remaining": [],
            "narrative": f"You are already at {current_location.replace('_', ' ')}.",
        }

    next_location = route[1]
    route_remaining = route[2:]

    # Update session location
    sm.set_variable("location", next_location)
    save_state(sm, db)

    # Narrative line
    if snapped:
        narrative = f"You find yourself at {next_location.replace('_', ' ')}."
    elif route_remaining:
        stops = len(route_remaining)
        narrative = f"You head toward {destination.replace('_', ' ')}, passing through {next_location.replace('_', ' ')}. ({stops} more stop{'s' if stops != 1 else ''} to go)"
    else:
        narrative = f"You arrive at {next_location.replace('_', ' ')}."

    # Derive a display name for the mover.
    # player_role is set explicitly at bootstrap (e.g. "Brunhilda"); prefer it
    # over player_name which can be stale (injected by world projection).
    _raw_role = sm.get_variable("player_role") or ""
    _role_name = (_raw_role.split(" — ")[0].strip() if " — " in _raw_role else _raw_role.strip()) or None
    mover_name = (
        _slug_display_name(session_id)
        or _role_name
        or sm.get_variable("player_name")
        or "Someone"
    )

    # Transit vs arrival summary — transit events let people at the intermediate
    # node see the traveller pass through without polluting the arrival location.
    if route_remaining:
        final_dest = route[-1] if route else destination
        event_summary = (
            f"{mover_name} passes through {next_location.replace('_', ' ')}, "
            f"continuing toward {final_dest.replace('_', ' ')}."
        )
    else:
        event_summary = f"{mover_name} arrives at {next_location.replace('_', ' ')}."

    # Log movement event so the digest/timeline tracks it
    event = WorldEvent(
        session_id=session_id,
        event_type="movement",
        summary=event_summary,
        world_state_delta={
            "location": current_location,
            "destination": next_location,
            "in_transit": bool(route_remaining),
        },
    )
    db.add(event)
    db.commit()

    return {
        "moved": True,
        "from_location": current_location,
        "to_location": next_location,
        "route": route,
        "route_remaining": route_remaining,
        "narrative": narrative,
    }


# ---------------------------------------------------------------------------
# Player ↔ Agent letter system
# ---------------------------------------------------------------------------

_OPENCLAW_ROOT = Path(__file__).parents[3] / ".openclaw"
_WW_AGENT_RESIDENTS = Path(os.environ.get("WW_AGENT_RESIDENTS_DIR", str(Path(__file__).parents[4] / "ww_agent" / "residents")))
_PLAYER_INBOX_ROOT = Path(__file__).parents[3] / "data" / "player_inboxes"
_SAFE_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_SAFE_SESSION_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_AGENT_SLUG_RE = re.compile(r"^([a-z][a-z0-9_]*)[-_]\d{8}")


def _slug_display_name(session_id: str) -> Optional[str]:
    """Extract a human-readable display name from an agent session ID.

    Agent sessions follow the pattern 'slug-YYYYMMDD-HHMMSS' where slug may
    contain underscores (e.g. 'fei_fei'). Returns 'Fei Fei' style title-cased
    name, or None if the session doesn't look like an agent session.
    """
    m = _AGENT_SLUG_RE.match(session_id)
    if not m:
        return None
    return " ".join(w.capitalize() for w in m.group(1).split("_"))


def _is_ww_agent_resident(agent_name: str) -> bool:
    """True if this agent is a ww_agent resident (not an openclaw workspace agent)."""
    return (_WW_AGENT_RESIDENTS / agent_name).is_dir()


def _agent_inbox(agent_name: str) -> Path:
    if _is_ww_agent_resident(agent_name):
        return _WW_AGENT_RESIDENTS / agent_name / "letters" / "inbox"
    return _OPENCLAW_ROOT / f"workspace-{agent_name}" / "worldweaver_runs" / agent_name / "letters" / "inbox"


def _player_inbox(session_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", session_id)[:64]
    return _PLAYER_INBOX_ROOT / safe


def _valid_agent(agent_name: str) -> bool:
    if not _SAFE_NAME_RE.match(agent_name):
        return False
    if _is_ww_agent_resident(agent_name):
        return True
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


# ---------------------------------------------------------------------------
# Shadow consent
# ---------------------------------------------------------------------------

_WW_AGENT_CONTRACTS = Path(os.environ.get(
    "WW_AGENT_RESIDENTS_DIR",
    str(Path(__file__).parents[4] / "ww_agent" / "residents"),
)) / "_contracts"


class ShadowConsentRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    consent: bool
    non_negotiables: list[str] = Field(default_factory=list)


@router.post("/world/shadow/consent")
def shadow_consent(payload: ShadowConsentRequest, db: Session = Depends(get_db)):
    """Record a player's shadow/twinning consent decision.

    Writes an identity contract to ww_agent/residents/_contracts/{name}.json.
    The doula loop reads this before deciding whether to spawn a shadow agent
    for a departing player. With consent=false, the player is permanently
    excluded from shadow spawning. With consent=true, optional non_negotiables
    are prepended to the soul seed context so the shadow respects them.
    """
    if not _SAFE_SESSION_RE.match(payload.session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")

    # Resolve the player's display name from their session state.
    from ...services.session_service import get_state_manager
    try:
        sm = get_state_manager(payload.session_id, db)
        player_role = sm.get_variable("player_role") or ""
    except Exception:
        raise HTTPException(status_code=404, detail="Session not found.")

    if not player_role:
        raise HTTPException(status_code=422, detail="Session has no player_role set.")

    display_name = player_role.split(" — ")[0].strip() if " — " in player_role else player_role.strip()
    if not display_name:
        raise HTTPException(status_code=422, detail="Could not derive player name from session.")

    normalized = re.sub(r"[^a-z0-9_]", "_", display_name.lower())
    _WW_AGENT_CONTRACTS.mkdir(parents=True, exist_ok=True)
    contract_path = _WW_AGENT_CONTRACTS / f"{normalized}.json"

    contract = {
        "name": display_name,
        "session_id": payload.session_id,
        "consent": payload.consent,
        "non_negotiables": [s.strip() for s in payload.non_negotiables if s.strip()],
        "ts": datetime.utcnow().isoformat(),
    }
    contract_path.write_text(
        json.dumps(contract, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    action = "allowed" if payload.consent else "blocked"
    logging.info(
        "Shadow consent recorded for %s (%s): %s", display_name, payload.session_id, action
    )
    return {
        "success": True,
        "name": display_name,
        "consent": payload.consent,
        "contract_path": str(contract_path),
    }


@router.get("/world/scene/{session_id}")
def get_agent_scene(session_id: str, db: Session = Depends(get_db)):
    """Local scene snapshot for agents — who is here, what just happened, what can I do next.

    Called by agents before submitting an action. Returns a focused, location-scoped
    picture of the world: co-located characters and their last actions, recent events
    at this location, and the known location graph so the agent can reason about movement.
    No LLM — pure aggregation. Fast.
    """
    if not _SAFE_SESSION_RE.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")

    from ...services.session_service import get_state_manager
    from ...services.world_memory import get_world_history, get_location_graph

    # ── Current session state ─────────────────────────────────────────────────
    try:
        sm = get_state_manager(session_id, db)
        location = sm.get_variable("location") or ""
        player_role = sm.get_variable("player_role") or ""
    except Exception:
        location = ""
        player_role = ""

    # ── Scan recent events for co-location and latest summaries ───────────────
    all_events = get_world_history(db, limit=200)

    session_last_location: Dict[str, str] = {}
    session_last_summary: Dict[str, str] = {}
    session_last_ts: Dict[str, str] = {}
    for e in reversed(all_events):
        sid = e.session_id or ""
        if not sid:
            continue
        loc = (e.world_state_delta or {}).get("location")
        if loc:
            session_last_location[sid] = str(loc)
        if e.summary:
            session_last_summary[sid] = str(e.summary)
        if e.created_at:
            session_last_ts[sid] = e.created_at.isoformat()

    # ── Present characters (same location, not self) ──────────────────────────
    present = []
    for sid, loc in session_last_location.items():
        if sid == session_id or loc != location:
            continue
        # Derive display name
        name = _slug_display_name(sid) or sid[:12]
        try:
            other_sm = get_state_manager(sid, db)
            if not _slug_display_name(sid):
                name = other_sm.get_variable("player_name") or other_sm.get_variable("player_role") or name
            raw_role = other_sm.get_variable("player_role") or ""
            role = raw_role.split(" — ")[0].strip() if " — " in raw_role else raw_role.strip()
        except Exception:
            role = ""
        last = session_last_summary.get(sid, "")
        # Strip the "Player action: ... Result: " boilerplate to surface just the result
        if "Result:" in last:
            last = last.split("Result:", 1)[1].strip()
        elif last.startswith("Player action:"):
            last = last[len("Player action:") :].strip()
        present.append(
            {
                "name": name,
                "role": role or name,
                "last_action": last[:200],
                "last_seen": session_last_ts.get(sid),
            }
        )

    # ── Recent events at this location (last 10) ──────────────────────────────
    local_events = []
    for e in all_events:
        loc = (e.world_state_delta or {}).get("location")
        if loc != location:
            continue
        sid = e.session_id or ""
        who = _slug_display_name(sid) or sid[:12]
        summary = e.summary or ""
        if "Result:" in summary:
            summary = summary.split("Result:", 1)[1].strip()
        elif summary.startswith("Player action:"):
            summary = summary[len("Player action:") :].strip()
        local_events.append(
            {
                "who": who,
                "summary": summary[:300],
                "ts": e.created_at.isoformat() if e.created_at else None,
            }
        )
        if len(local_events) >= 10:
            break

    # ── Location graph (for movement decisions) ───────────────────────────────
    graph = get_location_graph(db)

    return {
        "session_id": session_id,
        "location": location,
        "role": player_role,
        "present": present,
        "recent_events_here": local_events,
        "location_graph": {
            "nodes": [{"name": n["name"]} for n in graph.get("nodes", [])],
            "edges": [{"from": e["from"].replace("location:", ""), "to": e["to"].replace("location:", "")} for e in graph.get("edges", [])],
        },
    }


@router.get("/world/scene/{session_id}/new-events")
def get_new_events_for_agent(
    session_id: str,
    since: str = Query(..., description="ISO-8601 timestamp; return events after this time"),
    db: Session = Depends(get_db),
):
    """Poll for new events at the agent's current location since a given timestamp.

    Used by the fast loop to decide whether to fire. Returns only events that
    occurred at the agent's location after `since`, excluding the agent's own actions.
    No LLM — pure event log scan. Very fast.
    """
    if not _SAFE_SESSION_RE.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")

    from ...services.session_service import get_state_manager
    from ...services.world_memory import get_world_history
    from datetime import datetime, timezone

    try:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid since timestamp.")

    try:
        sm = get_state_manager(session_id, db)
        location = sm.get_variable("location") or ""
    except Exception:
        location = ""

    if not location:
        return {"events": [], "count": 0}

    all_events = get_world_history(db, limit=100)
    new_events = []
    for e in all_events:
        if e.session_id == session_id:
            continue
        if (e.world_state_delta or {}).get("location") != location:
            continue
        if e.created_at and e.created_at.replace(tzinfo=timezone.utc) <= since_dt.replace(tzinfo=timezone.utc):
            continue
        summary = e.summary or ""
        if "Result:" in summary:
            summary = summary.split("Result:", 1)[1].strip()
        who = _slug_display_name(e.session_id or "") or (e.session_id or "")[:12]
        new_events.append(
            {
                "who": who,
                "summary": summary[:300],
                "ts": e.created_at.isoformat() if e.created_at else None,
            }
        )

    return {"events": new_events, "count": len(new_events)}


# ---------------------------------------------------------------------------
# Co-located chat — lightweight async messaging at a location
# ---------------------------------------------------------------------------


class PostChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    message: str = Field(..., min_length=1, max_length=500)
    display_name: Optional[str] = Field(default=None, max_length=200)


@router.get("/world/location/{location}/chat")
def get_location_chat(
    location: str,
    since: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Return recent chat messages at a location, optionally filtered by timestamp."""
    q = db.query(LocationChat).filter(LocationChat.location == location)
    if since:
        try:
            from datetime import datetime

            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            q = q.filter(LocationChat.created_at > since_dt.replace(tzinfo=None))
        except ValueError:
            pass
    rows = q.order_by(LocationChat.created_at.desc()).limit(limit).all()
    rows = list(reversed(rows))  # oldest first
    return {
        "location": location,
        "messages": [
            {
                "id": r.id,
                "session_id": r.session_id,
                "display_name": r.display_name,
                "message": r.message,
                "ts": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.post("/world/location/{location}/chat")
def post_location_chat(
    location: str,
    payload: PostChatRequest,
    db: Session = Depends(get_db),
):
    """Post a chat message at a location. Stored directly — no narration."""
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    row = LocationChat(
        location=location,
        session_id=payload.session_id,
        display_name=payload.display_name,
        message=message,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "success": True,
        "id": row.id,
        "ts": row.created_at.isoformat() if row.created_at else None,
    }


# ---------------------------------------------------------------------------
# City map — grounded geographic skeleton for agents and narrator
# ---------------------------------------------------------------------------


@router.get("/world/map/{session_id}")
def get_world_map(session_id: str):
    """
    Return the grounded geographic map for a session's city.

    Phase 1: returns the full city skeleton (all neighborhoods, transit,
    landmarks, corridors). Phase 2 will filter to discovered locations only.

    Used by the slow loop to give agents a geographic scaffold —
    they know which neighborhoods connect to which, where BART runs,
    what landmarks exist nearby. The narrator uses this to stay coherent.
    """
    from ...services.city_pack_service import get_full_map_for_session, list_available

    # Phase 1: always serve the SF pack (the only one built so far)
    city_id = "san_francisco"
    result = get_full_map_for_session(city_id)
    if not result.get("available"):
        available = list_available()
        return {
            "available": False,
            "city_id": city_id,
            "message": "No city pack found. Run: python scripts/build_city_pack.py",
            "available_packs": available,
        }
    return result


@router.get("/world/grounding")
def get_world_grounding():
    """
    Return current real-world grounding context for SF: time, date, weather.
    Agents call this to build naturalistic awareness of the world outside.
    No API key required — derived from wall-clock time + Open-Meteo (free).
    """
    from ...services.grounding import get_sf_time_context

    return get_sf_time_context()


@router.get("/world/place-names")
def get_world_place_names(db: Session = Depends(get_db)):
    """Return all canonical city-pack place names (locations + landmarks).

    Used by the doula loop to classify candidate names as static entities
    without requiring external OSM queries. Cheap — no LLM, no embeddings.
    """
    rows = db.query(WorldNode.name, WorldNode.node_type, WorldNode.metadata_json).all()
    place_names = [
        {"name": name, "node_type": node_type}
        for name, node_type, meta in rows
        if (meta or {}).get("source") == "city_pack"
    ]
    return {"place_names": place_names, "count": len(place_names)}


@router.get("/world/map/{session_id}/context")
def get_location_map_context(
    session_id: str,
    location: str = Query(..., description="Location name to build context for"),
):
    """
    Return compressed prose geography context for a specific location.
    Used by the slow loop to inject grounded geographic awareness into LLM context.
    Returns a short prose block: neighborhood identity, adjacency, transit, landmarks.
    """
    from ...services.city_pack_service import build_location_map_context

    city_id = "san_francisco"
    context = build_location_map_context(location, city_id)
    return {
        "location": location,
        "city_id": city_id,
        "context": context,
        "available": bool(context),
    }
