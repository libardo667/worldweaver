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
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.runtime.pulse import Pulse, route_pulse
from src.runtime.salience import (
    check_fervor,
    check_ignition,
    check_settling,
    observe_surprise,
    record_idle,
    record_ignition,
    stimulus_from_substrate,
    update_baseline,
)

logger = logging.getLogger(__name__)

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


async def _tool_loop(pulse: Pulse, *, pulse_producer: PulseProducer, effector: Effector, now_iso: str) -> tuple[Pulse, dict[str, Any] | None]:
    """Major 59: when a pulse emits a 'do' act (tool call), execute it and let the
    model continue within the same ignition — a tight tool-use loop that exits when
    the model emits a non-'do' act or hits the cap. Returns (final_pulse, final_act_result)."""
    continue_fn = getattr(pulse_producer, "continue_tool", None)
    if continue_fn is None or pulse.act is None or pulse.act.kind != "do":
        if pulse.act is not None:
            act_result = await _maybe_await(effector(pulse.act, now=now_iso))
            return pulse, act_result
        return pulse, None

    cap = int(getattr(pulse_producer, "TOOL_LOOP_CAP", 6))
    steps = 0
    current = pulse
    while current.act is not None and current.act.kind == "do" and steps < cap:
        steps += 1
        act_result = await _maybe_await(effector(current.act, now=now_iso))
        detail = act_result.get("detail") or act_result.get("narrative") or "" if isinstance(act_result, dict) else ""
        logger.debug("tool-loop step %d/%d: %s", steps, cap, current.act.body[:80])
        next_pulse = await _maybe_await(continue_fn(action=current.act.body, result=detail, prior_felt=current.felt_sense or ""))
        if next_pulse is None:
            return current, act_result
        current = next_pulse if isinstance(next_pulse, Pulse) else Pulse.from_dict(next_pulse)

    if current.act is not None and current.act.kind != "do":
        final_result = await _maybe_await(effector(current.act, now=now_iso))
        return current, final_result
    if current.act is not None and current.act.kind == "do" and steps >= cap:
        final_result = await _maybe_await(effector(current.act, now=now_iso))
        return current, final_result
    return current, None


async def tick(
    memory_dir: Path,
    *,
    pulse_producer: PulseProducer,
    effector: Effector | None = None,
    stimulus: dict[str, dict[str, float]] | None = None,
    now: Any = None,
    reactivity: float = 1.0,
    force_ignite: bool = False,
    valence_fn=None,
    gate_contradiction_check=None,
    anchor_stimulus: dict[str, dict[str, float]] | None = None,
    gate_anchors: bool = False,
    muted_senses: tuple[str, ...] = (),
    refractory_seconds: float | None = None,
) -> dict[str, Any]:
    """Run one integration tick. Returns a summary of what happened.

    ``reactivity`` is circadian wakefulness (1.0 by day): it scales the arousal
    both ignition and settling see, so the same rhythm runs hot by day and quiet
    after dark without any branch in the mechanism.

    ``force_ignite`` fires the pulse this tick regardless of arousal — the
    "addressed → attend" path. The surprise/ignition mechanism reacts to node-level
    *change*, which (rightly) won't lift for every line said to it; but when
    something has directly called on the resident (a familiar's keeper speaking,
    a name called) the caller can guarantee it turns and attends. It does not
    script the response — the pulse still freely decides whether and how to act.
    """
    now_iso = _as_now_iso(now)
    if stimulus is None:
        stimulus = stimulus_from_substrate(memory_dir)
    # Anchor-gating (Major 51 Phase 4b.6): when a resident has it on, the realized,
    # drive-weighted anchor field is merged into the stimulus so its anchor
    # predictions are surprised against actual presence — concrete things it cares
    # about (the keeper) can now drive when it wakes. Off by default (scored-quiet).
    if anchor_stimulus:
        stimulus = {**stimulus, **{k: v for k, v in anchor_stimulus.items() if v}}

    trace = observe_surprise(memory_dir, stimulus=stimulus, now=now_iso, valence_fn=valence_fn, include_anchor_scope=gate_anchors, muted_senses=muted_senses)
    # Habituation: nudge the slow self-model toward what was just felt. Measured
    # *after* surprise, so this tick is surprised against the prior baseline and
    # the update only shapes what comes next (rate-limited internally).
    update_baseline(memory_dir, stimulus=stimulus, now=now_iso)
    decision = check_ignition(memory_dir, now=now_iso, reactivity=reactivity, refractory_seconds=refractory_seconds)

    should_ignite = bool(decision["fire"]) or bool(force_ignite)
    result: dict[str, Any] = {
        "now": now_iso,
        "observed_trace": trace,
        "arousal_level": decision["level"],
        "ignited": should_ignite,
        "ignition_reason": "crossed_threshold" if decision["fire"] else ("addressed" if force_ignite else decision["reason"]),
        "settled": False,
        "fervor": False,
        "pulse_routed": None,
        "act_executed": None,
    }
    if not should_ignite:
        # No surprise to react to — but the resident's own state may still invite a
        # self-directed pulse: a long enough CALM lull (settling → rest or potter),
        # or a sustained HIGH-arousal buzz with nowhere to aim it (fervor → make,
        # burn it off). The two are mutually exclusive by arousal band.
        settling = check_settling(memory_dir, now=now_iso, reactivity=reactivity)
        fervor = check_fervor(memory_dir, now=now_iso, reactivity=reactivity)
        if settling["settle"]:
            mode, igniting = "settling", []
        elif fervor["fire"]:
            mode, igniting = "fervor", decision["traces"]
        else:
            return result
        result["settled"] = settling["settle"]
        result["fervor"] = bool(fervor["fire"]) and not settling["settle"]
        produced = await _maybe_await(pulse_producer(traces=igniting, stimulus=stimulus, arousal=decision["level"], mode=mode))
        # Taking the moment — restful or restless — spends it.
        record_idle(memory_dir, now=now_iso)
        if produced is not None:
            pulse = produced if isinstance(produced, Pulse) else Pulse.from_dict(produced)
            if effector is not None:
                pulse, act_result = await _tool_loop(pulse, pulse_producer=pulse_producer, effector=effector, now_iso=now_iso)
                result["act_executed"] = act_result
            result["pulse_routed"] = route_pulse(memory_dir, pulse, now=now_iso, gate_contradiction_check=gate_contradiction_check)
        return result

    traces = decision["traces"]
    produced = await _maybe_await(pulse_producer(traces=traces, stimulus=stimulus, arousal=decision["level"], mode="react"))

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
        if effector is not None:
            pulse, act_result = await _tool_loop(pulse, pulse_producer=pulse_producer, effector=effector, now_iso=now_iso)
            result["act_executed"] = act_result
        result["pulse_routed"] = route_pulse(
            memory_dir,
            pulse,
            now=now_iso,
            gate_contradiction_check=gate_contradiction_check,
        )
    return result
