"""World memory and projection endpoints."""

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from ...config import settings
from ...database import get_db
from ...models import SessionVars, WorldEvent, WorldFact, WorldNode
from ...models import DirectMessage, LocationChat, DoulaPoll
from ...models.schemas import (
    WorldFactsResponse,
    WorldGraphFactsResponse,
    WorldGraphNeighborhoodResponse,
    WorldHistoryResponse,
    WorldLocationFactsResponse,
    WorldProjectionResponse,
)

_INTERNAL_SESSION_PREFIXES = ("world-", "_", "player-", "agent-")
_ACTIVE_HUMAN_SESSION_WINDOW = timedelta(hours=2)
_REST_CONFIG_DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "break_minutes": 45.0,
    "sleep_hours": 8.0,
    "sync_seconds": 30.0,
    "confirmations_required": 2,
    "confirmation_window_minutes": 60.0,
    "wake_grace_minutes": 60.0,
}


def _is_player_session(session_id: str) -> bool:
    """Return True if this looks like a player/agent session rather than a world admin session."""
    if not session_id:
        return False
    for prefix in _INTERNAL_SESSION_PREFIXES:
        if session_id.startswith(prefix):
            return False
    return True


def _parse_session_updated_at(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _runtime_status_from_vars(vars_payload: Dict[str, Any]) -> str:
    rest_state = str(vars_payload.get("_rest_state") or "").strip().lower()
    dormant_state = str(vars_payload.get("_dormant_state") or "").strip().lower()
    if rest_state == "returning":
        return "returning"
    if rest_state == "resting" or dormant_state == "dormant":
        return "resting"
    return "active"


def _session_variables_payload(raw_payload: Any) -> Dict[str, Any]:
    if not isinstance(raw_payload, dict):
        return {}
    nested_vars = raw_payload.get("variables")
    if raw_payload.get("_v") == 2 and isinstance(nested_vars, dict):
        return cast(Dict[str, Any], nested_vars)
    return cast(Dict[str, Any], raw_payload)


def _session_runtime_snapshot_from_vars(vars_payload: Dict[str, Any]) -> Dict[str, Any]:
    rest_until = _parse_session_updated_at(vars_payload.get("_rest_until"))
    rest_started_at = _parse_session_updated_at(vars_payload.get("_rest_started_at"))
    pending_since = _parse_session_updated_at(vars_payload.get("_rest_pending_since"))
    pending_hits_raw = vars_payload.get("_rest_pending_hits")
    try:
        pending_hits = int(pending_hits_raw or 0)
    except (TypeError, ValueError):
        pending_hits = 0
    return {
        "status": _runtime_status_from_vars(vars_payload),
        "rest_until": rest_until,
        "rest_started_at": rest_started_at,
        "rest_location": str(vars_payload.get("_rest_location") or "").strip(),
        "rest_reason": str(vars_payload.get("_rest_reason") or "").strip(),
        "pending_since": pending_since,
        "pending_reason": str(vars_payload.get("_rest_pending_reason") or "").strip(),
        "pending_location": str(vars_payload.get("_rest_pending_location") or "").strip(),
        "pending_hits": pending_hits,
        "last_completed_at": _parse_session_updated_at(vars_payload.get("_rest_last_completed_at")),
    }


def _session_display_details(session_id: str, vars_payload: Dict[str, Any]) -> tuple[Optional[str], str]:
    player_name: Optional[str] = None
    player_role = str(vars_payload.get("player_role") or "").strip()
    if player_role:
        name_part = player_role.split(" — ")[0].strip() if " — " in player_role else player_role
        player_name = name_part or None

    agent_name = _slug_display_name(session_id)
    if agent_name:
        return player_name, agent_name
    if player_name:
        return player_name, player_name
    return None, session_id[:12]


def _session_entity_type(session_id: str) -> str:
    return "agent" if _slug_display_name(session_id) else "human"


def _rest_config_summary() -> Dict[str, Any]:
    residents_dir = _WW_AGENT_RESIDENTS
    overrides: List[Dict[str, Any]] = []
    load_errors: List[str] = []
    resident_count = 0

    if residents_dir.exists():
        for resident_dir in sorted(residents_dir.iterdir()):
            if not resident_dir.is_dir() or resident_dir.name.startswith("_"):
                continue
            resident_count += 1
            tuning_path = resident_dir / "identity" / "tuning.json"
            if not tuning_path.exists():
                continue
            try:
                payload = json.loads(tuning_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                load_errors.append(f"{resident_dir.name}: {exc}")
                continue
            rest_payload = payload.get("rest") or {}
            if not isinstance(rest_payload, dict):
                load_errors.append(f"{resident_dir.name}: rest tuning must be an object")
                continue
            override = {
                key: rest_payload[key]
                for key, default in _REST_CONFIG_DEFAULTS.items()
                if key in rest_payload and rest_payload[key] != default
            }
            if override:
                overrides.append({"resident": resident_dir.name, **override})

    return {
        "residents_dir": str(residents_dir),
        "residents_dir_exists": residents_dir.exists(),
        "defaults": dict(_REST_CONFIG_DEFAULTS),
        "resident_count": resident_count,
        "override_count": len(overrides),
        "overrides": overrides,
        "load_errors": load_errors,
    }


def _shard_identity_payload() -> Dict[str, Any]:
    return {
        "shard_id": settings.city_id if settings.shard_type != "world" else "ww_world",
        "city_id": settings.city_id,
        "shard_type": settings.shard_type,
    }


def _load_active_human_session_ids(
    db: Session,
    requested_session_id: Optional[str] = None,
) -> set[str]:
    cutoff = datetime.now(timezone.utc) - _ACTIVE_HUMAN_SESSION_WINDOW
    active: set[str] = set()
    rows = db.execute(text("SELECT session_id, updated_at FROM session_vars")).fetchall()
    for session_id, updated_at in rows:
        sid = str(session_id or "")
        if not sid or not _is_player_session(sid):
            continue
        if _slug_display_name(sid):
            continue
        if requested_session_id and sid == requested_session_id:
            active.add(sid)
            continue
        parsed_updated_at = _parse_session_updated_at(updated_at)
        if parsed_updated_at is None:
            continue
        if parsed_updated_at >= cutoff:
            active.add(sid)
    return active


def _session_runtime_status(db: Session, session_id: str) -> str:
    row = db.get(SessionVars, session_id)
    if row is None:
        return "active"
    return _runtime_status_from_vars(_session_variables_payload(row.vars))


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
    # Use a larger window for location tracking so sessions don't show "unknown"
    # if their last location-stamped event is older than the timeline window.
    # 1000 covers ~4 hours with 6 agents firing every 90s; keeps human players
    # from falling off the roster when AI event volume is high.
    _LOCATION_SCAN_LIMIT = max(events_limit, 1000)
    location_scan_events = get_world_history(db, limit=_LOCATION_SCAN_LIMIT)
    events = location_scan_events[:events_limit]
    active_human_session_ids = _load_active_human_session_ids(db, session_id)
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
        if not e.session_id
        or not _is_player_session(e.session_id)
        or _slug_display_name(e.session_id)
        or e.session_id in active_human_session_ids
        or (session_id and e.session_id == session_id)
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
        if (
            _is_player_session(sid)
            and not _slug_display_name(sid)
            and sid not in active_human_session_ids
            and sid != session_id
        ):
            continue
        ts = e.created_at.isoformat() if e.created_at else None
        session_last_seen[sid] = ts or ""
        delta = e.world_state_delta or {}
        loc = delta.get("destination") or delta.get("location")
        if loc:
            session_last_location[sid] = str(loc)

    # Ensure the requesting session always appears in the roster even if their
    # WorldEvents have scrolled past the scan window (e.g. returning player
    # who resumes without a bootstrap call).
    if session_id and _is_player_session(session_id) and session_id not in session_last_seen:
        try:
            from ...services.session_service import get_state_manager as _get_sm_fallback
            _sm = _get_sm_fallback(session_id, db)
            _loc = _sm.get_variable("location") or ""
            if _loc:
                session_last_location[session_id] = _loc
                session_last_seen[session_id] = ""
        except Exception:
            pass

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
                "entity_type": _session_entity_type(sid),
                "status": _session_runtime_status(db, sid),
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

    # ── Location population count (human players only) ───────────────────────
    # Agent sessions are counted separately in agent_location_counts below;
    # including them here would double-count them in the map tooltip.
    location_counts: Dict[str, int] = {}
    for r in full_roster:
        if r.get("status") == "resting":
            continue
        if _slug_display_name(r["session_id"]):
            continue  # agent session — skip, counted in agent_location_counts
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

    # Contacts = agents the player has actually encountered.
    # "Encountered" means: ever been at the same location in the scan window,
    # OR has sent the player a DM. Location chat handles real-time co-located
    # speech; DMs are the async private channel for earned contacts only.
    known_agents: List[str] = []
    if session_id and _is_player_session(session_id):
        player_locations_seen: set[str] = set()
        for e in location_scan_events:
            if e.session_id == session_id:
                delta = e.world_state_delta or {}
                loc = delta.get("destination") or delta.get("location")
                if loc:
                    player_locations_seen.add(str(loc))
        for agent_name in available_agents:
            if agent_last_location.get(agent_name) in player_locations_seen:
                known_agents.append(agent_name)
        # Also add agents who have already DM'd this player
        if _SAFE_SESSION_RE.match(session_id):
            dmed_agents = (
                db.query(DirectMessage.from_name)
                .filter(DirectMessage.to_name == session_id)
                .distinct()
                .all()
            )
            for (agent_from_dm,) in dmed_agents:
                slug = agent_from_dm.lower().replace(" ", "_")
                if slug in available_agents and slug not in known_agents:
                    known_agents.append(slug)

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

    # Count tethered agents per location and track their display names
    agent_location_counts: Dict[str, int] = {}
    agent_location_names: Dict[str, List[str]] = {}
    for agent_name, loc in agent_last_location.items():
        agent_entry = next((r for r in full_roster if r["display_name"].lower() == agent_name.lower()), None)
        if agent_entry and agent_entry.get("status") == "resting":
            continue
        agent_location_counts[loc] = agent_location_counts.get(loc, 0) + 1
        display = agent_name.replace("_", " ").title()
        agent_location_names.setdefault(loc, []).append(display)

    # Human player display names per location
    player_location_names: Dict[str, List[str]] = {}
    for r in full_roster:
        if r.get("status") == "resting":
            continue
        if _slug_display_name(r["session_id"]):
            continue  # agent session — skip
        loc = r["location"]
        if loc and loc != "unknown":
            name = r.get("display_name") or r["session_id"][:12]
            player_location_names.setdefault(loc, []).append(name)
    # Guarantee the requesting player appears at their location even if they
    # haven't moved since their last session (no recent location delta event).
    if player_location and session_id and not _slug_display_name(session_id):
        req_entry = next((r for r in full_roster if r["session_id"] == session_id), None)
        req_name = (req_entry or {}).get("display_name") or (session_id[:12] if session_id else None)
        if req_name:
            names_here = player_location_names.setdefault(player_location, [])
            if req_name not in names_here:
                names_here.append(req_name)

    raw_graph = get_location_graph(db)
    graph_node_names: set[str] = {n["name"] for n in raw_graph.get("nodes", [])}

    # Occupied locations not in the neighborhood graph (e.g. landmarks an agent
    # or the player is currently at).  We fetch their metadata on-demand so they
    # appear on the map without being part of the static graph.
    occupied_outside_graph: list[str] = [
        loc for loc in set(list(agent_location_counts.keys()) + ([player_location] if player_location else []))
        if loc and loc not in graph_node_names
    ]
    extra_nodes: list[Dict[str, Any]] = []
    if occupied_outside_graph:
        from ...models import WorldNode as _WorldNode  # noqa: PLC0415
        extra_db_nodes = (
            db.query(_WorldNode)
            .filter(_WorldNode.name.in_(occupied_outside_graph))
            .all()
        )
        for n in extra_db_nodes:
            meta = n.metadata_json or {}
            extra_nodes.append({
                "key": f"{n.node_type}:{n.normalized_name}",
                "name": n.name,
                "count": location_counts.get(n.name, 0),
                "agent_count": agent_location_counts.get(n.name, 0),
                "agent_names": agent_location_names.get(n.name, []),
                "player_names": player_location_names.get(n.name, []),
                "is_player": n.name == player_location,
                "lat": meta.get("lat"),
                "lon": meta.get("lon"),
            })

    location_graph = {
        "nodes": [
            {
                "key": n["key"],
                "name": n["name"],
                "count": location_counts.get(n["name"], 0),
                "agent_count": agent_location_counts.get(n["name"], 0),
                "agent_names": agent_location_names.get(n["name"], []),
                "player_names": player_location_names.get(n["name"], []),
                "is_player": n["name"] == player_location,
                "lat": n.get("lat"),
                "lon": n.get("lon"),
            }
            for n in raw_graph.get("nodes", [])
        ] + extra_nodes,
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
        "active_sessions": sum(1 for r in roster if r.get("status") != "resting"),
        "roster": roster,
        "location_population": location_counts,
        "location_graph": location_graph,
        "timeline": timeline,
        "events_shown": len(timeline),
        "known_agents": known_agents,
        "player_location": player_location,
        "location_chat": location_chat,
    }


@router.get("/world/rest-metrics")
def get_world_rest_metrics(
    include_active: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Operator-facing snapshot of rest/dormancy state across the shard."""
    now = datetime.now(timezone.utc)
    active_human_session_ids = _load_active_human_session_ids(db)
    counts = {
        "total": 0,
        "active": 0,
        "resting": 0,
        "returning": 0,
        "pending_confirmation": 0,
    }
    sessions: List[Dict[str, Any]] = []

    rows = db.query(SessionVars).all()
    for row in rows:
        session_id = str(row.session_id or "").strip()
        if not _is_player_session(session_id):
            continue
        if not _slug_display_name(session_id) and session_id not in active_human_session_ids:
            continue
        vars_payload = _session_variables_payload(row.vars)
        snapshot = _session_runtime_snapshot_from_vars(vars_payload)
        status = str(snapshot["status"])
        counts["total"] += 1
        counts[status] = counts.get(status, 0) + 1
        if int(snapshot["pending_hits"] or 0) > 0:
            counts["pending_confirmation"] += 1

        if not include_active and status == "active" and int(snapshot["pending_hits"] or 0) <= 0:
            continue

        player_name, display_name = _session_display_details(session_id, vars_payload)
        entity_type = _session_entity_type(session_id)
        rest_until = cast(Optional[datetime], snapshot["rest_until"])
        rest_started_at = cast(Optional[datetime], snapshot["rest_started_at"])
        remaining_minutes: Optional[float] = None
        if rest_until is not None:
            remaining_minutes = max(0.0, round((rest_until - now).total_seconds() / 60.0, 1))

        sessions.append(
            {
                "session_id": session_id,
                "display_name": display_name,
                "player_name": player_name,
                "entity_type": entity_type,
                "location": str(vars_payload.get("location") or snapshot["rest_location"] or "unknown"),
                "last_updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "status": status,
                "rest_reason": snapshot["rest_reason"] or None,
                "rest_location": snapshot["rest_location"] or None,
                "rest_started_at": rest_started_at.isoformat() if rest_started_at else None,
                "rest_until": rest_until.isoformat() if rest_until else None,
                "remaining_minutes": remaining_minutes,
                "pending_reason": snapshot["pending_reason"] or None,
                "pending_location": snapshot["pending_location"] or None,
                "pending_since": snapshot["pending_since"].isoformat() if snapshot["pending_since"] else None,
                "pending_hits": int(snapshot["pending_hits"] or 0),
                "last_completed_at": snapshot["last_completed_at"].isoformat() if snapshot["last_completed_at"] else None,
            }
        )

    sessions.sort(
        key=lambda item: (
            {"resting": 0, "returning": 1, "active": 2}.get(str(item.get("status") or "active"), 3),
            str(item.get("display_name") or item.get("session_id") or ""),
        )
    )

    total = max(1, int(counts["total"]))
    return {
        "generated_at": now.isoformat(),
        "shard": _shard_identity_payload(),
        "counts": counts,
        "fractions": {
            "active": round(float(counts["active"]) / total, 4),
            "resting": round(float(counts["resting"]) / total, 4),
            "pending_confirmation": round(float(counts["pending_confirmation"]) / total, 4),
        },
        "rest_config": _rest_config_summary(),
        "sessions": sessions,
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

    # Entry nodes: city-pack locations only. Landmarks are sub-locations discovered
    # via natural language travel or the Nearby button — they shouldn't be arrival
    # points because they have no map coordinates and disorient new players.
    cp_entry_nodes = (
        db.query(WorldNode)
        .filter(WorldNode.node_type == "location")
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
    skip_to_destination: bool = False


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

    if payload.skip_to_destination and not snapped:
        # ── Skip mode: burn through every intermediate hop silently, log a
        # transit WorldEvent for each so passers-by see the trace, then land
        # at the final destination with a single arrival narrative.
        final_dest = route[-1]
        intermediate_hops = route[1:-1]  # all stops except current and final
        for hop in intermediate_hops:
            prev = sm.get_variable("location") or current_location
            sm.set_variable("location", hop)
            db.add(WorldEvent(
                session_id=session_id,
                event_type="movement",
                summary=(
                    f"{mover_name} passes through {hop.replace('_', ' ')}, "
                    f"continuing toward {final_dest.replace('_', ' ')}."
                ),
                world_state_delta={"location": prev, "destination": hop, "in_transit": True},
            ))
        # Final hop
        prev_final = sm.get_variable("location") or current_location
        sm.set_variable("location", final_dest)
        save_state(sm, db)
        db.add(WorldEvent(
            session_id=session_id,
            event_type="movement",
            summary=f"{mover_name} arrives at {final_dest.replace('_', ' ')}.",
            world_state_delta={"location": prev_final, "destination": final_dest, "in_transit": False},
        ))
        db.commit()
        via = intermediate_hops
        if via:
            via_str = ", ".join(h.replace("_", " ") for h in via)
            narrative = f"You pass through {via_str} and arrive at {final_dest.replace('_', ' ')}."
        else:
            narrative = f"You arrive at {final_dest.replace('_', ' ')}."
        return {
            "moved": True,
            "from_location": current_location,
            "to_location": final_dest,
            "route": route,
            "route_remaining": [],
            "narrative": narrative,
        }

    # ── Single-hop mode (default) ────────────────────────────────────────────
    next_location = route[1]
    route_remaining = route[2:]

    sm.set_variable("location", next_location)
    save_state(sm, db)

    if snapped:
        narrative = f"You find yourself at {next_location.replace('_', ' ')}."
    elif route_remaining:
        stops = len(route_remaining)
        narrative = f"You head toward {destination.replace('_', ' ')}, passing through {next_location.replace('_', ' ')}. ({stops} more stop{'s' if stops != 1 else ''} to go)"
    else:
        narrative = f"You arrive at {next_location.replace('_', ' ')}."

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

    db.add(WorldEvent(
        session_id=session_id,
        event_type="movement",
        summary=event_summary,
        world_state_delta={
            "location": current_location,
            "destination": next_location,
            "in_transit": bool(route_remaining),
        },
    ))
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
# Player ↔ Agent DM system
# ---------------------------------------------------------------------------

_OPENCLAW_ROOT = Path(__file__).parents[3] / ".openclaw"
_WW_AGENT_RESIDENTS = Path(os.environ.get("WW_AGENT_RESIDENTS_DIR", str(Path(__file__).parents[4] / "ww_agent" / "residents")))
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


def _valid_agent(agent_name: str) -> bool:
    if not _SAFE_NAME_RE.match(agent_name):
        return False
    if _is_ww_agent_resident(agent_name):
        return True
    workspace = _OPENCLAW_ROOT / f"workspace-{agent_name}"
    return workspace.is_dir()


class SendDMRequest(BaseModel):
    to_agent: str = Field(..., min_length=1, max_length=32)
    from_name: str = Field(..., min_length=1, max_length=60)
    body: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = Field(default=None, max_length=64)


class AgentDMReplyRequest(BaseModel):
    from_agent: str = Field(..., min_length=1, max_length=32)
    to_session_id: str = Field(..., min_length=1, max_length=64)
    body: str = Field(..., min_length=1, max_length=4000)


@router.post("/world/dm")
def send_dm(payload: SendDMRequest, db: Session = Depends(get_db)):
    """Send a DM from a player to an agent.

    Stored in the DB. The agent will see it on their next mail-loop poll.
    session_id is stored for reply routing.
    """
    agent = payload.to_agent.lower().strip()
    if not _valid_agent(agent):
        raise HTTPException(status_code=404, detail=f"No agent found for '{agent}'.")

    from_session = payload.session_id if payload.session_id and _SAFE_SESSION_RE.match(payload.session_id or "") else None

    dm = DirectMessage(
        from_name=payload.from_name,
        from_session_id=from_session,
        to_name=agent,
        body=payload.body,
    )
    db.add(dm)

    safe_from = re.sub(r"[^a-zA-Z0-9_-]", "_", payload.from_name)[:20]
    event = WorldEvent(
        session_id=f"player-{safe_from}",
        event_type="player_dm",
        summary=f"{payload.from_name} sent a DM to {agent}.",
        world_state_delta={},
    )
    db.add(event)
    db.commit()

    return {"success": True, "dm_id": dm.id, "delivered_to": agent}


@router.post("/world/dm/reply")
def agent_dm_reply(payload: AgentDMReplyRequest, db: Session = Depends(get_db)):
    """Agent sends a DM reply to a player session.

    Called by agent mail loops. to_session_id comes from the original DM.
    """
    agent = payload.from_agent.lower().strip()
    if not _valid_agent(agent):
        raise HTTPException(status_code=404, detail=f"No agent found for '{agent}'.")

    if not _SAFE_SESSION_RE.match(payload.to_session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")

    dm = DirectMessage(
        from_name=agent.capitalize(),
        from_session_id=None,
        to_name=payload.to_session_id,
        body=payload.body,
    )
    db.add(dm)

    event = WorldEvent(
        session_id=f"agent-{agent}",
        event_type="agent_dm",
        summary=f"{agent.capitalize()} sent a DM reply to a player.",
        world_state_delta={},
    )
    db.add(event)
    db.commit()

    return {"success": True, "dm_id": dm.id, "from_agent": agent}


@router.get("/world/dm/inbox/{agent}")
def get_agent_dm_inbox(agent: str, db: Session = Depends(get_db)):
    """Return unread DMs for an agent and mark them as read."""
    agent = agent.lower().strip()
    if not _valid_agent(agent):
        raise HTTPException(status_code=404, detail=f"No agent found for '{agent}'.")

    unread = (
        db.query(DirectMessage)
        .filter(DirectMessage.to_name == agent, DirectMessage.read_at.is_(None))
        .order_by(DirectMessage.sent_at)
        .all()
    )

    now = datetime.utcnow()
    dms = []
    for dm in unread:
        # Encode sender + id as filename for backward compat with mail loop parsing
        safe_from = re.sub(r"[^a-zA-Z0-9_-]", "_", dm.from_name)[:20].lower()
        ts = dm.sent_at.strftime("%Y%m%d-%H%M%S") if dm.sent_at else "000000-000000"
        filename = f"from_{safe_from}_{ts}.md"
        reply_header = f"Reply-To-Session: {dm.from_session_id}\n" if dm.from_session_id else ""
        body = f"# DM from {dm.from_name}\n{reply_header}\n{dm.body}\n"
        dms.append({"filename": filename, "body": body})
        dm.read_at = now

    if unread:
        db.commit()

    return {"agent": agent, "letters": dms, "count": len(dms)}


@router.get("/world/dm/my-inbox/{session_id}")
def get_player_dm_inbox(session_id: str, db: Session = Depends(get_db)):
    """Return all DMs received by a player session."""
    if not _SAFE_SESSION_RE.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")

    all_dms = (
        db.query(DirectMessage)
        .filter(DirectMessage.to_name == session_id)
        .order_by(DirectMessage.sent_at)
        .all()
    )

    dms = []
    for dm in all_dms:
        safe_from = re.sub(r"[^a-zA-Z0-9_-]", "_", dm.from_name)[:20].lower()
        ts = dm.sent_at.strftime("%Y%m%d-%H%M%S") if dm.sent_at else "000000-000000"
        filename = f"from_{safe_from}_{ts}.md"
        dms.append({"filename": filename, "body": dm.body, "dm_id": dm.id})

    return {"session_id": session_id, "letters": dms, "count": len(dms)}


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
            if str(other_sm.get_variable("_dormant_state") or "").strip().lower() == "dormant":
                continue
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
# World graph node injection — doula and other daemons call this to anchor
# narratively-grounded places/concepts as permanent WorldNodes.
# ---------------------------------------------------------------------------


class EnsureNodeRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    node_type: str = Field(default="location", max_length=50)
    metadata: dict = Field(default_factory=dict)


@router.post("/world/graph/ensure_node")
def post_ensure_world_node(
    payload: EnsureNodeRequest,
    db: Session = Depends(get_db),
):
    """Idempotently create a WorldNode. Used by the doula to inject narratively-grounded places."""
    from ...services.world_memory import ensure_location_node, _upsert_world_node

    if payload.node_type == "location":
        ensure_location_node(db, payload.name)
    else:
        _upsert_world_node(db, payload.name, payload.node_type, metadata=payload.metadata)
    db.commit()
    return {"ok": True, "name": payload.name, "node_type": payload.node_type}


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

    # Store in real-time chat table (fast path — agents poll this)
    row = LocationChat(
        location=location,
        session_id=payload.session_id,
        display_name=payload.display_name,
        message=message,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    # Also record as a lightweight utterance WorldEvent so speech becomes part of
    # world memory: doula can discover names, agents build slow-loop memories from
    # it, and the narrator sees it in recent events context. Best-effort only.
    display_name = payload.display_name or payload.session_id[:12]
    try:
        from ...services.world_memory import record_event, EVENT_TYPE_UTTERANCE
        record_event(
            db=db,
            session_id=payload.session_id,
            storylet_id=None,
            event_type=EVENT_TYPE_UTTERANCE,
            summary=f"{display_name} said: {message}",
            delta={"speaker": display_name, "location": location},
            skip_graph_extraction=True,  # raw speech → noisy graph nodes; summary embedding is enough
        )
    except Exception:
        pass  # never fail the chat post due to the utterance event

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

    city_id = settings.city_id
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


@router.get("/world/grounding/news")
def get_world_news():
    """
    Return recent SF/Bay Area news headlines for agent grounding.
    Sourced from free RSS feeds (KQED, SF Standard). Cached for 1 hour.
    No API key required.
    """
    from ...services.grounding import get_sf_news

    return {"headlines": get_sf_news(max_items=5)}


@router.get("/world/landmarks/nearby")
def get_nearby_landmarks(
    location: str = Query(..., description="Neighborhood name to search around"),
    radius_km: float = Query(0.75, description="Search radius in km"),
    db: Session = Depends(get_db),
):
    """Return landmarks within radius_km of the given neighborhood.

    Uses the neighborhood node's lat/lon as the center point.
    Returns landmarks sorted by distance ascending.
    """
    import math

    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        return R * 2 * math.asin(math.sqrt(a))

    # Find the anchor node (neighborhood or landmark) to get its lat/lon
    anchor = (
        db.query(WorldNode)
        .filter(WorldNode.name == location)
        .first()
    )
    if not anchor:
        raise HTTPException(status_code=404, detail=f"Location '{location}' not found.")

    anchor_meta = anchor.metadata_json or {}
    anchor_lat = anchor_meta.get("lat")
    anchor_lon = anchor_meta.get("lon")
    if anchor_lat is None or anchor_lon is None:
        raise HTTPException(status_code=422, detail=f"Location '{location}' has no coordinates.")

    # Fetch all landmarks and filter by distance in Python (2258 rows — fast enough)
    all_landmarks = (
        db.query(WorldNode)
        .filter(WorldNode.node_type == "landmark")
        .all()
    )
    results = []
    for lm in all_landmarks:
        meta = lm.metadata_json or {}
        lat = meta.get("lat")
        lon = meta.get("lon")
        if lat is None or lon is None:
            continue
        dist = _haversine(anchor_lat, anchor_lon, lat, lon)
        if dist <= radius_km:
            results.append({
                "key": f"landmark:{lm.normalized_name}",
                "name": lm.name,
                "node_type": lm.node_type,
                "lat": lat,
                "lon": lon,
                "distance_km": round(dist, 3),
                "description": meta.get("description", ""),
                "count": 0,
                "agent_count": 0,
                "is_player": False,
            })

    results.sort(key=lambda x: x["distance_km"])
    return {"location": location, "radius_km": radius_km, "landmarks": results, "count": len(results)}


@router.get("/world/place-names")
def get_world_place_names(db: Session = Depends(get_db)):
    """Return all known place names (locations + landmarks) from the world graph.

    Includes both city-pack nodes and doula-injected place nodes so the doula
    recognizes its own past decisions — once a place is classified as STATIC
    it stays that way across all future scan cycles without re-evaluation.
    """
    rows = db.query(WorldNode.name, WorldNode.node_type, WorldNode.metadata_json).all()
    place_names = [
        {"name": name, "node_type": node_type}
        for name, node_type, meta in rows
        if node_type in ("location", "landmark")
        or (meta or {}).get("source") == "city_pack"
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

    city_id = settings.city_id
    context = build_location_map_context(location, city_id)
    return {
        "location": location,
        "city_id": city_id,
        "context": context,
        "available": bool(context),
    }


# ---------------------------------------------------------------------------
# Doula polls — backend-tracked classification votes
# ---------------------------------------------------------------------------


class CreatePollRequest(BaseModel):
    candidate_name: str
    context_lines: list[str] = []
    entry_location: Optional[str] = None
    entity_class: str = "novel"
    weight: float = 0.0
    voters: list[str] = []
    expires_in_seconds: int = 7200  # 2 hours default


class CastVoteRequest(BaseModel):
    voter_session_id: str
    vote: str  # "AGENT" or "STATIC"


@router.post("/world/doula/polls")
def create_doula_poll(payload: CreatePollRequest, db: Session = Depends(get_db)):
    """Create a new doula classification poll. Called by the doula when it needs agent consensus."""
    import uuid
    from datetime import timezone, timedelta

    poll = DoulaPoll(
        id=str(uuid.uuid4()),
        candidate_name=payload.candidate_name,
        context_json=payload.context_lines,
        entry_location=payload.entry_location,
        entity_class=payload.entity_class,
        weight=payload.weight,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=payload.expires_in_seconds),
        voters_json=payload.voters,
        votes_json={},
    )
    db.add(poll)
    db.commit()
    db.refresh(poll)
    return {"poll_id": poll.id, "candidate_name": poll.candidate_name}


@router.get("/world/doula/polls")
def get_doula_polls(db: Session = Depends(get_db)):
    """Return all open (unresolved, unexpired) polls. Called by the doula each scan cycle."""
    from datetime import timezone

    now = datetime.now(timezone.utc)
    polls = (
        db.query(DoulaPoll)
        .filter(DoulaPoll.resolved_at.is_(None), DoulaPoll.expires_at > now)
        .all()
    )
    return {
        "polls": [
            {
                "poll_id": p.id,
                "candidate_name": p.candidate_name,
                "context_lines": p.context_json or [],
                "entry_location": p.entry_location,
                "entity_class": p.entity_class,
                "weight": p.weight,
                "expires_at": p.expires_at.isoformat(),
                "voters": p.voters_json or [],
                "votes": p.votes_json or {},
            }
            for p in polls
        ]
    }


@router.post("/world/doula/polls/{poll_id}/vote")
def cast_doula_vote(
    poll_id: str,
    payload: CastVoteRequest,
    db: Session = Depends(get_db),
):
    """Record a vote on an open poll. Called by agents after reading a poll letter."""
    poll = db.query(DoulaPoll).filter(DoulaPoll.id == poll_id).first()
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")
    if poll.resolved_at is not None:
        raise HTTPException(status_code=409, detail="Poll already resolved")

    vote = payload.vote.upper()
    if vote not in ("AGENT", "STATIC"):
        raise HTTPException(status_code=400, detail="vote must be AGENT or STATIC")

    votes = dict(poll.votes_json or {})
    votes[payload.voter_session_id] = vote
    poll.votes_json = votes
    db.commit()
    return {"ok": True, "poll_id": poll_id, "voter": payload.voter_session_id, "vote": vote}


@router.post("/world/doula/polls/{poll_id}/resolve")
def resolve_doula_poll(
    poll_id: str,
    db: Session = Depends(get_db),
):
    """Mark a poll as resolved (outcome computed by the doula). Returns final vote tally."""
    from datetime import timezone

    poll = db.query(DoulaPoll).filter(DoulaPoll.id == poll_id).first()
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")

    votes = poll.votes_json or {}
    agent_votes = sum(1 for v in votes.values() if v == "AGENT")
    static_votes = sum(1 for v in votes.values() if v == "STATIC")
    outcome = "static" if static_votes >= agent_votes else "agent"

    poll.resolved_at = datetime.now(timezone.utc)
    poll.outcome = outcome
    db.commit()
    return {
        "poll_id": poll_id,
        "outcome": outcome,
        "agent_votes": agent_votes,
        "static_votes": static_votes,
    }
