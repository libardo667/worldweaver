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
    travel_hubs.json       city-owned entry points used by cross-city travel
    inter_city.json        connections to other cities by mode/operator
    weather_config.json    NWS zone + Open-Meteo coordinates for grounding daemon
    transit_config.json    GTFS-rt feed URLs for grounding daemon
    generated_map.json     deterministic physical fields and section seams for fictional maps
    generated_map.svg      precompiled fictional terrain drawing for clients and City Studio

City-agnostic design
--------------------
The builder works for any city with only a ``bboxes.default`` bbox in its config.
All three Overpass pulls (neighbourhoods, transit, landmarks) are generic and
require no city-specific query code.

For transit systems, Overpass query generation follows this priority:
  1. Explicit ``query_template`` in the system config (highest fidelity).
  2. ``operator_osm`` field on the system — e.g. ``"operator_osm": "WMATA"`` —
     generates an operator-filtered station query automatically.
  3. Fallback: generic all-modes-in-bbox query (noisier, still useful).

To add a new city, create ``scripts/city_configs/<city_id>.json`` with at minimum:
  - ``city_id``, ``city_name``
  - ``bboxes.default`` (south,west,north,east)
  - Any ``curated_*`` lists you want as a baseline

The Overpass pull enriches the curated baseline — if OSM data is unavailable,
the curated dataset alone is still a rich, usable pack.

Requirements:
    pip install httpx  (already in worldweaver requirements)

OSM data is ODbL (openstreetmap.org/copyright). See manifest.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from src.services.city_pack_builder import assemble_city_pack  # noqa: E402

# ---------------------------------------------------------------------------
# Overpass API client
# ---------------------------------------------------------------------------

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _overpass_query(query: str, timeout: int = 60, retries: int = 4) -> dict:
    import httpx

    delay = 10  # initial retry delay in seconds
    for attempt in range(retries):
        try:
            resp = httpx.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=timeout,
                headers={"User-Agent": "WorldWeaver-CityPackBuilder/1.0 (worldweaver project)"},
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < retries - 1:
                    print(f"  [retry] HTTP {resp.status_code} — waiting {delay}s before retry {attempt + 2}/{retries}...", file=sys.stderr)
                    time.sleep(delay)
                    delay *= 2  # exponential backoff
                    continue
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            if attempt < retries - 1:
                print(f"  [retry] timeout — waiting {delay}s before retry {attempt + 2}/{retries}...", file=sys.stderr)
                time.sleep(delay)
                delay *= 2
                continue
            raise
    resp.raise_for_status()
    return resp.json()


def _pull_neighborhoods(bbox: str) -> list[dict]:
    """Query OSM for neighbourhood nodes and ways."""
    query = f"""
[out:json][timeout:60];
(
  node["place"="neighbourhood"]({bbox});
  node["place"="quarter"]({bbox});
  node["place"="suburb"]({bbox});
  way["place"="neighbourhood"]({bbox});
  way["place"="suburb"]({bbox});
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


def _make_transit_query(system: dict, bbox: str) -> str:
    """
    Build an Overpass query for a transit system.

    Priority:
    1. Explicit ``query_template`` in the system config (formatted with bbox).
    2. ``operator_osm`` field — generates operator-filtered node query.
    3. Generic fallback — all railway/tram/bus stations in bbox.
    """
    if system.get("query_template"):
        return system["query_template"].format(bbox=bbox)

    operator = system.get("operator_osm") or system.get("name", "")
    if operator:
        safe = operator.replace('"', '\\"')
        return f"""
[out:json][timeout:60];
(
  node["railway"~"station|tram_stop|halt"]["operator"~"{safe}",i]({bbox});
  node["public_transport"="station"]["operator"~"{safe}",i]({bbox});
  node["public_transport"="stop_position"]["operator"~"{safe}",i]({bbox});
);
out body;
"""
    # Generic: any named transit stop in bbox (noisier but still useful)
    return f"""
[out:json][timeout:60];
(
  node["railway"~"station|tram_stop|halt"]["name"]({bbox});
  node["public_transport"="station"]["name"]({bbox});
);
out body;
"""


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


def _pull_transit_system_auto(system: dict, bbox: str) -> list[dict]:
    """Pull transit stations for a system, auto-generating the query if needed."""
    query = _make_transit_query(system, bbox)
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
    """
    Query OSM for parks, viewpoints, cultural sites, and neighbourhood anchors.

    Pulls a broad set of tags so the result is city-agnostic — works equally
    well for SF, Portland, Chicago, or anywhere else.
    """
    query = f"""
