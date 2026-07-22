# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from __future__ import annotations

import asyncio
import inspect
import logging
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol

from src.familiar.config import HearthConfig
from src.familiar.file_scope import FileScope
from src.familiar.local_world import LocalWorld
from src.familiar.weather import WeatherProvider
from src.identity.hearth_activation import (
    HearthRuntimeLease,
    acquire_hearth_runtime,
    load_hearth_activation,
)
from src.identity.hearth_manifest import manifest_path
from src.identity.growth import repair_growth_adoptions
from src.identity.loader import IdentityLoader, ResidentIdentity
from src.identity.hearth_permissions import secure_hearth_permissions
from src.inference.client import InferenceClient
from src.runtime.effectors import WorldEffector
from src.runtime.information import InformationAccess
from src.runtime.ledger import (
    append_runtime_event,
    load_resident_process_envelope,
    load_runtime_events,
)
from src.runtime.naming import slugify_resident_name
from src.runtime.process_state import (
    PROCESS_HOST_LIFECYCLE_VERSION,
    ResidentProcessBinding,
)
from src.runtime.reference_core import ReferenceResidentCore, ReferenceScheduledReturn
from src.runtime.travel import (
    PendingShardTravel,
    TravelRequest,
    derive_pending_shard_travel,
)
from src.runtime.workshop import Workshop
from src.runtime.world_clock import SystemWorldClock, WorldClock
from src.world.city_tools import build_city_source_registry
from src.world.city_world import CityWorld
from src.world.client import LiveSignalBatch, LiveSignalCursor, WorldWeaverClient

logger = logging.getLogger(__name__)

_IDENTITY_TEMPERATURE = object()


class ResidentCore(Protocol):
    tick_seconds: float

    async def tick_once(
        self, *, now: Any = None, force_ignite: bool = False
    ) -> dict[str, Any]: ...


TickObserver = Callable[
    [ResidentIdentity, CityWorld | LocalWorld, ResidentCore, dict[str, Any], int],
    Awaitable[None] | None,
]
AttachmentCheckpointObserver = Callable[[ResidentIdentity, str], Awaitable[None] | None]


@dataclass(frozen=True, slots=True)
class PendingHearthDeparture:
    transition_id: str
    session_id: str


def build_reference_core(
    *,
    identity: ResidentIdentity,
    resident_dir: Path,
    world: CityWorld | LocalWorld,
    llm: Any,
    session_id: str,
    selected_model: str | None,
    temperature: float | None,
    attachment_kind: str,
    tick_seconds: float | None = None,
) -> ReferenceResidentCore:
    """Compose the production reference core for one established attachment.

    The resident host remains responsible for identity loading, process binding,
    attachment lifecycle, and exclusive hearth custody.  This function owns only
    the shared cognition/effector/information wiring so isolated hosts such as the
    gym cannot grow a subtly different resident composition.
    """

    if attachment_kind not in {"city", "hearth"}:
        raise ValueError("reference core attachment must be city or hearth")
    workshop = Workshop(resident_dir / "workshop")
    effector = WorldEffector(
        ww_client=world,
        session_id=session_id,
        identity=identity,
        memory_dir=resident_dir / "memory",
        workshop=workshop,
        all_writes_to_workshop=attachment_kind == "hearth",
    )
    information_access = InformationAccess(
        ww_client=world,
        memory_dir=resident_dir / "memory",
    )
    return ReferenceResidentCore(
        identity=identity,
        memory_dir=resident_dir / "memory",
        world=world,
        llm=llm,
        session_id=session_id,
        effector=effector,
        information_access=information_access,
        model=selected_model,
        temperature=temperature,
        **({"tick_seconds": tick_seconds} if tick_seconds is not None else {}),
    )


