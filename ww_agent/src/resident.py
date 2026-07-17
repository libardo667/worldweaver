# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from src.familiar.config import HearthConfig
from src.familiar.file_scope import FileScope
from src.familiar.local_world import LocalWorld
from src.familiar.weather import WeatherProvider
from src.identity.loader import IdentityLoader, ResidentIdentity
from src.inference.client import InferenceClient
from src.runtime.cognitive_core import CognitiveCore
from src.runtime.growth_proposals import collect_new_growth_proposals
from src.runtime.ledger import append_runtime_event, load_runtime_events
from src.runtime.mirror import ResidentRuntimeMirror
from src.runtime.naming import slugify_resident_name
from src.runtime.signals import StimulusPacketQueue
from src.runtime.travel import TravelRequest
from src.world.city_tools import build_city_source_registry
from src.world.city_world import CityWorld
from src.world.client import WorldWeaverClient

logger = logging.getLogger(__name__)

TickObserver = Callable[
    [ResidentIdentity, CityWorld | LocalWorld, CognitiveCore, dict[str, Any], int],
    Awaitable[None] | None,
]


def _env_flag(name: str) -> bool:
    """A truthy shard-wide toggle from the environment (1/true/yes/on)."""
    return str(os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


class Resident:
    """
    A single running agent: one character, one cognitive core.

    Residents are autonomous — they boot themselves, manage their own
    session with the world server, and run until cancelled. The mind is the
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
        tick_observer: TickObserver | None = None,
    ):
        self._resident_dir = resident_dir
        self._ww = ww_client
        self._llm = llm
        self._identity: ResidentIdentity | None = None
        self._session_id: str | None = None
        self._world_id: str = ""
        self._attachment_kind: str = "city"
        self._attachment_lock = asyncio.Lock()
        self._hearth_config = hearth_config
        self._weather_provider: WeatherProvider | None = None
        self._tick_seconds = tick_seconds
        self._tick_observer = tick_observer
        self._tasks: list[asyncio.Task] = []
        self._packet_queue: StimulusPacketQueue | None = None

    @property
    def name(self) -> str:
        if self._identity:
            return self._identity.name
        return self._resident_dir.name

    @property
    def identity(self) -> ResidentIdentity:
        """The loaded identity owned by this resident host."""
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
        self._attachment_kind = restored_attachment or default_attachment
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

    async def run(
        self,
        *,
        max_ticks: int = 0,
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

        # Initialize the runtime snapshot so the substrate state is inspectable
        # from the first tick. Packets are now emitted by perception.
        packet_queue = StimulusPacketQueue(self._resident_dir / "memory" / "stimulus_packets.json")
        packet_queue.ensure_file()
        self._packet_queue = packet_queue

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
                                if stop_after_tick:
                                    return
                                break
                            mirror_task = self._start_runtime_mirror()
                        if stop_after_tick:
                            return
                        delay = core.tick_seconds if pause_seconds is None else max(0.0, float(pause_seconds))
                        await asyncio.sleep(delay)
                finally:
                    await self._cancel_task(mirror_task)
        except asyncio.CancelledError:
            logger.info("[%s] resident cancelled", self.name)
            raise
        finally:
            await self._cancel_task(growth_task)
            await world.close()

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
            city_names={"city"},
        )

    def _build_core(
        self,
        world: CityWorld | LocalWorld,
        session_id: str,
    ) -> CognitiveCore:
        identity = self._require_identity()
        return CognitiveCore(
            identity=identity,
            resident_dir=self._resident_dir,
            ww_client=world,
            llm=self._llm,
            session_id=session_id,
            pulse_model=identity.tuning.slow_model or identity.tuning.fast_model,
            pulse_temperature=identity.tuning.fast_temperature,
            **({"tick_seconds": self._tick_seconds} if self._tick_seconds is not None else {}),
            writes_to_workshop_only=self._attachment_kind == "hearth",
            anchor_gating=identity.tuning.anchor_gating,
            incubation=(self._attachment_kind == "city" and (identity.tuning.incubation_enabled or _env_flag("WW_INCUBATION_ENABLED"))),
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
        city = self._build_city_world(city_session_id)
        self._record_transition(
            "world_attachment_changed",
            transition_id=transition_id,
            from_world="hearth",
            to_world="city",
            from_session_id=f"{self._require_identity().actor_id}-hearth",
            to_session_id=city_session_id,
        )
        logger.info("[%s] entered city session %s", self.name, city_session_id)
        return city

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
            if str(event.get("event_type") or "") != "world_attachment_changed":
                continue
            destination = str((event.get("payload") or {}).get("to_world") or "").strip()
            if destination in {"city", "hearth"}:
                return destination
        return None

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
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        name_slug = slugify_resident_name(self._identity.name)
        session_id = f"{name_slug}-{ts}-{uuid.uuid4().hex[:8]}"
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
