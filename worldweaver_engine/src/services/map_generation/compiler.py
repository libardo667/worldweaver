# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Compile physical fields and local sections into one stable fictional map.

The compiler deliberately produces a drawing *from* the city pack. It never
adds movement edges, doors, or other engine affordances.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from html import escape
from typing import Any, Mapping, Sequence

GENERATOR_ID = "worldweaver.field-map"
GENERATOR_VERSION = "0.1.0"
ARTIFACT_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class CompiledFictionalMap:
    artifact: dict[str, Any]
    svg: str


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _digest(*parts: object) -> bytes:
    payload = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(payload).digest()


def _unit(*parts: object) -> float:
    return int.from_bytes(_digest(*parts)[:8], "big") / float((1 << 64) - 1)


def _smooth(value: float) -> float:
    return value * value * (3.0 - 2.0 * value)


def _value_noise(seed: str, x: float, y: float, scale: float) -> float:
    safe_scale = max(1.0, float(scale))
    sx = x / safe_scale
    sy = y / safe_scale
    x0 = math.floor(sx)
    y0 = math.floor(sy)
    tx = _smooth(sx - x0)
    ty = _smooth(sy - y0)
    a = _unit(seed, x0, y0)
    b = _unit(seed, x0 + 1, y0)
    c = _unit(seed, x0, y0 + 1)
    d = _unit(seed, x0 + 1, y0 + 1)
    top = a + (b - a) * tx
    bottom = c + (d - c) * tx
    return top + (bottom - top) * ty


def _fractal_noise(seed: str, x: float, y: float, scale: float, octaves: int = 4) -> float:
    total = 0.0
    amplitude = 1.0
    weight = 0.0
    current_scale = max(1.0, float(scale))
    for octave in range(max(1, min(6, int(octaves)))):
        total += _value_noise(f"{seed}:{octave}", x, y, current_scale) * amplitude
        weight += amplitude
        amplitude *= 0.5
        current_scale = max(1.0, current_scale / 2.0)
    return total / weight


def _bounds(config: Mapping[str, Any]) -> dict[str, float]:
    raw = config.get("bboxes") if isinstance(config.get("bboxes"), Mapping) else {}
    parts = str(raw.get("default") or "").split(",")
    if len(parts) != 4:
        raise ValueError("fictional map generation requires bboxes.default")
    south, west, north, east = (float(part) for part in parts)
    if not south < north or not west < east:
        raise ValueError("fictional map bounds must have positive width and height")
    return {"south": south, "west": west, "north": north, "east": east}


def _validate_projected_aspect(bounds: Mapping[str, float], *, width: int, height: int) -> None:
    """Keep square generator cells square when Leaflet projects the SVG."""
    south_y = math.asinh(math.tan(math.radians(bounds["south"])))
    north_y = math.asinh(math.tan(math.radians(bounds["north"])))
    projected_width = math.radians(bounds["east"] - bounds["west"])
    projected_height = north_y - south_y
    actual = projected_width / projected_height
    expected = width / height
    if abs(actual / expected - 1.0) > 0.02:
        raise ValueError("fictional map bounds must match the grid aspect after Web Mercator projection " f"(expected {expected:.3f}, got {actual:.3f})")


def _grid_point(lat: float, lon: float, *, bounds: Mapping[str, float], width: int, height: int) -> tuple[float, float]:
    x = (float(lon) - bounds["west"]) / (bounds["east"] - bounds["west"]) * width
    y = (bounds["north"] - float(lat)) / (bounds["north"] - bounds["south"]) * height
    return (_clamp(x, 0.0, width - 0.001), _clamp(y, 0.0, height - 0.001))


