# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Resolve exact places onto the canonical city travel graph."""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import settings
from ..models import WorldEdge, WorldNode
from .city_pack_service import find_neighborhood_record_for_location, get_pack


def parent_location_name_for_node(
    *,
    name: str,
    node_type: str,
    metadata: dict[str, Any],
    city_id: str | None,
) -> str | None:
    """Return the canonical map location containing one exact place."""

    if node_type == "location":
        return name

    explicit_parent = str(metadata.get("parent_location") or "").strip()
    if explicit_parent:
        return explicit_parent

    selected_city_id = city_id or settings.city_id
    pack = get_pack(selected_city_id)
    neighborhood_id = str(metadata.get("neighborhood") or "").strip()
    if pack and neighborhood_id:
        for neighborhood in pack.get("neighborhoods", []):
            if str(neighborhood.get("id") or "").strip() == neighborhood_id:
                resolved = str(neighborhood.get("name") or "").strip()
                if resolved:
                    return resolved

    record = find_neighborhood_record_for_location(name, selected_city_id)
    if record:
        resolved = str(record.get("name") or "").strip()
        if resolved:
            return resolved
    return None


def node_has_path_edges(db: Session, node_id: int) -> bool:
    """Return whether one node participates in the canonical travel graph."""

    if not node_id:
        return False
    edge = (
        db.query(WorldEdge.id)
        .filter(
            WorldEdge.edge_type == "path",
            or_(
                WorldEdge.source_node_id == node_id,
                WorldEdge.target_node_id == node_id,
            ),
        )
        .first()
    )
    return edge is not None


def resolve_route_anchor(db: Session, location_name: str) -> str:
    """Resolve a landmark or sublocation to its canonical graph location.

    Unknown names remain unchanged so the caller can produce its ordinary
    no-route result. A canonical location with real path edges wins over any
    same-named landmark record.
    """

    candidate = str(location_name or "").strip()
    if not candidate:
        return candidate

    nodes = (
        db.query(WorldNode)
        .filter(WorldNode.name == candidate)
        .order_by(WorldNode.id.asc())
        .all()
    )
    if not nodes:
        return candidate

    for node in nodes:
        if str(node.node_type or "").strip() != "location":
            continue
        if node_has_path_edges(db, int(node.id or 0)):
            return candidate

    for node in nodes:
        node_type = str(node.node_type or "").strip()
        metadata = dict(node.metadata_json or {})
        parent = parent_location_name_for_node(
            name=candidate,
            node_type=node_type or "landmark",
            metadata=metadata,
            city_id=str(metadata.get("city_id") or settings.city_id or ""),
        )
        if parent and parent != candidate:
            return parent
    return candidate
