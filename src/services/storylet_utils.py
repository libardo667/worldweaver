"""Shared storylet normalization and lookup helpers."""

import json
import logging
from typing import Any, Dict, List, Optional, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import Storylet
from .db_json import loads_if_str, safe_json_dict

logger = logging.getLogger(__name__)


def normalize_requires(value: Any) -> Dict[str, Any]:
    """Normalize requires values stored as dict or JSON string."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return cast(Dict[str, Any], value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return cast(Dict[str, Any], parsed)
        except json.JSONDecodeError:
            return {}
    return {}


def normalize_choice(choice_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a raw choice payload to API shape."""
    label = choice_dict.get("label") or choice_dict.get("text") or "Continue"
    set_obj = choice_dict.get("set") or choice_dict.get("set_vars") or {}
    return {"label": label, "set": set_obj}


def storylet_location(storylet: Storylet) -> Optional[str]:
    """Extract the location string from a storylet's requires payload."""
    try:
        location = normalize_requires(storylet.requires).get("location")
    except Exception:
        return None
    return location if isinstance(location, str) else None


def _safe_json_list(value: Any) -> List[Dict[str, Any]]:
    parsed = value
    for _ in range(3):
        parsed = loads_if_str(parsed)
        if isinstance(parsed, list):
            out: List[Dict[str, Any]] = []
            for item in parsed:
                if isinstance(item, dict):
                    out.append(cast(Dict[str, Any], item))
            return out
        if not isinstance(parsed, str):
            break
    return []


def _find_storylet_by_location_raw(db: Session, location: str) -> Storylet | None:
    rows = db.execute(text("""
            SELECT id, title, text_template, requires, choices, effects, weight, position, source
            FROM storylets
            """)).mappings()
    for row in rows:
        requires = safe_json_dict(row.get("requires"))
        if requires.get("location") != location:
            continue
        title = str(row.get("title") or "").strip() or "Storylet"
        text_template = str(row.get("text_template") or "").strip() or "Something happens."
        raw_position = loads_if_str(row.get("position"))
        position = raw_position if isinstance(raw_position, dict) else {"x": 0, "y": 0}
        try:
            weight = float(row.get("weight", 1.0) or 1.0)
        except (TypeError, ValueError):
            weight = 1.0
        fallback_storylet = Storylet(
            title=title,
            text_template=text_template,
            requires=requires,
            choices=_safe_json_list(row.get("choices")),
            effects=_safe_json_list(row.get("effects")),
            weight=weight,
            position=position,
            source=str(row.get("source") or "authored"),
        )
        try:
            raw_id = row.get("id")
            if raw_id is not None:
                fallback_storylet.id = int(raw_id)
        except Exception:
            pass
        return fallback_storylet
    return None


def find_storylet_by_location(db: Session, location: str) -> Storylet | None:
    """Find the first storylet whose requires.location matches exactly."""
    target = str(location or "").strip()
    if not target:
        return None
    try:
        for storylet in db.query(Storylet).all():
            if storylet_location(storylet) == target:
                return storylet
    except Exception as exc:
        logger.warning("Storylet ORM location lookup failed; falling back to raw SQL scan: %s", exc)
    return _find_storylet_by_location_raw(db, target)
