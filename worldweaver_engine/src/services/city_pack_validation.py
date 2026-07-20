# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Structured city-pack validation shared by the CLI and future City Studio."""

from __future__ import annotations

import hashlib
import json
import math
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


def _issue(
    issues: list[CityPackIssue], level: str, code: str, path: str, message: str
) -> None:
    issues.append(CityPackIssue(level=level, code=code, path=path, message=message))


def _check_coordinates(
    issues: list[CityPackIssue],
    *,
    record: Mapping[str, Any],
    path: str,
) -> None:
    for coordinate, minimum, maximum in (("lat", -90.0, 90.0), ("lon", -180.0, 180.0)):
        value = record.get(coordinate)
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not minimum <= float(value) <= maximum
        ):
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
    id_field: str = "id",
) -> set[str]:
    found: set[str] = set()
    for index, record in enumerate(records):
        record_id = _stable_id(record.get(id_field))
        item_path = f"{path}[{index}].{id_field}"
        if not record_id:
            _issue(issues, "error", "missing_id", item_path, "A stable ID is required.")
            continue
        if not _STABLE_ID_RE.fullmatch(record_id):
            _issue(
                issues,
                invalid_level,
                "invalid_id",
                item_path,
                "Use lowercase letters, numbers, hyphens, or underscores.",
            )
        if record_id in found:
            _issue(
                issues,
                "error",
                "duplicate_id",
                item_path,
                f"ID '{record_id}' is used more than once.",
            )
        found.add(record_id)
    return found