def _anchors(
    neighborhoods: Sequence[Mapping[str, Any]],
    landmarks: Sequence[Mapping[str, Any]],
    *,
    bounds: Mapping[str, float],
    width: int,
    height: int,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for kind, records in (("neighborhood", neighborhoods), ("landmark", landmarks)):
        for record in records:
            if not isinstance(record.get("lat"), (int, float)) or not isinstance(record.get("lon"), (int, float)):
                continue
            x, y = _grid_point(float(record["lat"]), float(record["lon"]), bounds=bounds, width=width, height=height)
            result.append(
                {
                    "id": str(record.get("id") or "").strip(),
                    "name": str(record.get("name") or record.get("id") or "").strip(),
                    "kind": kind,
                    "type": str(record.get("type") or kind).strip(),
                    "parent_id": str(record.get("neighborhood") or "").strip() or None,
                    "x": round(x, 3),
                    "y": round(y, 3),
                    "required": True,
                }
            )
    return sorted(result, key=lambda item: (item["kind"], item["id"]))


def _routes(neighborhoods: Sequence[Mapping[str, Any]], anchors: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    points = {str(item.get("id") or ""): item for item in anchors if item.get("kind") == "neighborhood"}
    found: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for record in neighborhoods:
        source = str(record.get("id") or "").strip()
        for raw_target in record.get("adjacent_to", []) if isinstance(record.get("adjacent_to"), list) else []:
            target = str(raw_target or "").strip()
            pair = tuple(sorted((source, target)))
            if not source or not target or source == target or pair in found or source not in points or target not in points:
                continue
            found.add(pair)
            result.append(
                {
                    "id": f"path:{pair[0]}:{pair[1]}",
                    "kind": "path",
                    "from": pair[0],
                    "to": pair[1],
                    "points": [[points[pair[0]]["x"], points[pair[0]]["y"]], [points[pair[1]]["x"], points[pair[1]]["y"]]],
                }
            )
    return sorted(result, key=lambda item: item["id"])


def _piecewise(points: Sequence[Sequence[float]], t: float) -> float:
    if not points:
        return 0.5
    ordered = sorted((float(point[0]), float(point[1])) for point in points)
    if t <= ordered[0][0]:
        return ordered[0][1]
    if t >= ordered[-1][0]:
        return ordered[-1][1]
    for (x0, y0), (x1, y1) in zip(ordered, ordered[1:]):
        if x0 <= t <= x1:
            local = (t - x0) / max(1e-9, x1 - x0)
            return y0 + (y1 - y0) * _smooth(local)
    return ordered[-1][1]


def _waterways(source: Mapping[str, Any], *, seed: str, width: int, height: int) -> list[dict[str, Any]]:
    raw_waterways = source.get("waterways") if isinstance(source.get("waterways"), list) else []
    waterways: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_waterways):
        if not isinstance(raw, Mapping):
            continue
        waterway_id = str(raw.get("id") or f"waterway-{index + 1}").strip()
        control_points = raw.get("points") if isinstance(raw.get("points"), list) else [[0.0, 0.5], [1.0, 0.5]]
        meander = max(0.0, min(0.2, float(raw.get("meander") or 0.0)))
        path: list[list[float]] = []
        for x in range(width):
            t = x / max(1, width - 1)
            base_y = _piecewise(control_points, t)
            wiggle = (_fractal_noise(f"{seed}:{waterway_id}:meander", x, 0.0, max(5.0, width / 7.0), 3) - 0.5) * meander * math.sin(math.pi * t)
            y = _clamp(base_y + wiggle, 0.02, 0.98) * (height - 1)
            path.append([round(float(x), 3), round(y, 3)])
        waterways.append(
            {
                "id": waterway_id,
                "name": str(raw.get("name") or waterway_id.replace("-", " ").title()),
                "kind": str(raw.get("kind") or "river"),
                "width_cells": round(max(1.0, min(8.0, float(raw.get("width_cells") or 2.0))), 3),
                "points": path,
            }
        )
    return waterways


def _river_distance(x: int, y: int, waterways: Sequence[Mapping[str, Any]]) -> float:
    distances: list[float] = []
    for waterway in waterways:
        points = waterway.get("points") if isinstance(waterway.get("points"), list) else []
        if not points:
            continue
        point = points[min(x, len(points) - 1)]
        distances.append(abs(float(y) - float(point[1])))
    return min(distances) if distances else 1_000_000.0


def _elevation_grid(
    source: Mapping[str, Any],
    *,
    seed: str,
    width: int,
    height: int,
    waterways: Sequence[Mapping[str, Any]],
) -> list[list[float]]:
    terrain = source.get("terrain") if isinstance(source.get("terrain"), Mapping) else {}
    scale = float(terrain.get("noise_scale") or max(width, height) / 4.5)
    relief = _clamp(float(terrain.get("relief") or 0.32), 0.05, 0.7)
    base = _clamp(float(terrain.get("base_elevation") or 0.46), 0.1, 0.9)
    west_rise = float(terrain.get("west_rise") or 0.18)
    north_rise = float(terrain.get("north_rise") or 0.10)
    grid: list[list[float]] = []
    for y in range(height):
        row: list[float] = []
        for x in range(width):
            noise = _fractal_noise(f"{seed}:elevation", x, y, scale, 4) - 0.5
            elevation = base + noise * relief + (1.0 - x / max(1, width - 1)) * west_rise + (1.0 - y / max(1, height - 1)) * north_rise
            if waterways:
                distance = _river_distance(x, y, waterways)
                progress = x / max(1, width - 1)
                valley_floor = 0.31 - progress * 0.06
                valley_ceiling = valley_floor + min(0.28, distance * 0.035)
                elevation = min(elevation, valley_ceiling)
            row.append(_clamp(elevation))
        grid.append(row)
    return grid


def _slope_grid(elevation: Sequence[Sequence[float]], *, width: int, height: int) -> list[list[float]]:
    result: list[list[float]] = []
    for y in range(height):
        row: list[float] = []
        for x in range(width):
            left = elevation[y][max(0, x - 1)]
            right = elevation[y][min(width - 1, x + 1)]
            up = elevation[max(0, y - 1)][x]
            down = elevation[min(height - 1, y + 1)][x]
            row.append(_clamp(math.hypot(right - left, down - up) * 3.2))
        result.append(row)
    return result


def _flow_grid(elevation: Sequence[Sequence[float]], *, seed: str, width: int, height: int) -> list[list[float]]:
    accumulation = [[0.75 + _unit(seed, "rain", x, y) * 0.5 for x in range(width)] for y in range(height)]
    ordered = sorted(((float(elevation[y][x]), x, y) for y in range(height) for x in range(width)), reverse=True)
    for current, x, y in ordered:
        lowest: tuple[float, int, int] | None = None
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if not 0 <= nx < width or not 0 <= ny < height:
                    continue
                candidate = float(elevation[ny][nx])
                if candidate >= current - 1e-9:
                    continue
                if lowest is None or candidate < lowest[0]:
                    lowest = (candidate, nx, ny)
        if lowest is not None:
            accumulation[lowest[2]][lowest[1]] += accumulation[y][x]
    maximum = max(max(row) for row in accumulation)
    denominator = math.log1p(maximum)
    return [[_clamp(math.log1p(value) / denominator) for value in row] for row in accumulation]


def _wetness_grid(
    elevation: Sequence[Sequence[float]],
    flow: Sequence[Sequence[float]],
    *,
    width: int,
    height: int,
    waterways: Sequence[Mapping[str, Any]],
) -> list[list[float]]:
    result: list[list[float]] = []
    for y in range(height):
        row: list[float] = []
        for x in range(width):
            river_pull = math.exp(-_river_distance(x, y, waterways) / 3.0) if waterways else 0.0
            wetness = river_pull * 0.58 + float(flow[y][x]) * 0.27 + (1.0 - float(elevation[y][x])) * 0.15
            row.append(_clamp(wetness))
        result.append(row)
    return result


def _nearest_neighborhood(x: int, y: int, anchors: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any] | None, float]:
    nearest: Mapping[str, Any] | None = None
    distance = float("inf")
    for anchor in anchors:
        if anchor.get("kind") != "neighborhood":
            continue
        candidate = math.hypot(float(anchor["x"]) - x, float(anchor["y"]) - y)
        if candidate < distance:
            nearest = anchor
            distance = candidate
    return nearest, distance


