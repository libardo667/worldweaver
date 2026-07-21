# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Recoverable city-to-city travel on one shard's side of the handoff."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Player, SessionVars, ShardTravelHandoff
from . import city_pack_service, federation_discovery, federation_travel
from .event_submission import WorldEventCommand, submit_world_event
from .federation_identity import current_shard_id
from .resident_authority import bind_resident_session
from .session_lifecycle import (
    ResidentSessionBinding,
    SessionBootstrapCommand,
    bootstrap_session,
    stage_retire_session_presence,
)
from .session_service import get_state_manager, remove_cached_sessions
from .world_memory import (
    EVENT_TYPE_CROSS_SHARD_ARRIVAL,
    EVENT_TYPE_CROSS_SHARD_DEPARTURE,
)


class ShardTravelError(ValueError):
    """A safe, typed refusal from the local travel boundary."""

    def __init__(self, code: str, detail: str, *, status_code: int):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class ShardTravelReceipt:
    payload: dict[str, Any]
    status_code: int = 200


def handoff_payload(row: ShardTravelHandoff) -> dict[str, Any]:
    return {
        "travel_id": row.travel_id,
        "actor_id": row.actor_id,
        "session_id": row.session_id,
        "source_shard": row.source_shard,
        "destination_shard": row.destination_shard,
        "destination_url": row.destination_url,
        "destination_client_url": row.destination_client_url,
        "route_id": row.route_id,
        "departure_hub_id": row.departure_hub_id,
        "departure_hub": row.departure_hub,
        "arrival_hub_id": row.arrival_hub_id,
        "arrival_hub": row.arrival_hub,
        "status": row.status,
        "last_error": row.last_error,
    }


def handoff_place(db: Session, row: ShardTravelHandoff) -> str | None:
    if not row.session_id or row.status not in {"session_booted", "arrived"}:
        return None
    place = str(
        get_state_manager(str(row.session_id), db).get_variable("location") or ""
    ).strip()
    return place or None


def _error_detail(exc: Exception) -> str:
    detail = getattr(exc, "detail", None)
    return str(detail if detail is not None else exc) or exc.__class__.__name__


def require_handoff_owner(row: ShardTravelHandoff, player: Player | None) -> None:
    if row.owner_player_id and (player is None or player.id != row.owner_player_id):
        raise ShardTravelError(
            "handoff_owner_mismatch",
            "Cannot manage travel owned by another player.",
            status_code=403,
        )


def _resolve_departure_route(route_id: str, destination_shard: str) -> dict[str, Any]:
    discovery = federation_discovery.get_travel_destinations()
    registry = discovery.get("registry") if isinstance(discovery, dict) else None
    if not isinstance(registry, dict) or not registry.get("reachable"):
        raise ShardTravelError(
            "registry_unavailable",
            (
                "Federation registry is unavailable; local life can continue, "
                "but inter-city departure cannot start."
            ),
            status_code=503,
        )

    destinations = (
        discovery.get("destinations") if isinstance(discovery, dict) else None
    )
    for route in destinations if isinstance(destinations, list) else []:
        if (
            not isinstance(route, dict)
            or str(route.get("route_id") or "").strip() != route_id
        ):
            continue
        nodes = route.get("nodes")
        for node in nodes if isinstance(nodes, list) else []:
            if (
                not isinstance(node, dict)
                or str(node.get("shard_id") or "").strip() != destination_shard
            ):
                continue
            if str(node.get("status") or "").strip() not in {"healthy", "degraded"}:
                raise ShardTravelError(
                    "destination_unavailable",
                    f"Destination node '{destination_shard}' is not currently available.",
                    status_code=409,
                )
            departure_hub_id = str(route.get("departure_hub_id") or "").strip()
            arrival_hub_id = str(route.get("arrival_hub_id") or "").strip()
            if not departure_hub_id or not arrival_hub_id:
                raise ShardTravelError(
                    "unstable_route",
                    f"Route '{route_id}' has no stable travel hub IDs and cannot be used safely.",
                    status_code=409,
                )
            return {
                "route_id": route_id,
                "departure_hub_id": departure_hub_id,
                "departure_hub": str(route.get("departure_hub") or "").strip() or None,
                "arrival_hub_id": arrival_hub_id,
                "arrival_hub": str(route.get("arrival_hub") or "").strip() or None,
                "destination_url": str(node.get("shard_url") or "").strip() or None,
                "destination_client_url": str(node.get("client_url") or "").strip()
                or None,
            }
        raise ShardTravelError(
            "route_destination_mismatch",
            f"Route '{route_id}' does not lead to node '{destination_shard}'.",
            status_code=404,
        )
    raise ShardTravelError(
        "route_not_found",
        f"Travel route '{route_id}' not found in this city pack.",
        status_code=404,
    )