[out:json][timeout:120];
(
  way["leisure"="park"]["name"]({bbox});
  way["leisure"~"garden|nature_reserve|recreation_ground"]["name"]({bbox});
  node["tourism"~"attraction|viewpoint|museum|gallery|artwork"]["name"]({bbox});
  way["tourism"~"attraction|museum|gallery"]["name"]({bbox});
  node["amenity"~"theatre|arts_centre|library|community_centre|marketplace"]["name"]({bbox});
  node["amenity"~"music_venue"]["name"]({bbox});
  node["natural"~"beach|cliff|peak|water"]["name"]({bbox});
  node["historic"~"monument|memorial|landmark|building|ruins"]["name"]({bbox});
  way["historic"~"monument|memorial|landmark|building|ruins"]["name"]({bbox});
  node["shop"="bookstore"]["name"]({bbox});
  node["amenity"="food_court"]["name"]({bbox});
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
            ltype = tags.get("leisure") or tags.get("tourism") or tags.get("amenity") or tags.get("historic") or tags.get("natural") or tags.get("shop") or "landmark"
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

    city_name = config.get("city_name") or config.get("city", "Unknown City")
    default_bbox = config.get("bboxes", {}).get("default", "")
    fictional = bool(config.get("fictional", False))
    import_osm = bool(config.get("import_osm", True)) and not fictional

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Building {city_name} city pack → {output_dir}")

    # --- 1. Pull Overpass data ---
    osm_neighborhoods: list[dict] = []
    osm_landmarks: list[dict] = []
    osm_transit: dict[str, list[dict]] = {}

    if not offline and import_osm:
        print("Pulling neighborhoods from Overpass API...")
        osm_neighborhoods = _pull_neighborhoods(default_bbox)
        print(f"  Got {len(osm_neighborhoods)} OSM neighbourhood nodes")
        time.sleep(2)  # polite

        for system in config.get("transit_systems", []):
            sys_id = system["id"]
            bbox_key = system.get("bbox_key", "default")
            bbox = config.get("bboxes", {}).get(bbox_key, default_bbox)
            if not bbox:
                print(f"  [skip] {system['name']} — no bbox configured", file=sys.stderr)
                continue
            source = "config query" if system.get("query_template") else "auto-generated query"
            print(f"Pulling {system['name']} stations ({source})...")
            stations = _pull_transit_system_auto(system, bbox)
            osm_transit[sys_id] = stations
            print(f"  Got {len(stations)} OSM stations for {sys_id}")
            time.sleep(2)

        print("Pulling landmarks...")
        osm_landmarks = _pull_landmarks(default_bbox)
        print(f"  Got {len(osm_landmarks)} OSM landmark elements")
        time.sleep(1)
    else:
        reason = "fictional/curated mode" if not import_osm else "offline mode"
        print(f"{reason.capitalize()} — using curated baseline only")

    print("Assembling and validating pack...")
    built = assemble_city_pack(
        config,
        osm_neighborhoods=osm_neighborhoods,
        osm_landmarks=osm_landmarks,
        osm_transit=osm_transit,
    )
    counts = built.files["manifest.json"]["counts"]
    print(f"  {counts['neighborhoods']} neighborhoods with adjacency")
    print(f"  {counts['transit_stations']} total transit stations processed")
    print(f"  {counts['landmarks']} landmarks")
    print(f"  {counts['corridors']} corridors")
    if counts["map_sections"]:
        print(f"  {counts['map_sections']} independently seeded sections")
    for issue in built.validation.warnings:
        print(f"  [warn] {issue.path}: {issue.message}", file=sys.stderr)

    for filename, data in built.files.items():
        path = output_dir / filename
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        size_kb = path.stat().st_size / 1024
        print(f"  Wrote {filename} ({size_kb:.1f} KB)")

    if built.generated_map_svg is not None:
        svg_path = output_dir / "generated_map.svg"
        svg_path.write_text(built.generated_map_svg, encoding="utf-8")
        print(f"  Wrote generated_map.svg ({svg_path.stat().st_size / 1024:.1f} KB)")

    print(f"\nDone. City pack written to {output_dir}")
    output_filenames = [
        *built.files,
        *(["generated_map.svg"] if built.generated_map_svg is not None else []),
    ]
    print(f"  Total: {sum((output_dir / filename).stat().st_size for filename in output_filenames) / 1024:.1f} KB")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a WorldWeaver city pack from OpenStreetMap")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--city", help="City ID to load from scripts/city_configs/ (e.g. san_francisco, portland)")
    group.add_argument("--all", action="store_true", help="Build packs for every config in scripts/city_configs/")
    parser.add_argument("--output", help="Output directory (only valid with --city). Defaults to data/cities/{city_id}")
    parser.add_argument("--offline", action="store_true", help="Skip Overpass API, use curated data only")
    args = parser.parse_args()

    configs_dir = Path(__file__).parent / "city_configs"

    if args.all:
        configs = sorted(configs_dir.glob("*.json"))
        if not configs:
            print(f"No city configs found in {configs_dir}", file=sys.stderr)
            sys.exit(1)
        print(f"Building {len(configs)} city pack(s): {', '.join(c.stem for c in configs)}\n")
        failed = []
        for config_path in configs:
            city_id = config_path.stem
            output_dir = Path("data") / "cities" / city_id
            print(f"{'='*60}")
            try:
                build_pack(config_path, output_dir, offline=args.offline)
            except Exception as exc:
                print(f"  [ERROR] {city_id} failed: {exc}", file=sys.stderr)
                failed.append(city_id)
            print()
        if failed:
            print(f"Failed: {', '.join(failed)}", file=sys.stderr)
            sys.exit(1)
    else:
        city_id = args.city
        config_path = configs_dir / f"{city_id}.json"
        output_dir = Path(args.output) if args.output else Path("data") / "cities" / city_id
        build_pack(config_path, output_dir, offline=args.offline)


if __name__ == "__main__":
    main()