def _categorical_fields(
    source: Mapping[str, Any],
    *,
    seed: str,
    width: int,
    height: int,
    anchors: Sequence[Mapping[str, Any]],
    elevation: Sequence[Sequence[float]],
    slope: Sequence[Sequence[float]],
    wetness: Sequence[Sequence[float]],
    waterways: Sequence[Mapping[str, Any]],
) -> tuple[list[list[str]], list[list[str]]]:
    anchor_regions = source.get("anchor_regions") if isinstance(source.get("anchor_regions"), Mapping) else {}
    radius = max(2.0, min(16.0, float(source.get("anchor_region_radius") or min(width, height) / 7.0)))
    soils: list[list[str]] = []
    regions: list[list[str]] = []
    for y in range(height):
        soil_row: list[str] = []
        region_row: list[str] = []
        for x in range(width):
            distance = _river_distance(x, y, waterways)
            water_width = max((float(item.get("width_cells") or 2.0) for item in waterways), default=0.0)
            local_noise = _fractal_noise(f"{seed}:cover", x, y, max(4.0, width / 10.0), 3)
            if distance <= water_width / 2.0:
                soil = "water"
            elif float(wetness[y][x]) > 0.72:
                soil = "wet_alluvial"
            elif float(wetness[y][x]) > 0.42 and float(slope[y][x]) < 0.28:
                soil = "alluvial_loam"
            elif float(elevation[y][x]) > 0.69 or float(slope[y][x]) > 0.42:
                soil = "thin_rocky"
            elif local_noise > 0.56:
                soil = "woodland_floor"
            else:
                soil = "well_drained_loam"

            nearest, anchor_distance = _nearest_neighborhood(x, y, anchors)
            desired = str(anchor_regions.get(str((nearest or {}).get("id") or "")) or "").strip()
            if soil == "water":
                region = "water"
            elif distance <= water_width / 2.0 + 2.2:
                region = "riverbank"
            elif nearest is not None and anchor_distance <= radius and desired:
                if desired == "cultivated" and soil in {"thin_rocky", "wet_alluvial"}:
                    region = "meadow"
                else:
                    region = desired
            elif soil in {"thin_rocky", "woodland_floor"} and local_noise > 0.45:
                region = "woodland"
            elif soil in {"alluvial_loam", "well_drained_loam"} and float(slope[y][x]) < 0.22:
                region = "meadow"
            else:
                region = "rough_ground"
            soil_row.append(soil)
            region_row.append(region)
        soils.append(soil_row)
        regions.append(region_row)
    return soils, regions