def federated_trip(travel_id: str) -> dict[str, Any]:
    response = federation_travel.get_federated_travel(travel_id=travel_id)
    trip = response.get("travel") if isinstance(response, dict) else None
    if not isinstance(trip, dict):
        raise ShardTravelError(
            "invalid_federation_record",
            "The federation returned an invalid travel record.",
            status_code=502,
        )
    return trip


def _resolve_destination_arrival(trip: dict[str, Any]) -> dict[str, Any]:
    destination_shard = str(trip.get("destination_shard") or "").strip()
    local_shard = current_shard_id()
    if destination_shard != local_shard:
        raise ShardTravelError(
            "wrong_destination",
            f"Travel is intended for node '{destination_shard}', not '{local_shard}'.",
            status_code=409,
        )
    if str(trip.get("status") or "").strip() not in {"traveling", "arrived"}:
        raise ShardTravelError(
            "departure_incomplete",
            "Travel must be departed before the destination can receive it.",
            status_code=409,
        )

    arrival_hub_id = str(trip.get("arrival_hub_id") or "").strip()
    if not arrival_hub_id:
        raise ShardTravelError(
            "arrival_hub_missing",
            "Travel has no stable destination hub ID and cannot be placed safely.",
            status_code=409,
        )
    hub = city_pack_service.resolve_travel_hub_entry(arrival_hub_id, settings.city_id)
    if hub is None:
        raise ShardTravelError(
            "arrival_hub_unknown",
            (
                f"Arrival hub '{arrival_hub_id}' does not exist in city pack "
                f"'{settings.city_id}'."
            ),
            status_code=409,
        )
    return hub


def _normalized_place(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().casefold()).strip("-")


def _require_session_at_departure_hub(
    db: Session, session_id: str, departure_hub_id: str
) -> None:
    hub = city_pack_service.resolve_travel_hub_entry(departure_hub_id, settings.city_id)
    if hub is None:
        raise ShardTravelError(
            "departure_hub_unknown",
            f"Departure hub '{departure_hub_id}' does not resolve to a local place.",
            status_code=409,
        )
    required_place = str(hub.get("entry_location") or "").strip()
    current_place = str(
        get_state_manager(session_id, db).get_variable("location") or ""
    ).strip()
    if _normalized_place(current_place) != _normalized_place(required_place):
        raise ShardTravelError(
            "not_at_departure_hub",
            (
                f"Travel on this route departs from {required_place}. You are "
                f"currently at {current_place or 'an unknown place'}."
            ),
            status_code=409,
        )


def _require_arriving_actor(trip: dict[str, Any], player: Player | None) -> str:
    actor_id = str(trip.get("actor_id") or "").strip()
    if not actor_id:
        raise ShardTravelError(
            "actor_identity_missing",
            "The federation travel record has no actor identity.",
            status_code=502,
        )
    actor_type = str(trip.get("actor_type") or "agent").strip() or "agent"
    if player is not None and str(player.actor_id or "").strip() != actor_id:
        raise ShardTravelError(
            "actor_mismatch", "This trip belongs to another actor.", status_code=403
        )
    if player is None and actor_type not in {"agent", "player_shadow"}:
        raise ShardTravelError(
            "human_login_required",
            "A human traveler must authenticate before arrival.",
            status_code=401,
        )
    return actor_id


def _recoverable(
    db: Session,
    row: ShardTravelHandoff,
    *,
    message: str,
    error: Exception,
    deleted: dict[str, int] | None = None,
) -> ShardTravelReceipt:
    db.rollback()
    current = db.get(ShardTravelHandoff, row.travel_id)
    if current is not None:
        current.last_error = _error_detail(error)
        db.commit()
        row = current
    payload: dict[str, Any] = {
        "success": False,
        "recoverable": True,
        "message": message,
        "handoff": handoff_payload(row) if row is not None else None,
    }
    if deleted is not None:
        payload["deleted"] = deleted
    if row.role == "destination":
        payload["place"] = handoff_place(db, row)
    return ShardTravelReceipt(payload=payload, status_code=202)


