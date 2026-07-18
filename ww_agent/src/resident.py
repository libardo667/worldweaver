# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from src.familiar.config import HearthConfig
from src.familiar.file_scope import FileScope
from src.familiar.local_world import LocalWorld
from src.familiar.weather import WeatherProvider
from src.identity.hearth_activation import (
    HearthRuntimeLease,
    acquire_hearth_runtime,
)
from src.identity.loader import IdentityLoader, ResidentIdentity
from src.inference.client import InferenceClient
from src.runtime.cognitive_core import CognitiveCore
from src.runtime.growth_proposals import collect_new_growth_proposals
from src.runtime.ledger import append_runtime_event, load_runtime_events
from src.runtime.mirror import ResidentRuntimeMirror
from src.runtime.naming import slugify_resident_name
from src.runtime.signals import StimulusPacketQueue
from src.runtime.travel import (
    PendingShardTravel,
    TravelRequest,
    derive_pending_shard_travel,
)
from src.world.city_tools import build_city_source_registry
from src.world.city_world import CityWorld
from src.world.client import WorldWeaverClient

logger = logging.getLogger(__name__)

_IDENTITY_TEMPERATURE = object()

TickObserver = Callable[
    [ResidentIdentity, CityWorld | LocalWorld, CognitiveCore, dict[str, Any], int],
    Awaitable[None] | None,
]


