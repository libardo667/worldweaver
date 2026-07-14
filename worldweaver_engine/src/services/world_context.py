# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Thin shared world context used by active runtime prompts."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def build_world_context_header(
    *,
    world_name: str = "",
    city_id: str = "",
    theme: str = "",
    tone: str = "",
    premise: str = "",
    entry_point: str = "",
    canonical_locations: Optional[Iterable[str]] = None,
    style_constraints: Optional[Iterable[str]] = None,
    source: str = "runtime",
) -> Dict[str, Any]:
    """Create a bounded shared-world context object for prompts and bootstrap."""
    safe_world_name = str(world_name or "").strip() or (str(city_id or "").replace("_", " ").title() if city_id else "WorldWeaver")
    safe_theme = str(theme or "").strip()
    safe_tone = str(tone or "").strip() or "grounded, observational"
    safe_premise = str(premise or "").strip() or (f"A persistent shared world shaped by its inhabitants{': ' + safe_theme if safe_theme else ''}.")
    safe_entry_point = str(entry_point or "").strip()
    canonical = _dedupe_preserve_order(canonical_locations or [])
    constraints = _dedupe_preserve_order(
        style_constraints
        or [
            "Describe what is already present and happening.",
            "Do not invent drama or conflict not evidenced by the world state.",
            "Favor concrete geography, routine, and consequence over lore.",
        ]
    )
    return {
        "world_name": safe_world_name,
        "city_id": str(city_id or "").strip(),
        "theme": safe_theme,
        "tone": safe_tone,
        "premise": safe_premise,
        "entry_point": safe_entry_point,
        "canonical_locations": canonical,
        "style_constraints": constraints,
        "source": str(source or "runtime"),
    }


def get_canonical_locations_from_context(world_context: Dict[str, Any] | None) -> List[str]:
    """Return canonical movement/location names from a context header."""
    if not isinstance(world_context, dict):
        return []
    raw = world_context.get("canonical_locations", [])
    if not isinstance(raw, list):
        return []
    return _dedupe_preserve_order(str(item or "").strip() for item in raw)