def finish_source_departure(db: Session, row: ShardTravelHandoff) -> ShardTravelReceipt:
    if row.status == "traveling":
        return ShardTravelReceipt(
            {"success": True, "idempotent": True, "handoff": handoff_payload(row)}
        )

    deleted = {"sessions": 0}
    if row.status == "prepared":
        try:
            deleted = stage_retire_session_presence(db, str(row.session_id or ""))
            row.status = "session_retired"
            row.last_error = None
            db.commit()
            remove_cached_sessions([str(row.session_id or "")])
        except Exception as exc:
            return _recoverable(
                db,
                row,
                message="The source has not finished retiring this traveler. Retry this travel ID.",
                error=exc,
                deleted=deleted,
            )

    if row.status != "session_retired":
        raise ShardTravelError(
            "unexpected_source_state",
            f"Source handoff is in unexpected state '{row.status}'.",
            status_code=409,
        )

    try:
        federation_result = federation_travel.confirm_federated_departure(
            travel_id=row.travel_id,
            source_shard=row.source_shard,
        )
    except Exception as exc:
        return _recoverable(
            db,
            row,
            message=(
                "The local session has left, but the federation has not confirmed "
                "departure yet. Retry this travel ID."
            ),
            error=exc,
            deleted=deleted,
        )

    try:
        row.status = "traveling"
        row.last_error = None
        submit_world_event(
            db,
            WorldEventCommand(
                session_id=row.session_id,
                event_type=EVENT_TYPE_CROSS_SHARD_DEPARTURE,
                summary=f"Actor {row.actor_id} departed for node {row.destination_shard}.",
                delta={
                    "travel_id": row.travel_id,
                    "actor_id": row.actor_id,
                    "source_shard": row.source_shard,
                    "destination_shard": row.destination_shard,
                },
                metadata={"surface": "federation_travel"},
                idempotency_key=f"cross-shard-departure:{row.travel_id}",
                skip_graph_extraction=True,
                skip_projection=True,
                preserve_event_type=True,
                defer_commit=True,
            ),
        )
        db.commit()
    except Exception as exc:
        return _recoverable(
            db,
            row,
            message=(
                "The federation confirmed departure, but this shard has not "
                "finished its local record. Retry this travel ID."
            ),
            error=exc,
            deleted=deleted,
        )

    return ShardTravelReceipt(
        {
            "success": True,
            "idempotent": bool(federation_result.get("idempotent")),
            "deleted": deleted,
            "handoff": handoff_payload(row),
            "federation": federation_result,
        }
    )


def depart_session(
    db: Session,
    *,
    session_id: str,
    route_id: str,
    destination_shard: str,
    travel_id: str,
    reason: str | None,
    player: Player | None,
) -> ShardTravelReceipt:
    if settings.shard_type != "city":
        raise ShardTravelError(
            "city_required",
            "Inter-city departure must start on a city node.",
            status_code=409,
        )

    existing = db.get(ShardTravelHandoff, travel_id)
    if existing is not None:
        require_handoff_owner(existing, player)
        same_request = (
            existing.session_id == session_id
            and existing.destination_shard == destination_shard
            and existing.route_id == route_id
        )
        if not same_request:
            raise ShardTravelError(
                "travel_id_conflict",
                f"Travel ID '{travel_id}' already describes another local handoff.",
                status_code=409,
            )
        return finish_source_departure(db, existing)

    session = db.get(SessionVars, session_id)
    if session is None:
        raise ShardTravelError(
            "session_not_found", f"Session '{session_id}' not found.", status_code=404
        )
    if session.player_id and (player is None or session.player_id != player.id):
        raise ShardTravelError(
            "session_owner_mismatch",
            "Cannot depart a session owned by another player.",
            status_code=403,
        )
    actor_id = str(session.actor_id or "").strip()
    if not actor_id:
        raise ShardTravelError(
            "actor_identity_missing",
            "Session has no durable actor identity and cannot travel between nodes.",
            status_code=409,
        )

    route = _resolve_departure_route(route_id, destination_shard)
    _require_session_at_departure_hub(db, session_id, route["departure_hub_id"])
    source_shard = current_shard_id()
    federation_travel.start_federated_travel(
        travel_id=travel_id,
        actor_id=actor_id,
        source_shard=source_shard,
        destination_shard=destination_shard,
        departure_hub_id=route["departure_hub_id"],
        departure_hub=route["departure_hub"],
        arrival_hub_id=route["arrival_hub_id"],
        arrival_hub=route["arrival_hub"],
        reason=str(reason or "").strip() or None,
    )

    handoff = ShardTravelHandoff(
        travel_id=travel_id,
        actor_id=actor_id,
        session_id=session_id,
        owner_player_id=session.player_id,
        role="source",
        source_shard=source_shard,
        destination_shard=destination_shard,
        destination_url=route["destination_url"],
        destination_client_url=route["destination_client_url"],
        route_id=route_id,
        departure_hub_id=route["departure_hub_id"],
        departure_hub=route["departure_hub"],
        arrival_hub_id=route["arrival_hub_id"],
        arrival_hub=route["arrival_hub"],
        status="prepared",
    )
    db.add(handoff)
    db.commit()
    return finish_source_departure(db, handoff)


