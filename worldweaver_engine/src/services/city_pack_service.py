"""
City pack service — loads and serves WorldWeaver city pack data.

City packs are pre-built from OpenStreetMap (see scripts/build_city_pack.py).
They provide grounded geographic bones for the narrator and agents:
  - Neighborhoods with adjacency graph
  - Transit stations (BART, Muni Metro)
  - Landmarks, parks, waterfronts
  - Street corridors with vibes
  - Inter-city connections

The service loads packs at startup and caches them in memory.
It exposes query helpers used by the /api/world/map endpoint.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Root data directory, relative to worldweaver package root
_CITIES_DIR = Path(__file__).parent.parent.parent / "data" / "cities"

# In-memory pack cache: city_id → pack dict
_PACK_CACHE: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _load_pack(city_id: str) -> dict | None:
    """Load a city pack from disk. Returns None if not found."""
    pack_dir = _CITIES_DIR / city_id
    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.exists():
        return None

    pack: dict[str, Any] = {}
    for filename in [
        "manifest.json",
        "neighborhoods.json",
        "transit_graph.json",
        "landmarks.json",
        "street_corridors.json",
        "inter_city.json",
        "weather_config.json",
        "transit_config.json",
    ]:
        path = pack_dir / filename
        if path.exists():
            key = filename.replace(".json", "")
            try:
                pack[key] = json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("city_pack: failed to load %s: %s", path, e)

    return pack if pack else None


def get_pack(city_id: str = "san_francisco") -> dict | None:
    """Return cached city pack for city_id. Loads from disk on first call."""
    if city_id not in _PACK_CACHE:
        pack = _load_pack(city_id)
        if pack:
            _PACK_CACHE[city_id] = pack
            counts = pack.get("manifest", {}).get("counts", {})
            logger.info("city_pack: loaded '%s' — %s", city_id, counts)
        else:
            logger.info("city_pack: no pack found for '%s' at %s", city_id, _CITIES_DIR / city_id)
            return None
    return _PACK_CACHE.get(city_id)


def list_available() -> list[str]:
    """Return city IDs with a pack on disk."""
    if not _CITIES_DIR.exists():
        return []
    return [d.name for d in _CITIES_DIR.iterdir() if d.is_dir() and (d / "manifest.json").exists()]


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Querying
# ---------------------------------------------------------------------------


def find_neighborhood_by_name(name: str, city_id: str = "san_francisco") -> dict | None:
    """Fuzzy find a neighborhood by name (case-insensitive, partial match)."""
    pack = get_pack(city_id)
    if not pack:
        return None
    name_lower = name.lower()
    neighborhoods = pack.get("neighborhoods", [])
    # Exact match first
    for n in neighborhoods:
        if n["name"].lower() == name_lower or n["id"] == name_lower.replace(" ", "-"):
            return n
    # Partial match
    for n in neighborhoods:
        if name_lower in n["name"].lower() or n["name"].lower() in name_lower:
            return n
    return None


def find_nearest_neighborhood(lat: float, lon: float, city_id: str = "san_francisco") -> dict | None:
    """Return the neighborhood whose centroid is nearest to lat/lon."""
    pack = get_pack(city_id)
    if not pack:
        return None
    best, best_dist = None, float("inf")
    for n in pack.get("neighborhoods", []):
        d = _haversine_km(lat, lon, n["lat"], n["lon"])
        if d < best_dist:
            best_dist = d
            best = n
    return best


def get_nearby_transit(lat: float, lon: float, radius_km: float = 1.5, city_id: str = "san_francisco") -> list[dict]:
    """Return transit stations within radius_km of a point."""
    pack = get_pack(city_id)
    if not pack:
        return []
    transit = pack.get("transit_graph", {})
    results = []
    for system_key in ("bart", "muni_metro"):
        system = transit.get(system_key, {})
        for station in system.get("stations", []):
            if station.get("lat") and station.get("lon"):
                d = _haversine_km(lat, lon, station["lat"], station["lon"])
                if d <= radius_km:
                    results.append({**station, "_system": system_key, "_distance_km": round(d, 2)})
    results.sort(key=lambda s: s["_distance_km"])
    return results


def get_nearby_landmarks(lat: float, lon: float, radius_km: float = 1.0, city_id: str = "san_francisco", limit: int = 8) -> list[dict]:
    """Return landmarks within radius_km of a point."""
    pack = get_pack(city_id)
    if not pack:
        return []
    results = []
    for lm in pack.get("landmarks", []):
        if lm.get("lat") and lm.get("lon"):
            d = _haversine_km(lat, lon, lm["lat"], lm["lon"])
            if d <= radius_km:
                results.append({**lm, "_distance_km": round(d, 2)})
    results.sort(key=lambda x: x["_distance_km"])
    return results[:limit]


def get_corridors_in_neighborhood(neighborhood_id: str, city_id: str = "san_francisco") -> list[dict]:
    """Return street corridors that run through a neighborhood."""
    pack = get_pack(city_id)
    if not pack:
        return []
    return [c for c in pack.get("street_corridors", []) if neighborhood_id in c.get("neighborhoods", [])]


def get_adjacent_neighborhoods(neighborhood_id: str, city_id: str = "san_francisco") -> list[dict]:
    """Return the adjacent neighborhood records for a given neighborhood ID."""
    pack = get_pack(city_id)
    if not pack:
        return []
    neighborhoods_by_id = {n["id"]: n for n in pack.get("neighborhoods", [])}
    source = neighborhoods_by_id.get(neighborhood_id)
    if not source:
        return []
    return [neighborhoods_by_id[adj_id] for adj_id in source.get("adjacent_to", []) if adj_id in neighborhoods_by_id]


# ---------------------------------------------------------------------------
# Map summary — compressed geographic context for LLM prompts
# ---------------------------------------------------------------------------


def build_location_map_context(
    location_name: str,
    city_id: str = "san_francisco",
) -> str:
    """
    Build a compact prose geography context for a named location.
    Used by the slow loop to ground the agent's sense of where they are.

    Returns empty string if no pack is available.
    """
    pack = get_pack(city_id)
    if not pack:
        return ""

    # Find the neighborhood this location maps to
    neighborhood = find_neighborhood_by_name(location_name, city_id)
    if not neighborhood:
        # Try finding by matching the location to a known landmark or transit stop
        neighborhood = _infer_neighborhood_from_location(location_name, pack)
    if not neighborhood:
        return ""

    parts: list[str] = []

    # Neighborhood identity
    vibe = neighborhood.get("vibe", "")
    if vibe:
        parts.append(f"{neighborhood['name']}: {vibe[:200]}")
    else:
        parts.append(f"{neighborhood['name']}")

    # Adjacent neighborhoods
    adj = get_adjacent_neighborhoods(neighborhood["id"], city_id)
    if adj:
        adj_names = ", ".join(n["name"] for n in adj[:6])
        parts.append(f"Adjacent to: {adj_names}")

    # Nearby transit
    if neighborhood.get("lat") and neighborhood.get("lon"):
        transit = get_nearby_transit(neighborhood["lat"], neighborhood["lon"], radius_km=1.2, city_id=city_id)
        if transit:
            transit_lines = []
            for t in transit[:4]:
                lines = t.get("lines", [])
                line_str = f" ({'/'.join(str(ln) for ln in lines)})" if lines else ""
                transit_lines.append(f"{t['name']}{line_str}")
            parts.append("Nearby transit: " + ", ".join(transit_lines))

        # Nearby landmarks
        landmarks = get_nearby_landmarks(neighborhood["lat"], neighborhood["lon"], radius_km=0.8, city_id=city_id, limit=4)
        if landmarks:
            lm_names = ", ".join(lm["name"] for lm in landmarks)
            parts.append(f"Nearby: {lm_names}")

    # Corridors through this neighborhood
    corridors = get_corridors_in_neighborhood(neighborhood["id"], city_id)
    if corridors:
        corridor_bits = []
        for c in corridors[:3]:
            bit = c["name"]
            if c.get("vibe"):
                bit += f" ({c['vibe'][:80]})"
            corridor_bits.append(bit)
        parts.append("Key streets: " + " | ".join(corridor_bits))

    return "\n".join(parts)


def _infer_neighborhood_from_location(location: str, pack: dict) -> dict | None:
    """
    Try to match a location string to a transit station or landmark,
    then return the neighborhood record for that location.
    """
    loc_lower = location.lower()
    neighborhoods_by_id = {n["id"]: n for n in pack.get("neighborhoods", [])}

    # Check transit stations
    transit = pack.get("transit_graph", {})
    for system_key in ("bart", "muni_metro"):
        for station in transit.get(system_key, {}).get("stations", []):
            if loc_lower in station["name"].lower() or station["name"].lower() in loc_lower:
                n_id = station.get("neighborhood")
                if n_id and n_id in neighborhoods_by_id:
                    return neighborhoods_by_id[n_id]

    # Check landmarks
    for lm in pack.get("landmarks", []):
        if loc_lower in lm["name"].lower() or lm["name"].lower() in loc_lower:
            n_id = lm.get("neighborhood")
            if n_id and n_id in neighborhoods_by_id:
                return neighborhoods_by_id[n_id]

    # Check street corridors
    for corridor in pack.get("street_corridors", []):
        corridor_name = str(corridor.get("name") or "").strip().lower()
        if not corridor_name:
            continue
        if loc_lower in corridor_name or corridor_name in loc_lower:
            for neighborhood_id in corridor.get("neighborhoods", []):
                resolved = neighborhoods_by_id.get(str(neighborhood_id or "").strip())
                if resolved:
                    return resolved

    return None


def find_neighborhood_record_for_location(location: str, city_id: str = "san_francisco") -> dict | None:
    """Resolve a location string to its neighborhood record when possible.

    Matches exact neighborhood names first, then falls back to landmark/transit
    inference for named places inside the city pack.
    """
    pack = get_pack(city_id)
    if not pack:
        return None

    normalized = str(location or "").strip().lower()
    if not normalized:
        return None

    for neighborhood in pack.get("neighborhoods", []):
        if str(neighborhood.get("name", "")).strip().lower() == normalized:
            return neighborhood

    return _infer_neighborhood_from_location(str(location), pack)


def get_full_map_for_session(city_id: str = "san_francisco") -> dict:
    """
    Return the full city skeleton for Phase 1 (no per-session filtering yet).
    Phase 2 will filter to discovered locations only.
    """
    pack = get_pack(city_id)
    if not pack:
        return {"available": False, "city_id": city_id}

    manifest = pack.get("manifest", {})
    return {
        "available": True,
        "city_id": city_id,
        "city": manifest.get("city", city_id),
        "neighborhoods": pack.get("neighborhoods", []),
        "transit": pack.get("transit_graph", {}),
        "landmarks": pack.get("landmarks", []),
        "corridors": pack.get("street_corridors", []),
        "inter_city": pack.get("inter_city", []),
        "counts": manifest.get("counts", {}),
    }