def _env_flag(name: str) -> bool:
    """A truthy shard-wide toggle from the environment (1/true/yes/on)."""
    return str(os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


class Resident:
    """
    A single running resident: one identity, one cognitive core, and one active
    world attachment.

    This object is the resident's current software host, not their owner. The
    resident directory is the currently mounted hearth storage, not a permanent
    machine address. Residents manage their own session with the world server
    and run until cancelled. The mind is the
    Major 49 substrate + pulse: perception lays the world down as perturbations,
    the ledger-derived substrate accumulates surprise against its afterimage, and
    on ignition a single LLM pulse acts and re-predicts. Everything else comes
    from the world.
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
        world_client_factory: Callable[[str], WorldWeaverClient] | None = None,
        travel_retry_seconds: float = 5.0,
        action_tendency: bool | None = None,
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
        self._world_client_factory = world_client_factory or (lambda url: WorldWeaverClient(base_url=url))
        self._travel_retry_seconds = max(0.0, float(travel_retry_seconds))
        self._action_tendency = action_tendency
        self._owned_world_clients: list[WorldWeaverClient] = []
        self._tasks: list[asyncio.Task] = []
        self._packet_queue: StimulusPacketQueue | None = None
        self._runtime_lease: HearthRuntimeLease | None = None

    @property
    def name(self) -> str:
        if self._identity:
            return self._identity.name
        return self._resident_dir.name

    @property
    def identity(self) -> ResidentIdentity:
        """The resident identity currently loaded by this temporary host."""
        return self._require_identity()

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
        self._resident_dir.mkdir(parents=True, exist_ok=True)
        self._runtime_lease = acquire_hearth_runtime(self._resident_dir)
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
        if self._hearth_config is None:
            self._hearth_config = HearthConfig.load(self._resident_dir)
        logger.info("[%s] identity loaded", self.name)
        self._world_id = str(world_id or "").strip()
        if default_attachment not in {"city", "hearth"}:
            raise ValueError("default_attachment must be 'city' or 'hearth'")
        restored_attachment = self._last_attachment_kind()
        pending_travel = self._pending_shard_travel()
        last_city_url = self._last_city_url()
        if last_city_url and last_city_url != self._client_url(self._ww):
            self._ww = self._new_world_client(last_city_url)
        self._attachment_kind = restored_attachment or default_attachment
        if pending_travel is not None:
            self._attachment_kind = "traveling"
            self._session_id = None
            (self._resident_dir / "session_id.txt").unlink(missing_ok=True)
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
            await self._hydrate_identity_growth()
            await self._refresh_city_profile()

    async def run(
        self,
        *,
        max_ticks: int = 0,
        max_duration_seconds: float | None = None,
        pause_seconds: float | None = None,
        park_at_hearth_on_stop: bool = False,
    ) -> None:
        """Run the one resident core while holding its exclusive hearth lease."""
        if self._runtime_lease is None:
            if not self._identity:
                raise RuntimeError(f"Resident {self.name} not started — call start() first")
            self._runtime_lease = acquire_hearth_runtime(self._resident_dir)
        try:
            await self._run_started(
                max_ticks=max_ticks,
                max_duration_seconds=max_duration_seconds,
                pause_seconds=pause_seconds,
            )
        finally:
            try:
                if park_at_hearth_on_stop:
                    await self._park_current_city_at_hearth()
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

    async def _park_current_city_at_hearth(self) -> None:
        if self._attachment_kind == "hearth":
            return
        if self._attachment_kind != "city":
            raise RuntimeError(f"Resident {self.name} cannot park while {self._attachment_kind}")
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
    ) -> None:
        """
        Run the resident mind: one cognitive core (substrate + pulse), the
        runtime mirror, and growth-proposal sync, concurrently. Returns when
        they stop (or any raises an unhandled exception).

        The fast/slow/mail/ground/wander loops are gone (Major 49): cognition is
        the ignition-fired pulse over the ledger-derived substrate, perception is
        the core's sensory surface, and outward acts go through its effector.
        """
        if not self._identity:
            raise RuntimeError(f"Resident {self.name} not started — call start() first")
        if max_ticks > 0 and max_duration_seconds is not None:
            raise ValueError("choose either max_ticks or max_duration_seconds")
        duration = None if max_duration_seconds is None else max(0.0, float(max_duration_seconds))
        loop = asyncio.get_running_loop()
        deadline = loop.time() + duration if duration is not None else None

        # Initialize the runtime snapshot so the substrate state is inspectable
        # from the first tick. Packets are now emitted by perception.
        packet_queue = StimulusPacketQueue(self._resident_dir / "memory" / "stimulus_packets.json")
        packet_queue.ensure_file()
        self._packet_queue = packet_queue

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
        growth_task = asyncio.create_task(
            self._sync_growth_proposals(),
            name=f"resident:{self.name}:growth",
        )
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
                mirror_task = self._start_runtime_mirror()
                try:
                    while True:
                        if tick_count > 0 and deadline is not None and loop.time() >= deadline:
                            return
                        result: dict[str, Any] | None = None
                        try:
                            force_ignite = self._take_force_ignite(world)
                            result = await core.tick_once(force_ignite=force_ignite)
                        except asyncio.CancelledError:
                            raise
                        except Exception as exc:
                            logger.exception(
                                "[%s] cognitive tick error: %s",
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
                        stop_after_tick = max_ticks > 0 and tick_count >= max_ticks
                        stop_after_duration = deadline is not None and loop.time() >= deadline

                        take_pending = getattr(world, "take_pending_travel", None)
                        request = take_pending() if callable(take_pending) else None
                        if request is not None:
                            # A late mirror write could recreate city presence after
                            # departure, so quiesce it before changing worlds.
                            await self._cancel_task(mirror_task)
                            mirror_task = None
                            next_world = await self._apply_travel_request(
                                world,
                                request,
                            )
                            if next_world is not world:
                                world = next_world
                                if stop_after_tick or stop_after_duration:
                                    return
                                break
                            mirror_task = self._start_runtime_mirror()
                        if stop_after_tick or stop_after_duration:
                            return
                        delay = core.tick_seconds if pause_seconds is None else max(0.0, float(pause_seconds))
                        if deadline is not None:
                            delay = min(delay, max(0.0, deadline - loop.time()))
                        await asyncio.sleep(delay)
                finally:
                    await self._cancel_task(mirror_task)
        except asyncio.CancelledError:
            logger.info("[%s] resident cancelled", self.name)
            raise
        finally:
            await self._cancel_task(growth_task)
            await world.close()
            for client in list(self._owned_world_clients):
                await client.close()
            self._owned_world_clients.clear()

    def _release_runtime_lease(self) -> None:
        lease = self._runtime_lease
        self._runtime_lease = None
        if lease is not None:
            lease.release()

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
        file_scope = FileScope(read_roots=list(config.read_roots)) if config.read_roots else None
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
        )

    def _build_core(
        self,
        world: CityWorld | LocalWorld,
        session_id: str,
    ) -> CognitiveCore:
        identity = self._require_identity()
        pulse_temperature = identity.tuning.fast_temperature if self._pulse_temperature is _IDENTITY_TEMPERATURE else self._pulse_temperature
        return CognitiveCore(
            identity=identity,
            resident_dir=self._resident_dir,
            ww_client=world,
            llm=self._llm,
            session_id=session_id,
            pulse_model=self._pulse_model or identity.tuning.slow_model or identity.tuning.fast_model,
            pulse_temperature=pulse_temperature,
            **({"tick_seconds": self._tick_seconds} if self._tick_seconds is not None else {}),
            writes_to_workshop_only=self._attachment_kind == "hearth",
            pulse_vision=bool(self._hearth_config and self._hearth_config.vision),
            anchor_gating=identity.tuning.anchor_gating,
            incubation=(self._attachment_kind == "city" and (identity.tuning.incubation_enabled or _env_flag("WW_INCUBATION_ENABLED"))),
            action_tendency=self._action_tendency,
        )

    def _start_runtime_mirror(self) -> asyncio.Task | None:
        if self._attachment_kind != "city" or not self._session_id:
            return None
        mirror = ResidentRuntimeMirror(
            resident_dir=self._resident_dir,
            ww_client=self._ww,
            session_id=self._session_id,
        )
        return asyncio.create_task(
            mirror.run(),
            name=f"resident:{self.name}:mirror",
        )

    async def _apply_travel_request(
        self,
        world: CityWorld | LocalWorld,
        request: TravelRequest,
    ) -> CityWorld | LocalWorld:
        if self._attachment_kind == "city" and request.destination_kind == "hearth":
            return await self._enter_hearth(world)
        if self._attachment_kind == "city" and request.destination_kind == "city" and request.route_id and request.destination_shard:
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
    ) -> CityWorld | LocalWorld:
        transition_id = f"travel-{uuid.uuid4().hex}"
        city_session_id = self._active_session_id()
        self._record_transition(
            "world_attachment_transition_started",
            transition_id=transition_id,
            from_world="city",
            to_world="hearth",
            from_session_id=city_session_id,
        )
        try:
            receipt = await self._ww.leave_session(city_session_id)
            if not bool(receipt.get("success")):
                raise RuntimeError("city did not confirm session retirement")
        except Exception as exc:
            self._record_transition(
                "world_attachment_transition_failed",
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
        hearth = self._build_hearth_world()
        self._record_transition(
            "world_attachment_changed",
            transition_id=transition_id,
            from_world="city",
            to_world="hearth",
            from_session_id=city_session_id,
            from_world_url=self._client_url(self._ww),
            to_session_id=self._active_session_id(),
        )
        logger.info("[%s] entered private hearth", self.name)
        return hearth

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
        await self._hydrate_identity_growth()
        await self._refresh_city_profile()
        city = self._build_city_world(city_session_id)
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
        if not pending.source_departed and pending.source_url and self._client_url(source_client) != pending.source_url:
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
                    destination_url = str(handoff.get("destination_url") or destination_url).strip()
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
                    (self._resident_dir / "session_id.txt").write_text(self._session_id, encoding="utf-8")
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
                if isinstance(handoff, dict) and str(handoff.get("status") or "").strip() == "arrived":
                    world_id = await destination_client.get_world_id()
                    if not world_id:
                        raise RuntimeError("destination has no readable world ID after arrival")
                    previous_client = self._ww
                    self._ww = destination_client
                    self._world_id = world_id
                    self._session_id = pending.destination_session_id
                    self._attachment_kind = "city"
                    (self._resident_dir / "session_id.txt").write_text(self._session_id, encoding="utf-8")
                    await self._hydrate_identity_growth()
                    await self._refresh_city_profile()
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
                    if previous_client in self._owned_world_clients and previous_client is not destination_client:
                        await previous_client.close()
                        self._owned_world_clients.remove(previous_client)
                    logger.info("[%s] arrived at node %s", self.name, pending.destination_shard)
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
                disclosure = experience.get("entry_disclosure") if isinstance(experience, dict) else {}
                rows = disclosure.get("capabilities") if isinstance(disclosure, dict) else []
                self._city_capabilities = frozenset(capability_id for item in list(rows or []) if isinstance(item, dict) and (capability_id := str(item.get("id") or "").strip()))
            except Exception as exc:
                logger.warning("[%s] could not read shard capabilities: %s", self.name, exc)

        if callable(preview_reader):
            try:
                preview = await preview_reader()
                manifest = preview.get("manifest") if isinstance(preview, dict) else {}
                if isinstance(manifest, dict):
                    self._city_id = str(manifest.get("city_id") or "").strip()
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
        )

    def _last_attachment_kind(self) -> str | None:
        for event in reversed(load_runtime_events(self._resident_dir / "memory")):
            event_type = str(event.get("event_type") or "")
            if event_type == "inter_shard_travel_arrived":
                return "city"
            if event_type != "world_attachment_changed":
                continue
            destination = str((event.get("payload") or {}).get("to_world") or "").strip()
            if destination in {"city", "hearth"}:
                return destination
        return None

    def _last_city_url(self) -> str:
        for event in reversed(load_runtime_events(self._resident_dir / "memory")):
            event_type = str(event.get("event_type") or "").strip()
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
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
        return derive_pending_shard_travel(load_runtime_events(self._resident_dir / "memory"))

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
        core: CognitiveCore,
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

    @staticmethod
    async def _cancel_task(task: asyncio.Task | None) -> None:
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

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
            logger.warning("[%s] could not fetch live world_id — using startup value", self.name)

        # player_role format "Name — vibe" lets the server extract just the name
        player_role = f"{identity.name} — {identity.vibe}" if identity.vibe else identity.name

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
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        name_slug = slugify_resident_name(self._require_identity().name)
        return f"{name_slug}-{ts}-{uuid.uuid4().hex[:8]}"

    async def _hydrate_identity_growth(self) -> None:
        if not self._identity or not self._session_id:
            return
        try:
            payload = await self._ww.get_identity_growth(self._session_id)
        except Exception as exc:
            logger.debug("[%s] identity growth hydrate failed: %s", self.name, exc)
            return
        growth_text = str(payload.get("growth_text") or "").strip()
        self._identity.growth_soul = growth_text
        self._identity.soul = IdentityLoader.composed_soul(
            self._identity.canonical_soul,
            growth_text,
        )

    async def _sync_growth_proposals(self) -> None:
        # Post accepted self-delta proposals to the server's concordance gate, which
        # decides what becomes soul (>=3 proposals across >=2 calendar days). The agent
        # only posts proposals; the gate owns growth_text. The server dedups by pulse_id.
        posted: set[str] = set()
        memory_dir = self._resident_dir / "memory"
        while True:
            await asyncio.sleep(240.0)
            try:
                async with self._attachment_lock:
                    if not self._session_id:
                        continue
                    proposals = collect_new_growth_proposals(memory_dir, posted)
                    if proposals:
                        await self._ww.update_identity_growth(
                            self._session_id,
                            growth_proposals=proposals,
                        )
                        posted.update(p["pulse_id"] for p in proposals)
                        logger.debug(
                            "[%s] posted %d growth proposal(s)",
                            self.name,
                            len(proposals),
                        )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug("[%s] growth proposal sync failed: %s", self.name, exc)
