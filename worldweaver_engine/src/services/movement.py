# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Canonical movement rules shared by live routes and controlled simulations."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy.orm import Session

from .event_submission import WorldEventCommand, submit_world_event
from .location_routes import resolve_route_anchor
from .session_service import get_state_manager, stage_state
from .space_access import SpaceAccessError, assert_route_entry_allowed
from .sublocations import (
    create_or_refresh_ephemeral,
    is_local_sublocation_candidate,
    resolve_active_sublocation,
    touch_sublocation,
)
from .world_memory import EVENT_TYPE_MOVEMENT, find_route

_SESSION_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_AGENT_SLUG_RE = re.compile(r"^([a-z][a-z0-9_]*)[-_]\d{8}")


class MovementError(ValueError):
    """A safe, typed refusal from the movement boundary."""

    def __init__(
        self,
        code: str,
        detail: str | dict[str, str],
        *,
        status_code: int,
    ):
        message = detail if isinstance(detail, str) else detail.get("message", code)
        super().__init__(message)
        self.code = code
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class MovementReceipt:
    moved: bool
    from_location: str
    to_location: str
    route: list[str]
    route_remaining: list[str]
    narrative: str

    def as_payload(self) -> dict[str, Any]:
        return asdict(self)


def _slug_display_name(session_id: str) -> str | None:
    match = _AGENT_SLUG_RE.match(session_id)
    if not match:
        return None
    return " ".join(word.capitalize() for word in match.group(1).split("_"))


def _movement_fact_payload(
    *,
    mover_name: str,
    destination: str,
    in_transit: bool,
    summary: str,
) -> dict[str, Any]:
    return {
        "facts": [
            {
                "subject": mover_name,
                "subject_type": "entity",
                "predicate": "location",
                "value": destination,
                "location": destination,
                "summary": summary,
                "confidence": 0.95,
            },
            {
                "subject": mover_name,
                "subject_type": "entity",
                "predicate": "in_transit",
                "value": bool(in_transit),
                "location": destination,
                "summary": summary,
                "confidence": 0.9,
            },
        ],
        "parser_mode": "structured",
    }


def _movement_event_delta(
    *,
    origin: str,
    destination: str,
    in_transit: bool,
    mover_name: str,
    summary: str,
) -> dict[str, Any]:
    spatial_nodes: dict[str, dict[str, Any]] = {
        destination: {
            "last_arrival_actor": mover_name,
            "last_arrival_from": origin,
            "last_arrival_summary": summary,
            "last_movement_in_transit": bool(in_transit),
        }
    }
    if origin and origin != destination:
        spatial_nodes[origin] = {
            "last_departure_actor": mover_name,
            "last_departure_to": destination,
            "last_departure_summary": summary,
        }
    return {
        "origin": origin,
        "destination": destination,
        "in_transit": bool(in_transit),
        "spatial_nodes": spatial_nodes,
        "__world_facts__": _movement_fact_payload(
            mover_name=mover_name,
            destination=destination,
            in_transit=in_transit,
            summary=summary,
        ),
    }