def finish_destination_arrival(
    db: Session,
    row: ShardTravelHandoff,
    *,
    player: Player | None,
    world_id: str,
    trip: dict[str, Any] | None = None,
    resident_binding: ResidentSessionBinding | None = None,
) -> ShardTravelReceipt:
    if row.status == "arrived":
        return ShardTravelReceipt(
            {
                "success": True,
                "idempotent": True,
                "place": handoff_place(db, row),
                "handoff": handoff_payload(row),
            }
        )

    if row.status == "prepared":
        try:
            trip = trip or federated_trip(row.travel_id)
            hub = _resolve_destination_arrival(trip)
            actor_id = _require_arriving_actor(trip, player)
            if actor_id != row.actor_id:
                raise ShardTravelError(
                    "actor_changed",
                    "The federation trip actor no longer matches this local handoff.",
                    status_code=409,
                )
            if not world_id:
                raise ShardTravelError(
                    "world_not_seeded",
                    "This destination has no seeded world to receive the traveler.",
                    status_code=409,
                )

            existing_session = db.get(SessionVars, str(row.session_id or ""))
            if existing_session is not None:
                if str(existing_session.actor_id or "").strip() != actor_id:
                    raise ShardTravelError(
                        "session_id_conflict",
                        "The destination session ID is already owned by another actor.",
                        status_code=409,
                    )
                if resident_binding is not None:
                    bind_resident_session(
                        db,
                        session_id=str(row.session_id or ""),
                        actor_id=resident_binding.actor_id,
                        runtime_generation=resident_binding.runtime_generation,
                    )
            else:
                bootstrap_session(
                    db,
                    command=SessionBootstrapCommand(
                        session_id=str(row.session_id or ""),
                        actor_id=actor_id,
                        player_role=str(trip.get("name") or actor_id).strip()
                        or actor_id,
                        bootstrap_source="federation-travel",
                        world_id=world_id,
                        entry_location=str(hub.get("entry_location") or "").strip(),
                    ),
                    player=player,
                    resident_binding=resident_binding,
                )
            row = db.get(ShardTravelHandoff, row.travel_id)
            if row is None:
                raise ShardTravelError(
                    "handoff_missing",
                    "Local arrival recovery record disappeared.",
                    status_code=500,
                )
            row.status = "session_booted"
            row.last_error = None
            db.commit()
        except Exception as exc:
            return _recoverable(
                db,
                row,
                message=(
                    "The destination has not finished booting this traveler. "
                    "Retry this travel ID."
                ),
                error=exc,
            )

    if row.status != "session_booted":
        raise ShardTravelError(
            "unexpected_destination_state",
            f"Destination handoff is in unexpected state '{row.status}'.",
            status_code=409,
        )

    try:
        federation_result = federation_travel.confirm_federated_arrival(
            travel_id=row.travel_id,
            destination_shard=row.destination_shard,
        )
    except Exception as exc:
        return _recoverable(
            db,
            row,
            message=(
                "The local session is ready, but the federation has not confirmed "
                "arrival yet. Retry this travel ID."
            ),
            error=exc,
        )

    try:
        row.status = "arrived"
        row.last_error = None
        submit_world_event(
            db,
            WorldEventCommand(
                session_id=row.session_id,
                event_type=EVENT_TYPE_CROSS_SHARD_ARRIVAL,
                summary=f"Actor {row.actor_id} arrived from node {row.source_shard}.",
                delta={
                    "travel_id": row.travel_id,
                    "actor_id": row.actor_id,
                    "source_shard": row.source_shard,
                    "destination_shard": row.destination_shard,
                    "arrival_hub_id": row.arrival_hub_id,
                },
                metadata={"surface": "federation_travel"},
                idempotency_key=f"cross-shard-arrival:{row.travel_id}",
                skip_graph_extraction=True,
                skip_projection=True,
                preserve_event_type=True,
                defer_commit=True,
            ),
        )
        db.commit()
    except Exception as exc:
        return _recoverable(
            db,
            row,
            message=(
                "The federation confirmed arrival, but this shard has not "
                "finished its local record. Retry this travel ID."
            ),
            error=exc,
        )

    return ShardTravelReceipt(
        {
            "success": True,
            "idempotent": bool(federation_result.get("idempotent")),
            "place": handoff_place(db, row),
            "handoff": handoff_payload(row),
            "federation": federation_result,
        }
    )


