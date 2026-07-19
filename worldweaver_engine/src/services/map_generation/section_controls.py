# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Small immutable edits shared by a future City Studio and command-line tools."""

from __future__ import annotations

import copy
import re
from typing import Any, Mapping


def section_ids(source: Mapping[str, Any]) -> tuple[str, ...]:
    grid = source.get("grid") if isinstance(source.get("grid"), Mapping) else {}
    width = grid.get("width", 72)
    height = grid.get("height", 54)
    section_size = grid.get("section_size", 18)
    if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in (width, height, section_size)):
        raise ValueError("fictional_map grid dimensions must be positive integers")
    return tuple(f"section-{x // section_size}-{y // section_size}" for y in range(0, height, section_size) for x in range(0, width, section_size))


def edit_section(config: Mapping[str, Any], *, section_id: str, action: str) -> dict[str, Any]:
    """Return a copied config with one explicit lock, unlock, or reroll edit."""
    if action not in {"lock", "unlock", "reroll"}:
        raise ValueError("section action must be lock, unlock, or reroll")
    edited = copy.deepcopy(dict(config))
    source = edited.get("fictional_map")
    if not isinstance(source, dict):
        raise ValueError("fictional_map configuration is required")
    if section_id not in section_ids(source):
        raise ValueError(f"unknown map section: {section_id}")

    controls = source.setdefault("sections", {})
    if not isinstance(controls, dict):
        raise ValueError("fictional_map.sections must be an object")
    default_locked = controls.get("default_locked", False)
    if not isinstance(default_locked, bool):
        raise ValueError("fictional_map.sections.default_locked must be true or false")
    overrides = controls.setdefault("overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("fictional_map.sections.overrides must be an object")
    current = overrides.get(section_id, {})
    if not isinstance(current, dict):
        raise ValueError(f"section '{section_id}' override must be an object")
    revision = current.get("revision", 0)
    if not isinstance(revision, int) or isinstance(revision, bool) or not 0 <= revision <= 9999:
        raise ValueError(f"section '{section_id}' revision must be an integer between 0 and 9999")
    locked = current.get("locked", default_locked)
    if not isinstance(locked, bool):
        raise ValueError(f"section '{section_id}' locked state must be true or false")

    if action == "reroll":
        if locked:
            raise ValueError(f"section '{section_id}' is locked; unlock it before rerolling")
        if revision == 9999:
            raise ValueError(f"section '{section_id}' has reached its revision limit")
        revision += 1
    elif action == "lock":
        locked = True
    else:
        locked = False
    overrides[section_id] = {"revision": revision, "locked": locked}
    return edited


def section_preview_svg(svg: str, section: Mapping[str, Any]) -> str:
    """Crop one compiler-owned SVG to a section without regenerating the map."""
    coordinates = tuple(section.get(field) for field in ("x", "y", "width", "height"))
    if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in coordinates[2:]) or any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in coordinates[:2]):
        raise ValueError("map section needs non-negative coordinates and positive dimensions")
    x, y, width, height = coordinates
    cropped, replacements = re.subn(
        r'viewBox="[^"]+"',
        f'viewBox="{x} {y} {width} {height}"',
        svg,
        count=1,
    )
    if replacements != 1:
        raise ValueError("generated map SVG has no root viewBox")
    return cropped
