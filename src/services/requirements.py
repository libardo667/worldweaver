"""Shared requirement-evaluation helpers used across game services."""

import json
from typing import Any, Dict

_FLEXIBLE_LOCATION_VALUES = {"any_realm", "any_location", "anywhere"}
_VESSEL_LOCATIONS = {"start", "vessel", "ship", "craft"}


def _normalize_requires_payload(requires: Any) -> Dict[str, Any]:
    """Accept dict and legacy JSON-string payloads for requirements."""
    if isinstance(requires, dict):
        return requires
    parsed = requires
    for _ in range(3):
        if not isinstance(parsed, str):
            break
        try:
            parsed = json.loads(parsed)
        except (TypeError, ValueError):
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def evaluate_requirement_value(
    value: Any,
    requirement: Any,
    *,
    numeric_fallback_gte: bool = False,
) -> bool:
    """Evaluate a single requirement value against a current value."""
    if isinstance(requirement, dict):
        for op, target in requirement.items():
            try:
                if op == "gte":
                    if value is None or value < target:
                        return False
                elif op == "gt":
                    if value is None or value <= target:
                        return False
                elif op == "lte":
                    if value is None or value > target:
                        return False
                elif op == "lt":
                    if value is None or value >= target:
                        return False
                elif op == "eq":
                    if value != target:
                        return False
                elif op == "ne":
                    if value == target:
                        return False
                else:
                    return False
            except TypeError:
                return False
        return True

    if numeric_fallback_gte and isinstance(requirement, (int, float)) and isinstance(
        value, (int, float)
    ):
        return value >= requirement

    return value == requirement


def evaluate_requirements(
    requires: Dict[str, Any],
    vars: Dict[str, Any],
    *,
    allow_flexible_location: bool = False,
    numeric_fallback_gte: bool = False,
) -> bool:
    """Evaluate a requirements dictionary against current variables."""
    normalized_requires = _normalize_requires_payload(requires)
    for key, requirement in normalized_requires.items():
        if (
            allow_flexible_location
            and key == "location"
            and isinstance(requirement, str)
            and requirement in _FLEXIBLE_LOCATION_VALUES
        ):
            continue

        if key not in vars:
            return False

        value = vars.get(key)

        if (
            allow_flexible_location
            and key == "location"
            and requirement == "in_vessel"
            and isinstance(value, str)
            and value in _VESSEL_LOCATIONS
        ):
            continue

        if not evaluate_requirement_value(
            value,
            requirement,
            numeric_fallback_gte=numeric_fallback_gte,
        ):
            return False

    return True
