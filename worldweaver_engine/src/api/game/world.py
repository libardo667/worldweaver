# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""World memory and projection endpoints."""

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from ...config import settings
from ...database import get_db
from ...models import (
    SessionVars,
    WorldEvent,
    WorldFact,
    WorldNode,
    WorldTrace,
)
from ...models import DirectMessage, LocationChat, DoulaPoll
from ...models.schemas import (
    WorldFactsResponse,
    WorldGraphFactsResponse,
    WorldHistoryResponse,
)
from ...services.event_submission import WorldEventCommand, submit_world_event
from ...services.federation_identity import current_shard_id
from ...services.live_signals import (
    LiveSignalError,
    current_live_signal_revision,
    notify_live_signal,
    read_live_signals,
    wait_for_live_signal_change,
)
from ...services.location_routes import (
    parent_location_name_for_node,
    resolve_route_anchor,
)
from ...services.actor_authority import (
    ActorAuthorizationError,
    RequestActorCredentials,
    actor_authorization_http_error,
    authorize_bound_session_actor,
    get_request_actor_credentials,
)

_INTERNAL_SESSION_PREFIXES = ("world-", "_", "player-", "agent-")
_ACTIVE_HUMAN_SESSION_WINDOW = timedelta(hours=2)
_RECENT_SESSION_SCAN_WINDOW = timedelta(hours=8)
_RECENT_EVENT_CACHE_TTL_SECONDS = max(
    0.5, float(os.environ.get("WW_RECENT_EVENT_CACHE_SECONDS", "2.0"))
)
_ROSTER_DIRECTORY_CACHE_TTL_SECONDS = max(
    1.0, float(os.environ.get("WW_ROSTER_DIRECTORY_CACHE_SECONDS", "15.0"))
)
_WORLD_TRACE_TTL_SECONDS = max(
    3600,
    min(90 * 86400, int(os.environ.get("WW_WORLD_TRACE_TTL_SECONDS", str(14 * 86400)))),
)
_WORLD_TRACE_SCENE_LIMIT = 12


@dataclass(frozen=True)
class _WorldEventSnapshot:
    id: int
    session_id: Optional[str]
    event_type: str
    summary: str
    world_state_delta: Dict[str, Any]
    created_at: Optional[datetime]


_RECENT_WORLD_EVENTS_CACHE: Dict[
    tuple[int, str], tuple[float, tuple[int, str], List[_WorldEventSnapshot]]
] = {}
_ROSTER_DIRECTORY_CACHE: Dict[str, tuple[float, List[Dict[str, Any]]]] = {}


def _authorize_bound_actor_or_http(
    db: Session,
    *,
    credentials: RequestActorCredentials,
    session_id: str,
    required_scope: str = "session.act",
) -> None:
    try:
        authorize_bound_session_actor(
            db,
            credentials=credentials,
            session_id=session_id,
            required_scope=required_scope,
        )
    except ActorAuthorizationError as exc:
        raise actor_authorization_http_error(exc) from exc


def _world_trace_payload(row: WorldTrace) -> Dict[str, Any]:
    """Return the source-attributed record shared by create receipts and scenes."""
    trace_id = f"trace:{row.id}"
    return {
        "trace_id": trace_id,
        "source_id": trace_id,
        "author_session_id": str(row.session_id or ""),
        "author_name": str(row.author_name or ""),
        "location": str(row.location or ""),
        "target": str(row.target or ""),
        "body": str(row.body or ""),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "provenance": "physical_trace",
        "freshness": "active",
        "locality": str(row.location or ""),
        "visibility": "local",
        "selection_mode": "embodied_local",
    }


def _active_world_traces(
    db: Session, *, location: str, viewer_session_id: str
) -> List[Dict[str, Any]]:
    """Read a bounded local trace surface; expired and self-authored marks stay silent."""
    if not location:
        return []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = (
        db.query(WorldTrace)
        .filter(
            WorldTrace.location == location,
            WorldTrace.expires_at > now,
            WorldTrace.session_id != viewer_session_id,
        )
        .order_by(WorldTrace.created_at.desc(), WorldTrace.id.desc())
        .limit(_WORLD_TRACE_SCENE_LIMIT)
        .all()
    )
    return [_world_trace_payload(row) for row in reversed(rows)]


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


def _session_variables_payload(raw_payload: Any) -> Dict[str, Any]:
    if not isinstance(raw_payload, dict):
        return {}
    nested_vars = raw_payload.get("variables")
    if raw_payload.get("_v") == 2 and isinstance(nested_vars, dict):
        return cast(Dict[str, Any], nested_vars)
    return cast(Dict[str, Any], raw_payload)


def _session_display_details(
    session_id: str, vars_payload: Dict[str, Any]
) -> tuple[Optional[str], str]:
    player_name: Optional[str] = None
    player_role = str(vars_payload.get("player_role") or "").strip()
    if player_role:
        name_part = (
            player_role.split(" — ")[0].strip() if " — " in player_role else player_role
        )
        player_name = name_part or None

    agent_name = _slug_display_name(session_id)
    if agent_name:
        return player_name, agent_name
    if player_name:
        return player_name, player_name
    return None, session_id[:12]


def _session_entity_type(session_id: str) -> str:
    return "agent" if _slug_display_name(session_id) else "human"


def _shard_identity_payload() -> Dict[str, Any]:
    return {
        "shard_id": current_shard_id(),
        "city_id": settings.city_id,
        "shard_type": settings.shard_type,
    }


def _load_active_human_session_ids(
    db: Session,
    requested_session_id: Optional[str] = None,
) -> set[str]:
    cutoff = datetime.now(timezone.utc) - _ACTIVE_HUMAN_SESSION_WINDOW
    recent_rows = _load_recent_session_rows(
        db,
        requested_session_id=requested_session_id,
        window=_ACTIVE_HUMAN_SESSION_WINDOW,
    )
    active: set[str] = set()
    for row in recent_rows:
        sid = str(row.session_id or "")
        if not sid or not _is_player_session(sid):
            continue
        if _slug_display_name(sid):
            continue
        if requested_session_id and sid == requested_session_id:
            active.add(sid)
            continue
        parsed_updated_at = _parse_session_updated_at(row.updated_at)
        if parsed_updated_at is None:
            continue
        if parsed_updated_at >= cutoff:
            active.add(sid)
    return active


def _load_recent_session_rows(
    db: Session,
    *,
    requested_session_id: Optional[str] = None,
    window: timedelta = _RECENT_SESSION_SCAN_WINDOW,
) -> List[SessionVars]:
    cutoff = (datetime.now(timezone.utc) - window).replace(tzinfo=None)
    query = db.query(SessionVars)
    if requested_session_id:
        query = query.filter(
            or_(
                SessionVars.updated_at >= cutoff,
                SessionVars.session_id == requested_session_id,
            )
        )
    else:
        query = query.filter(SessionVars.updated_at >= cutoff)
    return query.all()


def _clean_event_summary(summary: str) -> str:
    cleaned = str(summary or "")
    if "Observed:" in cleaned:
        return cleaned.split("Observed:", 1)[1].strip()
    if "Result:" in cleaned:
        return cleaned.split("Result:", 1)[1].strip()
    if cleaned.startswith("Player action:"):
        return cleaned[len("Player action:") :].strip()
    return cleaned.strip()


def _recipient_key_for_session_id(session_id: str) -> str:
    agent_name = _slug_display_name(session_id)
    if agent_name:
        return str(session_id.split("-", 1)[0]).strip()
    return str(session_id).strip()