def _line_cells(points: Sequence[Sequence[float]], width: int, height: int) -> set[tuple[int, int]]:
    if len(points) < 2:
        return set()
    (x0, y0), (x1, y1) = points[0], points[-1]
    steps = max(1, int(max(abs(float(x1) - float(x0)), abs(float(y1) - float(y0))) * 3))
    return {
        (
            max(0, min(width - 1, int(round(float(x0) + (float(x1) - float(x0)) * index / steps)))),
            max(0, min(height - 1, int(round(float(y0) + (float(y1) - float(y0)) * index / steps)))),
        )
        for index in range(steps + 1)
    }


def _sections(
    *,
    seed: str,
    width: int,
    height: int,
    section_size: int,
    waterways: Sequence[Mapping[str, Any]],
    routes: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    feature_cells: list[tuple[str, str, set[tuple[int, int]]]] = []
    for waterway in waterways:
        points = waterway.get("points") if isinstance(waterway.get("points"), list) else []
        feature_cells.append((str(waterway.get("id") or "waterway"), str(waterway.get("kind") or "river"), {(int(round(float(point[0]))), int(round(float(point[1])))) for point in points}))
    for route in routes:
        points = route.get("points") if isinstance(route.get("points"), list) else []
        feature_cells.append((str(route.get("id") or "path"), "path", _line_cells(points, width, height)))

    result: list[dict[str, Any]] = []
    for sy in range(0, height, section_size):
        for sx in range(0, width, section_size):
            section_width = min(section_size, width - sx)
            section_height = min(section_size, height - sy)
            connectors: list[dict[str, Any]] = []
            for feature_id, kind, cells in feature_cells:
                candidates: set[tuple[str, int]] = set()
                for x, y in cells:
                    if not sx <= x < sx + section_width or not sy <= y < sy + section_height:
                        continue
                    if y == sy:
                        candidates.add(("north", x - sx))
                    if y == sy + section_height - 1:
                        candidates.add(("south", x - sx))
                    if x == sx:
                        candidates.add(("west", y - sy))
                    if x == sx + section_width - 1:
                        candidates.add(("east", y - sy))
                for edge, offset in sorted(candidates):
                    connectors.append({"feature_id": feature_id, "kind": kind, "edge": edge, "offset": offset})
            section_id = f"section-{sx // section_size}-{sy // section_size}"
            result.append(
                {
                    "id": section_id,
                    "x": sx,
                    "y": sy,
                    "width": section_width,
                    "height": section_height,
                    "seed": hashlib.sha256(f"{seed}:{section_id}".encode()).hexdigest()[:16],
                    "locked": False,
                    "connectors": connectors,
                }
            )
    return result


def _u8_field(values: Sequence[Sequence[float]]) -> dict[str, Any]:
    rows = ["".join(f"{round(_clamp(float(value)) * 255):02x}" for value in row) for row in values]
    return {"encoding": "hex-u8-rows", "rows": rows, "sha256": hashlib.sha256("\n".join(rows).encode()).hexdigest()}


def _category_field(values: Sequence[Sequence[str]], palette: Sequence[str]) -> dict[str, Any]:
    if len(palette) > 16:
        raise ValueError("categorical map fields support at most 16 values")
    indices = {name: index for index, name in enumerate(palette)}
    rows = ["".join(format(indices[value], "x") for value in row) for row in values]
    return {"encoding": "hex-palette-index-rows", "palette": list(palette), "rows": rows, "sha256": hashlib.sha256("\n".join(rows).encode()).hexdigest()}


_REGION_COLORS = {
    "water": "#7ca6ad",
    "riverbank": "#a8b99b",
    "village": "#c9b78f",
    "working": "#b8a486",
    "cultivated": "#c8bd83",
    "woodland": "#82956f",
    "meadow": "#b6bf8f",
    "rough_ground": "#aaa68d",
}


def _shade(hex_color: str, elevation: float) -> str:
    value = hex_color.lstrip("#")
    rgb = [int(value[index : index + 2], 16) for index in (0, 2, 4)]
    factor = 0.86 + _clamp(elevation) * 0.24
    return "#" + "".join(f"{max(0, min(255, round(channel * factor))):02x}" for channel in rgb)


def _render_svg(
    *,
    city_name: str,
    seed: str,
    width: int,
    height: int,
    section_size: int,
    elevation: Sequence[Sequence[float]],
    regions: Sequence[Sequence[str]],
    waterways: Sequence[Mapping[str, Any]],
) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Generated terrain map of {escape(city_name)}">',
        f"<title>{escape(city_name)} generated terrain</title>",
        '<rect width="100%" height="100%" fill="#efe8d7"/>',
        '<g shape-rendering="crispEdges">',
    ]
    for y in range(height):
        x = 0
        while x < width:
            color = _shade(_REGION_COLORS.get(regions[y][x], "#aaa68d"), elevation[y][x])
            end = x + 1
            while end < width and _shade(_REGION_COLORS.get(regions[y][end], "#aaa68d"), elevation[y][end]) == color:
                end += 1
            parts.append(f'<rect x="{x}" y="{y}" width="{end - x}" height="1" fill="{color}"/>')
            x = end
    parts.append("</g>")

    parts.append('<g fill="none" stroke="#587f87" stroke-linecap="round" stroke-linejoin="round">')
    for waterway in waterways:
        points = " ".join(f"{float(point[0]):.2f},{float(point[1]):.2f}" for point in waterway.get("points", []))
        stroke_width = max(1.0, float(waterway.get("width_cells") or 2.0))
        parts.append(f'<polyline points="{points}" stroke-width="{stroke_width:.2f}" opacity="0.92"/>')
        parts.append(f'<polyline points="{points}" stroke="#b8d1d0" stroke-width="{max(0.35, stroke_width * 0.2):.2f}" opacity="0.55"/>')
    parts.append("</g>")

    parts.append('<g fill="#536b4b" opacity="0.5">')
    for y in range(1, height, 2):
        for x in range(1, width, 2):
            if regions[y][x] == "woodland" and _unit(seed, "tree", x, y) > 0.42:
                radius = 0.18 + _unit(seed, "tree-size", x, y) * 0.16
                parts.append(f'<circle cx="{x + 0.5:.2f}" cy="{y + 0.5:.2f}" r="{radius:.2f}"/>')
    parts.append("</g>")

    parts.append('<g stroke="#8f8059" stroke-width="0.08" opacity="0.28">')
    for y in range(0, height, 2):
        runs: list[tuple[int, int]] = []
        start: int | None = None
        for x in range(width):
            if regions[y][x] == "cultivated" and start is None:
                start = x
            if start is not None and (regions[y][x] != "cultivated" or x == width - 1):
                end = x if regions[y][x] != "cultivated" else x + 1
                runs.append((start, end))
                start = None
        for start, end in runs:
            parts.append(f'<line x1="{start}" y1="{y + 0.5}" x2="{end}" y2="{y + 0.5}"/>')
    parts.append("</g>")

    parts.append('<g fill="none" stroke="#625f56" stroke-width="0.08" stroke-dasharray="0.35 0.3" opacity="0.24">')
    for x in range(section_size, width, section_size):
        parts.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{height}"/>')
    for y in range(section_size, height, section_size):
        parts.append(f'<line x1="0" y1="{y}" x2="{width}" y2="{y}"/>')
    parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def compile_fictional_map(
    config: Mapping[str, Any],
    *,
    neighborhoods: Sequence[Mapping[str, Any]],
    landmarks: Sequence[Mapping[str, Any]],
) -> CompiledFictionalMap:
    """Compile one fictional map without changing canonical city-pack facts."""
    if not bool(config.get("fictional")):
        raise ValueError("field map generation is only available for declared fictional packs")
    source = config.get("fictional_map") if isinstance(config.get("fictional_map"), Mapping) else None
    if source is None:
        raise ValueError("fictional_map configuration is required")
    seed = str(source.get("seed") or "").strip()
    if not seed:
        raise ValueError("fictional_map.seed is required")
    grid = source.get("grid") if isinstance(source.get("grid"), Mapping) else {}
    width = int(grid.get("width") or 72)
    height = int(grid.get("height") or 54)
    section_size = int(grid.get("section_size") or 18)
    if not 24 <= width <= 192 or not 24 <= height <= 192:
        raise ValueError("fictional map grid dimensions must be between 24 and 192")
    if not 8 <= section_size <= 48:
        raise ValueError("fictional map section size must be between 8 and 48")

    bounds = _bounds(config)
    _validate_projected_aspect(bounds, width=width, height=height)
    compiled_anchors = _anchors(neighborhoods, landmarks, bounds=bounds, width=width, height=height)
    routes = _routes(neighborhoods, compiled_anchors)
    waterways = _waterways(source, seed=seed, width=width, height=height)
    elevation = _elevation_grid(source, seed=seed, width=width, height=height, waterways=waterways)
    slope = _slope_grid(elevation, width=width, height=height)
    flow = _flow_grid(elevation, seed=seed, width=width, height=height)
    wetness = _wetness_grid(elevation, flow, width=width, height=height, waterways=waterways)
    soils, regions = _categorical_fields(source, seed=seed, width=width, height=height, anchors=compiled_anchors, elevation=elevation, slope=slope, wetness=wetness, waterways=waterways)
    sections = _sections(seed=seed, width=width, height=height, section_size=section_size, waterways=waterways, routes=routes)

    soil_palette = ["water", "wet_alluvial", "alluvial_loam", "well_drained_loam", "woodland_floor", "thin_rocky"]
    region_palette = ["water", "riverbank", "village", "working", "cultivated", "woodland", "meadow", "rough_ground"]
    artifact: dict[str, Any] = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "generator": {"id": GENERATOR_ID, "version": GENERATOR_VERSION, "seed": seed},
        "source": {"city_id": str(config.get("city_id") or ""), "pack_version": str(config.get("pack_version") or "")},
        "bounds": bounds,
        "grid": {"width": width, "height": height, "section_size": section_size},
        "fields": {
            "elevation": _u8_field(elevation),
            "slope": _u8_field(slope),
            "water_flow": _u8_field(flow),
            "wetness": _u8_field(wetness),
            "soil": _category_field(soils, soil_palette),
            "region": _category_field(regions, region_palette),
        },
        "waterways": waterways,
        "anchors": compiled_anchors,
        "routes": routes,
        "sections": sections,
        "validation": {
            "required_anchor_count": len(compiled_anchors),
            "canonical_route_count": len(routes),
            "all_required_anchors_placed": all(bool(item.get("id")) for item in compiled_anchors),
        },
    }
    svg = _render_svg(city_name=str(config.get("city_name") or config.get("city_id") or "Fictional city"), seed=seed, width=width, height=height, section_size=section_size, elevation=elevation, regions=regions, waterways=waterways)
    artifact["svg"] = {"filename": "generated_map.svg", "sha256": hashlib.sha256(svg.encode("utf-8")).hexdigest()}
    artifact["artifact_sha256"] = _canonical_hash(artifact)
    return CompiledFictionalMap(artifact=artifact, svg=svg)
