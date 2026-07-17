# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Pure parsing for travel between a resident's current world and its hearth."""

from __future__ import annotations

import re
from dataclasses import dataclass

_VERB = r"(?:travel|journey|go|head|walk|set\s*out|depart|move|leave|return)"
_HEARTH_RX = re.compile(
    r"\b(?:go|head|return|back|come|travel|journey|set\s*out)\b[^.!?]*\b(?:home|hearth)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TravelRequest:
    """One requested change of world attachment."""

    destination_kind: str  # hearth | city
    destination_name: str = ""


def parse_world_travel(
    text: str,
    *,
    city_names: set[str] | None = None,
    allow_hearth: bool,
) -> TravelRequest | None:
    """Recognize inter-world travel without swallowing ordinary map movement."""
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return None
    lowered = normalized.lower()

    if allow_hearth and _HEARTH_RX.search(lowered):
        return TravelRequest("hearth")

    names = {
        str(name).strip().lower() for name in (city_names or set()) if str(name).strip()
    }
    for name in sorted(names, key=len, reverse=True):
        if lowered in {name, f"the city of {name}"}:
            return TravelRequest("city", name)
        if re.search(rf"\b{_VERB}\b.*\b{re.escape(name)}\b", lowered):
            return TravelRequest("city", name)
    return None
