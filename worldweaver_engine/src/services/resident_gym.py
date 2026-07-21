# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""A small deterministic gym over the production world-rule services.

The gym owns scenario arrangement and an observation record.  It does not own
alternate movement, speech, presence, or signal-delivery rules.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy.orm import Session

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
from .session_lifecycle import (
    SessionBootstrapCommand,
    bootstrap_session,
    retire_session_presence,
)
from .session_service import get_state_manager, save_state
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
            "final_locations": dict(self.final_locations),
            "records": [asdict(item) for item in self.records],
        }


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
    ):
        self.db = db
        self.episode = str(episode or "").strip()
        self.world_id = str(world_id or "").strip()
        if not self.episode or not self.world_id:
            raise ValueError("episode and world_id are required")
        self.clock = clock or SystemClock()
        self._scheduled = (
            ScheduledEventQueue(self.clock)
            if isinstance(self.clock, ControlledClock)
            else None
        )
        self._locations: tuple[str, ...] = ()
        self._participants: dict[str, GymParticipant] = {}
        self._cursors: dict[str, _SignalCursor] = {}
        self._records: list[GymRecord] = []

    def _record(
        self,
        kind: str,
        *,
        participant: GymParticipant | None = None,
        location: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self._records.append(
            GymRecord(
                sequence=len(self._records) + 1,
                occurred_at=self.clock.now().isoformat(),
                kind=kind,
                actor=participant.display_name if participant is not None else None,
                location=location,
                detail=dict(detail or {}),
            )
        )

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
            [{"name": location, "description": ""} for location in normalized],
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
        save_state(host, self.db)
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
        )
        self._participants[participant.session_id] = participant
        self._record(
            "joined",
            participant=participant,
            location=location,
            detail={
                "implementation": participant.implementation,
                "bootstrap_state": receipt.bootstrap_state,
            },
        )

    def _participant(self, session_id: str) -> GymParticipant:
        try:
            return self._participants[session_id]
        except KeyError as exc:
            raise ValueError(f"unknown gym participant: {session_id}") from exc

    def retire(self, session_id: str) -> None:
        """End one temporary presence without erasing its durable actor."""

        participant = self._participant(session_id)
        location = str(
            get_state_manager(session_id, self.db).get_variable("location") or ""
        )
        receipt = retire_session_presence(self.db, session_id=session_id)
        self._participants.pop(session_id)
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

    def speak(self, session_id: str, message: str) -> None:
        """Speak through the production local-speech service."""

        participant = self._participant(session_id)
        state = get_state_manager(session_id, self.db)
        location = str(state.get_variable("location") or "").strip()
        receipt = post_local_speech(
            self.db,
            session_id=session_id,
            location=location,
            message=message,
        )
        self._record(
            "spoke",
            participant=participant,
            location=location,
            detail={"signal_id": receipt.id, "message": str(message).strip()},
        )

    def move(self, session_id: str, destination: str) -> None:
        """Move through the production route, access, state, and event rules."""

        participant = self._participant(session_id)
        receipt = move_session(
            self.db,
            session_id=session_id,
            destination=destination,
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

    def result(self) -> GymEpisodeResult:
        """Freeze the current structural episode record."""

        final_locations = {
            participant.display_name: str(
                get_state_manager(session_id, self.db).get_variable("location") or ""
            )
            for session_id, participant in self._participants.items()
        }
        return GymEpisodeResult(
            schema="worldweaver.resident-gym.episode",
            schema_version=2,
            episode=self.episode,
            world_id=self.world_id,
            locations=self._locations,
            participants=tuple(self._participants.values()),
            final_locations=final_locations,
            records=tuple(self._records),
        )


def run_first_conversation(db: Session) -> GymEpisodeResult:
    """Run the first deterministic co-presence and speech-delivery scenario."""

    gym = ProductionRuleGym(
        db,
        episode="The Footbridge Hello",
        world_id="gym-footbridge-world",
        clock=ControlledClock(datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)),
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


def run_waiting_letter(db: Session) -> GymEpisodeResult:
    """Run actor-addressed delivery across a temporary session change."""

    gym = ProductionRuleGym(
        db,
        episode="The Waiting Letter",
        world_id="gym-waiting-letter-world",
        clock=ControlledClock(datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)),
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


def run_quiet_interval(db: Session) -> GymEpisodeResult:
    """Mix a live exchange with a skipped two-day production lifetime."""

    gym = ProductionRuleGym(
        db,
        episode="The Long Afternoon",
        world_id="gym-long-afternoon-world",
        clock=ControlledClock(datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)),
    )
    gym.arrange_world(("Willow Court", "Footbridge"))
    mara = GymParticipant(
        session_id="gym-afternoon-mara",
        actor_id="gym-afternoon-actor-mara",
        display_name="Mara",
        implementation="scripted_actor",
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
