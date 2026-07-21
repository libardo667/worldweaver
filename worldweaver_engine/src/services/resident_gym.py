# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""A small deterministic gym over the production world-rule services.

The gym owns scenario arrangement and an observation record.  It does not own
alternate movement, speech, presence, or signal-delivery rules.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable

from sqlalchemy.orm import Session

from ..config import settings
from ..models import LocationChat, SessionVars, WorldEvent, WorldFact, WorldProjection
from .clock import (
    Clock,
    ControlledClock,
    ScheduledEvent,
    ScheduledEventQueue,
    SystemClock,
)
from .correspondence import (
    SendCorrespondenceCommand,
    acknowledge_correspondence,
    pending_correspondence,
    send_correspondence,
)
from .live_signals import read_live_signals
from .local_speech import post_local_speech
from .movement import move_session
from .participant_scene import build_participant_scene
from .session_lifecycle import (
    SessionBootstrapCommand,
    bootstrap_session,
    retire_session_presence,
)
from .gym_checkpoint import (
    CHECKPOINT_SCHEMA,
    CHECKPOINT_SCHEMA_VERSION,
    GymCheckpointError,
    capture_sqlite_database,
    restore_sqlite_database,
    seal_checkpoint,
    validate_checkpoint,
    validate_sqlite_participant_bindings,
)
from .session_service import clear_session_caches, get_state_manager, save_state
from .sublocations import (
    active_sublocations,
    create_or_refresh_ephemeral,
    sublocation_payload,
)
from .world_context import build_world_context_header
from .world_memory import seed_location_graph


@dataclass(frozen=True, slots=True)
class GymParticipant:
    """One synthetic participant and the implementation driving it."""

    session_id: str
    actor_id: str
    display_name: str
    implementation: str


def _empty_state_descriptor() -> dict[str, Any]:
    return {
        "custody": "participant_private",
        "format": "none",
        "format_version": 1,
        "artifact_id": "",
        "sha256": "",
        "byte_length": 0,
    }


