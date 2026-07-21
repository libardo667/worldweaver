# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Current, factual scene assembly shared by HTTP and resident-gym adapters."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import SessionVars, WorldTrace
from .location_routes import resolve_route_anchor
from .sublocations import active_sublocations, graph_with_sublocations
from .world_memory import get_location_graph

ACTIVE_HUMAN_SESSION_WINDOW = timedelta(hours=2)
RECENT_SESSION_SCAN_WINDOW = timedelta(hours=8)
WORLD_TRACE_SCENE_LIMIT = 12
INTERNAL_SESSION_PREFIXES = ("world-", "_", "player-", "agent-")
AGENT_SLUG_RE = re.compile(r"^([a-z][a-z0-9_]*)[-_]\d{8}")


def session_variables_payload(raw_payload: Any) -> dict[str, Any]:
    if not isinstance(raw_payload, dict):
        return {}
    nested_vars = raw_payload.get("variables")
    if raw_payload.get("_v") == 2 and isinstance(nested_vars, dict):
        return cast(dict[str, Any], nested_vars)
    return cast(dict[str, Any], raw_payload)


def session_location_from_vars(vars_payload: dict[str, Any]) -> str:
    return str(vars_payload.get("location") or "").strip()


def slug_display_name(session_id: str) -> str | None:
    match = AGENT_SLUG_RE.match(session_id)
    if not match:
        return None
    return " ".join(word.capitalize() for word in match.group(1).split("_"))


def is_player_session(session_id: str) -> bool:
    if not session_id:
        return False
    return not any(
        session_id.startswith(prefix) for prefix in INTERNAL_SESSION_PREFIXES
    )


def parse_session_updated_at(value: Any) -> datetime | None:
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


def session_display_details(
    session_id: str, vars_payload: dict[str, Any]
) -> tuple[str | None, str]:
    player_name: str | None = None
    player_role = str(vars_payload.get("player_role") or "").strip()
    if player_role:
        name_part = (
            player_role.split(" — ")[0].strip() if " — " in player_role else player_role
        )
        player_name = name_part or None
    agent_name = slug_display_name(session_id)
    if agent_name:
        return player_name, agent_name
    if player_name:
        return player_name, player_name
    return None, session_id[:12]


def session_entity_type(session_id: str) -> str:
    return "agent" if slug_display_name(session_id) else "human"


def session_role_label(vars_payload: dict[str, Any], fallback: str) -> str:
    raw_role = str(vars_payload.get("player_role") or "").strip()
    if raw_role:
        return (
            raw_role.split(" — ")[0].strip() if " — " in raw_role else raw_role.strip()
        )
    return fallback


def load_recent_session_rows(
    db: Session,
    *,
    requested_session_id: str | None = None,
    window: timedelta = RECENT_SESSION_SCAN_WINDOW,
    now: datetime | None = None,
) -> list[SessionVars]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = (current - window).replace(tzinfo=None)
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


def load_active_human_session_ids(
    db: Session,
    requested_session_id: str | None = None,
    *,
    now: datetime | None = None,
) -> set[str]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = current - ACTIVE_HUMAN_SESSION_WINDOW
    recent_rows = load_recent_session_rows(
        db,
        requested_session_id=requested_session_id,
        window=ACTIVE_HUMAN_SESSION_WINDOW,
        now=current,
    )
    active: set[str] = set()
    for row in recent_rows:
        session_id = str(row.session_id or "")
        if not session_id or not is_player_session(session_id):
            continue
        if slug_display_name(session_id):
            continue
        if requested_session_id and session_id == requested_session_id:
            active.add(session_id)
            continue
        updated_at = parse_session_updated_at(row.updated_at)
        if updated_at is not None and updated_at >= cutoff:
            active.add(session_id)
    return active


def world_trace_payload(row: WorldTrace) -> dict[str, Any]:
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


def active_world_traces(
    db: Session,
    *,
    location: str,
    viewer_session_id: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    if not location:
        return []
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    naive_now = current.replace(tzinfo=None)
    rows = (
        db.query(WorldTrace)
        .filter(
            WorldTrace.location == location,
            WorldTrace.expires_at > naive_now,
            WorldTrace.session_id != viewer_session_id,
        )
        .order_by(WorldTrace.created_at.desc(), WorldTrace.id.desc())
        .limit(WORLD_TRACE_SCENE_LIMIT)
        .all()
    )
    return [world_trace_payload(row) for row in reversed(rows)]


def _graph_alias_key(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(name or "").strip().lower()).strip("_")
    return f"location_alias:{slug or 'current_location'}"


def graph_with_anchor_alias(
    graph: dict[str, Any],
    *,
    location_name: str,
    anchor_name: str,
) -> dict[str, Any]:
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
    nodes.append({**anchor_node, "key": alias_key, "name": location})
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


def build_participant_scene(
    db: Session,
    *,
    session_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build current local facts without authorization or inferred narration."""

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    row = db.get(SessionVars, session_id)
    vars_payload = session_variables_payload(row.vars) if row is not None else {}
    location = session_location_from_vars(vars_payload)
    player_role = str(vars_payload.get("player_role") or "").strip()
    active_humans = load_active_human_session_ids(
        db, requested_session_id=session_id, now=current
    )
    session_rows = load_recent_session_rows(
        db, requested_session_id=session_id, now=current
    )
    graph_anchor = resolve_route_anchor(db, location) if location else ""
    present_by_session: dict[str, dict[str, Any]] = {}
    for session_row in session_rows:
        other_session_id = str(session_row.session_id or "").strip()
        if (
            not other_session_id
            or other_session_id == session_id
            or not is_player_session(other_session_id)
        ):
            continue
        if (
            not slug_display_name(other_session_id)
            and other_session_id not in active_humans
        ):
            continue
        other_vars = session_variables_payload(session_row.vars)
        if session_location_from_vars(other_vars) != location:
            continue
        _, display_name = session_display_details(other_session_id, other_vars)
        role = session_role_label(other_vars, display_name)
        present_by_session[other_session_id] = {
            "actor_id": str(
                session_row.actor_id or other_vars.get("actor_id") or ""
            ).strip(),
            "session_id": other_session_id,
            "name": display_name,
            "role": role or display_name,
            "last_action": "",
            "last_seen": (
                session_row.updated_at.isoformat() if session_row.updated_at else None
            ),
        }
    graph = get_location_graph(db)
    graph = graph_with_sublocations(
        graph,
        parent_location=graph_anchor,
        rows=active_sublocations(db, parent_location=graph_anchor, now=current),
    )
    scene_graph = graph_with_anchor_alias(
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
    return {
        "session_id": session_id,
        "location": location,
        "role": player_role,
        "present": list(present_by_session.values()),
        "ambient_presence": [],
        "traces_here": active_world_traces(
            db,
            location=location,
            viewer_session_id=session_id,
            now=current,
        ),
        "recent_events_here": [],
        "location_graph": scene_graph,
    }
