# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Pure city-pack assembly shared by the CLI and future City Studio.

Network retrieval and filesystem writes stay outside this module. Given one
configuration and optional source records, it returns the validated files that
make up a city pack.
"""

from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence

from .city_pack_validation import CityPackValidationReport, require_valid_city_pack
from .map_generation import CompiledFictionalMap, compile_fictional_map


@dataclass(frozen=True)
class BuiltCityPack:
    files: dict[str, Any]
    generated_map_svg: str | None
    validation: CityPackValidationReport


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    latitude_delta = math.radians(lat2 - lat1)
    longitude_delta = math.radians(lon2 - lon1)
    value = math.sin(latitude_delta / 2) ** 2 + (
        math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(longitude_delta / 2) ** 2
    )
    return radius_km * 2 * math.asin(math.sqrt(value))


def _slugify(name: str) -> str:
    value = name.lower().strip()
    value = re.sub(r"['\"/]", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def _compute_neighborhood_adjacency(
    neighborhoods: Sequence[Mapping[str, Any]], threshold_km: float = 1.8
) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = {
        str(neighborhood["id"]): [] for neighborhood in neighborhoods
    }
    for index, first in enumerate(neighborhoods):
        for second in neighborhoods[index + 1 :]:
            distance = _haversine_km(
                float(first["lat"]),
                float(first["lon"]),
                float(second["lat"]),
                float(second["lon"]),
            )
            if distance < threshold_km:
                adjacency[str(first["id"])].append(str(second["id"]))
                adjacency[str(second["id"])].append(str(first["id"]))
    return adjacency


def _assign_nearest_neighborhood(
    records: list[dict[str, Any]], neighborhoods: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    known_ids = {str(neighborhood["id"]) for neighborhood in neighborhoods}
    for record in records:
        if str(record.get("neighborhood") or "") in known_ids:
            continue
        nearest = min(
            neighborhoods,
            key=lambda neighborhood: _haversine_km(
                float(record["lat"]),
                float(record["lon"]),
                float(neighborhood["lat"]),
                float(neighborhood["lon"]),
            ),
            default=None,
        )
        record["neighborhood"] = str(nearest["id"]) if nearest else None
    return records


def merge_osm_neighborhoods(
    curated: Sequence[Mapping[str, Any]], osm: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    merged = copy.deepcopy(list(curated))
    existing_coordinates = [(float(item["lat"]), float(item["lon"])) for item in merged]
    for source in osm:
        latitude = float(source["lat"])
        longitude = float(source["lon"])
        if not str(source.get("name") or "").strip() or any(
            _haversine_km(latitude, longitude, existing_lat, existing_lon) < 0.5
            for existing_lat, existing_lon in existing_coordinates
        ):
            continue
        merged.append(
            {
                "name": str(source["name"]),
                "lat": latitude,
                "lon": longitude,
                "vibe": "",
                "region": "other",
                "source": "osm",
            }
        )
        existing_coordinates.append((latitude, longitude))
    return merged


def merge_osm_landmarks(
    curated: Sequence[Mapping[str, Any]], osm: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    merged = copy.deepcopy(list(curated))
    existing_names = {str(item.get("name") or "").lower() for item in merged}
    for source in osm:
        name = str(source.get("name") or "").strip()
        if len(name) < 4 or name.lower() in existing_names:
            continue
        merged.append(
            {
                "name": name,
                "lat": float(source["lat"]),
                "lon": float(source["lon"]),
                "type": str(source.get("type") or "landmark"),
                "neighborhood": None,
                "description": "",
                "source": "osm",
            }
        )
        existing_names.add(name.lower())
    return merged


def merge_osm_transit(
    curated: Sequence[Mapping[str, Any]], osm: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    merged = copy.deepcopy(list(curated))
    by_name = {str(item["name"]).lower(): item for item in merged}
    for source in osm:
        existing = by_name.get(str(source.get("name") or "").lower())
        if existing is None:
            continue
        if (
            _haversine_km(
                float(existing["lat"]),
                float(existing["lon"]),
                float(source["lat"]),
                float(source["lon"]),
            )
            > 0.05
        ):
            existing["lat"] = float(source["lat"])
            existing["lon"] = float(source["lon"])
            existing["osm_id"] = source.get("osm_id")
    return merged


def build_neighborhoods(
    raw: Sequence[Mapping[str, Any]], *, default_grounding: str = "grounded_geo"
) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for source in raw:
        item = copy.deepcopy(dict(source))
        by_name.setdefault(str(item["name"]).lower(), item)
    neighborhoods = list(by_name.values())
    for neighborhood in neighborhoods:
        neighborhood["id"] = _slugify(str(neighborhood["name"]))
        neighborhood.setdefault("grounding", default_grounding)
        neighborhood.setdefault("vibe", "")
        neighborhood.setdefault("region", "other")
    adjacency = _compute_neighborhood_adjacency(neighborhoods)
    for neighborhood in neighborhoods:
        explicit = neighborhood.get("adjacent_to")
        neighborhood["adjacent_to"] = (
            sorted({str(item).strip() for item in explicit if str(item).strip()})
            if isinstance(explicit, list)
            else sorted(adjacency[str(neighborhood["id"])])
        )
    return sorted(neighborhoods, key=lambda item: str(item["name"]))


def build_transit_graph(
    systems: Sequence[Mapping[str, Any]],
    processed_stations: Mapping[str, list[dict[str, Any]]],
    neighborhoods: Sequence[Mapping[str, Any]],
    *,
    default_grounding: str = "grounded_geo",
) -> dict[str, Any]:
    graph: dict[str, Any] = {}
    for system in systems:
        system_id = str(system["id"])
        stations = _assign_nearest_neighborhood(
            copy.deepcopy(processed_stations.get(system_id, [])), neighborhoods
        )
        station_ids = [
            _slugify(f"{system_id}-{station['name']}") for station in stations
        ]
        final_stations: list[dict[str, Any]] = []
        for index, station in enumerate(stations):
            connections: list[str] = []
            if index > 0:
                connections.append(station_ids[index - 1])
            if index < len(stations) - 1:
                connections.append(station_ids[index + 1])
            if isinstance(station.get("connects_to"), list):
                connections = list(
                    set([*connections, *map(str, station["connects_to"])])
                )
            final = {
                "id": station_ids[index],
                "name": station["name"],
                "grounding": station.get("grounding", default_grounding),
                "system": system["name"],
                "lines": station.get("lines", []),
                "lat": station["lat"],
                "lon": station["lon"],
                "neighborhood": station.get("neighborhood"),
                "notes": station.get("notes", ""),
            }
            if connections:
                final["connects_to"] = connections
            final_stations.append(final)
        graph[system_id] = {
            "description": system.get("description", ""),
            "fare_zone": system.get("fare_zone", system.get("fare", "")),
            "frequency": system.get("frequency", ""),
            "stations": final_stations,
        }
        if "lines" in system:
            graph[system_id]["lines"] = system["lines"]
    return graph


def build_landmarks(
    raw: Sequence[Mapping[str, Any]],
    neighborhoods: Sequence[Mapping[str, Any]],
    *,
    default_grounding: str = "grounded_geo",
) -> list[dict[str, Any]]:
    assigned = _assign_nearest_neighborhood(copy.deepcopy(list(raw)), neighborhoods)
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for landmark in assigned:
        name = str(landmark.get("name") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(
            {
                "id": _slugify(name),
                "name": name,
                "grounding": landmark.get("grounding", default_grounding),
                "type": landmark.get("type", "landmark"),
                "neighborhood": landmark.get("neighborhood"),
                "lat": landmark.get("lat"),
                "lon": landmark.get("lon"),
                "description": landmark.get("description", ""),
            }
        )
    return sorted(result, key=lambda item: str(item["name"]))


def build_corridors(
    raw: Sequence[Mapping[str, Any]], *, default_grounding: str = "grounded_geo"
) -> list[dict[str, Any]]:
    return [
        {
            "id": _slugify(str(corridor["name"])),
            "name": corridor["name"],
            "grounding": corridor.get("grounding", default_grounding),
            "type": corridor.get("type", "commercial"),
            "neighborhoods": corridor.get("neighborhoods", []),
            "vibe": corridor.get("vibe", ""),
        }
        for corridor in raw
    ]


def assemble_city_pack(
    config: Mapping[str, Any],
    *,
    osm_neighborhoods: Sequence[Mapping[str, Any]] = (),
    osm_landmarks: Sequence[Mapping[str, Any]] = (),
    osm_transit: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    built_at: str | None = None,
) -> BuiltCityPack:
    """Build and validate a pack in memory without network or filesystem access."""
    source = copy.deepcopy(dict(config))
    city_name = str(source.get("city_name") or source.get("city") or "Unknown City")
    city_id = str(source.get("city_id") or "unknown_city")
    default_bbox = str((source.get("bboxes") or {}).get("default") or "")
    fictional = bool(source.get("fictional", False))
    default_grounding = "fictional" if fictional else "grounded_geo"

    neighborhoods = build_neighborhoods(
        merge_osm_neighborhoods(
            source.get("curated_neighborhoods", []), osm_neighborhoods
        ),
        default_grounding=default_grounding,
    )
    landmarks = build_landmarks(
        merge_osm_landmarks(source.get("curated_landmarks", []), osm_landmarks),
        neighborhoods,
        default_grounding=default_grounding,
    )
    provided_transit = osm_transit or {}
    processed_transit: dict[str, list[dict[str, Any]]] = {}
    total_transit_stations = 0
    for system in source.get("transit_systems", []):
        system_id = str(system["id"])
        processed = merge_osm_transit(
            system.get("stations", []), provided_transit.get(system_id, [])
        )
        processed_transit[system_id] = processed
        total_transit_stations += len(processed)
    transit_graph = build_transit_graph(
        source.get("transit_systems", []),
        processed_transit,
        neighborhoods,
        default_grounding=default_grounding,
    )
    corridors = build_corridors(
        source.get("street_corridors", []),
        default_grounding=default_grounding,
    )
    compiled_map: CompiledFictionalMap | None = None
    if fictional and isinstance(source.get("fictional_map"), dict):
        compiled_map = compile_fictional_map(
            source, neighborhoods=neighborhoods, landmarks=landmarks
        )

    bounds: dict[str, float] = {}
    bbox_parts = default_bbox.split(",")
    if len(bbox_parts) == 4:
        south, west, north, east = map(float, bbox_parts)
        bounds = {"south": south, "west": west, "north": north, "east": east}
    travel_hubs = copy.deepcopy(source.get("travel_hubs", []))
    inter_city = copy.deepcopy(source.get("inter_city", []))
    stoops = copy.deepcopy(source.get("stoops", []))
    manifest: dict[str, Any] = {
        "city": city_name,
        "city_id": city_id,
        "schema_version": "1.1.0",
        "version": str(source.get("pack_version") or "1.0.0"),
        "built_at": built_at or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "bounds": bounds,
        "source": str(
            source.get("source")
            or (
                "WorldWeaver curated fictional geography"
                if fictional
                else "openstreetmap.org + curated"
            )
        ),
        "license": str(
            source.get("license")
            or (
                "Original fictional pack data; repository license applies"
                if fictional
                else "ODbL (openstreetmap.org/copyright) for OSM-derived data"
            )
        ),
        "fictional": fictional,
        "counts": {
            "neighborhoods": len(neighborhoods),
            "transit_stations": total_transit_stations,
            "landmarks": len(landmarks),
            "corridors": len(corridors),
            "travel_hubs": len(travel_hubs),
            "inter_city_routes": len(inter_city),
            "stoops": len(stoops),
            "map_sections": (
                len(compiled_map.artifact["sections"]) if compiled_map else 0
            ),
        },
    }
    if compiled_map:
        manifest["generated_map"] = {
            "schema_version": compiled_map.artifact["schema_version"],
            "generator": dict(compiled_map.artifact["generator"]),
            "artifact_sha256": compiled_map.artifact["artifact_sha256"],
        }
    files: dict[str, Any] = {
        "manifest.json": manifest,
        "neighborhoods.json": neighborhoods,
        "transit_graph.json": transit_graph,
        "landmarks.json": landmarks,
        "street_corridors.json": corridors,
        "travel_hubs.json": travel_hubs,
        "inter_city.json": inter_city,
        "stoops.json": stoops,
        "weather_config.json": copy.deepcopy(source.get("weather_config", {})),
        "transit_config.json": copy.deepcopy(source.get("transit_config", {})),
    }
    if compiled_map:
        files["generated_map.json"] = compiled_map.artifact
    report = require_valid_city_pack(
        {filename.removesuffix(".json"): data for filename, data in files.items()}
    )
    return BuiltCityPack(
        files=files,
        generated_map_svg=compiled_map.svg if compiled_map else None,
        validation=report,
    )


__all__ = [
    "BuiltCityPack",
    "assemble_city_pack",
    "build_corridors",
    "build_landmarks",
    "build_neighborhoods",
    "build_transit_graph",
    "merge_osm_landmarks",
    "merge_osm_neighborhoods",
    "merge_osm_transit",
]
