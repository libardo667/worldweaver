"""Helpers for tolerant JSON field handling from DB rows and ORM attributes."""

import json
from typing import Any


def loads_if_str(value: Any) -> Any:
    """JSON-decode string values; return all other values unchanged."""
    if not isinstance(value, str):
        return value

    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def dumps_if_dict(value: Any) -> Any:
    """JSON-encode dict/list values; return all other values unchanged."""
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


def safe_json_dict(value: Any) -> dict[str, Any]:
    """Return a dict from dict-or-JSON-string input; otherwise return {}."""
    parsed = loads_if_str(value)
    if isinstance(parsed, dict):
        return parsed
    return {}
