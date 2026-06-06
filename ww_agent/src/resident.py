from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.identity.loader import IdentityLoader, ResidentIdentity
from src.inference.client import InferenceClient
from src.runtime.cognitive_core import CognitiveCore
from src.runtime.growth_proposals import collect_new_growth_proposals
from src.runtime.mirror import ResidentRuntimeMirror
from src.runtime.guild import apply_runtime_adaptation, snapshot_authored_tuning
from src.runtime.naming import slugify_resident_name
from src.runtime.signals import StimulusPacketQueue
from src.world.city_tools import build_city_tool_scope
from src.world.city_world import CityWorld
from src.world.client import WorldWeaverClient

logger = logging.getLogger(__name__)


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
    ):
        self._resident_dir = resident_dir
        self._ww = ww_client
        self._llm = llm
        self._identity: ResidentIdentity | None = None
        self._authored_tuning = None
        self._session_id: str | None = None
        self._tasks: list[asyncio.Task] = []
        self._packet_queue: StimulusPacketQueue | None = None

    @property
    def name(self) -> str:
        if self._identity:
            return self._identity.name
        return self._resident_dir.name

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, world_id: str) -> None:
        """
        Load identity, establish session, wire up loops. Call before run().
        """
        self._identity = IdentityLoader.load(self._resident_dir)
        logger.info("[%s] identity loaded", self.name)
        self._authored_tuning = snapshot_authored_tuning(self._identity.tuning)

        self._session_id = await self._get_or_create_session(world_id)
        logger.info("[%s] session: %s", self.name, self._session_id)
        await self._hydrate_identity_growth()
        await self._hydrate_guild_state()

    async def run(self) -> None:
        """
        Run the resident mind: one cognitive core (substrate + pulse), the
        runtime mirror, and guild-state sync, concurrently. Returns when they
        stop (or any raises an unhandled exception).

        The fast/slow/mail/ground/wander loops are gone (Major 49): cognition is
        the ignition-fired pulse over the ledger-derived substrate, perception is
        the core's sensory surface, and outward acts go through its effector.
        """
        if not self._identity or not self._session_id:
            raise RuntimeError(f"Resident {self.name} not started — call start() first")

        identity = self._identity
        session_id = self._session_id

        # Initialize the runtime snapshot so the substrate state is inspectable
        # from the first tick. Packets are now emitted by perception.
        packet_queue = StimulusPacketQueue(self._resident_dir / "memory" / "stimulus_packets.json")
        packet_queue.ensure_file()
        self._packet_queue = packet_queue

        # Wrap the shared transport in a per-resident CityWorld so this resident carries
        # its own city tools (its vocations) — get_scene advertises them, post_action runs
        # them locally, everything else delegates to the shared client.
        city_world = CityWorld(
            self._ww,
            build_city_tool_scope(
                identity,
                client=self._ww,
                session_id=session_id,
                memory_dir=self._resident_dir / "memory",
            ),
        )

        core = CognitiveCore(
            identity=identity,
            resident_dir=self._resident_dir,
            ww_client=city_world,
            llm=self._llm,
            session_id=session_id,
            pulse_model=identity.tuning.slow_model or identity.tuning.fast_model,
            pulse_temperature=identity.tuning.fast_temperature,
            anchor_gating=identity.tuning.anchor_gating,
        )

        runtime_mirror = ResidentRuntimeMirror(
            resident_dir=self._resident_dir,
            ww_client=self._ww,
            session_id=session_id,
        )

        tasks: list[asyncio.Coroutine] = [
            core.run(),
            runtime_mirror.run(),
            self._sync_guild_state(),
            self._sync_growth_proposals(),
        ]

        logger.info("[%s] cognitive core + mirror starting", self.name)

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("[%s] resident cancelled", self.name)
            raise

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

        # New session — bootstrap with the world server.
        # Session ID uses slug-YYYYMMDD-HHMMSS so the digest endpoint can
        # extract the character name for display ("rowan-20260310-..." → "Rowan").
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        name_slug = slugify_resident_name(self._identity.name)
        session_id = f"{name_slug}-{ts}"
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

    async def _hydrate_guild_state(self) -> None:
        if not self._identity or not self._session_id:
            return
        guild_profile: dict = {}
        adaptation: dict = {}
        guild_quests: list[dict] = []
        try:
            guild_profile = await self._ww.get_guild_profile(self._session_id)
        except Exception as exc:
            logger.debug("[%s] guild profile hydrate failed: %s", self.name, exc)
        try:
            adaptation = await self._ww.get_runtime_adaptation(self._session_id)
        except Exception as exc:
            logger.debug("[%s] runtime adaptation hydrate failed: %s", self.name, exc)
        try:
            guild_quests = list((await self._ww.get_guild_quests(self._session_id, status="active", limit=24)).get("quests") or [])
        except Exception as exc:
            logger.debug("[%s] guild quest hydrate failed: %s", self.name, exc)
        apply_runtime_adaptation(
            self._identity,
            base_tuning=self._authored_tuning,
            adaptation_payload=adaptation,
            guild_profile=guild_profile,
            guild_quests=guild_quests,
        )

    async def _sync_guild_state(self) -> None:
        while True:
            await asyncio.sleep(180.0)
            try:
                await self._hydrate_guild_state()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug("[%s] guild state sync failed: %s", self.name, exc)

    async def _sync_growth_proposals(self) -> None:
        # Post accepted self-delta proposals to the server's concordance gate, which
        # decides what becomes soul (>=3 proposals across >=2 calendar days). The agent
        # only posts proposals; the gate owns growth_text. The server dedups by pulse_id.
        posted: set[str] = set()
        memory_dir = self._resident_dir / "memory"
        while True:
            await asyncio.sleep(240.0)
            try:
                proposals = collect_new_growth_proposals(memory_dir, posted)
                if proposals:
                    await self._ww.update_identity_growth(self._session_id, growth_proposals=proposals)
                    posted.update(p["pulse_id"] for p in proposals)
                    logger.debug("[%s] posted %d growth proposal(s)", self.name, len(proposals))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug("[%s] growth proposal sync failed: %s", self.name, exc)