class Resident:
    """
    A single running resident: one identity, one reference loop, and one active
    world attachment.

    This object is the resident's current software host, not their owner. The
    resident directory is the currently mounted hearth storage, not a permanent
    machine address. Residents manage their own session with the world server
    and run until cancelled. Each activation receives current local facts, may
    choose one private information source, and then acts, continues privately, or
    waits. The host supplies scheduling and carries typed consequences.
    """

    def __init__(
        self,
        resident_dir: Path,
        ww_client: WorldWeaverClient,
        llm: InferenceClient,
        *,
        hearth_config: HearthConfig | None = None,
        tick_seconds: float | None = None,
        pulse_model: str | None = None,
        pulse_temperature: float | None | object = _IDENTITY_TEMPERATURE,
        tick_observer: TickObserver | None = None,
        attachment_checkpoint_observer: AttachmentCheckpointObserver | None = None,
        world_client_factory: Callable[[str], WorldWeaverClient] | None = None,
        travel_retry_seconds: float = 5.0,
        world_clock: WorldClock | None = None,
    ):
        self._resident_dir = resident_dir
        self._ww = ww_client
        self._llm = llm
        self._identity: ResidentIdentity | None = None
        self._session_id: str | None = None
        self._world_id: str = ""
        self._city_id: str | None = None
        self._city_capabilities: frozenset[str] = frozenset()
        self._attachment_kind: str = "city"
        self._attachment_lock = asyncio.Lock()
        self._hearth_config = hearth_config
        self._weather_provider: WeatherProvider | None = None
        self._tick_seconds = tick_seconds
        self._pulse_model = str(pulse_model or "").strip() or None
        self._pulse_temperature = pulse_temperature
        self._tick_observer = tick_observer
        self._attachment_checkpoint_observer = attachment_checkpoint_observer
        self._world_client_factory = world_client_factory or (
            lambda url: WorldWeaverClient(base_url=url)
        )
        self._travel_retry_seconds = max(0.0, float(travel_retry_seconds))
        self._world_clock = world_clock or SystemWorldClock()
        self._owned_world_clients: list[WorldWeaverClient] = []
        self._runtime_lease: HearthRuntimeLease | None = None
        self._hearth_shard_id = ""
        self._runtime_generation = 0
        self._travel_id = ""
        self._host_run_id: str | None = None

    @property
    def name(self) -> str:
        if self._identity:
            return self._identity.name
        return self._resident_dir.name

    @property
    def identity(self) -> ResidentIdentity:
        """The resident identity currently loaded by this temporary host."""
        return self._require_identity()

    @property
    def city_id(self) -> str:
        """Public city-pack identity most recently disclosed by the attached node."""

        return str(self._city_id or "")

    @property
    def city_capabilities(self) -> tuple[str, ...]:
        """Public optional capability IDs most recently disclosed by the node."""

        return tuple(sorted(self._city_capabilities))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(
        self,
        world_id: str,
        *,
        default_attachment: str = "city",
    ) -> None:
        """Claim this hearth generation, then establish one world attachment."""
        if self._runtime_lease is not None:
            raise RuntimeError(f"Resident {self.name} is already started")
        self._resident_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        secure_hearth_permissions(self._resident_dir)
        self._runtime_lease = acquire_hearth_runtime(self._resident_dir)
        self._load_active_hearth_coordinates()
        try:
            await self._start_attached(
                world_id,
                default_attachment=default_attachment,
            )
        except BaseException:
            self._release_runtime_lease()
            raise

    async def _start_attached(
        self,
        world_id: str,
        *,
        default_attachment: str = "city",
    ) -> None:
        """
        Load identity, establish session, wire up loops. Call before run().
        """
        self._identity = IdentityLoader.load(self._resident_dir)
        repair_growth_adoptions(self._resident_dir, self._identity)
        if self._hearth_config is None:
            self._hearth_config = HearthConfig.load(self._resident_dir)
        logger.info("[%s] identity loaded", self.name)
        self._world_id = str(world_id or "").strip()
        if default_attachment not in {"city", "hearth"}:
            raise ValueError("default_attachment must be 'city' or 'hearth'")
        restored_attachment = self._last_attachment_kind()
        pending_hearth_departure = self._pending_hearth_departure()
        pending_travel = self._pending_shard_travel()
        last_city_url = self._last_city_url()
        if last_city_url and last_city_url != self._client_url(self._ww):
            self._ww = self._new_world_client(last_city_url)
        self._attachment_kind = restored_attachment or default_attachment
        if pending_hearth_departure is not None:
            self._attachment_kind = "city"
            self._session_id = pending_hearth_departure.session_id
            logger.info(
                "[%s] restored unfinished hearth departure %s",
                self.name,
                pending_hearth_departure.transition_id,
            )
            return
        if pending_travel is not None:
            self._attachment_kind = "traveling"
            self._session_id = None
            self._travel_id = pending_travel.travel_id
            (self._resident_dir / "session_id.txt").unlink(missing_ok=True)
            self._bind_current_reference_process()
            logger.info(
                "[%s] restored unfinished travel %s",
                self.name,
                pending_travel.travel_id,
            )
            return
        if restored_attachment is None and self._attachment_kind == "hearth":
            self._record_transition(
                "world_attachment_changed",
                transition_id=f"initial-{uuid.uuid4().hex}",
                from_world="unattached",
                to_world="hearth",
                to_session_id=self._active_session_id(),
            )

        if self._attachment_kind == "hearth":
            self._session_id = None
            (self._resident_dir / "session_id.txt").unlink(missing_ok=True)
            logger.info("[%s] restored at private hearth", self.name)
        else:
            self._session_id = await self._get_or_create_session(self._world_id)
            logger.info("[%s] session: %s", self.name, self._session_id)
            await self._refresh_city_profile()

    async def run(
        self,
        *,
        max_ticks: int = 0,
        max_duration_seconds: float | None = None,
        pause_seconds: float | None = None,
        park_at_hearth_on_stop: bool = False,
        force_initial_ignite: bool = False,
    ) -> None:
        """Run the one resident core while holding its exclusive hearth lease."""
        if self._runtime_lease is None:
            if not self._identity:
                raise RuntimeError(
                    f"Resident {self.name} not started — call start() first"
                )
            self._runtime_lease = acquire_hearth_runtime(self._resident_dir)
            self._load_active_hearth_coordinates()
        try:
            await self._run_started(
                max_ticks=max_ticks,
                max_duration_seconds=max_duration_seconds,
                pause_seconds=pause_seconds,
                force_initial_ignite=force_initial_ignite,
            )
        finally:
            try:
                if park_at_hearth_on_stop:
                    await self._park_current_city_at_hearth()
            finally:
                try:
                    self._suspend_process_hosting()
                finally:
                    self._release_runtime_lease()

    async def park_at_hearth_and_stop(self) -> None:
        """Retire a started resident's city session without running cognition."""
        if self._runtime_lease is None:
            raise RuntimeError(f"Resident {self.name} not started — call start() first")
        try:
            await self._park_current_city_at_hearth()
        finally:
            self._release_runtime_lease()

    async def run_scheduled_return(
        self,
        event_id: str,
        *,
        now: datetime,
    ) -> tuple[dict[str, Any], ReferenceScheduledReturn | None]:
        """Handle one exact private return through the bounded resident host.

        ``start`` must already have established the attachment and exclusive
        hearth custody. This method owns the matching hosted-process interval,
        attachment wrapper, and lease release just as ``run`` does, while letting
        an external scheduler offer one idempotent event instead of starting the
        resident's polling loop.
        """

        if self._runtime_lease is None or self._identity is None:
            raise RuntimeError(f"Resident {self.name} not started — call start() first")
        if self._attachment_kind == "traveling":
            raise RuntimeError(
                f"Resident {self.name} cannot handle a private return while traveling"
            )
        self._begin_process_hosting()
        world = self._build_current_world()
        try:
            world = await self._resume_pending_hearth_departure(world)
            core = self._build_core(world, self._active_session_id())
            result = await core.handle_scheduled_return(event_id, now=now)
            await self._notify_tick(world, core, result, 1)
            scheduled_return = core.scheduled_return()
            take_pending = getattr(world, "take_pending_travel", None)
            request = take_pending() if callable(take_pending) else None
            if request is not None:
                world = await self._apply_travel_request(world, request)
            return result, scheduled_return
        finally:
            try:
                await world.close()
                for client in list(self._owned_world_clients):
                    await client.close()
                self._owned_world_clients.clear()
            finally:
                try:
                    self._suspend_process_hosting()
                finally:
                    self._release_runtime_lease()

    async def _park_current_city_at_hearth(self) -> None:
        if self._attachment_kind == "hearth":
            return
        if self._attachment_kind != "city":
            raise RuntimeError(
                f"Resident {self.name} cannot park while {self._attachment_kind}"
            )
        city = self._build_city_world(self._active_session_id())
        hearth = await self._enter_hearth(city)
        if not isinstance(hearth, LocalWorld):
            raise RuntimeError("city did not confirm bounded-run session retirement")
        await hearth.close()

    async def _run_started(
        self,
        *,
        max_ticks: int = 0,
        max_duration_seconds: float | None = None,
        pause_seconds: float | None = None,
        force_initial_ignite: bool = False,
    ) -> None:
        """
        Run the resident's small reference loop. Returns when they stop or a
        bounded-run condition is reached. Outward acts still use the shared
        world effector and engine-owned consequence rules.
        """
        if not self._identity:
            raise RuntimeError(f"Resident {self.name} not started — call start() first")
        if max_ticks > 0 and max_duration_seconds is not None:
            raise ValueError("choose either max_ticks or max_duration_seconds")
        self._begin_process_hosting()
        duration = (
            None
            if max_duration_seconds is None
            else max(0.0, float(max_duration_seconds))
        )
        loop = asyncio.get_running_loop()
        deadline = loop.time() + duration if duration is not None else None

        pending_travel = self._pending_shard_travel()
        if pending_travel is not None:
            try:
                await self._resume_inter_shard_travel(pending_travel)
            except BaseException:
                for client in list(self._owned_world_clients):
                    await client.close()
                self._owned_world_clients.clear()
                raise
        world = self._build_current_world()
        world = await self._resume_pending_hearth_departure(world)
        logger.info(
            "[%s] resident host starting in %s",
            self.name,
            self._attachment_kind,
        )
        tick_count = 0
        try:
            while True:
                session_id = self._active_session_id()
                core = self._build_core(world, session_id)
                signal_cursor = (
                    self._restore_live_signal_cursor(session_id)
                    if self._attachment_kind == "city"
                    else None
                )
                pending_signals: LiveSignalBatch | None = None
                cursor_recovery_wake = False
                while True:
                    if (
                        tick_count > 0
                        and deadline is not None
                        and loop.time() >= deadline
                    ):
                        return
                    result: dict[str, Any] | None = None
                    try:
                        if pending_signals is not None:
                            offer_signals = getattr(core, "offer_live_signals", None)
                            if callable(offer_signals):
                                offer_signals(pending_signals.events)
                        force_ignite = (
                            (bool(force_initial_ignite) and tick_count == 0)
                            or self._take_force_ignite(world)
                            or cursor_recovery_wake
                        )
                        cursor_recovery_wake = False
                        result = await core.tick_once(
                            now=self._world_clock.now(),
                            force_ignite=force_ignite,
                        )
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        logger.exception(
                            "[%s] resident activation error: %s",
                            self.name,
                            exc,
                        )
                        await asyncio.sleep(10.0)

                    if result is not None:
                        tick_count += 1
                        await self._notify_tick(
                            world,
                            core,
                            result,
                            tick_count,
                        )
                    if pending_signals is not None:
                        take_acknowledged = getattr(
                            core, "take_acknowledged_live_signal_ids", None
                        )
                        acknowledged = (
                            set(take_acknowledged())
                            if callable(take_acknowledged)
                            else set()
                        )
                        expected = {event.id for event in pending_signals.events}
                        if expected and expected <= acknowledged:
                            self._record_live_signal_cursor(
                                previous=signal_cursor,
                                current=pending_signals.cursor,
                                session_id=session_id,
                                status="acknowledged",
                                delivered_count=len(expected),
                            )
                            signal_cursor = pending_signals.cursor
                            pending_signals = None
                    stop_after_tick = max_ticks > 0 and tick_count >= max_ticks
                    stop_after_duration = (
                        deadline is not None and loop.time() >= deadline
                    )

                    take_pending = getattr(world, "take_pending_travel", None)
                    request = take_pending() if callable(take_pending) else None
                    if request is not None:
                        next_world = await self._apply_travel_request(
                            world,
                            request,
                        )
                        if next_world is not world:
                            world = next_world
                            if stop_after_tick or stop_after_duration:
                                return
                            break
                    if stop_after_tick or stop_after_duration:
                        return
                    delay = (
                        core.tick_seconds
                        if pause_seconds is None
                        else max(0.0, float(pause_seconds))
                    )
                    if deadline is not None:
                        delay = min(delay, max(0.0, deadline - loop.time()))
                    if pending_signals is not None:
                        await asyncio.sleep(delay)
                        continue
                    signal_cursor, pending_signals, cursor_recovery_wake = (
                        await self._wait_for_live_signals(
                            world,
                            session_id=session_id,
                            cursor=signal_cursor,
                            delay=delay,
                        )
                    )
                    if pending_signals is not None:
                        has_seen = getattr(core, "has_seen_live_signals", None)
                        if callable(has_seen) and has_seen(pending_signals.events):
                            self._record_live_signal_cursor(
                                previous=signal_cursor,
                                current=pending_signals.cursor,
                                session_id=session_id,
                                status="reconciled",
                                delivered_count=len(pending_signals.events),
                            )
                            signal_cursor = pending_signals.cursor
                            pending_signals = None
                            cursor_recovery_wake = False
        except asyncio.CancelledError:
            logger.info("[%s] resident cancelled", self.name)
            raise
        finally:
            await world.close()
            for client in list(self._owned_world_clients):
                await client.close()
            self._owned_world_clients.clear()

    def _release_runtime_lease(self) -> None:
        lease = self._runtime_lease
        self._runtime_lease = None
        if lease is not None:
            try:
                # Files written during the run remain protected by the 0700 hearth
                # root. Normalize their own modes before this host gives up the
                # generation lease as well.
                secure_hearth_permissions(self._resident_dir)
            finally:
                lease.release()

    async def _wait_for_live_signals(
        self,
        world: CityWorld | LocalWorld,
        *,
        session_id: str,
        cursor: LiveSignalCursor | None,
        delay: float,
    ) -> tuple[LiveSignalCursor | None, LiveSignalBatch | None, bool]:
        """Wait cheaply for city signals, falling back to the normal timer."""

        wait_for_signals = getattr(world, "wait_for_live_signals", None)
        if not callable(wait_for_signals) or delay <= 0:
            await asyncio.sleep(max(0.0, delay))
            return cursor, None, False

        loop = asyncio.get_running_loop()
        deadline = loop.time() + delay
        current_cursor = cursor
        try:
            while True:
                remaining = max(0.0, deadline - loop.time())
                batch = await wait_for_signals(
                    session_id,
                    cursor=current_cursor,
                    wait_seconds=(remaining if current_cursor is not None else 0.0),
                    limit=10,
                )
                if batch.cursor_status in {
                    "established",
                    "scope_changed",
                    "retention_gap",
                }:
                    previous_cursor = current_cursor
                    current_cursor = batch.cursor
                    self._record_live_signal_cursor(
                        previous=previous_cursor,
                        current=current_cursor,
                        session_id=session_id,
                        status=batch.cursor_status,
                    )
                    if batch.cursor_status == "retention_gap":
                        return current_cursor, None, True
                    if loop.time() < deadline:
                        continue
                    return current_cursor, None, False
                if batch.events:
                    # Delivery gives the core new facts. The core's private
                    # schedule decides whether those facts open an early turn.
                    return current_cursor, batch, False
                self._record_live_signal_cursor(
                    previous=current_cursor,
                    current=batch.cursor,
                    session_id=session_id,
                    status="current",
                )
                current_cursor = batch.cursor
                if loop.time() < deadline:
                    continue
                return current_cursor, None, False
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.info("[%s] live signal wait unavailable: %s", self.name, exc)
            remaining = max(0.0, deadline - loop.time())
            await asyncio.sleep(remaining)
            return current_cursor, None, False

    def _restore_live_signal_cursor(self, session_id: str) -> LiveSignalCursor | None:
        """Restore the cursor bound to this exact checkpointed city attachment."""

        normalized_session_id = str(session_id or "").strip()
        envelope = load_resident_process_envelope(self._resident_dir / "memory") or {}
        attachment = (
            envelope.get("attachment")
            if isinstance(envelope.get("attachment"), dict)
            else {}
        )
        cursor = (
            envelope.get("event_cursor")
            if isinstance(envelope.get("event_cursor"), dict)
            else {}
        )
        if (
            attachment.get("kind") != "city"
            or str(attachment.get("session_id") or "").strip() != normalized_session_id
            or str(cursor.get("session_id") or "").strip() != normalized_session_id
        ):
            return None
        try:
            shard_id = str(cursor["shard_id"]).strip()
            location = str(cursor["location"]).strip()
            after_id = int(cursor["after_id"])
        except (KeyError, TypeError, ValueError):
            return None
        if shard_id and location and after_id >= 0:
            return LiveSignalCursor(
                shard_id=shard_id,
                location=location,
                after_id=after_id,
            )
        return None

    def _record_live_signal_cursor(
        self,
        *,
        previous: LiveSignalCursor | None,
        current: LiveSignalCursor,
        session_id: str,
        status: str,
        delivered_count: int = 0,
    ) -> None:
        """Persist an acknowledged cursor without copying public speech text."""

        if previous == current and status not in {"retention_gap", "scope_changed"}:
            return
        append_runtime_event(
            self._resident_dir / "memory",
            event_type="live_signal_cursor_advanced",
            payload={
                "version": 1,
                "session_id": str(session_id or "").strip(),
                "shard_id": current.shard_id,
                "location": current.location,
                "after_id": current.after_id,
                "status": status,
                "delivered_count": max(0, int(delivered_count)),
            },
        )

    def _build_current_world(self) -> CityWorld | LocalWorld:
        if self._attachment_kind == "hearth":
            return self._build_hearth_world()
        return self._build_city_world(self._active_session_id())

    def _build_city_world(self, session_id: str) -> CityWorld:
        identity = self._require_identity()
        return CityWorld(
            self._ww,
            build_city_source_registry(
                identity,
                client=self._ww,
                session_id=session_id,
                memory_dir=self._resident_dir / "memory",
                city_id=self._city_id,
                capabilities=self._city_capabilities,
            ),
            hearth_available=True,
        )

    def _build_hearth_world(self) -> LocalWorld:
        identity = self._require_identity()
        config = self._hearth_config or HearthConfig()
        file_scope = (
            FileScope(read_roots=list(config.read_roots)) if config.read_roots else None
        )
        if config.weather and self._weather_provider is None:
            self._weather_provider = WeatherProvider()
        return LocalWorld(
            home_dir=self._resident_dir,
            place=config.place,
            keeper_name=config.keeper,
            familiar_name=identity.display_name,
            weather_provider=self._weather_provider if config.weather else None,
            file_scope=file_scope,
            vision=config.vision,
            gifts_enabled=config.gifts,
            city_names={"city"},
            identity=identity,
            world_clock=self._world_clock,
        )

    def _build_core(
        self,
        world: CityWorld | LocalWorld,
        session_id: str,
    ) -> ReferenceResidentCore:
        identity = self._require_identity()
        pulse_temperature = (
            identity.tuning.fast_temperature
            if self._pulse_temperature is _IDENTITY_TEMPERATURE
            else self._pulse_temperature
        )
        selected_model, model_id = self._process_model_binding()
        self._bind_reference_process(model_id=model_id, session_id=session_id)
        return build_reference_core(
            identity=identity,
            resident_dir=self._resident_dir,
            world=world,
            llm=self._llm,
            session_id=session_id,
            selected_model=selected_model,
            temperature=pulse_temperature,
            attachment_kind=self._attachment_kind,
            tick_seconds=self._tick_seconds,
        )

    def _load_active_hearth_coordinates(self) -> None:
        """Read the active generation already authorized by the runtime lease."""

        if not manifest_path(self._resident_dir).exists():
            self._hearth_shard_id = ""
            self._runtime_generation = 0
            return
        activation = load_hearth_activation(self._resident_dir)
        self._hearth_shard_id = activation.hearth_shard_id
        self._runtime_generation = activation.runtime_generation

    def _process_model_binding(self) -> tuple[str | None, str]:
        """Resolve the configured model override and the effective model ID."""

        identity = self._require_identity()
        selected_model = (
            self._pulse_model
            or identity.tuning.slow_model
            or identity.tuning.fast_model
        )
        model_id = (
            selected_model
            or str(getattr(self._llm, "default_model_id", "") or "").strip()
        )
        if not model_id:
            # Synthetic clients may not expose a configured model. Real
            # InferenceClient instances always do.
            model_id = "unresolved-client-default"
        return selected_model, model_id

    def _bind_current_reference_process(self, *, session_id: str | None = None) -> None:
        """Bind the process checkpoint to the host's current attachment."""

        if session_id is None:
            session_id = (
                ""
                if self._attachment_kind == "traveling"
                else self._active_session_id()
            )
        _selected_model, model_id = self._process_model_binding()
        self._bind_reference_process(model_id=model_id, session_id=session_id)

    def _bind_reference_process(self, *, model_id: str, session_id: str) -> None:
        """Bind checkpointed process state to authoritative host/runtime facts."""

        identity = self._require_identity()
        binding = ResidentProcessBinding(
            actor_id=identity.actor_id,
            hearth_shard_id=self._hearth_shard_id,
            runtime_generation=self._runtime_generation,
            attachment_kind=self._attachment_kind,
            world_id=self._world_id,
            city_id=str(self._city_id or ""),
            session_id=str(session_id or "").strip(),
            model_id=model_id,
            travel_id=self._travel_id,
        )
        candidate = binding.as_dict()
        current = load_resident_process_envelope(self._resident_dir / "memory")
        if current is not None:
            restored = ResidentProcessBinding.from_dict(current)
            if restored.actor_id != binding.actor_id:
                raise RuntimeError(
                    "resident process checkpoint belongs to a different actor"
                )
            if (
                restored.hearth_shard_id
                and binding.hearth_shard_id
                and restored.hearth_shard_id != binding.hearth_shard_id
            ):
                raise RuntimeError(
                    "resident process checkpoint belongs to a different hearth"
                )
            if restored.runtime_generation > binding.runtime_generation:
                raise RuntimeError(
                    "resident process checkpoint belongs to a newer hearth generation"
                )
            if restored.as_dict() == candidate:
                return
        append_runtime_event(
            self._resident_dir / "memory",
            event_type="reference_process_bound",
            payload=candidate,
        )

    def _process_lifecycle_payload(self, host_run_id: str) -> dict[str, Any]:
        identity = self._require_identity()
        return {
            "process_lifecycle_version": PROCESS_HOST_LIFECYCLE_VERSION,
            "actor_id": identity.actor_id,
            "hearth_shard_id": self._hearth_shard_id,
            "runtime_generation": self._runtime_generation,
            "host_run_id": host_run_id,
        }

    def _begin_process_hosting(self) -> None:
        """Record one running host interval after binding the current attachment."""

        if self._host_run_id is not None:
            return
        self._bind_current_reference_process()
        host_run_id = f"host-{uuid.uuid4().hex}"
        append_runtime_event(
            self._resident_dir / "memory",
            event_type="reference_process_host_started",
            payload=self._process_lifecycle_payload(host_run_id),
        )
        self._host_run_id = host_run_id

    def _suspend_process_hosting(self) -> None:
        """Record a clean stop; absence of this event leaves stop time unknown."""

        host_run_id = self._host_run_id
        if host_run_id is None:
            return
        try:
            append_runtime_event(
                self._resident_dir / "memory",
                event_type="reference_process_host_suspended",
                payload=self._process_lifecycle_payload(host_run_id),
            )
        finally:
            self._host_run_id = None

    async def _apply_travel_request(
        self,
        world: CityWorld | LocalWorld,
        request: TravelRequest,
    ) -> CityWorld | LocalWorld:
        if self._attachment_kind == "city" and request.destination_kind == "hearth":
            return await self._enter_hearth(world)
        if (
            self._attachment_kind == "city"
            and request.destination_kind == "city"
            and request.route_id
            and request.destination_shard
        ):
            return await self._enter_remote_city(world, request)
        if self._attachment_kind == "hearth" and request.destination_kind == "city":
            return await self._enter_city(world)
        self._record_transition(
            "world_attachment_transition_failed",
            transition_id=f"travel-{uuid.uuid4().hex}",
            from_world=self._attachment_kind,
            to_world=request.destination_kind,
            reason="invalid_destination_from_current_world",
        )
        return world

    async def _enter_hearth(
        self,
        city_world: CityWorld,
    ) -> CityWorld | LocalWorld:
        async with self._attachment_lock:
            return await self._enter_hearth_locked(city_world)

    async def _enter_hearth_locked(
        self,
        city_world: CityWorld,
        *,
        pending: PendingHearthDeparture | None = None,
    ) -> CityWorld | LocalWorld:
        transition_id = (
            pending.transition_id
            if pending is not None
            else f"travel-{uuid.uuid4().hex}"
        )
        city_session_id = (
            pending.session_id if pending is not None else self._active_session_id()
        )
        if pending is None:
            self._record_transition(
                "world_attachment_transition_started",
                transition_id=transition_id,
                from_world="city",
                to_world="hearth",
                from_session_id=city_session_id,
            )
        try:
            receipt = await self._ww.leave_session(
                city_session_id,
                transition_id=transition_id,
            )
            if not bool(receipt.get("success")):
                raise RuntimeError("city did not confirm session retirement")
            if (
                str(receipt.get("transition_id") or "") != transition_id
                or str(receipt.get("session_id") or "") != city_session_id
                or str(receipt.get("actor_id") or "")
                != str(self._require_identity().actor_id)
                or int(receipt.get("runtime_generation") or 0)
                != self._runtime_generation
            ):
                raise RuntimeError("city returned a mismatched retirement receipt")
        except Exception as exc:
            self._record_transition(
                "world_attachment_transition_deferred",
                transition_id=transition_id,
                from_world="city",
                to_world="hearth",
                from_session_id=city_session_id,
                reason=str(exc),
            )
            logger.warning(
                "[%s] city departure not confirmed; remaining in city: %s",
                self.name,
                exc,
            )
            return city_world

        await city_world.close()
        (self._resident_dir / "session_id.txt").unlink(missing_ok=True)
        self._session_id = None
        self._attachment_kind = "hearth"
        self._travel_id = ""
        self._bind_current_reference_process()
        self._record_transition(
            "world_attachment_changed",
            transition_id=transition_id,
            from_world="city",
            to_world="hearth",
            from_session_id=city_session_id,
            from_world_url=self._client_url(self._ww),
            to_session_id=self._active_session_id(),
        )
        await self._notify_attachment_checkpoint(transition_id)
        hearth = self._build_hearth_world()
        logger.info("[%s] entered private hearth", self.name)
        return hearth

    async def _resume_pending_hearth_departure(
        self,
        world: CityWorld | LocalWorld,
    ) -> CityWorld | LocalWorld:
        pending = self._pending_hearth_departure()
        if pending is None:
            return world
        if not isinstance(world, CityWorld):
            raise RuntimeError("pending hearth departure requires its city attachment")
        async with self._attachment_lock:
            return await self._enter_hearth_locked(world, pending=pending)

    async def _enter_city(
        self,
        hearth_world: LocalWorld,
    ) -> CityWorld | LocalWorld:
        async with self._attachment_lock:
            return await self._enter_city_locked(hearth_world)

    async def _enter_city_locked(
        self,
        hearth_world: LocalWorld,
    ) -> CityWorld | LocalWorld:
        transition_id = f"travel-{uuid.uuid4().hex}"
        self._record_transition(
            "world_attachment_transition_started",
            transition_id=transition_id,
            from_world="hearth",
            to_world="city",
            from_session_id=self._active_session_id(),
        )
        try:
            city_session_id = await self._get_or_create_session(self._world_id)
        except Exception as exc:
            self._record_transition(
                "world_attachment_transition_failed",
                transition_id=transition_id,
                from_world="hearth",
                to_world="city",
                from_session_id=self._active_session_id(),
                reason=str(exc),
            )
            logger.warning(
                "[%s] city arrival failed; remaining at hearth: %s",
                self.name,
                exc,
            )
            return hearth_world

        await hearth_world.close()
        self._session_id = city_session_id
        self._attachment_kind = "city"
        self._travel_id = ""
        await self._refresh_city_profile()
        city = self._build_city_world(city_session_id)
        self._bind_current_reference_process(session_id=city_session_id)
        self._record_transition(
            "world_attachment_changed",
            transition_id=transition_id,
            from_world="hearth",
            to_world="city",
            from_session_id=f"{self._require_identity().actor_id}-hearth",
            to_world_url=self._client_url(self._ww),
            to_session_id=city_session_id,
        )
        logger.info("[%s] entered city session %s", self.name, city_session_id)
        return city

    async def _enter_remote_city(
        self,
        city_world: CityWorld,
        request: TravelRequest,
    ) -> CityWorld | LocalWorld:
        async with self._attachment_lock:
            transition_id = f"travel-{uuid.uuid4().hex}"
            travel_id = str(uuid.uuid4())
            destination_session_id = self._new_session_id()
            pending = PendingShardTravel(
                travel_id=travel_id,
                transition_id=transition_id,
                route_id=request.route_id,
                source_url=self._client_url(self._ww),
                source_session_id=self._active_session_id(),
                destination_shard=request.destination_shard,
                destination_url="",
                destination_session_id=destination_session_id,
            )
            self._record_transition(
                "inter_shard_travel_started",
                travel_id=travel_id,
                transition_id=transition_id,
                route_id=pending.route_id,
                source_url=pending.source_url,
                source_session_id=pending.source_session_id,
                destination_shard=pending.destination_shard,
                destination_url="",
                destination_session_id=pending.destination_session_id,
            )
            await city_world.close()
            completed = await self._resume_inter_shard_travel(pending)
            if not completed:
                return city_world
            return self._build_city_world(self._active_session_id())

    async def _resume_inter_shard_travel(self, pending: PendingShardTravel) -> bool:
        """Finish one ledger-recorded trip without running cognition in both cities."""
        source_client = self._ww
        if (
            not pending.source_departed
            and pending.source_url
            and self._client_url(source_client) != pending.source_url
        ):
            source_client = self._new_world_client(pending.source_url)
        if not pending.source_departed:
            self._ww = source_client

        destination_url = pending.destination_url
        while not pending.source_departed:
            try:
                receipt = await source_client.depart_session_for_travel(
                    session_id=pending.source_session_id,
                    route_id=pending.route_id,
                    destination_shard=pending.destination_shard,
                    travel_id=pending.travel_id,
                    reason="resident chose inter-city travel",
                )
                handoff = receipt.get("handoff") if isinstance(receipt, dict) else None
                if isinstance(handoff, dict):
                    destination_url = str(
                        handoff.get("destination_url") or destination_url
                    ).strip()
                    if str(handoff.get("status") or "").strip() == "traveling":
                        pending = replace(
                            pending,
                            source_departed=True,
                            destination_url=destination_url,
                        )
                        self._record_transition(
                            "inter_shard_source_departed",
                            travel_id=pending.travel_id,
                            transition_id=pending.transition_id,
                            destination_url=destination_url,
                        )
                        (self._resident_dir / "session_id.txt").unlink(missing_ok=True)
                        self._session_id = None
                        self._attachment_kind = "traveling"
                        self._travel_id = pending.travel_id
                        self._bind_current_reference_process()
                        break
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                try:
                    await source_client.get_scene(pending.source_session_id)
                except Exception:
                    pass
                else:
                    self._record_transition(
                        "inter_shard_travel_aborted",
                        travel_id=pending.travel_id,
                        transition_id=pending.transition_id,
                        reason=str(exc),
                    )
                    self._session_id = pending.source_session_id
                    self._attachment_kind = "city"
                    self._travel_id = ""
                    (self._resident_dir / "session_id.txt").write_text(
                        self._session_id, encoding="utf-8"
                    )
                    self._bind_current_reference_process(
                        session_id=pending.source_session_id
                    )
                    logger.warning(
                        "[%s] departure failed before source retirement; remaining in source city: %s",
                        self.name,
                        exc,
                    )
                    return False
                logger.warning(
                    "[%s] source departure %s will retry: %s",
                    self.name,
                    pending.travel_id,
                    exc,
                )
            await asyncio.sleep(self._travel_retry_seconds)

        if not destination_url:
            raise RuntimeError(f"Travel {pending.travel_id} has no destination URL")

        destination_client = self._new_world_client(destination_url)
        while True:
            try:
                receipt = await destination_client.arrive_session_from_travel(
                    travel_id=pending.travel_id,
                    session_id=pending.destination_session_id,
                )
                handoff = receipt.get("handoff") if isinstance(receipt, dict) else None
                if (
                    isinstance(handoff, dict)
                    and str(handoff.get("status") or "").strip() == "arrived"
                ):
                    world_id = await destination_client.get_world_id()
                    if not world_id:
                        raise RuntimeError(
                            "destination has no readable world ID after arrival"
                        )
                    previous_client = self._ww
                    self._ww = destination_client
                    self._world_id = world_id
                    self._session_id = pending.destination_session_id
                    self._attachment_kind = "city"
                    self._travel_id = ""
                    (self._resident_dir / "session_id.txt").write_text(
                        self._session_id, encoding="utf-8"
                    )
                    await self._refresh_city_profile()
                    self._bind_current_reference_process(
                        session_id=pending.destination_session_id
                    )
                    self._record_transition(
                        "inter_shard_travel_arrived",
                        travel_id=pending.travel_id,
                        transition_id=pending.transition_id,
                        from_world="city",
                        to_world="city",
                        from_world_url=pending.source_url,
                        to_world_url=destination_url,
                        from_session_id=pending.source_session_id,
                        to_session_id=pending.destination_session_id,
                        destination_shard=pending.destination_shard,
                    )
                    if (
                        previous_client in self._owned_world_clients
                        and previous_client is not destination_client
                    ):
                        await previous_client.close()
                        self._owned_world_clients.remove(previous_client)
                    logger.info(
                        "[%s] arrived at node %s", self.name, pending.destination_shard
                    )
                    return True
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "[%s] destination arrival %s will retry: %s",
                    self.name,
                    pending.travel_id,
                    exc,
                )
            await asyncio.sleep(self._travel_retry_seconds)

    async def _refresh_city_profile(self) -> None:
        """Refresh place identity and optional verbs after attaching to a node."""

        experience_reader = getattr(self._ww, "get_shard_experience", None)
        preview_reader = getattr(self._ww, "get_city_pack_preview", None)
        if not callable(experience_reader) and not callable(preview_reader):
            # Small test and third-party clients predating public shard profiles keep
            # the old catalog until they adopt the two public endpoints.
            return

        self._city_id = ""
        self._city_capabilities = frozenset()
        if callable(experience_reader):
            try:
                experience = await experience_reader()
                disclosure = (
                    experience.get("entry_disclosure")
                    if isinstance(experience, dict)
                    else {}
                )
                rows = (
                    disclosure.get("capabilities")
                    if isinstance(disclosure, dict)
                    else []
                )
                self._city_capabilities = frozenset(
                    capability_id
                    for item in list(rows or [])
                    if isinstance(item, dict)
                    and (capability_id := str(item.get("id") or "").strip())
                )
            except Exception as exc:
                logger.warning(
                    "[%s] could not read shard capabilities: %s", self.name, exc
                )

        if callable(preview_reader):
            try:
                preview = await preview_reader()
                manifest = preview.get("manifest") if isinstance(preview, dict) else {}
                if isinstance(manifest, dict):
                    self._city_id = str(manifest.get("city_id") or "").strip()
                if not self._city_id and isinstance(preview, dict):
                    self._city_id = str(preview.get("city_id") or "").strip()
            except Exception as exc:
                logger.warning("[%s] could not read city identity: %s", self.name, exc)

    def _record_transition(
        self,
        event_type: str,
        **payload: str,
    ) -> None:
        identity = self._require_identity()
        append_runtime_event(
            self._resident_dir / "memory",
            event_type=event_type,
            payload={
                "actor_id": str(identity.actor_id or ""),
                **payload,
            },
            ts=self._world_clock.now(),
        )

    def _last_attachment_kind(self) -> str | None:
        for event in reversed(load_runtime_events(self._resident_dir / "memory")):
            event_type = str(event.get("event_type") or "")
            if event_type == "inter_shard_travel_arrived":
                return "city"
            if event_type != "world_attachment_changed":
                continue
            destination = str(
                (event.get("payload") or {}).get("to_world") or ""
            ).strip()
            if destination in {"city", "hearth"}:
                return destination
        return None

    def _last_city_url(self) -> str:
        for event in reversed(load_runtime_events(self._resident_dir / "memory")):
            event_type = str(event.get("event_type") or "").strip()
            payload = (
                event.get("payload") if isinstance(event.get("payload"), dict) else {}
            )
            if event_type == "inter_shard_travel_arrived":
                city_url = str(payload.get("to_world_url") or "").strip()
                if city_url:
                    return city_url
            if event_type == "world_attachment_changed":
                if str(payload.get("to_world") or "").strip() == "city":
                    city_url = str(payload.get("to_world_url") or "").strip()
                    if city_url:
                        return city_url
                if str(payload.get("from_world") or "").strip() == "city":
                    city_url = str(payload.get("from_world_url") or "").strip()
                    if city_url:
                        return city_url
        return ""

    def _pending_shard_travel(self) -> PendingShardTravel | None:
        return derive_pending_shard_travel(
            load_runtime_events(self._resident_dir / "memory")
        )

    def _pending_hearth_departure(self) -> PendingHearthDeparture | None:
        pending: dict[str, PendingHearthDeparture] = {}
        for event in load_runtime_events(self._resident_dir / "memory"):
            event_type = str(event.get("event_type") or "").strip()
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            transition_id = str(payload.get("transition_id") or "").strip()
            if not transition_id:
                continue
            if (
                event_type == "world_attachment_transition_started"
                and str(payload.get("from_world") or "").strip() == "city"
                and str(payload.get("to_world") or "").strip() == "hearth"
            ):
                session_id = str(payload.get("from_session_id") or "").strip()
                if session_id:
                    pending[transition_id] = PendingHearthDeparture(
                        transition_id=transition_id,
                        session_id=session_id,
                    )
            elif event_type in {
                "world_attachment_changed",
                "world_attachment_transition_failed",
            }:
                pending.pop(transition_id, None)
        return list(pending.values())[-1] if pending else None

    async def _notify_attachment_checkpoint(self, transition_id: str) -> None:
        observer = self._attachment_checkpoint_observer
        if observer is None:
            return
        observed = observer(self._require_identity(), transition_id)
        if inspect.isawaitable(observed):
            await observed

    @staticmethod
    def _client_url(client: Any) -> str:
        return str(getattr(client, "base_url", "") or "").strip().rstrip("/")

    def _new_world_client(self, url: str) -> WorldWeaverClient:
        client = self._world_client_factory(str(url or "").strip().rstrip("/"))
        self._owned_world_clients.append(client)
        return client

    def _restored_attachment_kind(self) -> str:
        """Compatibility helper for callers that expect the normal city default."""
        return self._last_attachment_kind() or "city"

    @staticmethod
    def _take_force_ignite(world: CityWorld | LocalWorld) -> bool:
        take_signal = getattr(world, "take_force_ignite", None)
        return bool(take_signal()) if callable(take_signal) else False

    async def _notify_tick(
        self,
        world: CityWorld | LocalWorld,
        core: ResidentCore,
        result: dict[str, Any],
        tick_count: int,
    ) -> None:
        if self._tick_observer is None:
            return
        try:
            observed = self._tick_observer(
                self._require_identity(),
                world,
                core,
                result,
                tick_count,
            )
            if inspect.isawaitable(observed):
                await observed
        except Exception as exc:
            logger.warning("[%s] tick observer failed: %s", self.name, exc)

    def _active_session_id(self) -> str:
        if self._attachment_kind == "hearth":
            return f"{self._require_identity().actor_id}-hearth"
        if not self._session_id:
            raise RuntimeError(f"Resident {self.name} has no active city session")
        return self._session_id

    def _require_identity(self) -> ResidentIdentity:
        if self._identity is None:
            raise RuntimeError("resident identity is not loaded")
        return self._identity

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def _get_or_create_session(self, world_id: str) -> str:
        session_path = self._resident_dir / "session_id.txt"

        if session_path.exists():
            session_id = session_path.read_text(encoding="utf-8").strip()
            try:
                await self._ww.get_scene(session_id)
                logger.debug("[%s] resumed session: %s", self.name, session_id)
                return session_id
            except Exception:
                logger.info(
                    "[%s] session %s stale — creating new session",
                    self.name,
                    session_id,
                )
                session_path.unlink(missing_ok=True)

        # New session — bootstrap with the world server. The random suffix matters
        # when a resident leaves and returns within the same second: a new city
        # incarnation must never reuse the retired session ID. The server only reads
        # the leading slug/date when deriving an agent display name.
        session_id = self._new_session_id()
        identity = self._identity

        # Always re-fetch the live world_id when creating a new session.
        # The startup world_id may be stale after a canon reset — using it
        # would attach the session to a world that no longer exists.
        live_world_id = await self._ww.get_world_id()
        if live_world_id:
            world_id = live_world_id
        else:
            logger.warning(
                "[%s] could not fetch live world_id — using startup value", self.name
            )

        # player_role format "Name — vibe" lets the server extract just the name
        player_role = (
            f"{identity.display_name} — {identity.vibe}"
            if identity.vibe
            else identity.display_name
        )

        entry_location_path = self._resident_dir / "identity" / "entry_location.txt"
        entry_location = ""
        if entry_location_path.exists():
            entry_location = entry_location_path.read_text(encoding="utf-8").strip()
            entry_location_path.unlink()  # consume once

        await self._ww.bootstrap_session(
            session_id=session_id,
            world_id=world_id,
            world_theme="",  # server uses existing world theme
            player_role=player_role,
            actor_id=str(identity.actor_id or "").strip(),
            tone="natural, grounded",
            description=identity.soul[:300],
            entry_location=entry_location,
        )

        session_path.write_text(session_id, encoding="utf-8")
        logger.info("[%s] bootstrapped new session: %s", self.name, session_id)
        return session_id

    def _new_session_id(self) -> str:
        ts = self._world_clock.now().astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S")
        name_slug = slugify_resident_name(self._require_identity().name)
        return f"{name_slug}-{ts}-{uuid.uuid4().hex[:8]}"
