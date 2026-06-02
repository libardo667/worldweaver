"""The predictive integrator: one tick of the self-generating rhythm (Major 49).

This is the mechanism that closes the loop the architecture is built around:

    perturbation in  →  node transition  →  surprise vs afterimage
        →  leaky arousal  →  ignition  →  pulse  →  afterimage out
        →  (afterimage decays)  →  surprise re-accumulates  →  …

``tick`` runs that cycle once. It is pure mechanism — it never calls the LLM
itself. The single LLM pulse is injected as ``pulse_producer``; ignition hands
it the igniting traces and current self-state, and whatever typed ``Pulse`` it
returns is validated and routed back into the substrate. Phase 3 wires the real
LLM-backed producer (and the perception/effector loops) in; tests inject a
deterministic stub, which is enough to exercise the full closure.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.runtime.pulse import Pulse, route_pulse
from src.runtime.salience import (
    check_ignition,
    observe_surprise,
    record_ignition,
    stimulus_from_substrate,
)

# A pulse producer is handed the igniting traces, the current stimulus field, and
# the arousal level, and returns a typed Pulse (or a raw dict to validate), or
# None if no pulse could be produced. Phase 3 supplies the LLM-backed one.
PulseProducer = Callable[..., "Pulse | dict[str, Any] | None"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_now_iso(now: Any) -> str:
    if isinstance(now, datetime):
        dt = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    raw = str(now or "").strip()
    return raw or _utc_now_iso()


def tick(
    memory_dir: Path,
    *,
    pulse_producer: PulseProducer,
    stimulus: dict[str, dict[str, float]] | None = None,
    now: Any = None,
    valence_fn=None,
    gate_contradiction_check=None,
) -> dict[str, Any]:
    """Run one integration tick. Returns a summary of what happened."""
    now_iso = _as_now_iso(now)
    if stimulus is None:
        stimulus = stimulus_from_substrate(memory_dir)

    trace = observe_surprise(memory_dir, stimulus=stimulus, now=now_iso, valence_fn=valence_fn)
    decision = check_ignition(memory_dir, now=now_iso)

    result: dict[str, Any] = {
        "now": now_iso,
        "observed_trace": trace,
        "arousal_level": decision["level"],
        "ignited": bool(decision["fire"]),
        "ignition_reason": decision["reason"],
        "pulse_routed": None,
    }
    if not decision["fire"]:
        return result

    traces = decision["traces"]
    produced = pulse_producer(traces=traces, stimulus=stimulus, arousal=decision["level"])

    # Record the ignition regardless of producer success so arousal resets and
    # the refractory window applies (a failed producer must not spin the rhythm).
    record_ignition(
        memory_dir,
        now=now_iso,
        level=decision["level"],
        trace_ids=[str(item.get("trace_id") or "") for item in traces],
    )

    if produced is not None:
        pulse = produced if isinstance(produced, Pulse) else Pulse.from_dict(produced)
        result["pulse_routed"] = route_pulse(
            memory_dir,
            pulse,
            now=now_iso,
            gate_contradiction_check=gate_contradiction_check,
        )
    return result
