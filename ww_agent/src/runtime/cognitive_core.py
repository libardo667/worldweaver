"""The cognitive core: the resident's mind as substrate + pulse (Major 49, Phase 3).

This is what replaces the loop-era mind. On each tick the core:

  1. perceives the world  → emits substrate perturbations (perception.py),
  2. runs one integrator tick → surprise vs afterimage, leaky arousal, and on
     ignition the single LLM pulse (pulse_engine.py),
  3. routes the typed pulse back into the substrate and lets the effector carry
     the one act to the world (effectors.py).

The core holds no behavioral logic. It is the orchestration seam between the
mechanism (substrate, salience, integrator) and the world (perception, effector,
LLM pulse). The fast / slow / mail / ground / wander loops are demoted beneath
it to pure sensorimotor mechanism.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from src.identity.loader import ResidentIdentity
from src.inference.client import InferenceClient
from src.runtime import integrator
from src.runtime.anchors import extract_anchors, record_anchors
from src.runtime.drive import DriveVector, RemoteEmbedder
from src.runtime.effectors import WorldEffector
from src.runtime.ledger import load_runtime_events
from src.runtime.memory import MemoryRecall
from src.runtime.perception import perceive
from src.runtime.pulse_engine import LLMPulseProducer
from src.runtime.workshop import Workshop
from src.world.client import WorldWeaverClient

logger = logging.getLogger(__name__)


def _embedder_from_env() -> Any:
    """A drive-vector embedder from WW_EMBEDDING_* (any OpenAI-compatible
    /v1/embeddings endpoint, e.g. a local Ollama nomic-embed-text). Absent → the
    drive vector is disabled and affect stays neutral."""
    url = os.environ.get("WW_EMBEDDING_URL", "").strip()
    if not url:
        return None
    return RemoteEmbedder(
        base_url=url,
        api_key=os.environ.get("WW_EMBEDDING_KEY", "ollama").strip() or "ollama",
        model=os.environ.get("WW_EMBEDDING_MODEL", "nomic-embed-text").strip() or "nomic-embed-text",
    )


class CognitiveCore:
    """One resident mind: perceive → integrate → pulse → act, on a cadence."""

    def __init__(
        self,
        *,
        identity: ResidentIdentity,
        resident_dir: Path,
        ww_client: WorldWeaverClient,
        llm: InferenceClient,
        session_id: str,
        tick_seconds: float = 20.0,
        pulse_model: str | None = None,
        pulse_temperature: float = 0.7,
        embedder: Any = None,
        writes_to_workshop_only: bool = False,
    ) -> None:
        self._identity = identity
        self._memory_dir = resident_dir / "memory"
        self._ww = ww_client
        self._session_id = session_id
        self._tick_seconds = max(2.0, float(tick_seconds))
        # Drive vector (Phase 4): built lazily on the first tick from the embedder.
        self._embedder = embedder if embedder is not None else _embedder_from_env()
        self._drive_built = False

        self._producer = LLMPulseProducer(
            llm=llm,
            identity=identity,
            memory_dir=self._memory_dir,
            model=pulse_model,
            temperature=pulse_temperature,
        )
        # The resident's own, capability-scoped workshop (Major 50) — a real place
        # it authors its life into, sandboxed to this directory.
        self._workshop = Workshop(resident_dir / "workshop")
        self._effector = WorldEffector(
            ww_client=ww_client,
            session_id=session_id,
            identity=identity,
            memory_dir=self._memory_dir,
            workshop=self._workshop,
            all_writes_to_workshop=writes_to_workshop_only,
        )

    @property
    def name(self) -> str:
        return self._identity.name

    async def run(self) -> None:
        logger.info("[%s] cognitive core starting", self.name)
        while True:
            try:
                await self.tick_once()
            except asyncio.CancelledError:
                logger.info("[%s] cognitive core cancelled", self.name)
                raise
            except Exception as exc:
                logger.exception("[%s] cognitive tick error: %s", self.name, exc)
                await asyncio.sleep(10.0)
            await asyncio.sleep(self._tick_seconds)

    async def _ensure_drive_vector(self) -> None:
        if self._drive_built or self._embedder is None:
            return
        self._drive_built = True  # one attempt; never retry-storm on a bad endpoint
        # The same embedder powers relevance recall over kept memories — one
        # mechanism, two stores: "what stirs you" (soul) and "what you recall here"
        # (memory). With no embedder both stay off and memory falls back to recency.
        self._producer.memory_recall = MemoryRecall(self._embedder)
        try:
            self._producer.drive_vector = await DriveVector.build(
                embedder=self._embedder,
                constitution=self._identity.canonical_soul,
                growth=self._identity.growth_soul,
            )
            logger.info("[%s] drive vector built (%d constitution fragments)", self.name, len(self._producer.drive_vector.slices.get("constitution", [])))
        except Exception as exc:
            logger.warning("[%s] drive vector build failed — affect stays neutral: %s", self.name, exc)

    async def tick_once(self, *, now: Any = None, force_ignite: bool = False) -> dict[str, Any]:
        """Run one full perceive → integrate → (pulse → act) cycle."""
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        await self._ensure_drive_vector()
        brief = await perceive(
            ww_client=self._ww,
            session_id=self._session_id,
            memory_dir=self._memory_dir,
            identity=self._identity,
        )
        reactivity = 1.0
        if brief:
            brief["workshop"] = self._workshop.summary()
            # The recent sequence of its OWN makings, for self-output novelty: the
            # last journal entries + drawing titles, newest last.
            makings = [str(e.get("body") or "") for e in self._workshop.recent(6)]
            makings += [str(d.get("title") or "") for d in self._workshop.drawings(limit=6)]
            brief["recent_makings"] = [m for m in makings if m.strip()][-8:]
            # Concrete anchors (Major 51 granularity): the things THIS resident's
            # inner world is actually about, lifted from its own recent felt sense
            # plus the entities perceived. Surfaced to the pulse so it can predict
            # them by name; snapshotted as the realized field for offline scoring.
            # Scored-but-quiet: anchors never touch the arousal/ignition rhythm.
            events = load_runtime_events(self._memory_dir)
            prose = [str((e.get("payload") or {}).get("felt_sense") or "") for e in events if str(e.get("event_type") or "") == "felt_sense_logged"][-10:]
            structured = list(brief.get("present") or [])
            structured += [str(e.get("who") or "") for e in (brief.get("recent_events") or [])]
            structured += [str(h.get("speaker") or "") for h in (brief.get("heard") or [])]
            anchors = extract_anchors(prose, structured=structured, top_k=8)
            brief["anchors"] = anchors
            record_anchors(self._memory_dir, anchors, now=now, events=events)
            self._producer.latest_perception = brief
            self._effector.present = list(brief.get("present") or [])
            location = str(brief.get("location") or "").strip()
            if location:
                self._effector.location = location
            # Circadian wakefulness scales the rhythm: the town quiets after dark.
            reactivity = float(brief.get("wakefulness") if brief.get("wakefulness") is not None else 1.0)

        return await integrator.tick(
            self._memory_dir,
            pulse_producer=self._producer,
            effector=self._effector,
            now=now,
            reactivity=reactivity,
            force_ignite=force_ignite,
        )
