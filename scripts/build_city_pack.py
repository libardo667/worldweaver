#!/usr/bin/env python3
"""
Build a WorldWeaver city pack from OpenStreetMap via the Overpass API.

Usage:
    python scripts/build_city_pack.py --city san_francisco --output data/cities/san_francisco/
    python scripts/build_city_pack.py --city portland --offline  # skip Overpass, use curated data only

What it produces:
    manifest.json          city metadata, bounds, license
    neighborhoods.json     districts with adjacency graph and vibes
    transit_graph.json     stations, lines, stop sequences, connections
    landmarks.json         parks, waterfronts, viewpoints, cultural sites
    street_corridors.json  named corridors with neighborhood mapping and vibe
    inter_city.json        connections to other cities by mode/operator
    weather_config.json    NWS zone + Open-Meteo coordinates for grounding daemon
    transit_config.json    GTFS-rt feed URLs for grounding daemon

The Overpass pull enriches the curated baseline — if OSM data is unavailable,
the curated dataset alone is still a rich, usable pack.

Requirements:
    pip install httpx  (already in worldweaver requirements)

OSM data is ODbL (openstreetmap.org/copyright). See manifest.json.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def _slugify(name: str) -> str:
    """Simple slug: lowercase, spaces → hyphens, drop punctuation."""
    import re

    s = name.lower().strip()
    s = re.sub(r"['\"/]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


# ---------------------------------------------------------------------------
# Overpass API client
# ---------------------------------------------------------------------------

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _overpass_query(query: str, timeout: int = 60) -> dict:
    import httpx

    resp = httpx.post(
        OVERPASS_URL,
        data={"data": query},
        timeout=timeout,
        headers={"User-Agent": "WorldWeaver-CityPackBuilder/1.0 (worldweaver project)"},
    )
    resp.raise_for_status()
    return resp.json()


def _pull_neighborhoods(bbox: str) -> list[dict]:
    """Query OSM for neighbourhood nodes and ways."""
    query = f"""
[out:json][timeout:60];
(
  node["place"="neighbourhood"]({bbox});
  node["place"="quarter"]({bbox});
  way["place"="neighbourhood"]({bbox});
);
out center;
"""
    try:
        data = _overpass_query(query)
        results = []
        for el in data.get("elements", []):
            name = el.get("tags", {}).get("name") or el.get("tags", {}).get("alt_name")
            if not name:
                continue
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            if lat and lon:
                results.append({"name": name, "lat": float(lat), "lon": float(lon)})
        return results
    except Exception as exc:
        print(f"  [warn] Overpass neighbourhood query failed: {exc}", file=sys.stderr)
        return []


def _pull_transit_system(query_template: str, bbox: str) -> list[dict]:
    """Query OSM for transit stations based on a generic template."""
    query = query_template.format(bbox=bbox)
    try:
        data = _overpass_query(query)
        results = []
        for el in data.get("elements", []):
            name = el.get("tags", {}).get("name")
            if not name:
                continue
            results.append(
                {
                    "name": name,
                    "lat": float(el["lat"]),
                    "lon": float(el["lon"]),
                    "osm_id": el.get("id"),
                    "lines": el.get("tags", {}).get("ref", ""),
                }
            )
        return results
    except Exception as exc:
        print(f"  [warn] Overpass transit query failed: {exc}", file=sys.stderr)
        return []


def _pull_landmarks(bbox: str) -> list[dict]:
    """Query OSM for parks, viewpoints, cultural sites."""
    query = f"""
