# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Parent-scoped places beneath the canonical city graph.

Sublocations reuse ``WorldNode`` storage but never receive ``path`` edges and
therefore never enter ``get_location_graph``. Their parent is canonical map
truth; their own lifetime is explicit metadata. This module owns the bounded
creation and expiry rules so movement, scenes, and future steward tools share
one contract.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..models import WorldNode

NODE_TYPE_SUBLOCATION = "sublocation"
DEFAULT_TTL_SECONDS = max(
    900,
    min(
        7 * 86400,
        int(os.environ.get("WW_SUBLOCATION_TTL_SECONDS", str(6 * 3600))),
    ),
)
_LOCAL_CUES = {
    "alley",
    "apartment",
    "back room",
    "balcony",
    "bench",
    "booth",
    "corner",
    "counter",
    "courtyard",
    "doorway",
    "duplex",
    "flat",
    "garden",
    "home",
    "kitchen",
    "landing",
    "loft",
    "porch",
    "room",
    "shop",
    "stall",
    "stoop",
    "studio",
    "table",
    "upstairs",
    "workshop",
    "yard",
}
_LOCAL_RELATIONS = {"behind", "beside", "inside", "near", "under", "within"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def is_local_sublocation_candidate(label: str, parent_location: str) -> bool:
    """Conservatively recognize a within-place destination.

    This is intentionally narrower than generic place-name recognition. Unknown
    destinations such as another city must continue to fail rather than being
    silently installed beneath the resident's current neighborhood.
    """
    clean = re.sub(r"\s+", " ", str(label or "").strip()).strip(" .")
    parent = re.sub(r"\s+", " ", str(parent_location or "").strip())
    if not clean or not parent or len(clean) < 3 or len(clean) > 120:
        return False
    lowered = clean.lower()
    if lowered == parent.lower() or "://" in lowered:
        return False
    if parent.lower() in lowered:
        return True
    words = set(re.findall(r"[a-z]+", lowered))
    return bool(words & _LOCAL_RELATIONS) or any(cue in lowered for cue in _LOCAL_CUES)


def _is_active(node: WorldNode, *, now: datetime) -> bool:
    metadata = dict(node.metadata_json or {})
    if str(metadata.get("persistence") or "ephemeral") == "durable":
        return True
    expires_at = _parse_dt(metadata.get("expires_at"))
    return expires_at is not None and expires_at > now


def active_sublocations(
    db: Session,
    *,
    parent_location: str | None = None,
    now: datetime | None = None,
) -> list[WorldNode]:
    current = now or _utc_now()
    rows = (
        db.query(WorldNode)
        .filter(WorldNode.node_type == NODE_TYPE_SUBLOCATION)
        .order_by(WorldNode.id.asc())
        .all()
    )
    active: list[WorldNode] = []
    for row in rows:
        metadata = dict(row.metadata_json or {})
        if parent_location and str(metadata.get("parent_location") or "") != str(
            parent_location
        ):
            continue
        if _is_active(row, now=current):
            active.append(row)
    return active


def resolve_active_sublocation(
    db: Session,
    *,
    label: str,
    parent_location: str,
    now: datetime | None = None,
) -> WorldNode | None:
    target = re.sub(r"\s+", " ", str(label or "").strip()).lower()
    if not target:
        return None
    for row in active_sublocations(
        db,
        parent_location=parent_location,
        now=now,
    ):
        metadata = dict(row.metadata_json or {})
        labels = {
            str(row.name or "").strip().lower(),
            str(metadata.get("label") or "").strip().lower(),
        }
        if target in labels:
            return row
    return None


def create_or_refresh_ephemeral(
    db: Session,
    *,
    parent_location: str,
    label: str,
    created_by_session: str,
    ttl_seconds: int | None = None,
    now: datetime | None = None,
) -> WorldNode:
    clean_label = re.sub(r"\s+", " ", str(label or "").strip()).strip(" .")
    clean_parent = re.sub(r"\s+", " ", str(parent_location or "").strip())
    if not is_local_sublocation_candidate(clean_label, clean_parent):
        raise ValueError("destination is not a bounded within-place sublocation")

    current = now or _utc_now()
    ttl = max(900, min(7 * 86400, int(ttl_seconds or DEFAULT_TTL_SECONDS)))
    normalized_name = f"{_slug(clean_parent)}::{_slug(clean_label)}"
    row = (
        db.query(WorldNode)
        .filter(
            WorldNode.node_type == NODE_TYPE_SUBLOCATION,
            WorldNode.normalized_name == normalized_name,
        )
        .one_or_none()
    )
    if row is None:
        duplicate_name = (
            db.query(WorldNode.id)
            .filter(
                WorldNode.node_type == NODE_TYPE_SUBLOCATION,
                WorldNode.name == clean_label,
            )
            .first()
            is not None
        )
        display_name = (
            f"{clean_label} ({clean_parent})" if duplicate_name else clean_label
        )
        row = WorldNode(
            node_type=NODE_TYPE_SUBLOCATION,
            name=display_name,
            normalized_name=normalized_name,
            metadata_json={},
        )
        db.add(row)

    metadata = dict(row.metadata_json or {})
    metadata.update(
        {
            "label": clean_label,
            "parent_location": clean_parent,
            "persistence": "ephemeral",
            "created_by_session": str(
                metadata.get("created_by_session") or created_by_session or ""
            ),
            "created_at": str(metadata.get("created_at") or current.isoformat()),
            "last_active_at": current.isoformat(),
            "ttl_seconds": ttl,
            "expires_at": (current + timedelta(seconds=ttl)).isoformat(),
        }
    )
    row.metadata_json = metadata
    db.flush()
    return row


def touch_sublocation(
    node: WorldNode,
    *,
    now: datetime | None = None,
) -> None:
    current = now or _utc_now()
    metadata = dict(node.metadata_json or {})
    metadata["last_active_at"] = current.isoformat()
    if str(metadata.get("persistence") or "ephemeral") == "ephemeral":
        ttl = max(900, int(metadata.get("ttl_seconds") or DEFAULT_TTL_SECONDS))
        metadata["expires_at"] = (current + timedelta(seconds=ttl)).isoformat()
    node.metadata_json = metadata


def sublocation_payload(node: WorldNode) -> dict[str, Any]:
    metadata = dict(node.metadata_json or {})
    return {
        "sublocation_id": f"sublocation:{node.id}",
        "name": str(node.name or ""),
        "label": str(metadata.get("label") or node.name or ""),
        "parent_location": str(metadata.get("parent_location") or ""),
        "persistence": str(metadata.get("persistence") or "ephemeral"),
        "created_by_session": str(metadata.get("created_by_session") or ""),
        "created_at": metadata.get("created_at"),
        "last_active_at": metadata.get("last_active_at"),
        "ttl_seconds": metadata.get("ttl_seconds"),
        "expires_at": metadata.get("expires_at"),
    }


def graph_with_sublocations(
    graph: dict[str, Any],
    *,
    parent_location: str,
    rows: list[WorldNode],
) -> dict[str, Any]:
    nodes = [dict(node) for node in list(graph.get("nodes") or [])]
    edges = [dict(edge) for edge in list(graph.get("edges") or [])]
    parent_node = next(
        (
            node
            for node in nodes
            if str(node.get("name") or "").strip() == parent_location
        ),
        None,
    )
    if parent_node is None:
        return {"nodes": nodes, "edges": edges}
    parent_key = str(parent_node.get("key") or "").strip()
    edge_pairs = {
        (str(edge.get("from") or ""), str(edge.get("to") or "")) for edge in edges
    }
    for row in rows:
        key = f"sublocation:{row.id}"
        payload = sublocation_payload(row)
        if not any(str(node.get("key") or "") == key for node in nodes):
            nodes.append(
                {
                    "key": key,
                    "name": str(row.name or ""),
                    "node_type": NODE_TYPE_SUBLOCATION,
                    "parent_location": parent_location,
                    "persistence": payload["persistence"],
                    "expires_at": payload["expires_at"],
                }
            )
        for source, target in ((parent_key, key), (key, parent_key)):
            if source and target and (source, target) not in edge_pairs:
                edges.append({"from": source, "to": target})
                edge_pairs.add((source, target))
    return {"nodes": nodes, "edges": edges}