def move_session(
    db: Session,
    *,
    session_id: str,
    destination: str,
    skip_to_destination: bool = False,
    allow_sublocation_create: bool = False,
) -> MovementReceipt:
    """Move one session through the canonical place graph.

    Authorization stays at the transport boundary. This service owns route
    resolution, destination access, session mutation, and movement events.
    """

    normalized_session_id = str(session_id or "").strip()
    if not _SESSION_RE.fullmatch(normalized_session_id):
        raise MovementError(
            "invalid_session", "Invalid session_id format.", status_code=400
        )

    state_manager = get_state_manager(normalized_session_id, db)
    current_location = str(state_manager.get_variable("location") or "").strip()
    if not current_location:
        raise MovementError(
            "location_required",
            "Session has no current location set.",
            status_code=400,
        )

    normalized_destination = str(destination or "").strip()
    if not normalized_destination or len(normalized_destination) > 200:
        raise MovementError(
            "invalid_destination",
            "Destination must contain 1 to 200 characters.",
            status_code=422,
        )

    current_anchor = resolve_route_anchor(db, current_location)
    destination_sublocation = resolve_active_sublocation(
        db,
        label=normalized_destination,
        parent_location=current_anchor,
    )
    if (
        destination_sublocation is None
        and allow_sublocation_create
        and is_local_sublocation_candidate(normalized_destination, current_anchor)
    ):
        destination_sublocation = create_or_refresh_ephemeral(
            db,
            parent_location=current_anchor,
            label=normalized_destination,
            created_by_session=normalized_session_id,
        )
    if destination_sublocation is not None:
        normalized_destination = str(
            destination_sublocation.name or normalized_destination
        )
    destination_anchor = resolve_route_anchor(db, normalized_destination)

    if (
        current_location != normalized_destination
        and current_anchor
        and destination_anchor
        and current_anchor == destination_anchor
    ):
        route = [current_location, normalized_destination]
    else:
        route = find_route(
            db,
            current_anchor or current_location,
            destination_anchor or normalized_destination,
        )
        if (
            route
            and current_anchor
            and current_location != current_anchor
            and route[0] == current_anchor
        ):
            route = [current_location, *route[1:]]
        if (
            route
            and destination_anchor
            and destination_anchor != normalized_destination
            and route[-1] == destination_anchor
        ):
            route = [*route, normalized_destination]

    snapped = False
    if not route:
        destination_route = find_route(
            db,
            destination_anchor or normalized_destination,
            destination_anchor or normalized_destination,
        )
        if destination_route and current_location != normalized_destination:
            route = [current_location, normalized_destination]
            snapped = True
        else:
            raise MovementError(
                "route_not_found",
                f"No route from '{current_location}' to '{normalized_destination}'.",
                status_code=404,
            )

    if len(route) == 1:
        return MovementReceipt(
            moved=False,
            from_location=current_location,
            to_location=current_location,
            route=route,
            route_remaining=[],
            narrative=f"You are already at {current_location.replace('_', ' ')}.",
        )

    entered_locations = route[1:] if skip_to_destination and not snapped else [route[1]]
    try:
        assert_route_entry_allowed(
            db,
            session_id=normalized_session_id,
            destinations=entered_locations,
        )
    except SpaceAccessError as exc:
        db.rollback()
        raise MovementError(
            exc.code,
            {"code": exc.code, "message": str(exc)},
            status_code=exc.status_code,
        ) from exc

    raw_role = str(state_manager.get_variable("player_role") or "")
    role_name = (
        raw_role.split(" — ")[0].strip() if " — " in raw_role else raw_role.strip()
    ) or None
    mover_name = (
        _slug_display_name(normalized_session_id)
        or role_name
        or state_manager.get_variable("player_name")
        or "Someone"
    )
    state_snapshot = deepcopy(state_manager.export_state())

    if skip_to_destination and not snapped:
        try:
            final_destination = route[-1]
            intermediate_hops = route[1:-1]
            for hop in intermediate_hops:
                previous = state_manager.get_variable("location") or current_location
                state_manager.set_variable("location", hop)
                summary = (
                    f"{mover_name} passes through {hop.replace('_', ' ')}, "
                    f"continuing toward {final_destination.replace('_', ' ')}."
                )
                submit_world_event(
                    db,
                    WorldEventCommand(
                        session_id=normalized_session_id,
                        event_type=EVENT_TYPE_MOVEMENT,
                        summary=summary,
                        delta=_movement_event_delta(
                            origin=previous,
                            destination=hop,
                            in_transit=True,
                            mover_name=str(mover_name),
                            summary=summary,
                        ),
                        metadata={
                            "surface": "map_move",
                            "mode": "skip_to_destination",
                        },
                        preserve_event_type=True,
                        defer_commit=True,
                    ),
                )
            previous_final = state_manager.get_variable("location") or current_location
            state_manager.set_variable("location", final_destination)
            if (
                destination_sublocation is not None
                and final_destination == normalized_destination
            ):
                touch_sublocation(destination_sublocation)
            stage_state(state_manager, db)
            final_summary = (
                f"{mover_name} arrives at {final_destination.replace('_', ' ')}."
            )
            submit_world_event(
                db,
                WorldEventCommand(
                    session_id=normalized_session_id,
                    event_type=EVENT_TYPE_MOVEMENT,
                    summary=final_summary,
                    delta=_movement_event_delta(
                        origin=previous_final,
                        destination=final_destination,
                        in_transit=False,
                        mover_name=str(mover_name),
                        summary=final_summary,
                    ),
                    metadata={"surface": "map_move", "mode": "skip_to_destination"},
                    preserve_event_type=True,
                    defer_commit=True,
                ),
            )
            db.commit()
        except Exception:
            db.rollback()
            state_manager.import_state(state_snapshot)
            raise
        if intermediate_hops:
            via = ", ".join(hop.replace("_", " ") for hop in intermediate_hops)
            narrative = (
                f"You pass through {via} and arrive at "
                f"{final_destination.replace('_', ' ')}."
            )
        else:
            narrative = f"You arrive at {final_destination.replace('_', ' ')}."
        return MovementReceipt(
            moved=True,
            from_location=current_location,
            to_location=final_destination,
            route=route,
            route_remaining=[],
            narrative=narrative,
        )

    next_location = route[1]
    route_remaining = route[2:]

    if snapped:
        narrative = f"You find yourself at {next_location.replace('_', ' ')}."
    elif route_remaining:
        stops = len(route_remaining)
        plural = "s" if stops != 1 else ""
        narrative = (
            f"You head toward {normalized_destination.replace('_', ' ')}, "
            f"passing through {next_location.replace('_', ' ')}. "
            f"({stops} more stop{plural} to go)"
        )
    else:
        narrative = f"You arrive at {next_location.replace('_', ' ')}."

    if route_remaining:
        final_destination = route[-1] if route else normalized_destination
        event_summary = (
            f"{mover_name} passes through {next_location.replace('_', ' ')}, "
            f"continuing toward {final_destination.replace('_', ' ')}."
        )
    else:
        event_summary = f"{mover_name} arrives at {next_location.replace('_', ' ')}."

    try:
        state_manager.set_variable("location", next_location)
        if (
            destination_sublocation is not None
            and next_location == normalized_destination
        ):
            touch_sublocation(destination_sublocation)
        stage_state(state_manager, db)
        submit_world_event(
            db,
            WorldEventCommand(
                session_id=normalized_session_id,
                event_type=EVENT_TYPE_MOVEMENT,
                summary=event_summary,
                delta=_movement_event_delta(
                    origin=current_location,
                    destination=next_location,
                    in_transit=bool(route_remaining),
                    mover_name=str(mover_name),
                    summary=event_summary,
                ),
                metadata={"surface": "map_move", "mode": "single_hop"},
                preserve_event_type=True,
                defer_commit=True,
            ),
        )
        db.commit()
    except Exception:
        db.rollback()
        state_manager.import_state(state_snapshot)
        raise

    return MovementReceipt(
        moved=True,
        from_location=current_location,
        to_location=next_location,
        route=route,
        route_remaining=route_remaining,
        narrative=narrative,
    )
