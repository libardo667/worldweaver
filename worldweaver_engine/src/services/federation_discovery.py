# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Join local inter-city routes to the live federation node registry."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Optional

from ..config import settings
from .city_pack_service import get_pack
from .federation_identity import current_shard_id

log = logging.getLogger(__name__)
_AVAILABLE_NODE_STATES = {"healthy", "degraded"}


def _fetch_registry_shards() -> Optional[list[dict[str, Any]]]:
    federation_url = str(settings.federation_url or "").strip().rstrip("/")
    if not federation_url:
        return None

    request = urllib.request.Request(
        f"{federation_url}/api/federation/shards",
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError) as exc:
        log.info("Federation registry unavailable during route discovery: %s", exc)
        return None

    raw_shards = payload.get("shards") if isinstance(payload, dict) else None
    if not isinstance(raw_shards, list):
        return None
    return [item for item in raw_shards if isinstance(item, dict)]


def resolve_inter_city_routes(
    *,
    city_id: str,
    routes: list[dict[str, Any]],
    registry_shards: Optional[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Attach live node choices to locally defined geographic routes."""
    registry_reachable = registry_shards is not None
    shards = registry_shards or []
    resolved: list[dict[str, Any]] = []

    for route in routes:
        from_city_id = str(route.get("from_city") or route.get("from") or "").strip()
        to_city_id = str(route.get("to_city") or route.get("to") or "").strip()
        if not to_city_id or (from_city_id and from_city_id != city_id):
            continue

        nodes = [
            {
                "shard_id": str(shard.get("shard_id") or "").strip(),
                "shard_url": str(shard.get("shard_url") or "").strip(),
                "client_url": str(shard.get("client_url") or "").strip(),
                "status": str(shard.get("status") or "offline").strip(),
            }
            for shard in shards
            if str(shard.get("city_id") or "").strip() == to_city_id and str(shard.get("shard_type") or "city").strip() == "city" and str(shard.get("shard_id") or "").strip() != current_shard_id()
        ]
        nodes.sort(key=lambda node: (str(node["status"]) not in _AVAILABLE_NODE_STATES, str(node["shard_id"])))

        if not registry_reachable:
            availability = "unknown"
        elif not nodes:
            availability = "unhosted"
        elif any(str(node["status"]) in _AVAILABLE_NODE_STATES for node in nodes):
            availability = "available"
        else:
            availability = "offline"

        resolved.append(
            {
                "route_id": str(route.get("id") or "").strip(),
                "from_city_id": from_city_id or city_id,
                "to_city_id": to_city_id,
                "mode": str(route.get("mode") or "").strip(),
                "operator": str(route.get("operator") or "").strip(),
                "duration_hours": route.get("duration_hours"),
                "departure_hub_id": str(route.get("departure_hub_id") or "").strip(),
                "departure_hub": str(route.get("departure_hub") or "").strip(),
                "arrival_hub_id": str(route.get("arrival_hub_id") or "").strip(),
                "arrival_hub": str(route.get("arrival_hub") or "").strip(),
                "notes": str(route.get("notes") or "").strip(),
                "availability": availability,
                "nodes": nodes,
            }
        )

    return resolved


def get_travel_destinations() -> dict[str, Any]:
    """Return local routes enriched with current federation availability."""
    city_id = str(settings.city_id or "").strip()
    pack = get_pack(city_id) or {}
    raw_routes = pack.get("inter_city")
    routes = [item for item in raw_routes if isinstance(item, dict)] if isinstance(raw_routes, list) else []
    registry_shards = _fetch_registry_shards()
    return {
        "source": {
            "shard_id": current_shard_id(),
            "city_id": city_id,
        },
        "registry": {
            "configured": bool(str(settings.federation_url or "").strip()),
            "reachable": registry_shards is not None,
        },
        "destinations": resolve_inter_city_routes(
            city_id=city_id,
            routes=routes,
            registry_shards=registry_shards,
        ),
    }
