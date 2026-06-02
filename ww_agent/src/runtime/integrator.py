"""The predictive integrator: one tick of the self-generating rhythm (Major 49).

This is the mechanism that closes the loop the architecture is built around:

    perturbation in  →  node transition  →  surprise vs afterimage
        →  leaky arousal  →  ignition  →  pulse  →  afterimage out  →  act
        →  (afterimage decays)  →  surprise re-accumulates  →  …

``tick`` runs that cycle once. It is pure mechanism — it never calls the LLM or
the world itself. The single LLM pulse is injected as ``pulse_producer`` and the
outward act is carried by an injected ``effector``; ignition hands the producer
the igniting traces and current self-state, routes whatever typed ``Pulse`` it
returns back into the substrate, then lets the effector carry the one ``act`` to
the world. Both injected callables may be sync or async, so the same tick drives
the deterministic test stubs and the real LLM/world clients (see
cognitive_core.py). Phase 3 wires the real producer and effector in.
"""

from __future__ import annotations

import inspect
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
# None if no pulse could be produced. May be sync or async.
PulseProducer = Callable[..., "Pulse | dict[str, Any] | None"]
# An effector carries one routed Act to the world. May be sync or async.
Effector = Callable[..., Any]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_now_iso(now: Any) -> str:
    if isinstance(now, datetime):
        dt = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    raw = str(now or "").strip()
    return raw or _utc_now_iso()


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def tick(
    memory_dir: Path,
    *,
    pulse_producer: PulseProducer,
    effector: Effector | None = None,
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
        "act_executed": None,
    }
    if not decision["fire"]:
        return result

    traces = decision["traces"]
    produced = await _maybe_await(pulse_producer(traces=traces, stimulus=stimulus, arousal=decision["level"]))

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
        if effector is not None and pulse.act is not None:
            result["act_executed"] = await _maybe_await(effector(pulse.act, now=now_iso))
    return result
