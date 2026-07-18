# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Structured city-pack validation shared by the CLI and future City Studio."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

_STABLE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")


@dataclass(frozen=True)
class CityPackIssue:
    level: str
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "level": self.level,
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class CityPackValidationReport:
    issues: tuple[CityPackIssue, ...]

    @property
    def valid(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)

    @property
    def errors(self) -> tuple[CityPackIssue, ...]:
        return tuple(issue for issue in self.issues if issue.level == "error")

    @property
    def warnings(self) -> tuple[CityPackIssue, ...]:
        return tuple(issue for issue in self.issues if issue.level == "warning")

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }


def _items(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _stable_id(value: Any) -> str:
    return str(value or "").strip()


def _issue(issues: list[CityPackIssue], level: str, code: str, path: str, message: str) -> None:
    issues.append(CityPackIssue(level=level, code=code, path=path, message=message))


def _check_coordinates(
    issues: list[CityPackIssue],
    *,
    record: Mapping[str, Any],
    path: str,
) -> None:
    for coordinate, minimum, maximum in (("lat", -90.0, 90.0), ("lon", -180.0, 180.0)):
        value = record.get(coordinate)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not minimum <= float(value) <= maximum:
            _issue(
                issues,
                "error",
                "invalid_coordinate",
                f"{path}.{coordinate}",
                f"{coordinate} must be between {minimum:g} and {maximum:g}.",
            )


def _check_unique_ids(
    issues: list[CityPackIssue],
    *,
    records: list[Mapping[str, Any]],
    path: str,
    invalid_level: str = "error",
) -> set[str]:
    found: set[str] = set()
    for index, record in enumerate(records):
        record_id = _stable_id(record.get("id"))
        item_path = f"{path}[{index}].id"
        if not record_id:
            _issue(issues, "error", "missing_id", item_path, "A stable ID is required.")
            continue
        if not _STABLE_ID_RE.fullmatch(record_id):
            _issue(issues, invalid_level, "invalid_id", item_path, "Use lowercase letters, numbers, hyphens, or underscores.")
        if record_id in found:
            _issue(issues, "error", "duplicate_id", item_path, f"ID '{record_id}' is used more than once.")
        found.add(record_id)
    return found


def validate_city_pack(pack: Mapping[str, Any]) -> CityPackValidationReport:
    """Return UI-ready errors and warnings without changing the supplied pack."""
    issues: list[CityPackIssue] = []
    manifest = pack.get("manifest") if isinstance(pack.get("manifest"), Mapping) else {}
    city_id = _stable_id(manifest.get("city_id"))
    if not city_id:
        _issue(issues, "error", "missing_city_id", "manifest.city_id", "The pack needs a stable city ID.")
    elif not _STABLE_ID_RE.fullmatch(city_id):
        _issue(issues, "error", "invalid_city_id", "manifest.city_id", "Use lowercase letters, numbers, hyphens, or underscores.")
    if not _stable_id(manifest.get("schema_version")):
        _issue(issues, "warning", "missing_schema_version", "manifest.schema_version", "Legacy pack: add an explicit schema version when it is rebuilt.")
    if not _stable_id(manifest.get("version")):
        _issue(issues, "error", "missing_pack_version", "manifest.version", "A published pack needs an explicit version.")
    fictional = manifest.get("fictional", False)
    if not isinstance(fictional, bool):
        _issue(issues, "error", "invalid_fictional_flag", "manifest.fictional", "The fictional marker must be true or false.")
    if fictional and "openstreetmap" in _stable_id(manifest.get("source")).lower():
        _issue(issues, "error", "fictional_osm_source", "manifest.source", "A fictional pack must not claim OpenStreetMap as its geography source.")
    place_reference_level = "error" if fictional is True else "warning"

    neighborhoods = _items(pack.get("neighborhoods"))
    if not neighborhoods:
        _issue(issues, "error", "missing_neighborhoods", "neighborhoods", "A city needs at least one neighborhood.")
    neighborhood_ids = _check_unique_ids(issues, records=neighborhoods, path="neighborhoods")
    neighborhood_names = {_stable_id(item.get("name")).lower() for item in neighborhoods if _stable_id(item.get("name"))}
    for index, neighborhood in enumerate(neighborhoods):
        _check_coordinates(issues, record=neighborhood, path=f"neighborhoods[{index}]")
        adjacent = neighborhood.get("adjacent_to")
        for adjacent_id in adjacent if isinstance(adjacent, list) else []:
            normalized = _stable_id(adjacent_id)
            if normalized and normalized not in neighborhood_ids:
                _issue(issues, "error", "unknown_neighborhood", f"neighborhoods[{index}].adjacent_to", f"Neighborhood '{normalized}' does not exist in this pack.")

    landmarks = _items(pack.get("landmarks"))
    _check_unique_ids(
        issues,
        records=landmarks,
        path="landmarks",
        invalid_level=place_reference_level,
    )
    for index, landmark in enumerate(landmarks):
        landmark_path = f"landmarks[{index}]"
        _check_coordinates(issues, record=landmark, path=landmark_path)
        neighborhood_id = _stable_id(landmark.get("neighborhood"))
        if neighborhood_id and neighborhood_id not in neighborhood_ids:
            _issue(
                issues,
                place_reference_level,
                "unknown_neighborhood",
                f"{landmark_path}.neighborhood",
                f"Neighborhood '{neighborhood_id}' does not exist in this pack.",
            )

    corridors = _items(pack.get("street_corridors"))
    _check_unique_ids(issues, records=corridors, path="street_corridors")
    for index, corridor in enumerate(corridors):
        references = corridor.get("neighborhoods")
        for neighborhood_id in references if isinstance(references, list) else []:
            normalized = _stable_id(neighborhood_id)
            if normalized and normalized not in neighborhood_ids:
                _issue(
                    issues,
                    place_reference_level,
                    "unknown_neighborhood",
                    f"street_corridors[{index}].neighborhoods",
                    f"Neighborhood '{normalized}' does not exist in this pack.",
                )

    transit_graph = pack.get("transit_graph")
    if isinstance(transit_graph, Mapping):
        transit_ids: set[str] = set()
        transit_references: list[tuple[str, str]] = []
        for system_id, raw_system in transit_graph.items():
            if not isinstance(raw_system, Mapping):
                continue
            stations = _items(raw_system.get("stations"))
            system_path = f"transit_graph.{system_id}.stations"
            ids = _check_unique_ids(issues, records=stations, path=system_path)
            for station_id in ids:
                if station_id in transit_ids:
                    _issue(issues, "error", "duplicate_id", system_path, f"Transit ID '{station_id}' is used in more than one system.")
                transit_ids.add(station_id)
            for index, station in enumerate(stations):
                station_path = f"{system_path}[{index}]"
                _check_coordinates(issues, record=station, path=station_path)
                neighborhood_id = _stable_id(station.get("neighborhood"))
                if neighborhood_id and neighborhood_id not in neighborhood_ids:
                    _issue(
                        issues,
                        place_reference_level,
                        "unknown_neighborhood",
                        f"{station_path}.neighborhood",
                        f"Neighborhood '{neighborhood_id}' does not exist in this pack.",
                    )
                connections = station.get("connects_to")
                for connected_id in connections if isinstance(connections, list) else []:
                    transit_references.append((f"{station_path}.connects_to", _stable_id(connected_id)))
        for path, connected_id in transit_references:
            if connected_id and connected_id not in transit_ids:
                _issue(issues, "error", "unknown_transit_stop", path, f"Transit stop '{connected_id}' does not exist in this pack.")

    travel_hubs = _items(pack.get("travel_hubs"))
    hub_ids = _check_unique_ids(issues, records=travel_hubs, path="travel_hubs")
    for index, hub in enumerate(travel_hubs):
        entry_location = _stable_id(hub.get("entry_location"))
        if not entry_location:
            _issue(issues, "error", "missing_entry_location", f"travel_hubs[{index}].entry_location", "A travel hub must enter through a local neighborhood.")
        elif entry_location not in neighborhood_ids and entry_location.lower() not in neighborhood_names:
            _issue(issues, "error", "unknown_entry_location", f"travel_hubs[{index}].entry_location", f"Entry location '{entry_location}' is not a neighborhood in this pack.")
        modes = hub.get("modes")
        if not isinstance(modes, list) or not any(_stable_id(mode) for mode in modes):
            _issue(issues, "warning", "missing_hub_modes", f"travel_hubs[{index}].modes", "List at least one travel mode so the studio can explain this hub.")

    routes = _items(pack.get("inter_city"))
    _check_unique_ids(issues, records=routes, path="inter_city")
    if routes and not travel_hubs:
        _issue(issues, "error", "missing_travel_hubs", "travel_hubs", "Inter-city routes require destination-owned travel hubs.")
    for index, route in enumerate(routes):
        route_path = f"inter_city[{index}]"
        from_city = _stable_id(route.get("from_city") or route.get("from"))
        to_city = _stable_id(route.get("to_city") or route.get("to"))
        if city_id and from_city != city_id:
            _issue(issues, "error", "wrong_source_city", f"{route_path}.from", f"Route source '{from_city}' must match pack city '{city_id}'.")
        if not to_city:
            _issue(issues, "error", "missing_destination_city", f"{route_path}.to", "A route needs a destination city ID.")
        departure_hub_id = _stable_id(route.get("departure_hub_id"))
        if not departure_hub_id:
            _issue(issues, "error", "missing_departure_hub_id", f"{route_path}.departure_hub_id", "A route must reference a local departure hub ID.")
        elif departure_hub_id not in hub_ids:
            _issue(issues, "error", "unknown_departure_hub", f"{route_path}.departure_hub_id", f"Local travel hub '{departure_hub_id}' does not exist.")
        if not _stable_id(route.get("arrival_hub_id")):
            _issue(issues, "error", "missing_arrival_hub_id", f"{route_path}.arrival_hub_id", "A route must name the destination-owned arrival hub ID.")

    return CityPackValidationReport(tuple(issues))


def require_valid_city_pack(pack: Mapping[str, Any]) -> CityPackValidationReport:
    report = validate_city_pack(pack)
    if report.valid:
        return report
    summary = "; ".join(f"{issue.path}: {issue.message}" for issue in report.errors)
    raise ValueError(f"City pack validation failed: {summary}")