def _roster_directory_entries(
    db: Session,
    *,
    requested_session_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    cache_key = requested_session_id or ""
    now_monotonic = time.monotonic()
    cached = _ROSTER_DIRECTORY_CACHE.get(cache_key)
    if cached and cached[0] > now_monotonic:
        return cached[1]

    active_human_session_ids = _load_active_human_session_ids(
        db, requested_session_id=requested_session_id
    )
    session_rows = _load_recent_session_rows(
        db, requested_session_id=requested_session_id
    )
    entries: List[Dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()

    for session_row in session_rows:
        sid = str(session_row.session_id or "").strip()
        if not sid or not _is_player_session(sid):
            continue
        if not _slug_display_name(sid) and sid not in active_human_session_ids:
            continue

        vars_payload = _session_variables_payload(session_row.vars)
        player_name, display_name = _session_display_details(sid, vars_payload)
        entity_type = _session_entity_type(sid)
        recipient_type = "agent" if entity_type == "agent" else "player"
        recipient_key = _recipient_key_for_session_id(sid)
        dedupe_key = (recipient_type, recipient_key)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        entries.append(
            {
                "session_id": sid,
                "player_name": player_name,
                "display_name": display_name,
                "entity_type": entity_type,
                "recipient_type": recipient_type,
                "recipient_key": recipient_key,
                "location": _session_location_from_vars(vars_payload),
                "updated_at": (
                    session_row.updated_at.isoformat()
                    if session_row.updated_at
                    else None
                ),
            }
        )

    _ROSTER_DIRECTORY_CACHE[cache_key] = (
        now_monotonic + _ROSTER_DIRECTORY_CACHE_TTL_SECONDS,
        entries,
    )
    if len(_ROSTER_DIRECTORY_CACHE) > 16:
        expired = [
            key
            for key, value in _ROSTER_DIRECTORY_CACHE.items()
            if value[0] <= now_monotonic
        ]
        for key in expired:
            _ROSTER_DIRECTORY_CACHE.pop(key, None)
    return entries


def _session_location_from_vars(vars_payload: Dict[str, Any]) -> str:
    return str(vars_payload.get("location") or "").strip()


def _session_role_label(vars_payload: Dict[str, Any], fallback: str) -> str:
    raw_role = str(vars_payload.get("player_role") or "").strip()
    if raw_role:
        return (
            raw_role.split(" — ")[0].strip() if " — " in raw_role else raw_role.strip()
        )
    return fallback


def _recent_world_events_rows(
    db: Session,
    *,
    limit: int,
    since: Optional[datetime] = None,
) -> List[_WorldEventSnapshot]:
    since_key = since.isoformat() if since is not None else ""
    cache_key = (int(limit), since_key)
    now_monotonic = time.monotonic()
    latest_row = (
        db.query(WorldEvent.id, WorldEvent.created_at)
        .order_by(desc(WorldEvent.id))
        .limit(1)
        .first()
    )
    latest_event_marker = (
        int(latest_row[0] or 0) if latest_row else 0,
        latest_row[1].isoformat() if latest_row and latest_row[1] else "",
    )
    cached = _RECENT_WORLD_EVENTS_CACHE.get(cache_key)
    if cached and cached[0] > now_monotonic and cached[1] == latest_event_marker:
        return cached[2]

    query = db.query(
        WorldEvent.id,
        WorldEvent.session_id,
        WorldEvent.event_type,
        WorldEvent.summary,
        WorldEvent.world_state_delta,
        WorldEvent.created_at,
    ).order_by(desc(WorldEvent.id))
    if since is not None:
        query = query.filter(WorldEvent.created_at > since)
    rows = query.limit(limit).all()
    events = [
        _WorldEventSnapshot(
            id=int(event_id),
            session_id=str(session_id) if session_id else None,
            event_type=str(event_type or ""),
            summary=str(summary or ""),
            world_state_delta=(
                world_state_delta if isinstance(world_state_delta, dict) else {}
            ),
            created_at=created_at,
        )
        for event_id, session_id, event_type, summary, world_state_delta, created_at in rows
    ]
    _RECENT_WORLD_EVENTS_CACHE[cache_key] = (
        now_monotonic + _RECENT_EVENT_CACHE_TTL_SECONDS,
        latest_event_marker,
        events,
    )
    if len(_RECENT_WORLD_EVENTS_CACHE) > 16:
        expired = [
            key
            for key, value in _RECENT_WORLD_EVENTS_CACHE.items()
            if value[0] <= now_monotonic
        ]
        for key in expired:
            _RECENT_WORLD_EVENTS_CACHE.pop(key, None)
    return events


def _event_origin_location(delta: Dict[str, Any]) -> Any:
    return delta.get("origin") or delta.get("location")


def _event_destination_location(delta: Dict[str, Any]) -> Any:
    return delta.get("destination") or delta.get("location")


def _event_metadata(delta: Dict[str, Any]) -> Dict[str, Any]:
    raw = delta.get("__action_meta__")
    return raw if isinstance(raw, dict) else {}


def _resolve_neighborhood_name_for_location(location: str) -> Optional[str]:
    from ...services.city_pack_service import find_neighborhood_record_for_location

    neighborhood = find_neighborhood_record_for_location(location, settings.city_id)
    if not neighborhood:
        return None
    name = str(neighborhood.get("name") or "").strip()
    return name or None


def _normalize_search_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _matches_map_query(*parts: Any, query: str) -> bool:
    normalized_query = _normalize_search_text(query)
    if not normalized_query:
        return True
    haystack = " ".join(_normalize_search_text(part) for part in parts if part)
    return normalized_query in haystack


def _is_exact_map_query_match(name: Any, query: str) -> bool:
    normalized_query = _normalize_search_text(query)
    if not normalized_query:
        return False
    normalized_name = _normalize_search_text(
        str(name or "").replace("_", " ").replace("-", " ")
    )
    return normalized_name == normalized_query


def _coerce_coordinate(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _location_in_bbox(
    *,
    lat: Any,
    lon: Any,
    north: float,
    south: float,
    east: float,
    west: float,
) -> bool:
    lat_value = _coerce_coordinate(lat)
    lon_value = _coerce_coordinate(lon)
    if lat_value is None or lon_value is None:
        return False
    if lat_value < south or lat_value > north:
        return False
    if west <= east:
        return west <= lon_value <= east
    return lon_value >= west or lon_value <= east


def _load_live_presence_maps(
    db: Session,
    requested_session_id: Optional[str] = None,
) -> Dict[str, Any]:
    active_human_session_ids = _load_active_human_session_ids(db, requested_session_id)
    deduped_entries: Dict[tuple[str, str], Dict[str, Any]] = {}
    requested_location: Optional[str] = None

    rows = db.query(SessionVars).all()
    for row in rows:
        sid = str(row.session_id or "")
        if not sid or not _is_player_session(sid):
            continue

        vars_payload = _session_variables_payload(row.vars)
        location = str(vars_payload.get("location") or "").strip()
        if not location or location == "unknown":
            continue

        if sid == requested_session_id:
            requested_location = location

        is_agent = bool(_slug_display_name(sid))
        if (
            not is_agent
            and sid != requested_session_id
            and sid not in active_human_session_ids
        ):
            continue

        _, display_name = _session_display_details(sid, vars_payload)
        parsed_updated_at = _parse_session_updated_at(row.updated_at)
        actor_id = str(row.actor_id or vars_payload.get("actor_id") or "").strip()
        dedupe_key = (
            ("agent", display_name.lower())
            if is_agent
            else ("human", actor_id) if actor_id else ("human", sid)
        )
        entry = {
            "entity_type": "agent" if is_agent else "human",
            "location": location,
            "display_name": display_name,
            "_updated_sort": parsed_updated_at.isoformat() if parsed_updated_at else "",
        }
        existing = deduped_entries.get(dedupe_key)
        if existing is None or str(entry["_updated_sort"]) >= str(
            existing.get("_updated_sort") or ""
        ):
            deduped_entries[dedupe_key] = entry

    human_counts: Dict[str, int] = {}
    agent_counts: Dict[str, int] = {}
    player_names: Dict[str, List[str]] = {}
    agent_names: Dict[str, List[str]] = {}
    for entry in deduped_entries.values():
        location = str(entry.get("location") or "").strip()
        if not location:
            continue
        display_name = str(entry.get("display_name") or "").strip()
        if str(entry.get("entity_type") or "") == "agent":
            agent_counts[location] = agent_counts.get(location, 0) + 1
            agent_names.setdefault(location, []).append(display_name)
        else:
            human_counts[location] = human_counts.get(location, 0) + 1
            player_names.setdefault(location, []).append(display_name)

    present_names: Dict[str, List[str]] = {}
    for location in set(player_names) | set(agent_names):
        names = player_names.get(location, []) + agent_names.get(location, [])
        present_names[location] = list(dict.fromkeys(names))

    return {
        "requested_location": requested_location,
        "human_counts": human_counts,
        "agent_counts": agent_counts,
        "player_names": player_names,
        "agent_names": agent_names,
        "present_names": present_names,
    }


def _prefer_map_node_candidate(
    existing: Optional[Dict[str, Any]],
    *,
    node_type: str,
    metadata: Dict[str, Any],
) -> bool:
    if existing is None:
        return True
    existing_has_coords = (
        _coerce_coordinate(existing.get("lat")) is not None
        and _coerce_coordinate(existing.get("lon")) is not None
    )
    candidate_has_coords = (
        _coerce_coordinate(metadata.get("lat")) is not None
        and _coerce_coordinate(metadata.get("lon")) is not None
    )
    if candidate_has_coords and not existing_has_coords:
        return True
    current_type = str(existing.get("node_type") or "").strip()
    if node_type == "corridor" and current_type == "location":
        return True
    if node_type == "landmark" and current_type == "location":
        return True
    return False


def _build_map_node_payload(
    *,
    name: str,
    key: str,
    node_type: str,
    lat: Any,
    lon: Any,
    description: str,
    is_player: bool,
    parent_location: Optional[str],
    presence: Dict[str, Any],
    include_presence_names: bool = True,
) -> Dict[str, Any]:
    human_count = int(presence["human_counts"].get(name, 0))
    agent_count = int(presence["agent_counts"].get(name, 0))
    present_names = (
        list(presence["present_names"].get(name, [])) if include_presence_names else []
    )
    return {
        "key": key,
        "name": name,
        "node_type": node_type,
        "count": human_count,
        "agent_count": agent_count,
        "present_count": human_count + agent_count,
        "present_names": present_names,
        "player_names": (
            list(presence["player_names"].get(name, []))
            if include_presence_names
            else []
        ),
        "agent_names": (
            list(presence["agent_names"].get(name, []))
            if include_presence_names
            else []
        ),
        "is_player": is_player,
        "lat": _coerce_coordinate(lat),
        "lon": _coerce_coordinate(lon),
        "description": description,
        "parent_location": parent_location,
    }


def _graph_alias_key(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(name or "").strip().lower()).strip("_")
    return f"location_alias:{slug or 'current_location'}"


def _graph_with_anchor_alias(
    graph: Dict[str, Any],
    *,
    location_name: str,
    anchor_name: str,
) -> Dict[str, Any]:
    location = str(location_name or "").strip()
    anchor = str(anchor_name or "").strip()
    if not location or not anchor or location == anchor:
        return graph

    nodes = [
        dict(node) for node in list(graph.get("nodes") or []) if isinstance(node, dict)
    ]
    edges = [
        dict(edge) for edge in list(graph.get("edges") or []) if isinstance(edge, dict)
    ]
    if any(str(node.get("name") or "").strip() == location for node in nodes):
        return {"nodes": nodes, "edges": edges}

    anchor_node = next(
        (
            node
            for node in nodes
            if str(node.get("name") or "").strip() == anchor
            and str(node.get("key") or "").strip()
        ),
        None,
    )
    if anchor_node is None:
        return {"nodes": nodes, "edges": edges}

    alias_key = _graph_alias_key(location)
    nodes.append(
        {
            **anchor_node,
            "key": alias_key,
            "name": location,
        }
    )

    edge_pairs = {
        (str(edge.get("from") or "").strip(), str(edge.get("to") or "").strip())
        for edge in edges
    }
    anchor_key = str(anchor_node.get("key") or "").strip()
    for source_key, target_key in ((alias_key, anchor_key), (anchor_key, alias_key)):
        if source_key and target_key and (source_key, target_key) not in edge_pairs:
            edges.append({"from": source_key, "to": target_key})
            edge_pairs.add((source_key, target_key))
    return {"nodes": nodes, "edges": edges}


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
                "event_type": event.event_type,
                "summary": event.summary,
                "world_state_delta": event.world_state_delta or {},
                "created_at": (
                    event.created_at.isoformat() if event.created_at else None
                ),
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
                "event_type": event.event_type,
                "summary": event.summary,
                "world_state_delta": event.world_state_delta or {},
                "created_at": (
                    event.created_at.isoformat() if event.created_at else None
                ),
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
    from ...services.world_memory import query_graph_facts

    facts = query_graph_facts(db, query=query, session_id=session_id, limit=limit)
    serialized = _serialize_world_facts(db, facts)
    return {"query": query, "facts": serialized, "count": len(serialized)}


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
    from ..game.state import _read_world_id

    world_id = _read_world_id()

    # ── Recent events ────────────────────────────────────────────────────────
    # Use a larger window for location tracking so sessions don't show "unknown"
    # if their last location-stamped event is older than the timeline window.
    # 1000 covers ~4 hours with 6 agents firing every 90s; keeps human players
    # from falling off the roster when AI event volume is high.
    _LOCATION_SCAN_LIMIT = max(events_limit, 1000)
    location_scan_events = _recent_world_events_rows(db, limit=_LOCATION_SCAN_LIMIT)
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
            "location": _event_origin_location(e.world_state_delta or {}),
            "destination": _event_destination_location(e.world_state_delta or {}),
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
        loc = _event_destination_location(delta)
        if loc:
            session_last_location[sid] = str(loc)

    # Ensure the requesting session always appears in the roster even if their
    # WorldEvents have scrolled past the scan window (e.g. returning player
    # who resumes without a bootstrap call).
    if (
        session_id
        and _is_player_session(session_id)
        and session_id not in session_last_seen
    ):
        try:
            from ...services.session_service import (
                get_state_manager as _get_sm_fallback,
            )

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
        timeline = [
            e
            for e in full_timeline
            if e["location"] == player_location
            or e.get("destination") == player_location
            or e["who"] == session_id
        ]
    else:
        timeline = full_timeline

    # Build roster — recent player sessions only
    session_rows = _load_recent_session_rows(db, requested_session_id=session_id)
    full_roster = []
    for session_row in session_rows:
        sid = str(session_row.session_id or "").strip()
        if not sid or not _is_player_session(sid):
            continue
        if not _slug_display_name(sid) and sid not in active_human_session_ids:
            continue

        vars_payload = _session_variables_payload(session_row.vars)
        player_name, display_name = _session_display_details(sid, vars_payload)
        full_roster.append(
            {
                "session_id": sid,
                "location": session_last_location.get(
                    sid, _session_location_from_vars(vars_payload) or "unknown"
                ),
                "last_seen": session_last_seen.get(
                    sid,
                    (
                        session_row.updated_at.isoformat()
                        if session_row.updated_at
                        else None
                    ),
                ),
                "player_name": player_name,
                "display_name": display_name,
                "entity_type": _session_entity_type(sid),
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
        roster = [
            r
            for r in full_roster
            if r["location"] == player_location or r["session_id"] == session_id
        ]
    else:
        roster = full_roster

    # ── Location population count (human players only) ───────────────────────
    # Agent sessions are counted separately in agent_location_counts below;
    # including them here would double-count them in the map tooltip.
    location_counts: Dict[str, int] = {}
    for r in full_roster:
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
            if (
                res.is_dir()
                and not res.name.startswith("_")
                and _SAFE_NAME_RE.match(res.name)
            ):
                if res.name not in available_agents:
                    available_agents.append(res.name)
    available_agents.sort()

    # Agent last-known locations from event history.
    # Agent session IDs follow the pattern "{agentname}-{YYYYMMDD-HHMMSS}".
    agent_last_location: Dict[str, str] = {}
    active_agent_session_ids = {
        str(row["session_id"])
        for row in full_roster
        if _slug_display_name(str(row.get("session_id") or ""))
    }
    for sid, loc in session_last_location.items():
        # Public history outlives a resident's city incarnation. Once /session/leave
        # removes that incarnation, its last movement remains true history but must
        # not continue to count as current map presence.
        if sid not in active_agent_session_ids:
            continue
        for agent_name in available_agents:
            if sid == agent_name or sid.startswith(agent_name + "-"):
                agent_last_location[agent_name] = loc
                break

    # Contacts = agents the player has actually encountered.
    # "Encountered" means: ever been at the same location in the scan window,
    # OR has sent the player a DM. Location chat handles real-time co-located
    # speech; DMs are the async private channel for earned contacts only.
    known_agents: List[str] = []
    known_contacts: List[Dict[str, str]] = []
    if session_id and _is_player_session(session_id):
        player_locations_seen: set[str] = set()
        current_player_location = ""
        for row in full_roster:
            if row["session_id"] == session_id:
                current_player_location = str(row.get("location") or "").strip()
                break
        for e in location_scan_events:
            if e.session_id == session_id:
                delta = e.world_state_delta or {}
                loc = _event_destination_location(delta)
                if loc:
                    player_locations_seen.add(str(loc))
        for agent_name in available_agents:
            if agent_last_location.get(agent_name) in player_locations_seen:
                known_agents.append(agent_name)
        if current_player_location:
            for row in full_roster:
                agent_name = _slug_display_name(str(row.get("session_id") or ""))
                if (
                    agent_name
                    and row.get("location") == current_player_location
                    and agent_name in available_agents
                    and agent_name not in known_agents
                ):
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

        for agent_name in known_agents:
            known_contacts.append(
                {
                    "key": agent_name,
                    "label": agent_name.replace("_", " ").title(),
                    "recipient_type": "agent",
                }
            )

        seen_contact_keys = {item["key"] for item in known_contacts}
        if current_player_location:
            for row in full_roster:
                sid = str(row.get("session_id") or "")
                if sid == session_id or not sid or _slug_display_name(sid):
                    continue
                if row.get("location") != current_player_location:
                    continue
                label = str(row.get("display_name") or sid[:12]).strip()
                if sid in seen_contact_keys or not label:
                    continue
                known_contacts.append(
                    {
                        "key": sid,
                        "label": label,
                        "recipient_type": "player",
                    }
                )
                seen_contact_keys.add(sid)

        if _SAFE_SESSION_RE.match(session_id):
            thread_rows = (
                db.query(DirectMessage)
                .filter(
                    or_(
                        DirectMessage.to_name == session_id,
                        DirectMessage.from_session_id == session_id,
                    )
                )
                .order_by(DirectMessage.sent_at, DirectMessage.id)
                .all()
            )
            for dm in thread_rows:
                counterpart_sid = ""
                counterpart_label = ""
                if str(dm.to_name or "").strip() == session_id:
                    counterpart_sid = str(dm.from_session_id or "").strip()
                    counterpart_label = str(dm.from_name or "").strip()
                else:
                    outbound_target = str(dm.to_name or "").strip()
                    if outbound_target and not _valid_agent(outbound_target):
                        counterpart_sid = outbound_target
                        counterpart_label = _player_label_for_session(
                            db, outbound_target
                        )
                if not counterpart_sid or not _SAFE_SESSION_RE.match(counterpart_sid):
                    continue
                if (
                    counterpart_sid == session_id
                    or counterpart_sid in seen_contact_keys
                ):
                    continue
                if not counterpart_label:
                    counterpart_label = _player_label_for_session(db, counterpart_sid)
                known_contacts.append(
                    {
                        "key": counterpart_sid,
                        "label": counterpart_label,
                        "recipient_type": "player",
                    }
                )
                seen_contact_keys.add(counterpart_sid)

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
        agent_location_counts[loc] = agent_location_counts.get(loc, 0) + 1
        display = agent_name.replace("_", " ").title()
        agent_location_names.setdefault(loc, []).append(display)

    # Human player display names per location
    player_location_names: Dict[str, List[str]] = {}
    for r in full_roster:
        if _slug_display_name(r["session_id"]):
            continue  # agent session — skip
        loc = r["location"]
        if loc and loc != "unknown":
            name = r.get("display_name") or r["session_id"][:12]
            player_location_names.setdefault(loc, []).append(name)
    # Guarantee the requesting player appears at their location even if they
    # haven't moved since their last session (no recent location delta event).
    if player_location and session_id and not _slug_display_name(session_id):
        req_entry = next(
            (r for r in full_roster if r["session_id"] == session_id), None
        )
        req_name = (req_entry or {}).get("display_name") or (
            session_id[:12] if session_id else None
        )
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
        loc
        for loc in set(
            list(agent_location_counts.keys())
            + ([player_location] if player_location else [])
        )
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
            extra_nodes.append(
                {
                    "key": f"{n.node_type}:{n.normalized_name}",
                    "name": n.name,
                    "count": location_counts.get(n.name, 0),
                    "agent_count": agent_location_counts.get(n.name, 0),
                    "agent_names": agent_location_names.get(n.name, []),
                    "player_names": player_location_names.get(n.name, []),
                    "is_player": n.name == player_location,
                    "lat": meta.get("lat"),
                    "lon": meta.get("lon"),
                }
            )

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
        ]
        + extra_nodes,
        "edges": raw_graph.get("edges", []),
    }

    # ── Location chat snapshot ────────────────────────────────────────────────
    location_chat: List[Dict[str, Any]] = []
    if player_location:
        chat_rows = (
            db.query(LocationChat)
            .filter(LocationChat.location == player_location)
            .order_by(LocationChat.created_at.desc())
            .limit(30)
            .all()
        )
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
        "known_contacts": known_contacts,
        "player_location": player_location,
        "location_chat": location_chat,
    }


@router.get("/world/roster-directory")
def get_world_roster_directory(
    session_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Lightweight directory of recent human and resident sessions for agent lookups."""
    entries = _roster_directory_entries(db, requested_session_id=session_id)
    return {
        "roster": entries,
        "count": len(entries),
    }


@router.get("/world/vitality/neighborhoods")
def get_neighborhood_vitality(
    hours: int = Query(default=6, ge=1, le=72),
    db: Session = Depends(get_db),
):
    """Neighborhood-level liveliness snapshot for doula targeting and operator inspection."""
    from ...services.city_pack_service import get_full_map_for_session

    city_map = get_full_map_for_session(settings.city_id)
    if not city_map.get("available"):
        return {
            "available": False,
            "city_id": settings.city_id,
            "hours": hours,
            "neighborhoods": [],
        }

    by_name: Dict[str, Dict[str, Any]] = {}
    for neighborhood in city_map.get("neighborhoods", []):
        name = str(neighborhood.get("name") or "").strip()
        if not name:
            continue
        by_name[name] = {
            "name": name,
            "current_present": 0,
            "current_agents": 0,
            "current_humans": 0,
            "total_present": 0,
            "total_agents": 0,
            "total_humans": 0,
            "chat_messages_recent": 0,
            "unique_chat_speakers_recent": 0,
            "recent_event_count": 0,
        }

    active_human_session_ids = _load_active_human_session_ids(db)
    rows = db.query(SessionVars).all()
    for row in rows:
        session_id = str(row.session_id or "").strip()
        if not _is_player_session(session_id):
            continue
        if (
            not _slug_display_name(session_id)
            and session_id not in active_human_session_ids
        ):
            continue
        vars_payload = _session_variables_payload(row.vars)
        location = str(vars_payload.get("location") or "").strip()
        if not location:
            continue
        neighborhood_name = _resolve_neighborhood_name_for_location(location)
        if not neighborhood_name or neighborhood_name not in by_name:
            continue
        entry = by_name[neighborhood_name]
        is_agent = bool(_slug_display_name(session_id))
        entry["total_present"] += 1
        if is_agent:
            entry["total_agents"] += 1
        else:
            entry["total_humans"] += 1
        entry["current_present"] += 1
        if is_agent:
            entry["current_agents"] += 1
        else:
            entry["current_humans"] += 1

    since_naive = (datetime.now(timezone.utc) - timedelta(hours=hours)).replace(
        tzinfo=None
    )

    chat_rows = (
        db.query(LocationChat).filter(LocationChat.created_at >= since_naive).all()
    )
    chat_speakers: Dict[str, set[str]] = {name: set() for name in by_name}
    for row in chat_rows:
        neighborhood_name = _resolve_neighborhood_name_for_location(
            str(row.location or "")
        )
        if not neighborhood_name or neighborhood_name not in by_name:
            continue
        by_name[neighborhood_name]["chat_messages_recent"] += 1
        speaker = str(row.display_name or row.session_id or "").strip()
        if speaker:
            chat_speakers[neighborhood_name].add(speaker)
    for neighborhood_name, speakers in chat_speakers.items():
        by_name[neighborhood_name]["unique_chat_speakers_recent"] = len(speakers)

    event_rows = db.query(WorldEvent).filter(WorldEvent.created_at >= since_naive).all()
    for row in event_rows:
        delta = row.world_state_delta if isinstance(row.world_state_delta, dict) else {}
        location = str(
            _event_destination_location(delta) or _event_origin_location(delta) or ""
        ).strip()
        if not location:
            continue
        neighborhood_name = _resolve_neighborhood_name_for_location(location)
        if not neighborhood_name or neighborhood_name not in by_name:
            continue
        by_name[neighborhood_name]["recent_event_count"] += 1

    neighborhoods: List[Dict[str, Any]] = []
    for name, entry in by_name.items():
        vitality_score = (
            float(entry["current_present"]) * 1.0
            + float(entry["chat_messages_recent"]) * 0.35
            + float(entry["unique_chat_speakers_recent"]) * 0.5
            + float(entry["recent_event_count"]) * 0.2
        )
        neighborhoods.append(
            {
                **entry,
                "vitality_score": round(vitality_score, 3),
                "needs_residents": bool(
                    entry["total_agents"] == 0
                    and (entry["total_humans"] > 0 or entry["recent_event_count"] > 0)
                ),
            }
        )

    neighborhoods.sort(key=lambda item: (float(item["vitality_score"]), item["name"]))
    return {
        "available": True,
        "city_id": settings.city_id,
        "hours": hours,
        "neighborhoods": neighborhoods,
    }


@router.get("/world/entry")
def get_world_entry(
    db: Session = Depends(get_db),
):
    """Return deterministic shard disclosure and valid starting areas."""
    from ...services.city_pack_service import get_pack
    from ...services.shard_experience import configured_shard_experience
    from ...services.world_memory import get_location_graph
    from ..game.state import _read_world_id

    world_id = _read_world_id()
    graph = get_location_graph(db)
    graph_locations = [n["name"] for n in graph["nodes"]]
    pack = get_pack(settings.city_id) or {}
    manifest = dict(pack.get("manifest") or {})
    place_name = str(
        manifest.get("city") or settings.city_id.replace("_", " ").title()
    ).strip()
    experience = configured_shard_experience()
    snapshot = f"{place_name}. {experience.entry_disclosure.summary}".strip()

    # Entry nodes: city-pack locations only. Landmarks are sub-locations discovered
    # via natural language travel or the Nearby button — they shouldn't be arrival
    # points because they have no map coordinates and disorient new players.
    cp_entry_nodes = db.query(WorldNode).filter(WorldNode.node_type == "location").all()
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
        "snapshot": snapshot,
        "fictional": bool(manifest.get("fictional", False)),
        "map_style": (
            "schematic" if bool(manifest.get("fictional", False)) else "geographic"
        ),
        "cards": [],
        "locations": dropdown_locations,
        "entry_nodes": entry_nodes,
    }


def _movement_fact_payload(
    *,
    mover_name: str,
    destination: str,
    in_transit: bool,
    summary: str,
) -> Dict[str, Any]:
    return {
        "facts": [
            {
                "subject": mover_name,
                "subject_type": "entity",
                "predicate": "location",
                "value": destination,
                "location": destination,
                "summary": summary,
                "confidence": 0.95,
            },
            {
                "subject": mover_name,
                "subject_type": "entity",
                "predicate": "in_transit",
                "value": bool(in_transit),
                "location": destination,
                "summary": summary,
                "confidence": 0.9,
            },
        ],
        "parser_mode": "structured",
    }


def _movement_event_delta(
    *,
    origin: str,
    destination: str,
    in_transit: bool,
    mover_name: str,
    summary: str,
) -> Dict[str, Any]:
    spatial_nodes: Dict[str, Dict[str, Any]] = {
        destination: {
            "last_arrival_actor": mover_name,
            "last_arrival_from": origin,
            "last_arrival_summary": summary,
            "last_movement_in_transit": bool(in_transit),
        }
    }
    if origin and origin != destination:
        spatial_nodes[origin] = {
            "last_departure_actor": mover_name,
            "last_departure_to": destination,
            "last_departure_summary": summary,
        }
    return {
        "origin": origin,
        "destination": destination,
        "in_transit": bool(in_transit),
        "spatial_nodes": spatial_nodes,
        "__world_facts__": _movement_fact_payload(
            mover_name=mover_name,
            destination=destination,
            in_transit=in_transit,
            summary=summary,
        ),
    }


def _utterance_event_delta(
    *,
    speaker_name: str,
    location: str,
    message: str,
    summary: str,
) -> Dict[str, Any]:
    return {
        "speaker": speaker_name,
        "channel": location,
        "spatial_nodes": {
            location: {
                "last_public_speaker": speaker_name,
                "last_public_utterance": message,
                "last_public_activity_type": "utterance",
                "last_public_activity_summary": summary,
            }
        },
        "__world_facts__": {
            "facts": [
                {
                    "subject": speaker_name,
                    "subject_type": "entity",
                    "predicate": "spoke_at",
                    "value": location,
                    "location": location,
                    "summary": summary,
                    "confidence": 0.6,
                }
            ],
            "parser_mode": "structured",
        },
    }


class MapMoveRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    destination: str = Field(..., min_length=1, max_length=200)
    skip_to_destination: bool = False
    allow_sublocation_create: bool = False


class SublocationCreateRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    label: str = Field(..., min_length=3, max_length=120)
    ttl_seconds: int = Field(default=6 * 3600, ge=900, le=7 * 86400)


@router.get("/world/sublocations")
def get_world_sublocations(
    parent_location: str = Query(..., min_length=1, max_length=200),
    db: Session = Depends(get_db),
):
    """List active child places without adding them to the canonical map."""
    from ...services.sublocations import active_sublocations, sublocation_payload

    rows = active_sublocations(db, parent_location=parent_location.strip())
    return {
        "parent_location": parent_location.strip(),
        "sublocations": [sublocation_payload(row) for row in rows],
        "count": len(rows),
    }


@router.post("/game/sublocations")
def create_world_sublocation(
    payload: SublocationCreateRequest,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
):
    """Create or refresh one bounded ephemeral place under the caller's map node."""
    from ...services.session_service import get_state_manager
    from ...services.sublocations import (
        create_or_refresh_ephemeral,
        sublocation_payload,
    )

    if not _SAFE_SESSION_RE.match(payload.session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")
    _authorize_bound_actor_or_http(
        db, credentials=credentials, session_id=payload.session_id
    )
    sm = get_state_manager(payload.session_id, db)
    current_location = str(sm.get_variable("location") or "").strip()
    if not current_location:
        raise HTTPException(
            status_code=400, detail="Session has no current location set."
        )
    parent_location = resolve_route_anchor(db, current_location)
    try:
        row = create_or_refresh_ephemeral(
            db,
            parent_location=parent_location,
            label=payload.label,
            created_by_session=payload.session_id,
            ttl_seconds=payload.ttl_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(row)
    return sublocation_payload(row)


@router.post("/game/move")
def map_move(
    payload: MapMoveRequest,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
):
    """Move one hop toward destination along the shortest graph path.

    Bypasses LLM — pure graph traversal over 'path' edges.
    Each call advances one hop. Call repeatedly to continue transit.
    Returns the new location, the full planned route, and remaining hops.
    """
    from ...services.session_service import get_state_manager, save_state
    from ...services.world_memory import EVENT_TYPE_MOVEMENT, find_route

    session_id = payload.session_id
    if not _SAFE_SESSION_RE.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")
    _authorize_bound_actor_or_http(db, credentials=credentials, session_id=session_id)

    sm = get_state_manager(session_id, db)
    current_location = sm.get_variable("location") or ""

    if not current_location:
        raise HTTPException(
            status_code=400, detail="Session has no current location set."
        )

    destination = payload.destination.strip()
    current_anchor = resolve_route_anchor(db, current_location)
    from ...services.sublocations import (
        create_or_refresh_ephemeral,
        is_local_sublocation_candidate,
        resolve_active_sublocation,
        touch_sublocation,
    )

    destination_sublocation = resolve_active_sublocation(
        db,
        label=destination,
        parent_location=current_anchor,
    )
    if (
        destination_sublocation is None
        and payload.allow_sublocation_create
        and is_local_sublocation_candidate(destination, current_anchor)
    ):
        destination_sublocation = create_or_refresh_ephemeral(
            db,
            parent_location=current_anchor,
            label=destination,
            created_by_session=session_id,
        )
    if destination_sublocation is not None:
        destination = str(destination_sublocation.name or destination)
    destination_anchor = resolve_route_anchor(db, destination)

    if (
        current_location != destination
        and current_anchor
        and destination_anchor
        and current_anchor == destination_anchor
    ):
        route = [current_location, destination]
    else:
        route = find_route(
            db, current_anchor or current_location, destination_anchor or destination
        )
        if (
            route
            and current_anchor
            and current_location != current_anchor
            and route[0] == current_anchor
        ):
            route = [current_location, *route[1:]]
        if (
            route
            and destination_anchor
            and destination_anchor != destination
            and route[-1] == destination_anchor
        ):
            route = [*route, destination]

    snapped = False
    if not route:
        # If routing failed because current_location is a narrative sublocation that isn't
        # in the graph (e.g. "The Bakery Stall"), snap the agent directly to the destination
        # as a one-time recovery move. This re-anchors orphaned agents without stranding them.
        dest_route = find_route(
            db, destination_anchor or destination, destination_anchor or destination
        )
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

    # Access rules apply only to places this command is about to enter. The
    # current/origin place is intentionally absent, so no policy can trap a
    # resident inside. Skip mode validates the whole route before changing any
    # session state or writing any movement event.
    from ...services.space_access import SpaceAccessError, assert_route_entry_allowed

    entered_locations = (
        route[1:] if payload.skip_to_destination and not snapped else [route[1]]
    )
    try:
        assert_route_entry_allowed(
            db,
            session_id=session_id,
            destinations=entered_locations,
        )
    except SpaceAccessError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    # Derive a display name for the mover.
    # player_role is set explicitly at bootstrap (e.g. "Brunhilda"); prefer it
    # over player_name which can be stale (injected by world projection).
    _raw_role = sm.get_variable("player_role") or ""
    _role_name = (
        _raw_role.split(" — ")[0].strip() if " — " in _raw_role else _raw_role.strip()
    ) or None
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
            summary = (
                f"{mover_name} passes through {hop.replace('_', ' ')}, "
                f"continuing toward {final_dest.replace('_', ' ')}."
            )
            submit_world_event(
                db,
                WorldEventCommand(
                    session_id=session_id,
                    event_type=EVENT_TYPE_MOVEMENT,
                    summary=summary,
                    delta=_movement_event_delta(
                        origin=prev,
                        destination=hop,
                        in_transit=True,
                        mover_name=mover_name,
                        summary=summary,
                    ),
                    metadata={"surface": "map_move", "mode": "skip_to_destination"},
                    preserve_event_type=True,
                ),
            )
        # Final hop
        prev_final = sm.get_variable("location") or current_location
        sm.set_variable("location", final_dest)
        if destination_sublocation is not None and final_dest == destination:
            touch_sublocation(destination_sublocation)
        save_state(sm, db)
        final_summary = f"{mover_name} arrives at {final_dest.replace('_', ' ')}."
        submit_world_event(
            db,
            WorldEventCommand(
                session_id=session_id,
                event_type=EVENT_TYPE_MOVEMENT,
                summary=final_summary,
                delta=_movement_event_delta(
                    origin=prev_final,
                    destination=final_dest,
                    in_transit=False,
                    mover_name=mover_name,
                    summary=final_summary,
                ),
                metadata={"surface": "map_move", "mode": "skip_to_destination"},
                preserve_event_type=True,
            ),
        )
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
    if destination_sublocation is not None and next_location == destination:
        touch_sublocation(destination_sublocation)
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

    submit_world_event(
        db,
        WorldEventCommand(
            session_id=session_id,
            event_type=EVENT_TYPE_MOVEMENT,
            summary=event_summary,
            delta=_movement_event_delta(
                origin=current_location,
                destination=next_location,
                in_transit=bool(route_remaining),
                mover_name=mover_name,
                summary=event_summary,
            ),
            metadata={"surface": "map_move", "mode": "single_hop"},
            preserve_event_type=True,
        ),
    )

    return {
        "moved": True,
        "from_location": current_location,
        "to_location": next_location,
        "route": route,
        "route_remaining": route_remaining,
        "narrative": narrative,
    }


@router.get("/world/map/query")
def query_world_map(
    north: float = Query(...),
    south: float = Query(...),
    east: float = Query(...),
    west: float = Query(...),
    session_id: Optional[str] = Query(default=None),
    query: str = Query(default=""),
    occupied_only: bool = Query(default=False),
    quiet_only: bool = Query(default=False),
    include_landmarks: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Return a viewport-scoped mixed map graph with occupancy and optional search."""
    from ...services.world_memory import find_route, get_location_graph

    if south > north:
        raise HTTPException(
            status_code=422, detail="south cannot be greater than north"
        )

    normalized_query = str(query or "").strip()
    identified_session = (
        db.get(SessionVars, str(session_id or "").strip()) if session_id else None
    )
    presence = _load_live_presence_maps(
        db,
        requested_session_id=(
            str(identified_session.session_id)
            if identified_session is not None
            else None
        ),
    )
    requested_location = str(presence.get("requested_location") or "").strip()
    base_graph = get_location_graph(db)
    base_nodes_by_name = {
        str(node["name"]): node for node in base_graph.get("nodes", [])
    }

    included_nodes: Dict[str, Dict[str, Any]] = {}
    parent_links: Dict[str, str] = {}
    exact_focus_names: set[str] = set()
    exact_focus_location_names: set[str] = set()

    def include_location(name: str) -> None:
        base = base_nodes_by_name.get(name)
        if not base:
            return
        included_nodes[name] = _build_map_node_payload(
            name=name,
            key=str(base["key"]),
            node_type="location",
            lat=base.get("lat"),
            lon=base.get("lon"),
            description=str(base.get("description") or ""),
            is_player=name == requested_location,
            parent_location=name,
            presence=presence,
            include_presence_names=identified_session is not None,
        )

    for name, base in base_nodes_by_name.items():
        if exact_focus_location_names and name not in exact_focus_location_names:
            continue
        in_bbox = _location_in_bbox(
            lat=base.get("lat"),
            lon=base.get("lon"),
            north=north,
            south=south,
            east=east,
            west=west,
        )
        matches_query = _matches_map_query(
            name, base.get("description"), query=normalized_query
        )
        if not in_bbox and not matches_query:
            continue
        if normalized_query and not matches_query:
            continue
        include_location(name)

    node_query = db.query(WorldNode).filter(
        WorldNode.node_type.in_(["location", "landmark", "corridor"])
    )
    all_candidate_nodes = node_query.all()

    if normalized_query:
        for name in base_nodes_by_name:
            if _is_exact_map_query_match(name, normalized_query):
                exact_focus_names.add(name)
                exact_focus_location_names.add(name)

        for node in all_candidate_nodes:
            node_name = str(node.name or "").strip()
            if not node_name or not _is_exact_map_query_match(
                node_name, normalized_query
            ):
                continue
            exact_focus_names.add(node_name)
            metadata = dict(node.metadata_json or {})
            node_type = str(node.node_type or "").strip()
            parent_location = parent_location_name_for_node(
                name=node_name,
                node_type=node_type,
                metadata=metadata,
                city_id=str(metadata.get("city_id") or settings.city_id or ""),
            )
            exact_focus_location_names.add(parent_location or node_name)

        if exact_focus_location_names:
            current_anchor = (
                resolve_route_anchor(db, requested_location)
                if requested_location
                else ""
            )
            expanded_locations = set(exact_focus_location_names)
            if current_anchor:
                expanded_locations.add(current_anchor)
            for focus_name in list(exact_focus_location_names):
                destination_anchor = resolve_route_anchor(db, focus_name)
                if current_anchor and destination_anchor:
                    expanded_locations.update(
                        find_route(db, current_anchor, destination_anchor)
                    )
            exact_focus_location_names = {name for name in expanded_locations if name}

    include_landmarks_now = include_landmarks and not bool(normalized_query)
    for node in all_candidate_nodes:
        metadata = dict(node.metadata_json or {})
        city_id = str(metadata.get("city_id") or settings.city_id or "")
        if city_id and settings.city_id and city_id != settings.city_id:
            continue
        node_name = str(node.name or "").strip()
        node_type = str(node.node_type or "").strip()
        if not node_name:
            continue

        lat = metadata.get("lat")
        lon = metadata.get("lon")
        in_bbox = _location_in_bbox(
            lat=lat, lon=lon, north=north, south=south, east=east, west=west
        )
        is_occupied = bool(
            int(presence["human_counts"].get(node_name, 0))
            + int(presence["agent_counts"].get(node_name, 0))
        )
        is_player_location = node_name == requested_location
        matches_query = _matches_map_query(
            node_name,
            metadata.get("description"),
            metadata.get("type"),
            metadata.get("vibe"),
            metadata.get("category"),
            query=normalized_query,
        )

        should_include = False
        if exact_focus_location_names:
            if node_type == "location":
                should_include = (
                    node_name in exact_focus_location_names or is_player_location
                )
            elif node_type in {"landmark", "corridor"}:
                should_include = node_name in exact_focus_names or is_player_location
        elif node_type == "location":
            should_include = (
                node_name in included_nodes or is_player_location or matches_query
            )
        elif node_type in {"landmark", "corridor"}:
            should_include = (
                (include_landmarks_now and in_bbox)
                or is_occupied
                or is_player_location
                or matches_query
            )

        if not should_include:
            continue
        if (
            not in_bbox
            and not is_occupied
            and not is_player_location
            and not matches_query
        ):
            continue

        parent_location = parent_location_name_for_node(
            name=node_name,
            node_type=node_type,
            metadata=metadata,
            city_id=city_id,
        )
        if parent_location and parent_location in base_nodes_by_name:
            include_location(parent_location)
            parent_links[node_name] = parent_location

        if (
            (lat is None or lon is None)
            and parent_location
            and parent_location in base_nodes_by_name
        ):
            parent_base = base_nodes_by_name[parent_location]
            lat = parent_base.get("lat")
            lon = parent_base.get("lon")

        existing = included_nodes.get(node_name)
        candidate_metadata = {**metadata, "lat": lat, "lon": lon}
        if not _prefer_map_node_candidate(
            existing, node_type=node_type, metadata=candidate_metadata
        ):
            continue

        included_nodes[node_name] = _build_map_node_payload(
            name=node_name,
            key=f"{node_type}:{node.normalized_name}",
            node_type=node_type,
            lat=lat,
            lon=lon,
            description=str(metadata.get("description") or ""),
            is_player=is_player_location,
            parent_location=parent_location,
            presence=presence,
            include_presence_names=identified_session is not None,
        )

    filtered_nodes: Dict[str, Dict[str, Any]] = {}
    for name, node in included_nodes.items():
        present_count = int(node.get("present_count") or 0)
        keep = True
        if occupied_only and present_count <= 0 and name not in parent_links.values():
            keep = False
        if quiet_only and present_count > 0:
            keep = False
        if keep:
            filtered_nodes[name] = node

    for parent_name in parent_links.values():
        if parent_name in included_nodes and parent_name not in filtered_nodes:
            filtered_nodes[parent_name] = included_nodes[parent_name]

    node_keys = {node["key"] for node in filtered_nodes.values()}
    edges: List[Dict[str, str]] = []
    for edge in base_graph.get("edges", []):
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        if src in node_keys and dst in node_keys:
            edges.append({"from": src, "to": dst, "kind": "path"})

    for child_name, parent_name in parent_links.items():
        child = filtered_nodes.get(child_name)
        parent = filtered_nodes.get(parent_name)
        if not child or not parent:
            continue
        edge = {"from": parent["key"], "to": child["key"], "kind": "contains"}
        if edge not in edges:
            edges.append(edge)

    sorted_nodes = sorted(
        filtered_nodes.values(),
        key=lambda node: (
            0 if node.get("is_player") else 1,
            0 if int(node.get("present_count") or 0) > 0 else 1,
            0 if str(node.get("node_type") or "") == "location" else 1,
            str(node.get("name") or "").lower(),
        ),
    )

    return {
        "query": normalized_query,
        "viewport": {
            "north": north,
            "south": south,
            "east": east,
            "west": west,
        },
        "occupied_only": occupied_only,
        "quiet_only": quiet_only,
        "include_landmarks": include_landmarks,
        "nodes": sorted_nodes,
        "edges": edges,
        "count": len(sorted_nodes),
    }


# ---------------------------------------------------------------------------
# Player ↔ Agent DM system
# ---------------------------------------------------------------------------

_OPENCLAW_ROOT = Path(__file__).parents[3] / ".openclaw"
# Resident souls live per-shard under <shard>/residents/, located at runtime via
# WW_AGENT_RESIDENTS_DIR (each shard's compose sets it to /app/residents). Since the
# shard-first split there is no universal monorepo location; when unset, fall back to a
# runtime-data dir under the engine — absent by default, which simply means "no local roster".
_WW_AGENT_RESIDENTS = Path(
    os.environ.get("WW_AGENT_RESIDENTS_DIR")
    or str(Path(__file__).parents[3] / "var" / "residents")
)
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
    recipient: Optional[str] = Field(default=None, min_length=1, max_length=64)
    recipient_type: str = Field(default="agent", min_length=1, max_length=16)
    to_agent: Optional[str] = Field(default=None, min_length=1, max_length=32)
    from_name: str = Field(..., min_length=1, max_length=60)
    body: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = Field(default=None, max_length=64)


class AgentDMReplyRequest(BaseModel):
    from_agent: str = Field(..., min_length=1, max_length=32)
    to_session_id: str = Field(..., min_length=1, max_length=64)
    body: str = Field(..., min_length=1, max_length=4000)


def _dm_counterpart_key(dm: DirectMessage, session_id: str) -> str:
    if str(dm.to_name or "").strip() == session_id:
        raw = str(dm.from_name or "").strip()
    else:
        raw = str(dm.to_name or "").strip()
    return re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")


def _player_label_for_session(db: Session, session_id: str) -> str:
    row = db.get(SessionVars, session_id)
    if row is not None:
        vars_payload = _session_variables_payload(row.vars)
        _, display_name = _session_display_details(session_id, vars_payload)
        if display_name:
            return display_name
    return session_id[:12]


def _dm_counterpart_label(
    dm: DirectMessage,
    session_id: str,
    *,
    db: Session | None = None,
) -> str:
    if str(dm.to_name or "").strip() == session_id:
        raw = str(dm.from_name or "").strip()
        return raw.replace("_", " ").strip().title()
    raw = str(dm.to_name or "").strip()
    if db is not None and _SAFE_SESSION_RE.match(raw) and not _valid_agent(raw):
        return _player_label_for_session(db, raw)
    return raw.replace("_", " ").strip().title()


@router.post("/world/dm")
def send_dm(
    payload: SendDMRequest,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
):
    """Store a DM claiming the supplied sender and recipient.

    The current route validates names and row existence but does not authenticate
    control of ``session_id``. The agent poll also marks unread rows read before
    resident prompt delivery; both are tracked as correspondence audit gaps.
    """
    recipient = str(payload.recipient or payload.to_agent or "").strip()
    recipient_type = str(payload.recipient_type or "agent").strip().lower()
    if not recipient:
        raise HTTPException(status_code=400, detail="Missing recipient.")

    from_session = (
        payload.session_id
        if payload.session_id and _SAFE_SESSION_RE.match(payload.session_id or "")
        else None
    )
    if from_session:
        _authorize_bound_actor_or_http(
            db, credentials=credentials, session_id=from_session
        )
    delivered_to = recipient

    if recipient_type == "player":
        if not _SAFE_SESSION_RE.match(recipient):
            raise HTTPException(status_code=400, detail="Invalid player recipient.")
        if _slug_display_name(recipient):
            raise HTTPException(
                status_code=400, detail="Player recipient must be a human session."
            )
        row = db.get(SessionVars, recipient)
        if row is None:
            raise HTTPException(
                status_code=404, detail=f"No player session found for '{recipient}'."
            )
        delivered_to = _player_label_for_session(db, recipient)
    else:
        agent = recipient.lower().strip()
        if not _valid_agent(agent):
            raise HTTPException(
                status_code=404, detail=f"No agent found for '{agent}'."
            )
        recipient = agent
        delivered_to = agent

    dm = DirectMessage(
        from_name=payload.from_name,
        from_session_id=from_session,
        to_name=recipient,
        body=payload.body,
    )
    db.add(dm)
    db.commit()

    return {
        "success": True,
        "dm_id": dm.id,
        "delivered_to": delivered_to,
        "recipient_type": recipient_type,
        "recipient_key": recipient,
    }


@router.post("/world/dm/reply")
def agent_dm_reply(payload: AgentDMReplyRequest, db: Session = Depends(get_db)):
    """Store a DM reply claiming a locally valid agent name.

    This compatibility route does not yet authenticate control of the agent.
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
    db.commit()

    return {"success": True, "dm_id": dm.id, "from_agent": agent}


@router.get("/world/dm/inbox/{agent}")
def get_agent_dm_inbox(agent: str, db: Session = Depends(get_db)):
    """Return unread DMs and mark them read during this unauthenticated poll.

    This is legacy mail-loop behavior, not consume-on-prompt delivery.
    """
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
        reply_header = (
            f"Reply-To-Session: {dm.from_session_id}\n" if dm.from_session_id else ""
        )
        body = f"# DM from {dm.from_name}\n{reply_header}\n{dm.body}\n"
        dms.append({"filename": filename, "body": body})
        dm.read_at = now

    if unread:
        db.commit()

    return {"agent": agent, "letters": dms, "count": len(dms)}


@router.get("/world/dm/my-inbox/{session_id}")
def get_player_dm_inbox(
    session_id: str,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
):
    """Return all DMs for a proven named session."""
    if not _SAFE_SESSION_RE.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")
    _authorize_bound_actor_or_http(db, credentials=credentials, session_id=session_id)

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


@router.get("/world/dm/my-threads/{session_id}")
def get_player_dm_threads(
    session_id: str,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
):
    """Return threads for a proven named session."""
    if not _SAFE_SESSION_RE.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")
    _authorize_bound_actor_or_http(db, credentials=credentials, session_id=session_id)

    all_dms = (
        db.query(DirectMessage)
        .filter(
            or_(
                DirectMessage.to_name == session_id,
                DirectMessage.from_session_id == session_id,
            )
        )
        .order_by(DirectMessage.sent_at, DirectMessage.id)
        .all()
    )

    threads: dict[str, dict[str, Any]] = {}
    for dm in all_dms:
        counterpart_key = _dm_counterpart_key(dm, session_id)
        if not counterpart_key:
            continue
        thread = threads.setdefault(
            counterpart_key,
            {
                "thread_key": counterpart_key,
                "counterpart": _dm_counterpart_label(dm, session_id, db=db),
                "messages": [],
                "last_at": None,
                "unread_count": 0,
            },
        )
        direction = (
            "inbound" if str(dm.to_name or "").strip() == session_id else "outbound"
        )
        sent_at = dm.sent_at.isoformat() if dm.sent_at else None
        thread["messages"].append(
            {
                "dm_id": dm.id,
                "direction": direction,
                "body": str(dm.body or ""),
                "sent_at": sent_at,
                "read_at": dm.read_at.isoformat() if dm.read_at else None,
                "from_name": str(dm.from_name or ""),
                "to_name": str(dm.to_name or ""),
            }
        )
        thread["last_at"] = sent_at or thread["last_at"]
        if direction == "inbound" and dm.read_at is None:
            thread["unread_count"] = int(thread["unread_count"] or 0) + 1

    ordered_threads = sorted(
        threads.values(),
        key=lambda item: str(item.get("last_at") or ""),
        reverse=True,
    )
    return {
        "session_id": session_id,
        "threads": ordered_threads,
        "count": len(ordered_threads),
    }


@router.post("/world/dm/my-threads/{session_id}/read/{thread_key}")
def mark_player_dm_thread_read(
    session_id: str,
    thread_key: str,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
):
    """Mark a proven named session's thread read."""
    if not _SAFE_SESSION_RE.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")
    _authorize_bound_actor_or_http(db, credentials=credentials, session_id=session_id)
    normalized_thread_key = re.sub(
        r"[^a-z0-9]+", "_", str(thread_key or "").lower()
    ).strip("_")
    if not normalized_thread_key:
        raise HTTPException(status_code=400, detail="Invalid thread_key format.")

    unread = (
        db.query(DirectMessage)
        .filter(DirectMessage.to_name == session_id, DirectMessage.read_at.is_(None))
        .order_by(DirectMessage.sent_at, DirectMessage.id)
        .all()
    )

    now = datetime.utcnow()
    updated = 0
    for dm in unread:
        if _dm_counterpart_key(dm, session_id) != normalized_thread_key:
            continue
        dm.read_at = now
        updated += 1

    if updated:
        db.commit()

    return {
        "session_id": session_id,
        "thread_key": normalized_thread_key,
        "marked_read": updated,
    }


# ---------------------------------------------------------------------------
# Shadow consent
# ---------------------------------------------------------------------------

_WW_AGENT_CONTRACTS = _WW_AGENT_RESIDENTS / "_contracts"


class ShadowConsentRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    consent: bool
    non_negotiables: list[str] = Field(default_factory=list)


@router.post("/world/shadow/consent")
def shadow_consent(
    payload: ShadowConsentRequest,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
):
    """Record a player's shadow/twinning consent decision.

    Writes an identity contract to ww_agent/residents/_contracts/{name}.json.
    The doula loop reads this before deciding whether to spawn a shadow agent
    for a departing player. With consent=false, the player is permanently
    excluded from shadow spawning. With consent=true, optional non_negotiables
    are prepended to the soul seed context so the shadow respects them.
    """
    if not _SAFE_SESSION_RE.match(payload.session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")
    _authorize_bound_actor_or_http(
        db, credentials=credentials, session_id=payload.session_id
    )

    # Resolve the player's display name from their session state.
    from ...services.session_service import get_state_manager

    try:
        sm = get_state_manager(payload.session_id, db)
        player_role = sm.get_variable("player_role") or ""
    except Exception:
        raise HTTPException(status_code=404, detail="Session not found.")

    if not player_role:
        raise HTTPException(status_code=422, detail="Session has no player_role set.")

    display_name = (
        player_role.split(" — ")[0].strip()
        if " — " in player_role
        else player_role.strip()
    )
    if not display_name:
        raise HTTPException(
            status_code=422, detail="Could not derive player name from session."
        )

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
        "Shadow consent recorded for %s (%s): %s",
        display_name,
        payload.session_id,
        action,
    )
    return {
        "success": True,
        "name": display_name,
        "consent": payload.consent,
        "contract_path": str(contract_path),
    }


@router.get("/world/scene/{session_id}")
def get_agent_scene(
    session_id: str,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
):
    """Return current, directly reportable local state for a participant.

    Historical event summaries and inferred scenery are not current perception. They
    remain available through explicit history queries instead of being mixed into this
    scene snapshot.
    """
    if not _SAFE_SESSION_RE.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")
    _authorize_bound_actor_or_http(db, credentials=credentials, session_id=session_id)

    from ...services.world_memory import get_location_graph

    row = db.get(SessionVars, session_id)
    vars_payload = _session_variables_payload(row.vars) if row is not None else {}
    location = _session_location_from_vars(vars_payload)
    player_role = str(vars_payload.get("player_role") or "").strip()

    active_human_session_ids = _load_active_human_session_ids(
        db, requested_session_id=session_id
    )
    session_rows = _load_recent_session_rows(db, requested_session_id=session_id)
    graph_anchor = resolve_route_anchor(db, location) if location else ""
    present_by_sid: Dict[str, Dict[str, Any]] = {}
    for session_row in session_rows:
        sid = str(session_row.session_id or "").strip()
        if not sid or sid == session_id or not _is_player_session(sid):
            continue
        if not _slug_display_name(sid) and sid not in active_human_session_ids:
            continue

        row_vars = _session_variables_payload(session_row.vars)
        if _session_location_from_vars(row_vars) != location:
            continue

        _, display_name = _session_display_details(sid, row_vars)
        role = _session_role_label(row_vars, display_name)
        present_by_sid[sid] = {
            "actor_id": str(
                session_row.actor_id or row_vars.get("actor_id") or ""
            ).strip(),
            "session_id": sid,
            "name": display_name,
            "role": role or display_name,
            "last_action": "",
            "last_seen": (
                session_row.updated_at.isoformat() if session_row.updated_at else None
            ),
        }

    # ── Location graph (for movement decisions) ───────────────────────────────
    graph = get_location_graph(db)
    from ...services.sublocations import active_sublocations, graph_with_sublocations

    graph = graph_with_sublocations(
        graph,
        parent_location=graph_anchor,
        rows=active_sublocations(db, parent_location=graph_anchor),
    )
    scene_graph = _graph_with_anchor_alias(
        {
            "nodes": [
                dict(node)
                for node in list(graph.get("nodes") or [])
                if isinstance(node, dict)
            ],
            "edges": [
                dict(edge)
                for edge in list(graph.get("edges") or [])
                if isinstance(edge, dict)
            ],
        },
        location_name=location,
        anchor_name=graph_anchor,
    )
    traces_here = _active_world_traces(
        db, location=location, viewer_session_id=session_id
    )

    return {
        "session_id": session_id,
        "location": location,
        "role": player_role,
        "present": list(present_by_sid.values()),
        # Reserved for source-labelled environmental facts.  Do not turn
        # weather, headcount, event count, or city-pack prose into authored
        # social scenery and present it as direct perception.
        "ambient_presence": [],
        "traces_here": traces_here,
        # Kept empty for response-shape compatibility. Historical events are
        # available through explicit history and fact-query endpoints.
        "recent_events_here": [],
        "location_graph": scene_graph,
    }


@router.get("/world/scene/{session_id}/new-events")
def get_new_events_for_agent(
    session_id: str,
    since: str = Query(
        ..., description="ISO-8601 timestamp; return events after this time"
    ),
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
):
    """Poll for new events at the agent's current location since a given timestamp.

    Used by the fast loop to decide whether to fire. Returns only events that
    occurred at the agent's location after `since`, excluding the agent's own actions.
    No LLM — pure event log scan. Very fast.
    """
    if not _SAFE_SESSION_RE.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")
    _authorize_bound_actor_or_http(db, credentials=credentials, session_id=session_id)

    from datetime import datetime, timezone

    try:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid since timestamp.")

    row = db.get(SessionVars, session_id)
    vars_payload = _session_variables_payload(row.vars) if row is not None else {}
    location = _session_location_from_vars(vars_payload)

    if not location:
        return {"events": [], "count": 0}

    since_naive = since_dt.astimezone(timezone.utc).replace(tzinfo=None)
    all_events = _recent_world_events_rows(db, limit=300, since=since_naive)
    new_events = []
    for e in all_events:
        if e.session_id == session_id:
            continue
        delta = e.world_state_delta or {}
        if (
            _event_origin_location(delta) != location
            and _event_destination_location(delta) != location
        ):
            continue
        summary = _clean_event_summary(str(e.summary or ""))
        who = _slug_display_name(e.session_id or "") or (e.session_id or "")[:12]
        new_events.append(
            {
                "event_id": str(e.id),
                "event_type": str(e.event_type or ""),
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


class LeaveWorldTraceRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    body: str = Field(..., min_length=1, max_length=500)
    target: str = Field(default="", max_length=200)


@router.get("/world/traces")
def get_world_traces(
    session_id: str = Query(..., min_length=1, max_length=64),
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
):
    """Show another visitor's active public marks at the caller's exact place."""
    normalized_session_id = str(session_id or "").strip()
    if not _SAFE_SESSION_RE.match(normalized_session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")
    _authorize_bound_actor_or_http(
        db, credentials=credentials, session_id=normalized_session_id
    )

    session_row = db.get(SessionVars, normalized_session_id)
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    vars_payload = _session_variables_payload(session_row.vars)
    location = _session_location_from_vars(vars_payload)
    if not location:
        raise HTTPException(status_code=409, detail="Session has no current location.")

    traces = _active_world_traces(
        db, location=location, viewer_session_id=normalized_session_id
    )
    for trace in traces:
        # Humans need authorship, not the temporary transport identifier the
        # resident runtime uses to connect local observations.
        trace.pop("author_session_id", None)
    return {"location": location, "traces": traces, "count": len(traces)}


@router.post("/world/traces")
def post_world_trace(
    payload: LeaveWorldTraceRequest,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
):
    """Leave one expiring physical mark at the actor's current location.

    Author and location are derived from canonical session state. The write does
    not enter chat, the generic world-event feed, or either narration path.
    """
    session_id = str(payload.session_id or "").strip()
    if not _SAFE_SESSION_RE.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")
    _authorize_bound_actor_or_http(db, credentials=credentials, session_id=session_id)

    session_row = db.get(SessionVars, session_id)
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    vars_payload = _session_variables_payload(session_row.vars)
    location = _session_location_from_vars(vars_payload)
    if not location:
        raise HTTPException(status_code=409, detail="Session has no current location.")

    body = str(payload.body or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="Trace body cannot be empty.")
    target = str(payload.target or "").strip()
    _, author_name = _session_display_details(session_id, vars_payload)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row = WorldTrace(
        session_id=session_id,
        author_name=author_name,
        location=location,
        target=target or None,
        body=body,
        created_at=now,
        expires_at=now + timedelta(seconds=_WORLD_TRACE_TTL_SECONDS),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "trace": _world_trace_payload(row)}


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
        _upsert_world_node(
            db, payload.name, payload.node_type, metadata=payload.metadata
        )
    db.commit()
    return {"ok": True, "name": payload.name, "node_type": payload.node_type}


# ---------------------------------------------------------------------------
# Co-located chat — lightweight async messaging at a location
# ---------------------------------------------------------------------------


class PostChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    message: str = Field(..., min_length=1, max_length=500)
    display_name: Optional[str] = Field(default=None, max_length=200)


@router.get("/world/session/{session_id}/signals")
def get_live_signals(
    session_id: str,
    after: Optional[int] = Query(default=None, ge=0),
    cursor_shard: Optional[str] = Query(default=None, max_length=80),
    cursor_location: Optional[str] = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    wait_seconds: float = Query(default=0.0, ge=0.0, le=25.0),
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
):
    """Read durable new signals at the caller's current exact place.

    The current location comes from the authenticated session rather than from a
    caller-selected path.  An empty request establishes a cursor without
    replaying archived room speech as a live event.
    """

    _authorize_bound_actor_or_http(db, credentials=credentials, session_id=session_id)
    try:
        revision = current_live_signal_revision()
        result = read_live_signals(
            db,
            session_id=session_id,
            after_id=after,
            cursor_shard=str(cursor_shard or "").strip() or None,
            cursor_location=str(cursor_location or "").strip() or None,
            limit=limit,
        )
        if (
            wait_seconds > 0
            and result["cursor_status"] == "current"
            and not result["events"]
            and not result["has_more"]
        ):
            wait_for_live_signal_change(
                after_revision=revision,
                timeout=wait_seconds,
            )
            db.expire_all()
            result = read_live_signals(
                db,
                session_id=session_id,
                after_id=after,
                cursor_shard=str(cursor_shard or "").strip() or None,
                cursor_location=str(cursor_location or "").strip() or None,
                limit=limit,
            )
        return result
    except LiveSignalError as exc:
        status_code = 404 if exc.code == "session_not_found" else 409
        raise HTTPException(
            status_code=status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


@router.get("/world/location/{location}/chat")
def get_location_chat(
    location: str,
    since: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session_id: Optional[str] = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
):
    """Return recent chat messages at a location, optionally filtered by timestamp.

    Speaker session/actor identifiers are included when a caller proves control of
    an existing session. Public readers get display names, text, and timestamps only.
    """
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
    requested_session_id = str(session_id or "").strip()
    if requested_session_id:
        _authorize_bound_actor_or_http(
            db, credentials=credentials, session_id=requested_session_id
        )
    include_speaker_ids = bool(
        requested_session_id and db.get(SessionVars, requested_session_id) is not None
    )
    actor_ids_by_session: dict[str, str] = {}
    if include_speaker_ids:
        session_ids = {
            str(row.session_id or "").strip()
            for row in rows
            if str(row.session_id or "").strip()
        }
        actor_ids_by_session = {
            str(row.session_id or "")
            .strip(): str(
                row.actor_id
                or (_session_variables_payload(row.vars).get("actor_id"))
                or ""
            )
            .strip()
            for row in db.query(SessionVars)
            .filter(SessionVars.session_id.in_(session_ids))
            .all()
        }
    messages = []
    for r in rows:
        entry: dict[str, Any] = {
            "id": r.id,
            "display_name": r.display_name,
            "message": r.message,
            "ts": r.created_at.isoformat() if r.created_at else None,
        }
        if include_speaker_ids:
            entry["session_id"] = r.session_id
            entry["actor_id"] = str(
                r.actor_id
                or actor_ids_by_session.get(str(r.session_id or "").strip(), "")
                or ""
            ).strip()
        messages.append(entry)
    return {"location": location, "messages": messages}


@router.get("/world/location/{location}/presence")
def get_location_presence(
    location: str,
    db: Session = Depends(get_db),
):
    """Return public, current presence for one place.

    The town map exposes counts only. Names become visible when a visitor opens
    one particular place, keeping this an encounter rather than a town roster.
    """
    normalized_location = str(location or "").strip()
    presence = _load_live_presence_maps(db)
    names = list(presence["present_names"].get(normalized_location, []))
    return {
        "location": normalized_location,
        "present_count": int(presence["human_counts"].get(normalized_location, 0))
        + int(presence["agent_counts"].get(normalized_location, 0)),
        "present_names": names,
    }


@router.post("/world/location/{location}/chat")
def post_location_chat(
    location: str,
    payload: PostChatRequest,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
):
    """Post as a proven named session at its location."""
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    session_id = str(payload.session_id or "").strip()
    _authorize_bound_actor_or_http(db, credentials=credentials, session_id=session_id)
    session_row = db.get(SessionVars, session_id)
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    vars_payload = _session_variables_payload(session_row.vars)
    session_location = _session_location_from_vars(vars_payload)
    requested_location = str(location or "").strip()
    if not session_location:
        raise HTTPException(status_code=409, detail="Session has no current location.")
    if session_location != requested_location:
        raise HTTPException(
            status_code=409, detail="You can only speak where you are standing."
        )
    _, display_name = _session_display_details(session_id, vars_payload)

    # Store in real-time chat table (fast path — agents poll this)
    row = LocationChat(
        location=session_location,
        session_id=session_id,
        actor_id=str(session_row.actor_id or vars_payload.get("actor_id") or "").strip()
        or None,
        display_name=display_name,
        message=message,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    notify_live_signal()

    # Also record as a lightweight utterance WorldEvent so speech becomes part of
    # world memory: resident perception can recognize the same utterance as one
    # event instead of treating chat and history as separate occurrences.
    try:
        from ...services.world_memory import EVENT_TYPE_UTTERANCE

        summary = f"{display_name} said: {message}"
        submit_world_event(
            db,
            WorldEventCommand(
                session_id=session_id,
                event_type=EVENT_TYPE_UTTERANCE,
                summary=summary,
                delta=_utterance_event_delta(
                    speaker_name=display_name,
                    location=session_location,
                    message=message,
                    summary=summary,
                ),
                metadata={"surface": "chat", "channel": session_location},
                preserve_event_type=True,
            ),
        )
    except Exception:
        pass  # never fail the chat post due to the utterance event

    return {
        "success": True,
        "id": row.id,
        "ts": row.created_at.isoformat() if row.created_at else None,
    }


# ---------------------------------------------------------------------------
# City map — grounded geographic skeleton for clients and residents
# ---------------------------------------------------------------------------


def _location_map_context_payload(location: str) -> dict[str, Any]:
    from ...services.city_pack_service import build_location_map_context

    city_id = settings.city_id
    context = build_location_map_context(location, city_id)
    return {
        "location": location,
        "city_id": city_id,
        "context": context,
        "available": bool(context),
    }


# Declared before /world/map/{session_id} so literal public-map resource names
# are never captured as session IDs.
@router.get("/world/map/context")
def get_public_location_map_context(
    location: str = Query(..., description="Location name to build context for"),
):
    """Sessionless prose geography for a location — the public commons client's
    view of a place. Same payload as /world/map/{session_id}/context, whose
    session path segment was never actually used."""
    return _location_map_context_payload(location)


@router.get("/world/map/generated")
def get_public_generated_map():
    """Return the small public descriptor for a precompiled fictional map."""
    from ...services.city_pack_service import get_generated_map_artifact

    artifact = get_generated_map_artifact(settings.city_id)
    if artifact is None:
        return {"available": False, "city_id": settings.city_id, "artifact": None}
    return {
        "available": True,
        "city_id": settings.city_id,
        "artifact": {
            "schema_version": artifact.get("schema_version"),
            "artifact_sha256": artifact.get("artifact_sha256"),
            "generator": artifact.get("generator"),
            "bounds": artifact.get("bounds"),
            "grid": artifact.get("grid"),
            "svg": artifact.get("svg"),
            "section_count": len(artifact.get("sections") or []),
        },
    }


@router.get("/world/map/generated.svg", response_class=Response)
def get_public_generated_map_svg():
    """Serve a precompiled SVG; generation never runs in a participant request."""
    from ...services.city_pack_service import (
        get_generated_map_artifact,
        get_generated_map_svg,
    )

    artifact = get_generated_map_artifact(settings.city_id)
    svg = get_generated_map_svg(settings.city_id)
    if artifact is None or svg is None:
        raise HTTPException(
            status_code=404, detail="This shard has no compiled fictional map."
        )
    svg_meta = artifact.get("svg") if isinstance(artifact.get("svg"), dict) else {}
    digest = str(svg_meta.get("sha256") or "").strip()
    headers = {"Cache-Control": "public, max-age=300"}
    if digest:
        headers["ETag"] = f'"{digest}"'
    return Response(content=svg, media_type="image/svg+xml", headers=headers)


@router.get("/world/map/{session_id}")
def get_world_map(session_id: str):
    """
    Return the grounded geographic map for a session's city.

    Phase 1: returns the full city skeleton (all neighborhoods, transit,
    landmarks, corridors). Phase 2 will filter to discovered locations only.

    Used by the slow loop to give agents a geographic scaffold —
    they know which neighborhoods connect to which, where BART runs,
    what landmarks exist nearby. Human clients use the same graph for travel.
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


@router.get("/world/travel/destinations")
def get_world_travel_destinations():
    """Return local inter-city routes joined to currently registered destination nodes.

    This is discovery only. It does not depart, transfer, or arrive an actor.
    """
    from ...services.federation_discovery import get_travel_destinations

    return get_travel_destinations()


@router.get("/world/grounding")
def get_world_grounding():
    """Return the configured city's current clock and weather context."""
    from ...services.grounding import get_city_time_context

    return get_city_time_context(settings.city_id)


@router.get("/world/grounding/news")
def get_world_news():
    """
    Return recent local headlines where the city has a configured source.
    Sourced from free RSS feeds (KQED, SF Standard). Cached for 1 hour.
    No API key required.
    """
    from ...services.grounding import get_sf_news

    # The only current feed is San Francisco-specific. Other cities receive
    # silence instead of imported concerns from the wrong place.
    return {
        "headlines": (
            get_sf_news(max_items=5) if settings.city_id == "san_francisco" else []
        )
    }


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
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.asin(math.sqrt(a))

    # Find the anchor node (neighborhood or landmark) to get its lat/lon
    anchor = db.query(WorldNode).filter(WorldNode.name == location).first()
    if not anchor:
        raise HTTPException(status_code=404, detail=f"Location '{location}' not found.")

    anchor_meta = anchor.metadata_json or {}
    anchor_lat = anchor_meta.get("lat")
    anchor_lon = anchor_meta.get("lon")
    if anchor_lat is None or anchor_lon is None:
        raise HTTPException(
            status_code=422, detail=f"Location '{location}' has no coordinates."
        )

    # Fetch all landmarks and filter by distance in Python (2258 rows — fast enough)
    all_landmarks = db.query(WorldNode).filter(WorldNode.node_type == "landmark").all()
    results = []
    for lm in all_landmarks:
        meta = lm.metadata_json or {}
        lat = meta.get("lat")
        lon = meta.get("lon")
        if lat is None or lon is None:
            continue
        dist = _haversine(anchor_lat, anchor_lon, lat, lon)
        if dist <= radius_km:
            results.append(
                {
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
                }
            )

    results.sort(key=lambda x: x["distance_km"])
    return {
        "location": location,
        "radius_km": radius_km,
        "landmarks": results,
        "count": len(results),
    }


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
    from ...services.sublocations import active_sublocations

    place_names.extend(
        {"name": row.name, "node_type": row.node_type}
        for row in active_sublocations(db)
    )
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
    The session_id path segment is unused; /world/map/context is the canonical path.
    """
    _ = session_id
    return _location_map_context_payload(location)


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
        expires_at=datetime.now(timezone.utc)
        + timedelta(seconds=payload.expires_in_seconds),
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
    return {
        "ok": True,
        "poll_id": poll_id,
        "voter": payload.voter_session_id,
        "vote": vote,
    }


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
