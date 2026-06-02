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
from pathlib import Path
from typing import Any

from src.identity.loader import ResidentIdentity
from src.inference.client import InferenceClient
from src.runtime import integrator
from src.runtime.effectors import WorldEffector
from src.runtime.perception import perceive
from src.runtime.pulse_engine import LLMPulseProducer
from src.world.client import WorldWeaverClient

logger = logging.getLogger(__name__)


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
    ) -> None:
        self._identity = identity
        self._memory_dir = resident_dir / "memory"
        self._ww = ww_client
        self._session_id = session_id
        self._tick_seconds = max(2.0, float(tick_seconds))

        self._producer = LLMPulseProducer(
            llm=llm,
            identity=identity,
            memory_dir=self._memory_dir,
            model=pulse_model,
            temperature=pulse_temperature,
        )
        self._effector = WorldEffector(
            ww_client=ww_client,
            session_id=session_id,
            identity=identity,
            memory_dir=self._memory_dir,
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

    async def tick_once(self, *, now: Any = None) -> dict[str, Any]:
        """Run one full perceive → integrate → (pulse → act) cycle."""
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        brief = await perceive(
            ww_client=self._ww,
            session_id=self._session_id,
            memory_dir=self._memory_dir,
            identity=self._identity,
        )
        if brief:
            self._producer.latest_perception = brief
            self._effector.present = list(brief.get("present") or [])
            location = str(brief.get("location") or "").strip()
            if location:
                self._effector.location = location

        return await integrator.tick(
            self._memory_dir,
            pulse_producer=self._producer,
            effector=self._effector,
            now=now,
        )
