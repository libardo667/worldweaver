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


def _check_unique_ids(
    issues: list[CityPackIssue],
    *,
    records: list[Mapping[str, Any]],
    path: str,
) -> set[str]:
    found: set[str] = set()
    for index, record in enumerate(records):
        record_id = _stable_id(record.get("id"))
        item_path = f"{path}[{index}].id"
        if not record_id:
            _issue(issues, "error", "missing_id", item_path, "A stable ID is required.")
            continue
        if not _STABLE_ID_RE.fullmatch(record_id):
            _issue(issues, "error", "invalid_id", item_path, "Use lowercase letters, numbers, hyphens, or underscores.")
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

    neighborhoods = _items(pack.get("neighborhoods"))
    if not neighborhoods:
        _issue(issues, "error", "missing_neighborhoods", "neighborhoods", "A city needs at least one neighborhood.")
    neighborhood_ids = _check_unique_ids(issues, records=neighborhoods, path="neighborhoods")
    neighborhood_names = {_stable_id(item.get("name")).lower() for item in neighborhoods if _stable_id(item.get("name"))}
    for index, neighborhood in enumerate(neighborhoods):
        for coordinate, minimum, maximum in (("lat", -90.0, 90.0), ("lon", -180.0, 180.0)):
            value = neighborhood.get(coordinate)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not minimum <= float(value) <= maximum:
                _issue(issues, "error", "invalid_coordinate", f"neighborhoods[{index}].{coordinate}", f"{coordinate} must be between {minimum:g} and {maximum:g}.")
        adjacent = neighborhood.get("adjacent_to")
        for adjacent_id in adjacent if isinstance(adjacent, list) else []:
            normalized = _stable_id(adjacent_id)
            if normalized and normalized not in neighborhood_ids:
                _issue(issues, "error", "unknown_neighborhood", f"neighborhoods[{index}].adjacent_to", f"Neighborhood '{normalized}' does not exist in this pack.")

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
