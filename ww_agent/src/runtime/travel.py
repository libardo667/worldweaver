# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Pure parsing for travel between a resident's current world and its hearth."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

_VERB = r"(?:travel|journey|go|head|walk|set\s*out|depart|move|leave|return)"
_HEARTH_RX = re.compile(
    r"\b(?:go|head|return|back|come|travel|journey|set\s*out)\b[^.!?]*\b(?:home|hearth)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TravelRequest:
    """One requested change of world attachment."""

    destination_kind: str  # hearth | city
    destination_name: str = ""
    route_id: str = ""
    destination_shard: str = ""


@dataclass(frozen=True)
class PendingShardTravel:
    """Ledger-derived information needed to finish one interrupted city trip."""

    travel_id: str
    transition_id: str
    route_id: str
    source_url: str
    source_session_id: str
    destination_shard: str
    destination_url: str
    destination_session_id: str
    source_departed: bool = False


def parse_world_travel(
    text: str,
    *,
    city_names: set[str] | None = None,
    allow_hearth: bool,
) -> TravelRequest | None:
    """Recognize inter-world travel without swallowing ordinary map movement."""
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return None
    lowered = normalized.lower()

    # Structured move acts carry an exact target rather than a sentence. The
    # resident prompt may therefore choose `home` directly; treat that as the
    # hearth boundary before a city backend can mistake it for a sublocation.
    exact_hearth_targets = {"home", "hearth", "your home", "your hearth", "the hearth"}
    if allow_hearth and (lowered in exact_hearth_targets or _HEARTH_RX.search(lowered)):
        return TravelRequest("hearth")

    names = {
        str(name).strip().lower() for name in (city_names or set()) if str(name).strip()
    }
    for name in sorted(names, key=len, reverse=True):
        if lowered in {name, f"the city of {name}"}:
            return TravelRequest("city", name)
        if re.search(rf"\b{_VERB}\b.*\b{re.escape(name)}\b", lowered):
            return TravelRequest("city", name)
    return None


def parse_city_travel(text: str, destinations: list[dict[str, Any]]) -> TravelRequest | None:
    """Resolve an explicit live node name without guessing between city hosts."""
    normalized = " ".join(str(text or "").split()).lower()
    if not normalized or not re.search(rf"\b{_VERB}\b", normalized):
        return None

    matches: list[TravelRequest] = []
    for route in destinations:
        if not isinstance(route, dict):
            continue
        route_id = str(route.get("route_id") or "").strip()
        for node in list(route.get("nodes") or []):
            if not isinstance(node, dict):
                continue
            shard_id = str(node.get("shard_id") or "").strip()
            shard_url = str(node.get("shard_url") or "").strip()
            status = str(node.get("status") or "").strip()
            if not route_id or not shard_id or not shard_url or status not in {"healthy", "degraded"}:
                continue
            shard_pattern = rf"(?<![a-z0-9_-]){re.escape(shard_id.lower())}(?![a-z0-9_-])"
            if re.search(shard_pattern, normalized):
                matches.append(TravelRequest("city", shard_id, route_id, shard_id))
    unique = {(match.route_id, match.destination_shard): match for match in matches}
    return next(iter(unique.values())) if len(unique) == 1 else None


def looks_like_city_travel(text: str) -> bool:
    """Cheap guard so ordinary actions do not poll federation discovery."""
    normalized = " ".join(str(text or "").split()).lower()
    if not normalized:
        return False
    return bool(re.search(r"\b(?:travel|journey|depart|set\s*out)\b", normalized))


def derive_pending_shard_travel(events: list[dict[str, Any]]) -> PendingShardTravel | None:
    """Recover the newest city trip that has not reached a destination attachment."""
    pending: dict[str, PendingShardTravel] = {}
    order: list[str] = []
    for event in events:
        event_type = str(event.get("event_type") or "").strip()
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        travel_id = str(payload.get("travel_id") or "").strip()
        if not travel_id:
            continue
        if event_type == "inter_shard_travel_started":
            pending[travel_id] = PendingShardTravel(
                travel_id=travel_id,
                transition_id=str(payload.get("transition_id") or "").strip(),
                route_id=str(payload.get("route_id") or "").strip(),
                source_url=str(payload.get("source_url") or "").strip(),
                source_session_id=str(payload.get("source_session_id") or "").strip(),
                destination_shard=str(payload.get("destination_shard") or "").strip(),
                destination_url=str(payload.get("destination_url") or "").strip(),
                destination_session_id=str(payload.get("destination_session_id") or "").strip(),
            )
            order.append(travel_id)
        elif event_type == "inter_shard_source_departed" and travel_id in pending:
            current = pending[travel_id]
            pending[travel_id] = replace(
                current,
                source_departed=True,
                destination_url=str(payload.get("destination_url") or current.destination_url).strip(),
            )
        elif event_type in {"inter_shard_travel_arrived", "inter_shard_travel_aborted"}:
            pending.pop(travel_id, None)
    return next((pending[travel_id] for travel_id in reversed(order) if travel_id in pending), None)