[out:json][timeout:90];
(
  way["leisure"="park"]["name"]({bbox});
  node["tourism"~"attraction|viewpoint|museum|gallery|artwork"]["name"]({bbox});
  node["amenity"~"theatre|arts_centre|library"]["name"]({bbox});
  node["natural"="beach"]["name"]({bbox});
  node["landuse"="recreation_ground"]["name"]({bbox});
);
out center;
"""
    try:
        data = _overpass_query(query)
        results = []
        seen = set()
        for el in data.get("elements", []):
            name = el.get("tags", {}).get("name")
            if not name or name in seen:
                continue
            seen.add(name)
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            if not lat or not lon:
                continue
            tags = el.get("tags", {})
            ltype = tags.get("leisure") or tags.get("tourism") or tags.get("amenity") or tags.get("natural") or "landmark"
            results.append(
                {
                    "name": name,
                    "type": ltype,
                    "lat": float(lat),
                    "lon": float(lon),
                }
            )
        return results
    except Exception as exc:
        print(f"  [warn] Overpass landmarks query failed: {exc}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# Adjacency computation
# ---------------------------------------------------------------------------


def _compute_neighborhood_adjacency(
    neighborhoods: list[dict],
    threshold_km: float = 1.8,
) -> dict[str, list[str]]:
    """
    Build adjacency graph by centroid proximity.
    Two neighborhoods are 'adjacent' if centroids are within threshold_km.
    We use 1.8km — generous enough to connect most real neighbors.
    """
    adjacency: dict[str, list[str]] = {n["id"]: [] for n in neighborhoods}
    for i, a in enumerate(neighborhoods):
        for j, b in enumerate(neighborhoods):
            if i >= j:
                continue
            dist = _haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
            if dist < threshold_km:
                adjacency[a["id"]].append(b["id"])
                adjacency[b["id"]].append(a["id"])
    return adjacency


def _assign_landmark_neighborhoods(landmarks: list[dict], neighborhoods: list[dict]) -> list[dict]:
    """Assign each landmark to its nearest neighborhood by centroid distance."""
    for lm in landmarks:
        if lm.get("neighborhood"):
            continue  # already assigned
        best, best_dist = None, float("inf")
        for n in neighborhoods:
            d = _haversine_km(lm["lat"], lm["lon"], n["lat"], n["lon"])
            if d < best_dist:
                best_dist = d
                best = n["id"]
        lm["neighborhood"] = best
    return landmarks


def _assign_transit_neighborhoods(stations: list[dict], neighborhoods: list[dict]) -> list[dict]:
    """Assign each transit station to its nearest neighborhood."""
    for s in stations:
        if s.get("neighborhood") and any(n["id"] == s["neighborhood"] for n in neighborhoods):
            continue
        best, best_dist = None, float("inf")
        for n in neighborhoods:
            d = _haversine_km(s["lat"], s["lon"], n["lat"], n["lon"])
            if d < best_dist:
                best_dist = d
                best = n["id"]
        s["neighborhood"] = best
    return stations


# ---------------------------------------------------------------------------
# Merge Overpass data into curated baseline
# ---------------------------------------------------------------------------


def _merge_osm_neighborhoods(curated: list[dict], osm: list[dict]) -> list[dict]:
    """Add OSM-discovered neighborhoods not in the curated list (by distance check)."""
    existing_coords = [(n["lat"], n["lon"]) for n in curated]
    added = 0
    for osm_n in osm:
        # Skip if too close to an existing curated entry
        too_close = any(_haversine_km(osm_n["lat"], osm_n["lon"], lat, lon) < 0.5 for lat, lon in existing_coords)
        if not too_close and osm_n["name"]:
            curated.append(
                {
                    "name": osm_n["name"],
                    "lat": osm_n["lat"],
                    "lon": osm_n["lon"],
                    "vibe": "",  # Overpass doesn't give vibes
                    "region": "other",
                    "source": "osm",
                }
            )
            existing_coords.append((osm_n["lat"], osm_n["lon"]))
            added += 1
    if added:
        print(f"  Merged {added} additional neighborhoods from Overpass")
    return curated


def _merge_osm_landmarks(curated: list[dict], osm: list[dict]) -> list[dict]:
    """Add significant OSM landmarks not already in curated list."""
    existing_names = {lm["name"].lower() for lm in curated}
    added = 0
    for osm_lm in osm:
        name = osm_lm.get("name", "")
        if not name or name.lower() in existing_names:
            continue
        # Skip very generic/small things
        if len(name) < 4:
            continue
        curated.append(
            {
                "name": name,
                "lat": osm_lm["lat"],
                "lon": osm_lm["lon"],
                "type": osm_lm.get("type", "landmark"),
                "neighborhood": None,  # will be assigned below
                "description": "",
                "source": "osm",
            }
        )
        existing_names.add(name.lower())
        added += 1
    if added:
        print(f"  Merged {added} additional landmarks from Overpass")
    return curated


def _merge_osm_transit(curated_stations: list[dict], osm_stations: list[dict]) -> list[dict]:
    """Enrich curated transit data with OSM coordinates where better."""
    by_name = {s["name"].lower(): s for s in curated_stations}
    for osm_s in osm_stations:
        key = osm_s["name"].lower()
        if key in by_name:
            # Use OSM coordinates if they differ (OSM tends to be precise)
            existing = by_name[key]
            osm_dist = _haversine_km(existing["lat"], existing["lon"], osm_s["lat"], osm_s["lon"])
            if osm_dist > 0.05:  # more than 50m off
                existing["lat"] = osm_s["lat"]
                existing["lon"] = osm_s["lon"]
                existing["osm_id"] = osm_s.get("osm_id")
    return curated_stations


# ---------------------------------------------------------------------------
# Build final pack structures
# ---------------------------------------------------------------------------


def _build_neighborhoods(raw: list[dict]) -> list[dict]:
    """Finalize neighborhood records with IDs and adjacency."""
    # Deduplicate by name
    seen = {}
    for n in raw:
        key = n["name"].lower()
        if key not in seen:
            seen[key] = n
    deduped = list(seen.values())

    # Assign IDs
    for n in deduped:
        n["id"] = _slugify(n["name"])
        n.setdefault("grounding", "grounded_geo")
        n.setdefault("vibe", "")
        n.setdefault("region", "other")

    # Compute adjacency
    adjacency = _compute_neighborhood_adjacency(deduped)
    for n in deduped:
        n["adjacent_to"] = sorted(adjacency[n["id"]])

    return sorted(deduped, key=lambda n: n["name"])


def _build_transit_graph(config_systems: list[dict], processed_stations: dict[str, list[dict]], neighborhoods: list[dict]) -> dict:
    """Build the transit graph structure for all systems."""
    graph = {}
    
    for system in config_systems:
        sys_id = system["id"]
        stations = processed_stations.get(sys_id, [])
        stations = _assign_transit_neighborhoods(stations, neighborhoods)
        
        # Build sequential connections (assume stations listed in order if trunk)
        # This is a bit simplistic but preserves existing BART functionality
        sys_connections: dict[str, list[str]] = {}
        station_ids = [_slugify(f"{sys_id}-{s['name']}") for s in stations]
        
        for i, s in enumerate(stations):
            sid = station_ids[i]
            conns = []
            if i > 0:
                conns.append(station_ids[i - 1])
            if i < len(stations) - 1:
                conns.append(station_ids[i + 1])
            # Merge with explicitly defined connects_to if they existed in config
            if "connects_to" in s:
               conns = list(set(conns + s["connects_to"])) # dedup
            sys_connections[sid] = conns

        final_stations = []
        for i, s in enumerate(stations):
            sid = station_ids[i]
            st = {
                "id": sid,
                "name": s["name"],
                "grounding": "grounded_geo",
                "system": system["name"],
                "lines": s.get("lines", []),
                "lat": s["lat"],
                "lon": s["lon"],
                "neighborhood": s.get("neighborhood"),
                "notes": s.get("notes", ""),
            }
            if sys_connections[sid]:
                st["connects_to"] = sys_connections[sid]
            final_stations.append(st)
        
        graph[sys_id] = {
            "description": system.get("description", ""),
            "fare_zone": system.get("fare_zone", system.get("fare", "")),
            "frequency": system.get("frequency", ""),
            "stations": final_stations
        }
        if "lines" in system:
            graph[sys_id]["lines"] = system["lines"]

    return graph


def _build_landmarks(raw: list[dict], neighborhoods: list[dict]) -> list[dict]:
    """Finalize landmark records."""
    raw = _assign_landmark_neighborhoods(raw, neighborhoods)
    result = []
    seen = set()
    for lm in raw:
        name = lm.get("name", "")
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(
            {
                "id": _slugify(name),
                "name": name,
                "grounding": "grounded_geo",
                "type": lm.get("type", "landmark"),
                "neighborhood": lm.get("neighborhood"),
                "lat": lm.get("lat"),
                "lon": lm.get("lon"),
                "description": lm.get("description", ""),
            }
        )
    return sorted(result, key=lambda x: x["name"])


def _build_corridors(raw: list[dict]) -> list[dict]:
    result = []
    for c in raw:
        result.append(
            {
                "id": _slugify(c["name"]),
                "name": c["name"],
                "grounding": "grounded_geo",
                "type": c.get("type", "commercial"),
                "neighborhoods": c.get("neighborhoods", []),
                "vibe": c.get("vibe", ""),
            }
        )
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_pack(city_config_path: Path, output_dir: Path, offline: bool = False) -> None:
    if not city_config_path.exists():
        print(f"Error: Config file {city_config_path} not found.", file=sys.stderr)
        sys.exit(1)
        
    try:
        config = json.loads(city_config_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error reading config: {e}", file=sys.stderr)
        sys.exit(1)
        
    city_name = config.get("city_name", "Unknown City")
    city_id = config.get("city_id", "unknown_city")
    default_bbox = config.get("bboxes", {}).get("default", "")

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Building {city_name} city pack → {output_dir}")

    # --- 1. Pull Overpass data ---
    osm_neighborhoods: list[dict] = []
    osm_landmarks: list[dict] = []
    osm_transit: dict[str, list[dict]] = {}

    if not offline:
        print("Pulling neighborhoods from Overpass API...")
        osm_neighborhoods = _pull_neighborhoods(default_bbox)
        print(f"  Got {len(osm_neighborhoods)} OSM neighbourhood nodes")
        time.sleep(2)  # polite
        
        for system in config.get("transit_systems", []):
            sys_id = system["id"]
            bbox_key = system.get("bbox_key", "default")
            bbox = config.get("bboxes", {}).get(bbox_key, default_bbox)
            query_tpl = system.get("query_template")
            
            if query_tpl and bbox:
                print(f"Pulling {system['name']} stations...")
                stations = _pull_transit_system(query_tpl, bbox)
                osm_transit[sys_id] = stations
                print(f"  Got {len(stations)} OSM stations for {sys_id}")
                time.sleep(2)

        print("Pulling landmarks...")
        osm_landmarks = _pull_landmarks(default_bbox)
        print(f"  Got {len(osm_landmarks)} OSM landmark elements")
        time.sleep(1)
    else:
        print("Offline mode — using curated baseline only")

    # --- 2. Merge OSM into curated baseline ---
    print("Merging data...")
    all_neighborhoods = _merge_osm_neighborhoods(config.get("curated_neighborhoods", []), osm_neighborhoods)
    all_landmarks = _merge_osm_landmarks(config.get("curated_landmarks", []), osm_landmarks)
    
    processed_transit = {}
    total_transit_stations = 0
    for system in config.get("transit_systems", []):
        sys_id = system["id"]
        curated = system.get("stations", [])
        osm_stations = osm_transit.get(sys_id, [])
        processed = _merge_osm_transit(curated, osm_stations)
        processed_transit[sys_id] = processed
        total_transit_stations += len(processed)

    # --- 3. Build final structures ---
    print("Building neighborhood graph...")
    neighborhoods = _build_neighborhoods(all_neighborhoods)
    print(f"  {len(neighborhoods)} neighborhoods with adjacency")

    print("Building transit graph...")
    transit_graph = _build_transit_graph(config.get("transit_systems", []), processed_transit, neighborhoods)
    print(f"  {total_transit_stations} total transit stations processed")

    print("Building landmarks...")
    landmarks = _build_landmarks(all_landmarks, neighborhoods)
    print(f"  {len(landmarks)} landmarks")

    print("Building street corridors...")
    corridors = _build_corridors(config.get("street_corridors", []))
    print(f"  {len(corridors)} corridors")
    
    inter_city = config.get("inter_city", [])

    # --- 4. Write files ---
    bbox_parts = default_bbox.split(",")
    bounds = {}
    if len(bbox_parts) == 4:
        bounds = {
            "south": float(bbox_parts[0]),
            "west": float(bbox_parts[1]),
            "north": float(bbox_parts[2]),
            "east": float(bbox_parts[3])
        }
        
    manifest: dict[str, Any] = {
        "city": city_name,
        "city_id": city_id,
        "version": "1.0.0",
        "built_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "bounds": bounds,
        "source": "openstreetmap.org + curated",
        "license": "ODbL (openstreetmap.org/copyright) for OSM-derived data",
        "counts": {
            "neighborhoods": len(neighborhoods),
            "transit_stations": total_transit_stations,
            "landmarks": len(landmarks),
            "corridors": len(corridors),
            "inter_city_routes": len(inter_city),
        },
    }

    files: dict[str, Any] = {
        "manifest.json": manifest,
        "neighborhoods.json": neighborhoods,
        "transit_graph.json": transit_graph,
        "landmarks.json": landmarks,
        "street_corridors.json": corridors,
        "inter_city.json": inter_city,
        "weather_config.json": config.get("weather_config", {}),
        "transit_config.json": config.get("transit_config", {}),
    }

    for filename, data in files.items():
        path = output_dir / filename
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        size_kb = path.stat().st_size / 1024
        print(f"  Wrote {filename} ({size_kb:.1f} KB)")

    print(f"\nDone. City pack written to {output_dir}")
    print(f"  Total: {sum((output_dir / f).stat().st_size for f in files) / 1024:.1f} KB")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a WorldWeaver city pack from OpenStreetMap")
    parser.add_argument("--city", required=True, help="City ID to load from scripts/city_configs/ (e.g. san_francisco, portland)")
    parser.add_argument("--output", help="Output directory. Defaults to data/cities/{city_id}")
    parser.add_argument("--offline", action="store_true", help="Skip Overpass API, use curated data only")
    args = parser.parse_args()

    city_id = args.city
    config_path = Path(__file__).parent / "city_configs" / f"{city_id}.json"
    
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = Path("data") / "cities" / city_id
        
    build_pack(config_path, output_dir, offline=args.offline)


if __name__ == "__main__":
    main()
