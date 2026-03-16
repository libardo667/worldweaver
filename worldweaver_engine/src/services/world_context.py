"""Thin shared world context used by active runtime prompts.

This is intentionally smaller and less prescriptive than the legacy world bible.
It carries only the global facts that help prompts stay grounded without
dragging the runtime back toward repeated motifs or heavy authored framing.
"""

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
    safe_premise = str(premise or "").strip() or (
        f"A persistent shared world shaped by its inhabitants{': ' + safe_theme if safe_theme else ''}."
    )
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


def world_bible_to_context_header(
    world_bible: Dict[str, Any] | None,
    *,
    fallback_world_name: str = "",
    fallback_city_id: str = "",
    fallback_theme: str = "",
    fallback_tone: str = "",
) -> Dict[str, Any]:
    """Derive a thin context header from a legacy world bible payload."""
    bible = world_bible if isinstance(world_bible, dict) else {}
    raw_locations = bible.get("locations", [])
    canonical_locations: List[str] = []
    if isinstance(raw_locations, list):
        for loc in raw_locations:
            if isinstance(loc, dict):
                name = str(loc.get("name", "")).strip()
                if name:
                    canonical_locations.append(name)
    premise = str(
        bible.get("central_tension")
        or bible.get("atmosphere")
        or bible.get("entry_point")
        or ""
    ).strip()
    return build_world_context_header(
        world_name=str(bible.get("world_name", "")).strip() or fallback_world_name,
        city_id=fallback_city_id,
        theme=fallback_theme,
        tone=fallback_tone,
        premise=premise,
        entry_point=str(bible.get("entry_point", "")).strip(),
        canonical_locations=canonical_locations,
        source="legacy_world_bible",
    )


def get_canonical_locations_from_context(world_context: Dict[str, Any] | None) -> List[str]:
    """Return canonical movement/location names from a context header."""
    if not isinstance(world_context, dict):
        return []
    raw = world_context.get("canonical_locations", [])
    if not isinstance(raw, list):
        return []
    return _dedupe_preserve_order(str(item or "").strip() for item in raw)