def _check_generated_map(
    issues: list[CityPackIssue],
    *,
    artifact: Mapping[str, Any],
    fictional: bool,
    city_id: str,
    neighborhoods: Sequence[Mapping[str, Any]],
) -> None:
    path = "generated_map"
    if not fictional:
        _issue(
            issues,
            "error",
            "generated_map_requires_fictional_pack",
            path,
            "Generated field maps are currently limited to declared fictional packs.",
        )
    if _stable_id(artifact.get("schema_version")) != "1.0.0":
        _issue(
            issues,
            "error",
            "unsupported_generated_map_schema",
            f"{path}.schema_version",
            "Generated maps must use schema version 1.0.0.",
        )

    generator = (
        artifact.get("generator")
        if isinstance(artifact.get("generator"), Mapping)
        else {}
    )
    for field in ("id", "version", "seed"):
        if not _stable_id(generator.get(field)):
            _issue(
                issues,
                "error",
                "missing_generated_map_generator",
                f"{path}.generator.{field}",
                f"Generated map generator {field} is required.",
            )

    source = (
        artifact.get("source") if isinstance(artifact.get("source"), Mapping) else {}
    )
    if city_id and _stable_id(source.get("city_id")) != city_id:
        _issue(
            issues,
            "error",
            "generated_map_city_mismatch",
            f"{path}.source.city_id",
            "Generated map source city must match the pack city.",
        )

    grid = artifact.get("grid") if isinstance(artifact.get("grid"), Mapping) else {}
    width = grid.get("width")
    height = grid.get("height")
    section_size = grid.get("section_size")
    if not isinstance(width, int) or isinstance(width, bool) or not 24 <= width <= 192:
        _issue(
            issues,
            "error",
            "invalid_generated_map_grid",
            f"{path}.grid.width",
            "Generated map width must be an integer between 24 and 192.",
        )
    if (
        not isinstance(height, int)
        or isinstance(height, bool)
        or not 24 <= height <= 192
    ):
        _issue(
            issues,
            "error",
            "invalid_generated_map_grid",
            f"{path}.grid.height",
            "Generated map height must be an integer between 24 and 192.",
        )
    if (
        not isinstance(section_size, int)
        or isinstance(section_size, bool)
        or not 8 <= section_size <= 48
    ):
        _issue(
            issues,
            "error",
            "invalid_generated_map_section_size",
            f"{path}.grid.section_size",
            "Generated map section size must be an integer between 8 and 48.",
        )

    fields = (
        artifact.get("fields") if isinstance(artifact.get("fields"), Mapping) else {}
    )
    required_fields = {"elevation", "slope", "water_flow", "wetness", "soil", "region"}
    for field_name in sorted(required_fields):
        field = (
            fields.get(field_name)
            if isinstance(fields.get(field_name), Mapping)
            else {}
        )
        rows = field.get("rows")
        if not isinstance(rows, list) or (
            isinstance(height, int) and len(rows) != height
        ):
            _issue(
                issues,
                "error",
                "invalid_generated_map_field",
                f"{path}.fields.{field_name}.rows",
                f"Field '{field_name}' must contain one encoded row per grid row.",
            )
        if not re.fullmatch(r"[a-f0-9]{64}", _stable_id(field.get("sha256"))):
            _issue(
                issues,
                "error",
                "missing_generated_map_field_hash",
                f"{path}.fields.{field_name}.sha256",
                f"Field '{field_name}' needs a SHA-256 hash.",
            )
        elif isinstance(rows, list) and all(isinstance(row, str) for row in rows):
            expected_hash = hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()
            if field.get("sha256") != expected_hash:
                _issue(
                    issues,
                    "error",
                    "generated_map_field_hash_mismatch",
                    f"{path}.fields.{field_name}.sha256",
                    f"Field '{field_name}' does not match its SHA-256 hash.",
                )

        if isinstance(rows, list) and isinstance(width, int):
            expected_length = (
                width * 2
                if field_name in {"elevation", "slope", "water_flow", "wetness"}
                else width
            )
            if any(
                not isinstance(row, str)
                or len(row) != expected_length
                or not re.fullmatch(r"[a-f0-9]+", row)
                for row in rows
            ):
                _issue(
                    issues,
                    "error",
                    "invalid_generated_map_field_encoding",
                    f"{path}.fields.{field_name}.rows",
                    f"Field '{field_name}' contains a malformed encoded row.",
                )

    sections = _items(artifact.get("sections"))
    _check_unique_ids(issues, records=sections, path=f"{path}.sections")
    if not sections:
        _issue(
            issues,
            "error",
            "missing_generated_map_sections",
            f"{path}.sections",
            "A generated map needs at least one independently seeded section.",
        )
    for index, section in enumerate(sections):
        if not _stable_id(section.get("seed")):
            _issue(
                issues,
                "error",
                "missing_generated_map_section_seed",
                f"{path}.sections[{index}].seed",
                "Each map section needs a stable seed.",
            )
        revision = section.get("revision")
        if (
            not isinstance(revision, int)
            or isinstance(revision, bool)
            or not 0 <= revision <= 9999
        ):
            _issue(
                issues,
                "error",
                "invalid_generated_map_section_revision",
                f"{path}.sections[{index}].revision",
                "Each map section needs a bounded integer revision.",
            )
        if not isinstance(section.get("locked"), bool):
            _issue(
                issues,
                "error",
                "invalid_generated_map_section_lock",
                f"{path}.sections[{index}].locked",
                "Each map section needs an explicit lock state.",
            )
        connectors = section.get("connectors")
        if not isinstance(connectors, list):
            _issue(
                issues,
                "error",
                "invalid_generated_map_connectors",
                f"{path}.sections[{index}].connectors",
                "Section connectors must be a list.",
            )
        if not isinstance(section.get("seam_ids"), list):
            _issue(
                issues,
                "error",
                "invalid_generated_map_seam_ids",
                f"{path}.sections[{index}].seam_ids",
                "Section seam IDs must be a list.",
            )
        detail = (
            section.get("detail") if isinstance(section.get("detail"), Mapping) else {}
        )
        features = detail.get("features")
        detail_hash = _stable_id(detail.get("sha256"))
        expected_detail_hash = hashlib.sha256(
            json.dumps(
                {"features": features},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        if not isinstance(features, list) or detail_hash != expected_detail_hash:
            _issue(
                issues,
                "error",
                "invalid_generated_map_section_detail",
                f"{path}.sections[{index}].detail",
                "Section detail must match its recorded hash.",
            )

    section_ids = {_stable_id(section.get("id")) for section in sections}
    seams = _items(artifact.get("seams"))
    seam_ids = [_stable_id(seam.get("id")) for seam in seams]
    if len(seam_ids) != len(set(seam_ids)):
        _issue(
            issues,
            "error",
            "duplicate_generated_map_seam",
            f"{path}.seams",
            "Generated seam IDs must be unique.",
        )
    if (
        isinstance(width, int)
        and isinstance(height, int)
        and isinstance(section_size, int)
        and section_size > 0
    ):
        columns = math.ceil(width / section_size)
        rows_count = math.ceil(height / section_size)
        expected_seam_count = (columns - 1) * rows_count + (rows_count - 1) * columns
        if len(seams) != expected_seam_count:
            _issue(
                issues,
                "error",
                "missing_generated_map_seams",
                f"{path}.seams",
                "Generated sections must share one seam record for every internal border.",
            )
    seams_by_section: dict[str, set[str]] = {
        section_id: set() for section_id in section_ids
    }
    connectors_by_section: dict[str, list[dict[str, Any]]] = {
        section_id: [] for section_id in section_ids
    }
    for index, seam in enumerate(seams):
        seam_path = f"{path}.seams[{index}]"
        sides = _items(seam.get("sides"))
        side_ids = [_stable_id(side.get("section_id")) for side in sides]
        if (
            len(sides) != 2
            or len(set(side_ids)) != 2
            or any(section_id not in section_ids for section_id in side_ids)
        ):
            _issue(
                issues,
                "error",
                "invalid_generated_map_seam_sides",
                f"{seam_path}.sides",
                "A seam must join exactly two known sections.",
            )
        connectors = _items(seam.get("connectors"))
        for side in sides:
            section_id = _stable_id(side.get("section_id"))
            if section_id in seams_by_section:
                seams_by_section[section_id].add(_stable_id(seam.get("id")))
                connectors_by_section[section_id].extend(
                    {
                        **connector,
                        "edge": _stable_id(side.get("edge")),
                        "seam_id": _stable_id(seam.get("id")),
                    }
                    for connector in connectors
                )
        length = seam.get("length")
        elevation_bands = seam.get("elevation_bands")
        transitions = seam.get("region_transitions")
        if (
            not isinstance(length, int)
            or not isinstance(elevation_bands, str)
            or len(elevation_bands) != length
            or not isinstance(transitions, list)
            or len(transitions) != length
        ):
            _issue(
                issues,
                "error",
                "invalid_generated_map_seam_fields",
                seam_path,
                "A seam's terrain and region bands must cover its full shared edge.",
            )
        seam_hash = _stable_id(seam.get("sha256"))
        hash_payload = dict(seam)
        hash_payload.pop("sha256", None)
        expected_seam_hash = hashlib.sha256(
            json.dumps(
                hash_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
        ).hexdigest()
        if seam_hash != expected_seam_hash:
            _issue(
                issues,
                "error",
                "generated_map_seam_hash_mismatch",
                f"{seam_path}.sha256",
                "A generated map seam does not match its recorded hash.",
            )
    for index, section in enumerate(sections):
        recorded = (
            {_stable_id(value) for value in section.get("seam_ids", [])}
            if isinstance(section.get("seam_ids"), list)
            else set()
        )
        if recorded != seams_by_section.get(_stable_id(section.get("id")), set()):
            _issue(
                issues,
                "error",
                "generated_map_section_seam_mismatch",
                f"{path}.sections[{index}].seam_ids",
                "A section must name every shared seam exactly once.",
            )
        recorded_connectors = section.get("connectors")
        expected_connectors = connectors_by_section.get(
            _stable_id(section.get("id")), []
        )
        if recorded_connectors != expected_connectors:
            _issue(
                issues,
                "error",
                "generated_map_section_connector_mismatch",
                f"{path}.sections[{index}].connectors",
                "A section must copy its shared feature crossings from the seam record.",
            )

    anchors = _items(artifact.get("anchors"))
    if not anchors or not all(bool(item.get("required")) for item in anchors):
        _issue(
            issues,
            "error",
            "missing_generated_map_anchors",
            f"{path}.anchors",
            "Every compiled city-pack anchor must be recorded as required.",
        )
    anchor_ids = {_stable_id(anchor.get("id")) for anchor in anchors}

    expected_route_ids: set[str] = set()
    for neighborhood in neighborhoods:
        source_id = _stable_id(neighborhood.get("id"))
        adjacent = (
            neighborhood.get("adjacent_to")
            if isinstance(neighborhood.get("adjacent_to"), list)
            else []
        )
        for adjacent_id in adjacent:
            pair = tuple(sorted((source_id, _stable_id(adjacent_id))))
            if pair[0] and pair[1] and pair[0] != pair[1]:
                expected_route_ids.add(f"path:{pair[0]}:{pair[1]}")
    routes = _items(artifact.get("routes"))
    route_ids = [_stable_id(route.get("id")) for route in routes]
    if len(route_ids) != len(set(route_ids)):
        _issue(
            issues,
            "error",
            "duplicate_generated_map_route",
            f"{path}.routes",
            "Generated route IDs must be unique.",
        )
    if set(route_ids) != expected_route_ids:
        _issue(
            issues,
            "error",
            "generated_map_route_mismatch",
            f"{path}.routes",
            "Generated routes must exactly match the city pack's canonical neighborhood paths.",
        )
    for index, route in enumerate(routes):
        route_path = f"{path}.routes[{index}]"
        if _stable_id(route.get("kind")) != "path":
            _issue(
                issues,
                "error",
                "invalid_generated_map_route_kind",
                f"{route_path}.kind",
                "A generated route must remain a canonical path.",
            )
        if not _stable_id(route.get("name")) or not _stable_id(route.get("path_type")):
            _issue(
                issues,
                "error",
                "missing_generated_map_route_style",
                route_path,
                "A generated path needs a display name and path type.",
            )
        via = route.get("via") if isinstance(route.get("via"), list) else []
        if any(_stable_id(anchor_id) not in anchor_ids for anchor_id in via):
            _issue(
                issues,
                "error",
                "unknown_generated_map_route_anchor",
                f"{route_path}.via",
                "A generated path waypoint must be a required city-pack anchor.",
            )
        points = route.get("points") if isinstance(route.get("points"), list) else []
        if len(points) != len(via) + 2:
            _issue(
                issues,
                "error",
                "invalid_generated_map_route_points",
                f"{route_path}.points",
                "A generated path needs one point for each endpoint and required waypoint.",
            )

    claimed_hash = _stable_id(artifact.get("artifact_sha256"))
    if not re.fullmatch(r"[a-f0-9]{64}", claimed_hash):
        _issue(
            issues,
            "error",
            "missing_generated_map_hash",
            f"{path}.artifact_sha256",
            "The generated map artifact needs a SHA-256 hash.",
        )
    else:
        hash_payload = dict(artifact)
        hash_payload.pop("artifact_sha256", None)
        expected_hash = hashlib.sha256(
            json.dumps(
                hash_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
        ).hexdigest()
        if claimed_hash != expected_hash:
            _issue(
                issues,
                "error",
                "generated_map_hash_mismatch",
                f"{path}.artifact_sha256",
                "The generated map artifact does not match its SHA-256 hash.",
            )


def validate_city_pack(pack: Mapping[str, Any]) -> CityPackValidationReport:
    """Return UI-ready errors and warnings without changing the supplied pack."""
    issues: list[CityPackIssue] = []
    manifest = pack.get("manifest") if isinstance(pack.get("manifest"), Mapping) else {}
    city_id = _stable_id(manifest.get("city_id"))
    if not city_id:
        _issue(
            issues,
            "error",
            "missing_city_id",
            "manifest.city_id",
            "The pack needs a stable city ID.",
        )
    elif not _STABLE_ID_RE.fullmatch(city_id):
        _issue(
            issues,
            "error",
            "invalid_city_id",
            "manifest.city_id",
            "Use lowercase letters, numbers, hyphens, or underscores.",
        )
    if not _stable_id(manifest.get("schema_version")):
        _issue(
            issues,
            "warning",
            "missing_schema_version",
            "manifest.schema_version",
            "Legacy pack: add an explicit schema version when it is rebuilt.",
        )
    if not _stable_id(manifest.get("version")):
        _issue(
            issues,
            "error",
            "missing_pack_version",
            "manifest.version",
            "A published pack needs an explicit version.",
        )
    fictional = manifest.get("fictional", False)
    if not isinstance(fictional, bool):
        _issue(
            issues,
            "error",
            "invalid_fictional_flag",
            "manifest.fictional",
            "The fictional marker must be true or false.",
        )
    if fictional and "openstreetmap" in _stable_id(manifest.get("source")).lower():
        _issue(
            issues,
            "error",
            "fictional_osm_source",
            "manifest.source",
            "A fictional pack must not claim OpenStreetMap as its geography source.",
        )
    place_reference_level = "error" if fictional is True else "warning"

    neighborhoods = _items(pack.get("neighborhoods"))
    if not neighborhoods:
        _issue(
            issues,
            "error",
            "missing_neighborhoods",
            "neighborhoods",
            "A city needs at least one neighborhood.",
        )
    neighborhood_ids = _check_unique_ids(
        issues, records=neighborhoods, path="neighborhoods"
    )
    neighborhood_names = {
        _stable_id(item.get("name")).lower()
        for item in neighborhoods
        if _stable_id(item.get("name"))
    }
    for index, neighborhood in enumerate(neighborhoods):
        _check_coordinates(issues, record=neighborhood, path=f"neighborhoods[{index}]")
        adjacent = neighborhood.get("adjacent_to")
        for adjacent_id in adjacent if isinstance(adjacent, list) else []:
            normalized = _stable_id(adjacent_id)
            if normalized and normalized not in neighborhood_ids:
                _issue(
                    issues,
                    "error",
                    "unknown_neighborhood",
                    f"neighborhoods[{index}].adjacent_to",
                    f"Neighborhood '{normalized}' does not exist in this pack.",
                )

    generated_map = (
        pack.get("generated_map")
        if isinstance(pack.get("generated_map"), Mapping)
        else None
    )
    if generated_map is not None:
        _check_generated_map(
            issues,
            artifact=generated_map,
            fictional=fictional is True,
            city_id=city_id,
            neighborhoods=neighborhoods,
        )

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

    exact_place_names = {
        _stable_id(item.get("name"))
        for item in [*neighborhoods, *landmarks]
        if _stable_id(item.get("name"))
    }
    stoops = _items(pack.get("stoops"))
    _check_unique_ids(
        issues,
        records=stoops,
        path="stoops",
        id_field="stoop_id",
    )
    for index, stoop in enumerate(stoops):
        stoop_path = f"stoops[{index}]"
        location = _stable_id(stoop.get("location"))
        if not location:
            _issue(
                issues,
                "error",
                "missing_stoop_location",
                f"{stoop_path}.location",
                "A stoop needs an exact local place.",
            )
        elif location not in exact_place_names:
            _issue(
                issues,
                "error",
                "unknown_stoop_location",
                f"{stoop_path}.location",
                f"Place '{location}' does not exist in this pack.",
            )
        capacity = stoop.get("capacity")
        if (
            not isinstance(capacity, int)
            or isinstance(capacity, bool)
            or not 1 <= capacity <= 50
        ):
            _issue(
                issues,
                "error",
                "invalid_stoop_capacity",
                f"{stoop_path}.capacity",
                "Stoop capacity must be between 1 and 50.",
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
                    _issue(
                        issues,
                        "error",
                        "duplicate_id",
                        system_path,
                        f"Transit ID '{station_id}' is used in more than one system.",
                    )
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
                for connected_id in (
                    connections if isinstance(connections, list) else []
                ):
                    transit_references.append(
                        (f"{station_path}.connects_to", _stable_id(connected_id))
                    )
        for path, connected_id in transit_references:
            if connected_id and connected_id not in transit_ids:
                _issue(
                    issues,
                    "error",
                    "unknown_transit_stop",
                    path,
                    f"Transit stop '{connected_id}' does not exist in this pack.",
                )

    travel_hubs = _items(pack.get("travel_hubs"))
    hub_ids = _check_unique_ids(issues, records=travel_hubs, path="travel_hubs")
    for index, hub in enumerate(travel_hubs):
        entry_location = _stable_id(hub.get("entry_location"))
        if not entry_location:
            _issue(
                issues,
                "error",
                "missing_entry_location",
                f"travel_hubs[{index}].entry_location",
                "A travel hub must enter through a local neighborhood.",
            )
        elif (
            entry_location not in neighborhood_ids
            and entry_location.lower() not in neighborhood_names
        ):
            _issue(
                issues,
                "error",
                "unknown_entry_location",
                f"travel_hubs[{index}].entry_location",
                f"Entry location '{entry_location}' is not a neighborhood in this pack.",
            )
        modes = hub.get("modes")
        if not isinstance(modes, list) or not any(_stable_id(mode) for mode in modes):
            _issue(
                issues,
                "warning",
                "missing_hub_modes",
                f"travel_hubs[{index}].modes",
                "List at least one travel mode so the studio can explain this hub.",
            )

    routes = _items(pack.get("inter_city"))
    _check_unique_ids(issues, records=routes, path="inter_city")
    if routes and not travel_hubs:
        _issue(
            issues,
            "error",
            "missing_travel_hubs",
            "travel_hubs",
            "Inter-city routes require destination-owned travel hubs.",
        )
    for index, route in enumerate(routes):
        route_path = f"inter_city[{index}]"
        from_city = _stable_id(route.get("from_city") or route.get("from"))
        to_city = _stable_id(route.get("to_city") or route.get("to"))
        if city_id and from_city != city_id:
            _issue(
                issues,
                "error",
                "wrong_source_city",
                f"{route_path}.from",
                f"Route source '{from_city}' must match pack city '{city_id}'.",
            )
        if not to_city:
            _issue(
                issues,
                "error",
                "missing_destination_city",
                f"{route_path}.to",
                "A route needs a destination city ID.",
            )
        departure_hub_id = _stable_id(route.get("departure_hub_id"))
        if not departure_hub_id:
            _issue(
                issues,
                "error",
                "missing_departure_hub_id",
                f"{route_path}.departure_hub_id",
                "A route must reference a local departure hub ID.",
            )
        elif departure_hub_id not in hub_ids:
            _issue(
                issues,
                "error",
                "unknown_departure_hub",
                f"{route_path}.departure_hub_id",
                f"Local travel hub '{departure_hub_id}' does not exist.",
            )
        if not _stable_id(route.get("arrival_hub_id")):
            _issue(
                issues,
                "error",
                "missing_arrival_hub_id",
                f"{route_path}.arrival_hub_id",
                "A route must name the destination-owned arrival hub ID.",
            )

    return CityPackValidationReport(tuple(issues))


def require_valid_city_pack(pack: Mapping[str, Any]) -> CityPackValidationReport:
    report = validate_city_pack(pack)
    if report.valid:
        return report
    summary = "; ".join(f"{issue.path}: {issue.message}" for issue in report.errors)
    raise ValueError(f"City pack validation failed: {summary}")