def _validate_state_descriptor(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise GymCheckpointError("participant state descriptor must be an object")
    allowed = {
        "custody",
        "format",
        "format_version",
        "artifact_id",
        "sha256",
        "byte_length",
    }
    if set(raw) != allowed:
        raise GymCheckpointError("participant state descriptor fields are invalid")
    descriptor = {
        "custody": str(raw["custody"]),
        "format": str(raw["format"]),
        "format_version": int(raw["format_version"]),
        "artifact_id": str(raw["artifact_id"]),
        "sha256": str(raw["sha256"]),
        "byte_length": int(raw["byte_length"]),
    }
    if descriptor["custody"] != "participant_private":
        raise GymCheckpointError("participant state custody is invalid")
    if descriptor["format"] == "none":
        if (
            descriptor["format_version"] != 1
            or descriptor["artifact_id"]
            or descriptor["sha256"]
            or descriptor["byte_length"] != 0
        ):
            raise GymCheckpointError("empty participant state descriptor is invalid")
    elif (
        descriptor["format"] != "worldweaver.hearth-package"
        or descriptor["format_version"] != 1
        or not descriptor["artifact_id"]
        or len(descriptor["sha256"]) != 64
        or any(
            character not in "0123456789abcdef" for character in descriptor["sha256"]
        )
        or descriptor["byte_length"] <= 0
    ):
        raise GymCheckpointError("external participant state descriptor is invalid")
    return descriptor


@dataclass(frozen=True, slots=True)
class GymParticipantCheckpoint:
    """A participant binding plus opaque private/model artifact references."""

    session_id: str
    actor_id: str
    implementation: str
    adapter_id: str
    adapter_version: int
    model_id: str
    private_state: dict[str, Any] = field(default_factory=_empty_state_descriptor)
    model_state: dict[str, Any] = field(default_factory=_empty_state_descriptor)

    def as_payload(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_payload(cls, raw: Any) -> "GymParticipantCheckpoint":
        if not isinstance(raw, dict):
            raise GymCheckpointError("participant checkpoint must be an object")
        expected_fields = {
            "session_id",
            "actor_id",
            "implementation",
            "adapter_id",
            "adapter_version",
            "model_id",
            "private_state",
            "model_state",
        }
        if set(raw) != expected_fields:
            raise GymCheckpointError("participant checkpoint fields are invalid")
        try:
            checkpoint = cls(
                session_id=str(raw["session_id"]),
                actor_id=str(raw["actor_id"]),
                implementation=str(raw["implementation"]),
                adapter_id=str(raw["adapter_id"]),
                adapter_version=int(raw["adapter_version"]),
                model_id=str(raw["model_id"]),
                private_state=_validate_state_descriptor(raw["private_state"]),
                model_state=_validate_state_descriptor(raw["model_state"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise GymCheckpointError("participant checkpoint is invalid") from exc
        if (
            not checkpoint.session_id
            or not checkpoint.actor_id
            or not checkpoint.implementation
            or not checkpoint.adapter_id
            or checkpoint.adapter_version < 1
            or not checkpoint.model_id
        ):
            raise GymCheckpointError("participant checkpoint binding is invalid")
        return checkpoint


@dataclass(frozen=True, slots=True)
class GymRecord:
    """One fact observed at a production service boundary."""

    sequence: int
    occurred_at: str
    kind: str
    actor: str | None
    location: str | None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GymEpisodeResult:
    """Portable structural result from one synthetic episode."""

    schema: str
    schema_version: int
    episode: str
    world_id: str
    locations: tuple[str, ...]
    participants: tuple[GymParticipant, ...]
    fidelity: "GymFidelityProfile"
    final_locations: dict[str, str]
    records: tuple[GymRecord, ...]

    def as_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "episode": self.episode,
            "world_id": self.world_id,
            "locations": list(self.locations),
            "participants": [asdict(item) for item in self.participants],
            "fidelity": asdict(self.fidelity),
            "final_locations": dict(self.final_locations),
            "records": [asdict(item) for item in self.records],
        }


@dataclass(frozen=True, slots=True)
class GymFidelityProfile:
    """Machine-readable boundary on what one episode may claim to represent."""

    engine_rules: str
    world_state: str
    resident_composition: str
    participant_transport: str
    resident_authorization: str
    city_sources: str
    world_time: str
    hearth_attachment: str
    federation: str


@dataclass(frozen=True, slots=True)
class _SignalCursor:
    shard_id: str
    location: str
    after_id: int


class ProductionRuleGym:
    """Arrange and observe an episode through the live domain services."""

    def __init__(
        self,
        db: Session,
        *,
        episode: str,
        world_id: str,
        clock: Clock | None = None,
        scenario_id: str = "",
        scenario_version: int = 1,
        scenario_seed: int = 0,
        record_observer: Callable[[GymRecord], None] | None = None,
    ):
        self.db = db
        self.episode = str(episode or "").strip()
        self.world_id = str(world_id or "").strip()
        if not self.episode or not self.world_id:
            raise ValueError("episode and world_id are required")
        self.clock = clock or SystemClock()
        self.scenario_id = (
            str(scenario_id or self.episode).strip().lower().replace(" ", "-")
        )
        self.scenario_version = int(scenario_version)
        self.scenario_seed = int(scenario_seed)
        if not self.scenario_id or self.scenario_version < 1 or self.scenario_seed < 0:
            raise ValueError("gym scenario provenance is invalid")
        self._scheduled = (
            ScheduledEventQueue(self.clock)
            if isinstance(self.clock, ControlledClock)
            else None
        )
        self._locations: tuple[str, ...] = ()
        self._participants: dict[str, GymParticipant] = {}
        self._participant_checkpoints: dict[str, GymParticipantCheckpoint] = {}
        self._cursors: dict[str, _SignalCursor] = {}
        self._records: list[GymRecord] = []
        self._record_observer = record_observer

    def _record(
        self,
        kind: str,
        *,
        participant: GymParticipant | None = None,
        location: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        record = GymRecord(
            sequence=len(self._records) + 1,
            occurred_at=self.clock.now().isoformat(),
            kind=kind,
            actor=participant.display_name if participant is not None else None,
            location=location,
            detail=dict(detail or {}),
        )
        self._records.append(record)
        if self._record_observer is not None:
            self._record_observer(record)

    def _scheduled_queue(self) -> ScheduledEventQueue:
        if self._scheduled is None:
            raise ValueError("scheduled gym events require a controlled clock")
        return self._scheduled

    def schedule_in(
        self,
        elapsed: timedelta,
        *,
        kind: str,
        payload: dict[str, Any] | None = None,
    ) -> ScheduledEvent:
        """Schedule one structural instruction relative to current gym time."""

        event = self._scheduled_queue().schedule_at(
            self.clock.now() + elapsed,
            kind=kind,
            payload=payload,
        )
        self._record(
            "scheduled_event_created",
            detail={
                "event_id": event.event_id,
                "event_kind": event.kind,
                "due_at": event.due_at.isoformat(),
            },
        )
        return event

    def schedule_resident_return(
        self,
        session_id: str,
        *,
        resident_event_id: str,
        activity_id: str,
        due_at: datetime,
    ) -> ScheduledEvent:
        """Schedule one content-free private deadline for a bound participant."""

        participant = self._participant(session_id)
        binding = self._participant_checkpoints[session_id]
        if binding.private_state.get("format") != "worldweaver.hearth-package":
            raise ValueError("resident return requires a bound private artifact")
        normalized_event_id = str(resident_event_id or "").strip()
        normalized_activity_id = str(activity_id or "").strip()
        if not normalized_event_id or not normalized_activity_id:
            raise ValueError("resident return requires event and activity IDs")
        normalized_due_at = (
            due_at if due_at.tzinfo is not None else due_at.replace(tzinfo=timezone.utc)
        ).astimezone(timezone.utc)
        if normalized_due_at < self.clock.now():
            raise ValueError("resident return deadline is already past")
        event = self._scheduled_queue().schedule_at(
            normalized_due_at,
            kind="resident_private_return",
            payload={
                "session_id": participant.session_id,
                "resident_event_id": normalized_event_id,
                "activity_id": normalized_activity_id,
            },
        )
        self._record(
            "scheduled_event_created",
            participant=participant,
            detail={
                "event_id": event.event_id,
                "event_kind": event.kind,
                "due_at": event.due_at.isoformat(),
            },
        )
        return event

    def offer_next_scheduled(self) -> tuple[ScheduledEvent, ...]:
        """Move to the next deadline and offer it without consuming it."""

        before = self.clock.now()
        events = self._scheduled_queue().advance_to_next()
        after = self.clock.now()
        if after > before:
            self._record(
                "time_advanced",
                detail={
                    "from": before.isoformat(),
                    "to": after.isoformat(),
                    "elapsed_seconds": int((after - before).total_seconds()),
                },
            )
        for event in events:
            self._record(
                "scheduled_event_offered",
                detail={
                    "event_id": event.event_id,
                    "event_kind": event.kind,
                    "due_at": event.due_at.isoformat(),
                },
            )
        return events

    def acknowledge_scheduled(self, event_ids: Iterable[str]) -> tuple[str, ...]:
        """Consume exact due instructions after their handlers succeed."""

        acknowledged = self._scheduled_queue().acknowledge(event_ids)
        self._record(
            "scheduled_event_acknowledged",
            detail={"event_ids": list(acknowledged)},
        )
        return acknowledged

    def scheduled_checkpoint(self) -> dict[str, Any]:
        """Return the queue's complete JSON-safe restart checkpoint."""

        return self._scheduled_queue().as_payload()

    def arrange_world(self, locations: Iterable[str]) -> None:
        """Create a bounded synthetic setting with production seeding helpers."""

        normalized = tuple(
            dict.fromkeys(str(location or "").strip() for location in locations)
        )
        normalized = tuple(location for location in normalized if location)
        if len(normalized) < 2:
            raise ValueError("a gym world needs at least two named locations")
        if self._locations:
            raise ValueError("the gym world is already arranged")

        seed_location_graph(
            self.db,
            [
                {
                    "name": location,
                    "description": "",
                    "city_id": settings.city_id,
                }
                for location in normalized
            ],
        )
        host = get_state_manager(self.world_id, self.db)
        host.set_variable("world_theme", "A controlled communication scenario")
        host.set_variable("player_role", "synthetic scenario host")
        host.set_variable("_bootstrap_state", "completed")
        host.set_variable("_bootstrap_source", "resident-gym")
        host.set_world_context(
            build_world_context_header(
                world_name=self.episode,
                theme="A controlled communication scenario",
                premise="Synthetic participants exercise production world rules.",
                entry_point=normalized[0],
                canonical_locations=normalized,
                source="resident_gym",
            )
        )
        save_state(host, self.db, now=self.clock.now())
        self._locations = normalized
        self._record("world_arranged", detail={"locations": list(normalized)})

    def join(self, participant: GymParticipant, *, location: str) -> None:
        """Attach one synthetic actor through canonical session bootstrap."""

        if not self._locations:
            raise ValueError("arrange the gym world before participants join")
        if location not in self._locations:
            raise ValueError(f"unknown gym location: {location}")
        if participant.session_id in self._participants:
            raise ValueError(f"participant already joined: {participant.session_id}")

        receipt = bootstrap_session(
            self.db,
            command=SessionBootstrapCommand(
                session_id=participant.session_id,
                actor_id=participant.actor_id,
                player_role=participant.display_name,
                world_id=self.world_id,
                world_theme="A controlled communication scenario",
                tone="plain and observational",
                bootstrap_source="resident-gym",
                entry_location=location,
            ),
            now=self.clock.now(),
        )
        self._participants[participant.session_id] = participant
        self._participant_checkpoints[participant.session_id] = (
            GymParticipantCheckpoint(
                session_id=participant.session_id,
                actor_id=participant.actor_id,
                implementation=participant.implementation,
                adapter_id=f"worldweaver.gym.{participant.implementation}",
                adapter_version=1,
                model_id="none",
            )
        )
        self._record(
            "joined",
            participant=participant,
            location=location,
            detail={
                "implementation": participant.implementation,
                "bootstrap_state": receipt.bootstrap_state,
            },
        )

    def bind_participant_artifacts(
        self,
        session_id: str,
        *,
        adapter_id: str,
        adapter_version: int,
        model_id: str,
        private_state: dict[str, Any] | None = None,
        model_state: dict[str, Any] | None = None,
    ) -> None:
        """Bind externally custodied private/model artifacts by digest, not prose."""

        participant = self._participant(session_id)
        self._participant_checkpoints[session_id] = (
            GymParticipantCheckpoint.from_payload(
                {
                    "session_id": participant.session_id,
                    "actor_id": participant.actor_id,
                    "implementation": participant.implementation,
                    "adapter_id": str(adapter_id or ""),
                    "adapter_version": int(adapter_version),
                    "model_id": str(model_id or "none"),
                    "private_state": private_state or _empty_state_descriptor(),
                    "model_state": model_state or _empty_state_descriptor(),
                }
            )
        )

    def _participant(self, session_id: str) -> GymParticipant:
        try:
            return self._participants[session_id]
        except KeyError as exc:
            raise ValueError(f"unknown gym participant: {session_id}") from exc

    def _participant_location(self, session_id: str) -> str:
        """Read a live location or retain the last structural attachment location."""

        if self.db.get(SessionVars, session_id) is not None:
            return str(
                get_state_manager(session_id, self.db).get_variable("location") or ""
            )
        participant = self._participant(session_id)
        for record in reversed(self._records):
            if record.actor == participant.display_name and record.location:
                return str(record.location)
        return ""

    def place_names(self, session_id: str) -> tuple[str, ...]:
        """Return the bounded scenario graph vocabulary to one joined participant."""

        self._participant(session_id)
        return self._locations

    def retire(self, session_id: str) -> None:
        """End one temporary presence without erasing its durable actor."""

        participant = self._participant(session_id)
        location = str(
            get_state_manager(session_id, self.db).get_variable("location") or ""
        )
        receipt = retire_session_presence(self.db, session_id=session_id)
        self._participants.pop(session_id)
        self._participant_checkpoints.pop(session_id, None)
        self._cursors.pop(session_id, None)
        self._record(
            "departed",
            participant=participant,
            location=location,
            detail={"session_id": receipt.session_id},
        )

    def send_letter(
        self, sender_session_id: str, recipient_actor_id: str, message: str
    ) -> int:
        """Send private mail through the production correspondence service."""

        participant = self._participant(sender_session_id)
        receipt = send_correspondence(
            self.db,
            command=SendCorrespondenceCommand(
                sender_session_id=sender_session_id,
                recipient_actor_id=recipient_actor_id,
                body=message,
            ),
        )
        self._record(
            "letter_sent",
            participant=participant,
            detail={
                "message_id": receipt.message_id,
                "recipient_actor_id": receipt.recipient_actor_id,
                "message": str(message).strip(),
            },
        )
        return receipt.message_id

    def check_mail(self, session_id: str) -> tuple[dict[str, Any], ...]:
        """Offer pending mail without acknowledging it."""

        participant = self._participant(session_id)
        inbox = pending_correspondence(self.db, session_id=session_id, limit=50)
        messages = tuple(message.as_payload() for message in inbox.messages)
        if not messages:
            self._record("mailbox_empty", participant=participant)
        else:
            for message in messages:
                self._record(
                    "letter_waiting",
                    participant=participant,
                    detail={
                        "message_id": int(message["message_id"]),
                        "sender": str(message["sender_name"]),
                        "message": str(message["body"]),
                    },
                )
        return messages

    def acknowledge_mail(self, session_id: str, message_ids: Iterable[int]) -> None:
        """Explicitly acknowledge mail after a participant has processed it."""

        participant = self._participant(session_id)
        receipt = acknowledge_correspondence(
            self.db,
            session_id=session_id,
            message_ids=message_ids,
        )
        self._record(
            "letter_acknowledged",
            participant=participant,
            detail={"message_ids": list(receipt.acknowledged_ids)},
        )

    def create_sublocation(
        self,
        session_id: str,
        *,
        label: str,
        ttl_seconds: int,
    ) -> str:
        """Create a bounded child place using the production lifetime rule."""

        participant = self._participant(session_id)
        parent_location = str(
            get_state_manager(session_id, self.db).get_variable("location") or ""
        )
        row = create_or_refresh_ephemeral(
            self.db,
            parent_location=parent_location,
            label=label,
            created_by_session=session_id,
            ttl_seconds=ttl_seconds,
            now=self.clock.now(),
        )
        self.db.commit()
        self.db.refresh(row)
        payload = sublocation_payload(row)
        self._record(
            "sublocation_created",
            participant=participant,
            location=parent_location,
            detail={
                "sublocation_id": payload["sublocation_id"],
                "label": payload["label"],
                "expires_at": payload["expires_at"],
            },
        )
        return str(payload["sublocation_id"])

    def inspect_sublocation(
        self,
        *,
        parent_location: str,
        sublocation_id: str,
    ) -> bool:
        """Ask the production lifetime rule whether a child place is still active."""

        active_ids = {
            str(sublocation_payload(row)["sublocation_id"])
            for row in active_sublocations(
                self.db,
                parent_location=parent_location,
                now=self.clock.now(),
            )
        }
        active = sublocation_id in active_ids
        self._record(
            "sublocation_active" if active else "sublocation_expired",
            location=parent_location,
            detail={"sublocation_id": sublocation_id},
        )
        return active

    @staticmethod
    def _cursor_from_payload(payload: dict[str, Any]) -> _SignalCursor:
        cursor = payload.get("cursor")
        if not isinstance(cursor, dict):
            raise ValueError("production signal receipt omitted its cursor")
        return _SignalCursor(
            shard_id=str(cursor.get("shard_id") or ""),
            location=str(cursor.get("location") or ""),
            after_id=int(cursor.get("after_id") or 0),
        )

    def listen(self, session_id: str) -> tuple[dict[str, Any], ...]:
        """Read exact-place speech through the production live-signal cursor."""

        participant = self._participant(session_id)
        cursor = self._cursors.get(session_id)
        payload = read_live_signals(
            self.db,
            session_id=session_id,
            after_id=cursor.after_id if cursor is not None else None,
            cursor_shard=cursor.shard_id if cursor is not None else None,
            cursor_location=cursor.location if cursor is not None else None,
            limit=50,
        )
        next_cursor = self._cursor_from_payload(payload)
        self._cursors[session_id] = next_cursor
        status = str(payload.get("cursor_status") or "")
        raw_events = payload.get("events")
        events = tuple(raw_events if isinstance(raw_events, list) else [])

        if status != "current":
            self._record(
                "listening_scope",
                participant=participant,
                location=next_cursor.location,
                detail={"status": status, "after_id": next_cursor.after_id},
            )
        elif not events:
            self._record(
                "heard_nothing_new",
                participant=participant,
                location=next_cursor.location,
            )
        else:
            for event in events:
                self._record(
                    "heard",
                    participant=participant,
                    location=str(event.get("location") or next_cursor.location),
                    detail={
                        "signal_id": int(event.get("id") or 0),
                        "speaker": str(event.get("display_name") or ""),
                        "message": str(event.get("message") or ""),
                    },
                )
        return events

    def observe(self, session_id: str) -> dict[str, Any]:
        """Read the same factual local scene used by the live participant API."""

        participant = self._participant(session_id)
        scene = build_participant_scene(
            self.db,
            session_id=session_id,
            now=self.clock.now(),
        )
        graph = scene.get("location_graph")
        graph_payload = graph if isinstance(graph, dict) else {}
        present = scene.get("present")
        traces = scene.get("traces_here")
        self._record(
            "observation_ready",
            participant=participant,
            location=str(scene.get("location") or ""),
            detail={
                "present_count": len(present) if isinstance(present, list) else 0,
                "trace_count": len(traces) if isinstance(traces, list) else 0,
                "route_count": len(graph_payload.get("edges") or []),
                "place_count": len(graph_payload.get("nodes") or []),
            },
        )
        return scene

    def read_location_chat(
        self,
        session_id: str,
        *,
        location: str,
    ) -> tuple[dict[str, Any], ...]:
        """Read bounded exact-place speech for a participant adapter.

        This mirrors the authenticated live HTTP representation while keeping the
        isolated gym on its in-memory database.  It is a read, not signal-cursor
        delivery; the reference core applies its own activation-time filtering.
        """

        participant = self._participant(session_id)
        normalized_location = str(location or "").strip()
        current_location = str(
            get_state_manager(session_id, self.db).get_variable("location") or ""
        ).strip()
        if not normalized_location or normalized_location != current_location:
            raise ValueError("participant may read chat only at its current location")
        rows = list(
            reversed(
                self.db.query(LocationChat)
                .filter(LocationChat.location == normalized_location)
                .order_by(LocationChat.created_at.desc())
                .limit(30)
                .all()
            )
        )
        session_ids = {
            str(row.session_id or "").strip()
            for row in rows
            if str(row.session_id or "").strip()
        }
        actor_ids = {
            str(row.session_id or "").strip(): str(row.actor_id or "").strip()
            for row in self.db.query(SessionVars)
            .filter(SessionVars.session_id.in_(session_ids))
            .all()
        }
        messages = tuple(
            {
                "id": int(row.id),
                "session_id": str(row.session_id or ""),
                "actor_id": str(row.actor_id or actor_ids.get(row.session_id, "")),
                "display_name": str(row.display_name or ""),
                "message": str(row.message or ""),
                "ts": row.created_at.isoformat() if row.created_at else "",
                "location": normalized_location,
            }
            for row in rows
        )
        self._record(
            "local_speech_read",
            participant=participant,
            location=normalized_location,
            detail={"message_count": len(messages)},
        )
        return messages

    def record_resident_boundary(
        self,
        session_id: str,
        *,
        kind: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Record one content-safe child-process lifecycle boundary."""

        allowed = {
            "resident_host_started",
            "resident_host_finished",
            "resident_city_profile_loaded",
            "resident_inference_started",
            "resident_inference_finished",
            "resident_hearth_observed",
        }
        if kind not in allowed:
            raise ValueError("unsupported resident boundary record")
        safe_detail = dict(detail or {})
        if kind in {"resident_host_started", "resident_host_finished"}:
            if safe_detail:
                raise ValueError("resident host boundary must be content-free")
        elif kind == "resident_city_profile_loaded":
            if set(safe_detail) != {
                "city_id",
                "capability_ids",
                "source_names",
            }:
                raise ValueError("resident city profile fields are invalid")
            city_id = str(safe_detail.get("city_id") or "").strip()

            def public_ids(field: str) -> list[str]:
                raw = safe_detail.get(field)
                if not isinstance(raw, list) or len(raw) > 32:
                    raise ValueError("resident city profile IDs are invalid")
                values = [str(item or "").strip() for item in raw]
                if values != sorted(set(values)) or any(
                    not value
                    or len(value) > 80
                    or any(
                        character not in "abcdefghijklmnopqrstuvwxyz0123456789_.:-"
                        for character in value
                    )
                    for value in values
                ):
                    raise ValueError("resident city profile IDs are invalid")
                return values

            if (
                not city_id
                or len(city_id) > 80
                or any(
                    character not in "abcdefghijklmnopqrstuvwxyz0123456789_.:-"
                    for character in city_id
                )
            ):
                raise ValueError("resident city profile city ID is invalid")
            safe_detail = {
                "city_id": city_id,
                "capability_ids": public_ids("capability_ids"),
                "source_names": public_ids("source_names"),
            }
        elif kind == "resident_hearth_observed":
            if set(safe_detail) != {
                "attachment",
                "hosting_state",
                "location",
                "source_names",
                "hour",
                "day_of_week",
                "time_of_day",
                "observed_at",
            }:
                raise ValueError("resident hearth observation fields are invalid")
            source_names = safe_detail.get("source_names")
            hour = safe_detail.get("hour")
            try:
                observed_at = datetime.fromisoformat(
                    str(safe_detail.get("observed_at") or "")
                )
            except ValueError as exc:
                raise ValueError("resident hearth observation time is invalid") from exc
            if (
                safe_detail.get("attachment") != "hearth"
                or safe_detail.get("hosting_state") != "hosted"
                or not isinstance(source_names, list)
                or source_names != sorted(set(source_names))
                or any(
                    not str(name or "").strip() or len(str(name)) > 80
                    for name in source_names
                )
                or isinstance(hour, bool)
                or not isinstance(hour, int)
                or not 0 <= hour <= 23
                or observed_at.tzinfo is None
                or observed_at.astimezone(timezone.utc) != self.clock.now()
            ):
                raise ValueError("resident hearth observation is invalid")
            location = str(safe_detail.get("location") or "").strip()
            if not location or len(location) > 120:
                raise ValueError("resident hearth location is invalid")
            safe_detail = {
                **safe_detail,
                "location": location,
                "source_names": [str(name) for name in source_names],
                "observed_at": observed_at.astimezone(timezone.utc).isoformat(),
            }
        elif set(safe_detail) - {
            "call_index",
            "model_id",
            "prompt_tokens",
            "completion_tokens",
        }:
            raise ValueError("resident boundary detail is not content-safe")
        participant = self._participant(session_id)
        location = (
            str(safe_detail["location"])
            if kind == "resident_hearth_observed"
            else self._participant_location(session_id)
        )
        self._record(
            kind,
            participant=participant,
            location=location,
            detail=safe_detail,
        )

    def record_resident_attachment_verified(
        self,
        session_id: str,
        *,
        attachment: str,
        process_hosting_state: str,
        active_city_session_count: int,
    ) -> None:
        """Record engine and private-checkpoint agreement after city retirement."""

        participant = self._participant(session_id)
        if (
            attachment != "hearth"
            or process_hosting_state != "suspended"
            or active_city_session_count != 0
        ):
            raise ValueError("resident attachment verification failed")
        self._record(
            "resident_attachment_verified",
            participant=participant,
            location="the hearth",
            detail={
                "attachment": attachment,
                "process_hosting_state": process_hosting_state,
                "active_city_session_count": active_city_session_count,
            },
        )

    def record_participant_http(
        self,
        session_id: str,
        *,
        method: str,
        target: str,
        status_code: int,
        resident_proof: bool,
        response_payload: Any = None,
    ) -> None:
        """Record a content-free request crossing the production HTTP boundary."""

        participant = self._participant(session_id)
        request_method = str(method or "").strip().upper()
        path = str(target or "").partition("?")[0].strip()
        status = int(status_code)
        if request_method not in {"GET", "POST"} or not path.startswith("/"):
            raise ValueError("gym participant HTTP receipt is invalid")
        location = self._participant_location(session_id)
        self._record(
            "participant_http",
            participant=participant,
            location=location,
            detail={
                "method": request_method,
                "path": path,
                "status_code": status,
                "resident_proof": bool(resident_proof),
            },
        )

        if (
            request_method == "GET"
            and path == f"/api/world/scene/{session_id}"
            and 200 <= status < 300
            and isinstance(response_payload, dict)
        ):
            graph = response_payload.get("location_graph")
            graph_payload = graph if isinstance(graph, dict) else {}
            present = response_payload.get("present")
            traces = response_payload.get("traces_here")
            self._record(
                "participant_scene_ready",
                participant=participant,
                location=str(response_payload.get("location") or location),
                detail={
                    "present_count": (len(present) if isinstance(present, list) else 0),
                    "trace_count": len(traces) if isinstance(traces, list) else 0,
                    "route_count": len(graph_payload.get("edges") or []),
                    "place_count": len(graph_payload.get("nodes") or []),
                },
            )

        if (
            request_method == "POST"
            and path == "/api/game/move"
            and 200 <= status < 300
            and isinstance(response_payload, dict)
        ):
            destination = str(response_payload.get("to_location") or "").strip()
            origin = str(response_payload.get("from_location") or "").strip()
            route = response_payload.get("route")
            self._record(
                "moved" if bool(response_payload.get("moved")) else "stayed",
                participant=participant,
                location=destination or location,
                detail={
                    "from": origin,
                    "to": destination,
                    "route": (
                        [str(item) for item in route] if isinstance(route, list) else []
                    ),
                },
            )

    def audit_world_chronology(self) -> dict[str, Any]:
        """Prove exercised persistent world rows use recorded gym instants."""

        participant_ids = tuple(sorted(self._participants))
        allowed = {
            datetime.fromisoformat(record.occurred_at)
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
            for record in self._records
        }
        rows: list[tuple[str, datetime | None]] = []
        rows.extend(
            ("world_event", row.created_at)
            for row in self.db.query(WorldEvent)
            .filter(WorldEvent.session_id.in_(participant_ids))
            .all()
        )
        rows.extend(
            ("location_chat", row.created_at)
            for row in self.db.query(LocationChat)
            .filter(LocationChat.session_id.in_(participant_ids))
            .all()
        )
        rows.extend(
            ("session", row.updated_at)
            for row in self.db.query(SessionVars)
            .filter(
                (SessionVars.session_id.in_(participant_ids))
                | (SessionVars.session_id == self.world_id)
            )
            .all()
        )
        rows.extend(
            ("world_fact", row.valid_from)
            for row in self.db.query(WorldFact)
            .filter(WorldFact.session_id.in_(participant_ids))
            .all()
        )
        participant_event_ids = {
            int(row.id)
            for row in self.db.query(WorldEvent.id)
            .filter(WorldEvent.session_id.in_(participant_ids))
            .all()
        }
        rows.extend(
            ("world_projection", row.updated_at)
            for row in self.db.query(WorldProjection).all()
            if int(row.source_event_id or 0) in participant_event_ids
        )
        missing = [kind for kind, value in rows if value is None]
        off_clock = [
            (kind, value.isoformat())
            for kind, value in rows
            if value is not None and value not in allowed
        ]
        if missing or off_clock:
            raise RuntimeError(
                "persistent world chronology escaped the gym clock: "
                f"missing={missing!r} off_clock={off_clock!r}"
            )

        counts: dict[str, int] = {}
        instants: set[str] = set()
        for kind, value in rows:
            counts[kind] = counts.get(kind, 0) + 1
            if value is not None:
                instants.add(value.replace(tzinfo=timezone.utc).isoformat())
        detail = {
            "row_counts": dict(sorted(counts.items())),
            "instants": sorted(instants),
            "off_clock_count": 0,
        }
        self._record("world_chronology_audited", detail=detail)
        return detail

    def deliver_resident_return(
        self,
        event: ScheduledEvent,
        handler: Callable[[ScheduledEvent, dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        """Offer one due private return; the caller separately acknowledges it."""

        if event.kind != "resident_private_return":
            raise ValueError("scheduled event is not a resident return")
        if event.due_at > self.clock.now():
            raise ValueError("resident return was offered before its deadline")
        session_id = str(event.payload.get("session_id") or "").strip()
        expected_event_id = str(event.payload.get("resident_event_id") or "").strip()
        activity_id = str(event.payload.get("activity_id") or "").strip()
        if not session_id or not expected_event_id or not activity_id:
            raise ValueError("resident return binding is incomplete")
        participant = self._participant(session_id)
        scene = self.observe(session_id)
        self._record(
            "resident_activation_started",
            participant=participant,
            location=str(scene.get("location") or ""),
            detail={
                "event_id": expected_event_id,
                "activity_id": activity_id,
            },
        )
        try:
            result = handler(event, scene)
        except Exception as exc:
            self._record(
                "resident_activation_interrupted",
                participant=participant,
                location=str(scene.get("location") or ""),
                detail={
                    "event_id": expected_event_id,
                    "reason": type(exc).__name__,
                },
            )
            raise
        if not isinstance(result, dict):
            raise ValueError("resident return handler must return an object")
        status = str(result.get("status") or "").strip()
        reported_event_id = str(result.get("event_id") or "").strip()
        if reported_event_id != expected_event_id:
            self._record(
                "resident_activation_interrupted",
                participant=participant,
                location=str(scene.get("location") or ""),
                detail={
                    "event_id": expected_event_id,
                    "reason": "return_binding_mismatch",
                },
            )
            raise ValueError("resident return response does not match offered event")
        self._record(
            "resident_activation_finished",
            participant=participant,
            location=str(scene.get("location") or ""),
            detail={
                "event_id": expected_event_id,
                "status": status,
                "activation_status": str(result.get("activation_status") or ""),
                "choice": str(result.get("choice") or "none"),
                "model_call_count": int(result.get("model_call_count") or 0),
            },
        )
        if status not in {"processed", "already_processed"}:
            raise ValueError(
                f"resident return was not consumable: {status or 'unknown'}"
            )
        return result

    def speak(self, session_id: str, message: str) -> dict[str, Any]:
        """Speak through the production local-speech service."""

        participant = self._participant(session_id)
        state = get_state_manager(session_id, self.db)
        location = str(state.get_variable("location") or "").strip()
        receipt = post_local_speech(
            self.db,
            session_id=session_id,
            location=location,
            message=message,
            now=self.clock.now(),
        )
        self._record(
            "spoke",
            participant=participant,
            location=location,
            detail={"signal_id": receipt.id, "message": str(message).strip()},
        )
        return receipt.as_payload()

    def move(self, session_id: str, destination: str) -> dict[str, Any]:
        """Move through the production route, access, state, and event rules."""

        participant = self._participant(session_id)
        receipt = move_session(
            self.db,
            session_id=session_id,
            destination=destination,
            now=self.clock.now(),
        )
        self._record(
            "moved" if receipt.moved else "stayed",
            participant=participant,
            location=receipt.to_location,
            detail={
                "from": receipt.from_location,
                "to": receipt.to_location,
                "route": list(receipt.route),
            },
        )
        return {
            "moved": receipt.moved,
            "from_location": receipt.from_location,
            "to_location": receipt.to_location,
            "route": list(receipt.route),
        }

    def checkpoint(self) -> dict[str, Any]:
        """Capture one integrity-bound restart envelope for this synthetic run."""

        scheduler = self._scheduled_queue().as_payload()
        unsigned = {
            "schema": CHECKPOINT_SCHEMA,
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "captured_at": self.clock.now().isoformat(),
            "scenario": {
                "scenario_id": self.scenario_id,
                "scenario_version": self.scenario_version,
                "scenario_seed": self.scenario_seed,
                "episode": self.episode,
                "world_id": self.world_id,
            },
            "engine_database": capture_sqlite_database(self.db),
            "scheduler": scheduler,
            "gym": {
                "locations": list(self._locations),
                "participants": [
                    asdict(participant) for participant in self._participants.values()
                ],
                "signal_cursors": [
                    {
                        "session_id": session_id,
                        **asdict(cursor),
                    }
                    for session_id, cursor in sorted(self._cursors.items())
                ],
                "records": [asdict(record) for record in self._records],
            },
            "participants": [
                checkpoint.as_payload()
                for _, checkpoint in sorted(self._participant_checkpoints.items())
            ],
        }
        return seal_checkpoint(unsigned)

    @classmethod
    def from_checkpoint(
        cls,
        db: Session,
        raw_checkpoint: dict[str, Any],
        *,
        record_observer: Callable[[GymRecord], None] | None = None,
    ) -> "ProductionRuleGym":
        """Restore a validated checkpoint into an empty synthetic database."""

        body = validate_checkpoint(raw_checkpoint)
        scenario = body["scenario"]
        gym_state = body["gym"]
        try:
            captured_at = datetime.fromisoformat(str(body["captured_at"]))
            if captured_at.tzinfo is None:
                raise ValueError
            scheduler = ScheduledEventQueue.from_payload(body["scheduler"])
            if scheduler.clock.now() != captured_at.astimezone(timezone.utc):
                raise ValueError
            if set(scenario) != {
                "scenario_id",
                "scenario_version",
                "scenario_seed",
                "episode",
                "world_id",
            } or set(gym_state) != {
                "locations",
                "participants",
                "signal_cursors",
                "records",
            }:
                raise ValueError
            if (
                not isinstance(gym_state["locations"], list)
                or not isinstance(gym_state["participants"], list)
                or not isinstance(gym_state["signal_cursors"], list)
                or not isinstance(gym_state["records"], list)
            ):
                raise ValueError
            if not all(
                isinstance(item, dict)
                and set(item)
                == {"session_id", "actor_id", "display_name", "implementation"}
                for item in gym_state["participants"]
            ):
                raise ValueError
            if not all(
                isinstance(item, dict)
                and set(item) == {"session_id", "shard_id", "location", "after_id"}
                for item in gym_state["signal_cursors"]
            ):
                raise ValueError
            if not all(
                isinstance(item, dict)
                and set(item)
                == {
                    "sequence",
                    "occurred_at",
                    "kind",
                    "actor",
                    "location",
                    "detail",
                }
                and isinstance(item["detail"], dict)
                for item in gym_state["records"]
            ):
                raise ValueError
            locations = tuple(str(item).strip() for item in gym_state["locations"])
            participants = tuple(
                GymParticipant(
                    session_id=str(item["session_id"]).strip(),
                    actor_id=str(item["actor_id"]).strip(),
                    display_name=str(item["display_name"]).strip(),
                    implementation=str(item["implementation"]).strip(),
                )
                for item in gym_state["participants"]
            )
            cursors = {
                str(item["session_id"]): _SignalCursor(
                    shard_id=str(item["shard_id"]),
                    location=str(item["location"]),
                    after_id=int(item["after_id"]),
                )
                for item in gym_state["signal_cursors"]
            }
            records = tuple(
                GymRecord(
                    sequence=int(item["sequence"]),
                    occurred_at=str(item["occurred_at"]),
                    kind=str(item["kind"]),
                    actor=(
                        str(item["actor"]) if item.get("actor") is not None else None
                    ),
                    location=(
                        str(item["location"])
                        if item.get("location") is not None
                        else None
                    ),
                    detail=dict(item["detail"]),
                )
                for item in gym_state["records"]
            )
            participant_checkpoints = tuple(
                GymParticipantCheckpoint.from_payload(item)
                for item in body["participants"]
            )
            episode = str(scenario["episode"]).strip()
            world_id = str(scenario["world_id"]).strip()
            scenario_id = str(scenario["scenario_id"]).strip()
            scenario_version = int(scenario["scenario_version"])
            scenario_seed = int(scenario["scenario_seed"])
        except (KeyError, TypeError, ValueError) as exc:
            raise GymCheckpointError("gym checkpoint state is invalid") from exc

        if not locations or not all(locations) or len(locations) != len(set(locations)):
            raise GymCheckpointError("gym checkpoint locations are invalid")
        if not episode or not world_id or not scenario_id:
            raise GymCheckpointError("gym checkpoint scenario is invalid")
        if scenario_version < 1 or scenario_seed < 0:
            raise GymCheckpointError("gym checkpoint scenario provenance is invalid")
        if len(participants) != len(gym_state["participants"]):
            raise GymCheckpointError("gym checkpoint participants are invalid")
        if any(
            not participant.session_id
            or not participant.actor_id
            or not participant.display_name
            or not participant.implementation
            for participant in participants
        ):
            raise GymCheckpointError("gym checkpoint participants are invalid")
        participant_by_session = {
            participant.session_id: participant for participant in participants
        }
        if len(participant_by_session) != len(participants):
            raise GymCheckpointError(
                "gym checkpoint participant sessions are not unique"
            )
        checkpoint_by_session = {
            checkpoint.session_id: checkpoint for checkpoint in participant_checkpoints
        }
        if set(checkpoint_by_session) != set(participant_by_session):
            raise GymCheckpointError("participant checkpoint bindings are incomplete")
        for session_id, participant in participant_by_session.items():
            binding = checkpoint_by_session[session_id]
            if (
                binding.actor_id != participant.actor_id
                or binding.implementation != participant.implementation
            ):
                raise GymCheckpointError(
                    "participant checkpoint binding does not match"
                )
        if not set(cursors) <= set(participant_by_session):
            raise GymCheckpointError("signal cursor belongs to an unknown participant")
        if len(cursors) != len(gym_state["signal_cursors"]):
            raise GymCheckpointError("gym checkpoint signal cursors are not unique")
        if any(
            not cursor.shard_id or not cursor.location or cursor.after_id < 0
            for cursor in cursors.values()
        ):
            raise GymCheckpointError("gym checkpoint signal cursor is invalid")
        if [record.sequence for record in records] != list(range(1, len(records) + 1)):
            raise GymCheckpointError("gym checkpoint record sequence is invalid")
        for record in records:
            try:
                occurred_at = datetime.fromisoformat(record.occurred_at)
            except ValueError as exc:
                raise GymCheckpointError(
                    "gym checkpoint record time is invalid"
                ) from exc
            if occurred_at.tzinfo is None:
                raise GymCheckpointError("gym checkpoint record time is invalid")
            if occurred_at.astimezone(timezone.utc) > captured_at.astimezone(
                timezone.utc
            ):
                raise GymCheckpointError("gym checkpoint record is from the future")
            if not record.kind:
                raise GymCheckpointError("gym checkpoint record kind is invalid")

        validate_sqlite_participant_bindings(
            body["engine_database"],
            [
                (participant.session_id, participant.actor_id)
                for participant in participants
            ],
        )
        restore_sqlite_database(db, body["engine_database"])
        clear_session_caches()

        gym = cls(
            db,
            episode=episode,
            world_id=world_id,
            clock=scheduler.clock,
            scenario_id=scenario_id,
            scenario_version=scenario_version,
            scenario_seed=scenario_seed,
            record_observer=record_observer,
        )
        gym._scheduled = scheduler
        gym._locations = locations
        gym._participants = participant_by_session
        gym._participant_checkpoints = checkpoint_by_session
        gym._cursors = cursors
        gym._records = list(records)
        return gym

    def result(self) -> GymEpisodeResult:
        """Freeze the current structural episode record."""

        final_locations = {
            participant.display_name: self._participant_location(session_id)
            for session_id, participant in self._participants.items()
        }
        implementations = {
            participant.implementation for participant in self._participants.values()
        }
        model_resident = "reference_resident_model" in implementations
        reference_resident = model_resident or any(
            implementation.startswith("reference_resident_")
            for implementation in implementations
        )
        return GymEpisodeResult(
            schema="worldweaver.resident-gym.episode",
            schema_version=8,
            episode=self.episode,
            world_id=self.world_id,
            locations=self._locations,
            participants=tuple(self._participants.values()),
            fidelity=GymFidelityProfile(
                engine_rules=(
                    "production_fastapi_routes_and_services"
                    if model_resident
                    else "production_services"
                ),
                world_state="synthetic_sqlite",
                resident_composition=(
                    "normal_resident_host_and_reference_core"
                    if model_resident
                    else (
                        "shared_production_reference_core"
                        if reference_resident
                        else "not_exercised"
                    )
                ),
                participant_transport=(
                    "worldweaver_client_http_via_stdio"
                    if model_resident
                    else "direct_scenario_calls"
                ),
                resident_authorization=(
                    "signed_runtime_certificate" if model_resident else "not_exercised"
                ),
                city_sources=(
                    "node_published_then_local_world_registry"
                    if model_resident
                    else "not_exercised"
                ),
                world_time=(
                    "controlled_clock_across_engine_and_resident_world_state"
                    if model_resident and isinstance(self.clock, ControlledClock)
                    else (
                        "controlled_clock_in_exercised_production_services"
                        if isinstance(self.clock, ControlledClock)
                        else "system_utc"
                    )
                ),
                hearth_attachment=(
                    "local_world_city_to_hearth_restart"
                    if model_resident
                    else (
                        "portable_artifact_only"
                        if reference_resident
                        else "not_exercised"
                    )
                ),
                federation="not_exercised",
            ),
            final_locations=final_locations,
            records=tuple(self._records),
        )


def run_first_conversation(
    db: Session,
    *,
    record_observer: Callable[[GymRecord], None] | None = None,
) -> GymEpisodeResult:
    """Run the first deterministic co-presence and speech-delivery scenario."""

    gym = ProductionRuleGym(
        db,
        episode="The Footbridge Hello",
        world_id="gym-footbridge-world",
        clock=ControlledClock(datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)),
        record_observer=record_observer,
    )
    gym.arrange_world(("Willow Court", "Footbridge"))

    mara = GymParticipant(
        session_id="gym-mara",
        actor_id="gym-actor-mara",
        display_name="Mara",
        implementation="scripted_actor",
    )
    ivo = GymParticipant(
        session_id="gym-ivo",
        actor_id="gym-actor-ivo",
        display_name="Ivo",
        implementation="mechanical_listener",
    )
    gym.join(mara, location="Willow Court")
    gym.join(ivo, location="Willow Court")

    # Establish present-time cursors before either participant speaks. Archived
    # speech is intentionally not replayed as if it just happened.
    gym.listen(mara.session_id)
    gym.listen(ivo.session_id)

    gym.speak(mara.session_id, "Good morning. Is the footbridge open?")
    heard_by_ivo = gym.listen(ivo.session_id)
    if heard_by_ivo:
        gym.speak(ivo.session_id, "I heard you. I can go and look.")
    gym.listen(mara.session_id)

    gym.move(ivo.session_id, "Footbridge")
    gym.listen(ivo.session_id)
    gym.speak(mara.session_id, "Can you hear me from over there?")
    gym.listen(ivo.session_id)

    gym.move(mara.session_id, "Footbridge")
    gym.listen(mara.session_id)
    gym.speak(mara.session_id, "There you are.")
    gym.listen(ivo.session_id)
    return gym.result()


def run_waiting_letter(
    db: Session,
    *,
    record_observer: Callable[[GymRecord], None] | None = None,
) -> GymEpisodeResult:
    """Run actor-addressed delivery across a temporary session change."""

    gym = ProductionRuleGym(
        db,
        episode="The Waiting Letter",
        world_id="gym-waiting-letter-world",
        clock=ControlledClock(datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)),
        record_observer=record_observer,
    )
    gym.arrange_world(("Willow Court", "Footbridge"))
    mara = GymParticipant(
        session_id="gym-letter-mara",
        actor_id="gym-letter-actor-mara",
        display_name="Mara",
        implementation="scripted_actor",
    )
    ivo = GymParticipant(
        session_id="gym-letter-ivo-before",
        actor_id="gym-letter-actor-ivo",
        display_name="Ivo",
        implementation="mechanical_listener",
    )
    gym.join(mara, location="Willow Court")
    gym.join(ivo, location="Footbridge")
    message_id = gym.send_letter(
        mara.session_id,
        ivo.actor_id,
        "I will wait by the willow after the rain.",
    )

    gym.retire(ivo.session_id)
    returned_ivo = GymParticipant(
        session_id="gym-letter-ivo-after",
        actor_id=ivo.actor_id,
        display_name=ivo.display_name,
        implementation=ivo.implementation,
    )
    gym.join(returned_ivo, location="Footbridge")

    first_offer = gym.check_mail(returned_ivo.session_id)
    second_offer = gym.check_mail(returned_ivo.session_id)
    if first_offer and second_offer:
        gym.acknowledge_mail(returned_ivo.session_id, (message_id,))
    gym.check_mail(returned_ivo.session_id)
    return gym.result()


def prepare_quiet_interval(
    db: Session,
    *,
    record_observer: Callable[[GymRecord], None] | None = None,
    mara_implementation: str = "scripted_actor",
    episode: str = "The Long Afternoon",
) -> ProductionRuleGym:
    """Arrange the quiet-interval episode and leave its future work pending."""

    gym = ProductionRuleGym(
        db,
        episode=episode,
        world_id="gym-long-afternoon-world",
        clock=ControlledClock(datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)),
        record_observer=record_observer,
    )
    gym.arrange_world(("Willow Court", "Footbridge"))
    mara = GymParticipant(
        session_id="gym-afternoon-mara",
        actor_id="gym-afternoon-actor-mara",
        display_name="Mara",
        implementation=str(mara_implementation or "").strip(),
    )
    ivo = GymParticipant(
        session_id="gym-afternoon-ivo",
        actor_id="gym-afternoon-actor-ivo",
        display_name="Ivo",
        implementation="mechanical_listener",
    )
    gym.join(mara, location="Willow Court")
    gym.join(ivo, location="Willow Court")
    gym.listen(mara.session_id)
    gym.listen(ivo.session_id)
    gym.speak(mara.session_id, "I left a dry seat at the willow bench.")
    gym.listen(ivo.session_id)

    bench_id = gym.create_sublocation(
        mara.session_id,
        label="willow bench",
        ttl_seconds=2 * 86400,
    )
    gym.inspect_sublocation(parent_location="Willow Court", sublocation_id=bench_id)
    gym.schedule_in(
        timedelta(hours=47),
        kind="inspect_sublocation",
        payload={"parent_location": "Willow Court", "sublocation_id": bench_id},
    )
    gym.schedule_in(
        timedelta(hours=49),
        kind="inspect_sublocation",
        payload={"parent_location": "Willow Court", "sublocation_id": bench_id},
    )
    return gym


def finish_quiet_interval(gym: ProductionRuleGym) -> GymEpisodeResult:
    """Process every pending quiet-interval instruction through production rules."""

    while gym.scheduled_checkpoint()["pending"]:
        for event in gym.offer_next_scheduled():
            if event.kind != "inspect_sublocation":
                raise ValueError(f"unsupported gym event: {event.kind}")
            gym.inspect_sublocation(
                parent_location=str(event.payload["parent_location"]),
                sublocation_id=str(event.payload["sublocation_id"]),
            )
            gym.acknowledge_scheduled((event.event_id,))
    return gym.result()


def run_quiet_interval(
    db: Session,
    *,
    record_observer: Callable[[GymRecord], None] | None = None,
) -> GymEpisodeResult:
    """Mix a live exchange with a skipped two-day production lifetime."""

    return finish_quiet_interval(
        prepare_quiet_interval(db, record_observer=record_observer)
    )
