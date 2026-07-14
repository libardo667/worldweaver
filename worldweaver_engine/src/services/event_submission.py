# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Canonical application boundary for validating and recording world events."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping

from sqlalchemy.orm import Session

from ..models import WorldEvent, WorldProjection
from .rules.reducer import reduce_event
from .rules.schema import EventIntent, ReducerReceipt
from .state_manager import AdvancedStateManager
from .world_memory import record_event


class EventSubmissionError(ValueError):
    """Raised when a world-event command violates the application contract."""


@dataclass(frozen=True)
class WorldEventCommand:
    """One validated request to reduce and/or record a canonical world event.

    ``storylet_id`` remains only as a storage-compatibility field until Major 69's
    turn-pipeline migration removes it from the event model.
    """

    event_type: str
    summary: str
    session_id: str | None = None
    delta: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    intent: EventIntent | None = None
    state_manager: AdvancedStateManager | None = None
    storylet_id: int | None = None
    idempotency_key: str | None = None
    skip_graph_extraction: bool = False
    skip_projection: bool = False
    preserve_event_type: bool = False


@dataclass(frozen=True)
class WorldEventReceipt:
    """Stable application-level receipt for a submitted event."""

    event: WorldEvent
    reducer_receipt: ReducerReceipt | None
    projection_paths: tuple[str, ...]

    @property
    def event_id(self) -> int:
        if self.event.id is None:
            raise RuntimeError("persisted world event has no id")
        return int(self.event.id)

    @property
    def event_type(self) -> str:
        return str(self.event.event_type)


def _validate_command(command: WorldEventCommand) -> None:
    if not str(command.event_type or "").strip():
        raise EventSubmissionError("event_type must not be blank")
    if not str(command.summary or "").strip():
        raise EventSubmissionError("summary must not be blank")
    if command.session_id is not None and len(str(command.session_id)) > 64:
        raise EventSubmissionError("session_id exceeds the 64-character storage contract")
    if not isinstance(command.delta, Mapping):
        raise EventSubmissionError("delta must be a mapping")
    if not isinstance(command.metadata, Mapping):
        raise EventSubmissionError("metadata must be a mapping")
    if command.intent is not None and command.state_manager is None:
        raise EventSubmissionError("state_manager is required when intent is provided")
    if command.intent is None and command.state_manager is not None:
        raise EventSubmissionError("state_manager mutations require an explicit reducer intent")
    if command.idempotency_key and not command.session_id:
        raise EventSubmissionError("idempotency_key requires session_id")


def submit_world_event(db: Session, command: WorldEventCommand) -> WorldEventReceipt:
    """Validate, optionally reduce, persist, and report one world event.

    State is restored and the database transaction rolled back if reduction or
    persistence raises. Projection and graph updates remain delegated to the
    existing ``record_event`` implementation during the ownership migration.
    """

    _validate_command(command)

    reducer_receipt: ReducerReceipt | None = None
    state_snapshot: dict[str, Any] | None = None
    if command.state_manager is not None:
        # ``export_state`` contains the manager's live variables mapping, so a
        # shallow snapshot would be mutated by the reducer it is meant to undo.
        state_snapshot = deepcopy(command.state_manager.export_state())

    try:
        persisted_delta = dict(command.delta)
        persisted_metadata = dict(command.metadata)
        if command.intent is not None and command.state_manager is not None:
            reducer_receipt = reduce_event(db, command.state_manager, command.intent)
            persisted_delta.update(reducer_receipt.applied_changes)
            persisted_metadata.setdefault("reducer_receipt", reducer_receipt.model_dump())

        event = record_event(
            db=db,
            session_id=command.session_id,
            storylet_id=command.storylet_id,
            event_type=command.event_type,
            summary=command.summary,
            delta=persisted_delta,
            state_manager=None,
            metadata=persisted_metadata,
            idempotency_key=command.idempotency_key,
            skip_graph_extraction=command.skip_graph_extraction,
            skip_projection=command.skip_projection,
            preserve_event_type=command.preserve_event_type,
        )
    except Exception:
        db.rollback()
        if command.state_manager is not None and state_snapshot is not None:
            command.state_manager.import_state(state_snapshot)
        raise

    projection_paths: tuple[str, ...] = ()
    if event.id is not None and not command.skip_projection:
        projection_paths = tuple(row[0] for row in db.query(WorldProjection.path).filter(WorldProjection.source_event_id == int(event.id)).order_by(WorldProjection.path.asc()).all())

    return WorldEventReceipt(
        event=event,
        reducer_receipt=reducer_receipt,
        projection_paths=projection_paths,
    )
