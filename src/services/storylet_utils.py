"""Shared storylet normalization and lookup helpers."""

import json
from typing import Any, Dict, Optional, cast

from sqlalchemy.orm import Session

from ..models import Storylet


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
    location = normalize_requires(storylet.requires).get("location")
    return location if isinstance(location, str) else None


def find_storylet_by_location(db: Session, location: str) -> Storylet | None:
    """Find the first storylet whose requires.location matches exactly."""
    for storylet in db.query(Storylet).all():
        if storylet_location(storylet) == location:
            return storylet
    return None