def arrive_session(
    db: Session,
    *,
    travel_id: str,
    session_id: str,
    player: Player | None,
    world_id: str,
    trip: dict[str, Any] | None = None,
    resident_binding: ResidentSessionBinding | None = None,
) -> ShardTravelReceipt:
    if settings.shard_type != "city":
        raise ShardTravelError(
            "city_required",
            "Inter-city arrival must finish on a city node.",
            status_code=409,
        )

    existing = db.get(ShardTravelHandoff, travel_id)
    if existing is not None:
        if existing.role != "destination":
            raise ShardTravelError(
                "travel_id_conflict",
                f"Travel ID '{travel_id}' already describes a source handoff on this node.",
                status_code=409,
            )
        require_handoff_owner(existing, player)
        if existing.session_id != session_id:
            raise ShardTravelError(
                "session_id_conflict",
                f"Travel ID '{travel_id}' is already bound to another local session.",
                status_code=409,
            )
        return finish_destination_arrival(
            db,
            existing,
            player=player,
            world_id=world_id,
            trip=trip,
            resident_binding=resident_binding,
        )

    trip = trip or federated_trip(travel_id)
    hub = _resolve_destination_arrival(trip)
    actor_id = _require_arriving_actor(trip, player)
    if not world_id:
        raise ShardTravelError(
            "world_not_seeded",
            "This destination has no seeded world to receive the traveler.",
            status_code=409,
        )
    if db.get(SessionVars, session_id) is not None:
        raise ShardTravelError(
            "session_id_conflict",
            f"Session ID '{session_id}' is already in use on this node.",
            status_code=409,
        )
    live_actor_session = (
        db.query(SessionVars).filter(SessionVars.actor_id == actor_id).first()
    )
    if live_actor_session is not None:
        raise ShardTravelError(
            "actor_already_present",
            (
                f"Actor '{actor_id}' is already active in local session "
                f"'{live_actor_session.session_id}'."
            ),
            status_code=409,
        )

    handoff = ShardTravelHandoff(
        travel_id=travel_id,
        actor_id=actor_id,
        session_id=session_id,
        owner_player_id=player.id if player is not None else None,
        role="destination",
        source_shard=str(trip.get("source_shard") or "").strip(),
        destination_shard=current_shard_id(),
        departure_hub_id=str(trip.get("departure_hub_id") or "").strip() or None,
        departure_hub=str(trip.get("departure_hub") or "").strip() or None,
        arrival_hub_id=str(trip.get("arrival_hub_id") or "").strip() or None,
        arrival_hub=str(trip.get("arrival_hub") or hub.get("name") or "").strip()
        or None,
        status="prepared",
    )
    db.add(handoff)
    db.commit()
    return finish_destination_arrival(
        db,
        handoff,
        player=player,
        world_id=world_id,
        trip=trip,
        resident_binding=resident_binding,
    )
