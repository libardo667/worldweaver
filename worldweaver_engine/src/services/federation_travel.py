# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""City-node client for the federation root's travel lifecycle."""

from __future__ import annotations

from typing import Any, Optional

from .federation_identity import _federation_request


def start_federated_travel(
    *,
    travel_id: str,
    actor_id: str,
    source_shard: str,
    destination_shard: str,
    departure_hub: Optional[str],
    arrival_hub: Optional[str],
    reason: Optional[str],
) -> dict[str, Any]:
    return _federation_request(
        "POST",
        "/api/federation/travel/start",
        {
            "travel_id": travel_id,
            "actor_id": actor_id,
            "source_shard": source_shard,
            "destination_shard": destination_shard,
            "departure_hub": departure_hub,
            "arrival_hub": arrival_hub,
            "reason": reason,
        },
    )


def confirm_federated_departure(*, travel_id: str, source_shard: str) -> dict[str, Any]:
    return _federation_request(
        "POST",
        f"/api/federation/travel/{travel_id}/depart",
        {"shard_id": source_shard},
    )
