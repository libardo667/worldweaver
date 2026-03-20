from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.identity.loader import IdentityLoader, ResidentIdentity
from src.inference.client import InferenceClient
from src.loops.fast import FastLoop
from src.loops.ground import GroundLoop
from src.loops.mail import MailLoop
from src.loops.slow import SlowLoop
from src.loops.wander import WanderLoop
from src.memory.provisional import ProvisionalScratchpad
from src.memory.research_queue import ResearchQueue
from src.memory.retrieval import LongTermMemory
from src.memory.reveries import ReverieDeck
from src.memory.voice import VoiceDeck
from src.runtime.mirror import ResidentRuntimeMirror
from src.runtime.guild import apply_runtime_adaptation, snapshot_authored_tuning
from src.memory.working import WorkingMemory
from src.runtime.naming import slugify_resident_name
from src.runtime.rest import RestState
from src.runtime.signals import IntentQueue, StimulusPacketQueue
from src.world.client import WorldWeaverClient

logger = logging.getLogger(__name__)


class Resident:
    """
    A single running agent: one character, three loops, shared memory.

    Residents are autonomous — they boot themselves, manage their own
    session with the world server, and run until cancelled.

    The resident doesn't know about other residents. It knows who it is
    (SOUL.md), what it's been doing (working memory), and what it's been
    noticing (provisional scratchpad). Everything else comes from the world.
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
        self._intent_queue: IntentQueue | None = None

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
        Run fast, slow, and mail loops concurrently.
        Returns when all loops stop (or any raises an unhandled exception).
        """
        if not self._identity or not self._session_id:
            raise RuntimeError(f"Resident {self.name} not started — call start() first")

        identity = self._identity
        session_id = self._session_id

        # Shared memory — all three loops read/write these
        working = WorkingMemory(
            self._resident_dir / "memory" / "working.json",
            max_items=identity.tuning.slow_max_context_events,
        )
        provisional = ProvisionalScratchpad(
            self._resident_dir / "memory" / "impressions"
        )
        long_term = LongTermMemory(self._resident_dir / "memory" / "long_term.json")
        reveries = ReverieDeck(self._resident_dir / "memory" / "reveries.json")
        voice = VoiceDeck(self._resident_dir / "memory" / "voice.json")
        voice.seed(identity.voice_seed)
        research_queue = ResearchQueue(self._resident_dir / "memory" / "research_queue.json")
        packet_queue = StimulusPacketQueue(self._resident_dir / "memory" / "stimulus_packets.json")
        intent_queue = IntentQueue(self._resident_dir / "memory" / "intent_queue.json")
        packet_queue.ensure_file()
        intent_queue.ensure_file()
        rest = RestState(self._ww, session_id, identity.tuning)
        await rest.sync(force=True)
        self._packet_queue = packet_queue
        self._intent_queue = intent_queue

        fast = FastLoop(
            identity=identity,
            resident_dir=self._resident_dir,
            ww_client=self._ww,
            llm=self._llm,
            session_id=session_id,
            working_memory=working,
            provisional=provisional,
            reveries=reveries,
            voice=voice,
            rest_state=rest,
            research_queue=research_queue,
            packet_queue=packet_queue,
            intent_queue=intent_queue,
        )

        slow = SlowLoop(
            identity=identity,
            resident_dir=self._resident_dir,
            ww_client=self._ww,
            llm=self._llm,
            session_id=session_id,
            working_memory=working,
            provisional=provisional,
            long_term=long_term,
            reveries=reveries,
            voice=voice,
            research_queue=research_queue,
            rest_state=rest,
            packet_queue=packet_queue,
            intent_queue=intent_queue,
        )

        loops: list[asyncio.Coroutine] = [fast.run(), slow.run()]

        if identity.tuning.wander_enabled:
            wander = WanderLoop(
                identity=identity,
                resident_dir=self._resident_dir,
                ww_client=self._ww,
                session_id=session_id,
                working_memory=working,
                rest_state=rest,
                packet_queue=packet_queue,
            )
            loops.append(wander.run())

        if identity.tuning.ground_enabled:
            ground = GroundLoop(
                identity=identity,
                resident_dir=self._resident_dir,
                ww_client=self._ww,
                llm=self._llm,
                session_id=session_id,
                working_memory=working,
                research_queue=research_queue,
                rest_state=rest,
                packet_queue=packet_queue,
            )
            loops.append(ground.run())

        if identity.tuning.mail_enabled:
            mail = MailLoop(
                identity=identity,
                resident_dir=self._resident_dir,
                ww_client=self._ww,
                llm=self._llm,
                session_id=session_id,
                packet_queue=packet_queue,
            )
            loops.append(mail.run())

        runtime_mirror = ResidentRuntimeMirror(
            resident_dir=self._resident_dir,
            ww_client=self._ww,
            session_id=session_id,
        )
        loops.append(runtime_mirror.run())
        loops.append(self._sync_guild_state())

        logger.info("[%s] all loops starting", self.name)

        try:
            await asyncio.gather(*loops)
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
        player_role = (
            f"{identity.name} — {identity.vibe}" if identity.vibe else identity.name
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
        try:
            guild_profile = await self._ww.get_guild_profile(self._session_id)
        except Exception as exc:
            logger.debug("[%s] guild profile hydrate failed: %s", self.name, exc)
        try:
            adaptation = await self._ww.get_runtime_adaptation(self._session_id)
        except Exception as exc:
            logger.debug("[%s] runtime adaptation hydrate failed: %s", self.name, exc)
        apply_runtime_adaptation(
            self._identity,
            base_tuning=self._authored_tuning,
            adaptation_payload=adaptation,
            guild_profile=guild_profile,
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
