"""Perception: translate the world into substrate perturbations (Major 49, Phase 3).

Perception is the bottom-up half of the loop. It reads the scene and emits
ambient-pressure perturbations onto the canonical ledger — exactly the events the
Major 46 cognitive nodes already reduce into activations. It makes no decisions;
it only reports what the world is doing so the substrate can feel it (and, via
salience, be surprised by it). It also returns a compact perception *brief* the
pulse reads as its current sense of the moment.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.runtime.ledger import append_runtime_event
from src.world.client import WorldWeaverClient

logger = logging.getLogger(__name__)

_AMBIENT_KINDS = {"crowding", "quiet", "event_pull", "bad_weather"}


def _clamp01(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


async def perceive(
    *,
    ww_client: WorldWeaverClient,
    session_id: str,
    memory_dir: Path,
    self_name: str = "",
) -> dict[str, Any]:
    """Observe the scene, emit ambient perturbations, and return a perception brief."""
    try:
        scene = await ww_client.get_scene(session_id)
    except Exception as exc:
        logger.debug("[%s:perceive] scene fetch failed: %s", self_name or session_id, exc)
        return {}

    self_lower = str(self_name or "").strip().lower()
    others = [p for p in scene.present if str(p.name or "").strip().lower() != self_lower]
    recent_events = list(scene.recent_events_here or [])

    signals: list[dict[str, Any]] = []
    if others:
        signals.append({"kind": "crowding", "label": "others nearby", "level": round(min(1.0, len(others) * 0.25), 3)})
    if recent_events:
        signals.append({"kind": "event_pull", "label": "recent activity here", "level": round(min(1.0, len(recent_events) * 0.3), 3)})
    for ambient in scene.ambient_presence or []:
        kind = str(getattr(ambient, "kind", "") or "").strip()
        if kind not in _AMBIENT_KINDS:
            kind = "event_pull"
        signals.append({"kind": kind, "label": str(getattr(ambient, "label", "") or kind).strip(), "level": round(_clamp01(getattr(ambient, "intensity", 0.0) or 0.0), 3)})

    if signals:
        append_runtime_event(
            memory_dir,
            event_type="ambient_pressure_observed",
            payload={"source": "ambient", "signals": signals, "context": {"location": str(scene.location or "").strip()}},
        )

    return {
        "location": str(scene.location or "").strip(),
        "present": [str(p.name or "").strip() for p in others if str(p.name or "").strip()],
        "recent_events": [{"who": str(e.who or "").strip(), "summary": str(e.summary or "").strip()} for e in recent_events[-5:]],
        "ambient": [{"kind": s["kind"], "label": s["label"], "level": s["level"]} for s in signals],
    }
