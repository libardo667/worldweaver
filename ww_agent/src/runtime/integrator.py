# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

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
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.runtime.pulse import Pulse, route_pulse
from src.runtime.salience import (
    FERVOR_AROUSAL_FLOOR,
    check_fervor,
    check_ignition,
    check_settling,
    check_venture,
    observe_surprise,
    record_idle,
    record_ignition,
    stimulus_from_substrate,
    update_baseline,
    warn_if_strangled,
)

logger = logging.getLogger(__name__)

# Action-tendency (the substrate as motor cortex). When set, a keyed-up resident with
# nowhere put into words but somewhere to GO is steered toward the world (a venture pulse)
# instead of always re-deciding {speak,move,do,write} from a verbal-biased prior. Default
# off: unset leaves the idle gear exactly as it was (these files are shared with the-stable).
_ACTION_TENDENCY_ENABLED = (os.environ.get("WW_ACTION_TENDENCY") or "0") != "0"

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


async def _safe_produce(pulse_producer: "PulseProducer", **kwargs: Any) -> "Pulse | dict[str, Any] | None":
    """Call the pulse producer, never letting it RAISE — a raise degrades to 'no pulse
    this tick' (None), so the caller's record_ignition / record_idle still runs.

    Why this matters: the producer is an injected LLM call, and an *uncaught* failure
    (a transport error, a timeout — anything the producer's own except doesn't catch)
    would otherwise propagate out of ``tick`` BEFORE the ignition/idle is recorded. That
    skips the arousal reset, so the resident never resets, arousal climbs without bound,
    and it perceives forever while NEVER pulsing — silent catatonia that looks, from the
    ledger, like a merely quiet mind. A failed producer must not spin the rhythm; this is
    where that guarantee is actually enforced (the comment at record_ignition assumed it)."""
    try:
        return await _maybe_await(pulse_producer(**kwargs))
    except Exception as exc:
        logger.warning("pulse producer raised (%s) — treating as no pulse this tick", exc)
        return None


async def _reach_then_act(
    pulse: Pulse,
    *,
    pulse_producer: PulseProducer,
    effector: Effector | None,
    information_access: Callable[..., Any] | None,
    now_iso: str,
) -> tuple[Pulse, dict[str, Any] | None, list[dict[str, Any]], dict[str, Any] | None]:
    """Resolve private information reaches, then carry at most one outward act.

    Reaches continue inside this ignition and never pass through the world-action
    effector. The loop is bounded; a continuation may reach again, produce one
    outward act, or end with both fields null.
    """
    continue_fn = getattr(pulse_producer, "continue_reach", None)
    cap = int(getattr(pulse_producer, "REACH_LOOP_CAP", 6))
    current = pulse
    accesses: list[dict[str, Any]] = []
    steps = 0

    while current.reach is not None and steps < cap:
        if information_access is None or continue_fn is None:
            accesses.append({"accessed": False, "source": current.reach.source, "reason": "reach_boundary_unavailable"})
            return current, None, accesses, None
        steps += 1
        access_result = await _maybe_await(information_access(current.reach, now=now_iso))
        normalized = dict(access_result or {}) if isinstance(access_result, dict) else {"detail": str(access_result or "")}
        accesses.append(normalized)
        logger.debug("reach-loop step %d/%d: %s:%s", steps, cap, current.reach.kind, current.reach.source)
        next_pulse = await _maybe_await(
            continue_fn(
                request=current.reach.to_dict(),
                result=normalized,
                prior_felt=current.felt_sense or "",
            )
        )
        if next_pulse is None:
            return current, None, accesses, None
        current = next_pulse if isinstance(next_pulse, Pulse) else Pulse.from_dict(next_pulse)

    if current.reach is not None:
        accesses.append({"accessed": False, "source": current.reach.source, "reason": "reach_cap"})
        return current, None, accesses, None
    if current.act is not None and effector is not None:
        context_fn = getattr(effector, "relational_context", None)
        act_context = dict(context_fn() or {}) if callable(context_fn) else None
        act_result = await _maybe_await(effector(current.act, now=now_iso))
        return current, act_result, accesses, act_context
    return current, None, accesses, None


async def tick(
    memory_dir: Path,
    *,
    pulse_producer: PulseProducer,
    effector: Effector | None = None,
    information_access: Callable[..., Any] | None = None,
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
        "venture": False,
        "pulse_routed": None,
        "act_executed": None,
        "information_accessed": [],
    }
    if not should_ignite:
        # No surprise to react to — but the resident's own state may still invite a
        # self-directed pulse: a long enough CALM lull (settling → rest or potter),
        # or a sustained HIGH-arousal buzz with nowhere to aim it (fervor → make,
        # burn it off). The two are mutually exclusive by arousal band.
        settling = check_settling(memory_dir, now=now_iso, reactivity=reactivity)
        fervor = check_fervor(memory_dir, now=now_iso, reactivity=reactivity)
        tendency: dict[str, Any] | None = None
        if settling["settle"]:
            mode, igniting = "settling", []
        elif fervor["fire"]:
            mode, igniting = "fervor", decision["traces"]
            # The substrate as motor cortex: if this keyed-up charge has gone all words and
            # there is somewhere to go, steer it OUT (a venture) rather than onto the page.
            if _ACTION_TENDENCY_ENABLED:
                perception = getattr(pulse_producer, "latest_perception", {}) or {}
                has_destination = bool(perception.get("reachable") or perception.get("present"))
                venture = check_venture(memory_dir, now=now_iso, reactivity=reactivity, has_destination=has_destination)
                if venture["venture"]:
                    mode, tendency = "venture", venture
                    result["venture"] = True
        else:
            # No discharge this tick. If arousal is nonetheless elevated, read the
            # recent waveform: a ramp with no falling edge is the strangled-silence
            # shape (Minor 55) and must not hide as a merely quiet mind.
            if decision["level"] >= FERVOR_AROUSAL_FLOOR:
                warn_if_strangled(memory_dir, now=now_iso)
            return result
        result["settled"] = settling["settle"]
        result["fervor"] = bool(fervor["fire"]) and not settling["settle"]
        # Only forward a tendency when one fired — so producers that don't know about it
        # (and the entire flag-off path) are called exactly as before.
        extra = {"tendency": tendency} if tendency is not None else {}
        produced = await _safe_produce(pulse_producer, traces=igniting, stimulus=stimulus, arousal=decision["level"], mode=mode, **extra)
        # Taking the moment — restful or restless — spends it.
        record_idle(memory_dir, now=now_iso)
        if produced is not None:
            pulse = produced if isinstance(produced, Pulse) else Pulse.from_dict(produced)
            act_context = None
            if effector is not None or information_access is not None:
                pulse, act_result, access_results, act_context = await _reach_then_act(
                    pulse,
                    pulse_producer=pulse_producer,
                    effector=effector,
                    information_access=information_access,
                    now_iso=now_iso,
                )
                result["act_executed"] = act_result
                result["information_accessed"] = access_results
            result["pulse_routed"] = route_pulse(memory_dir, pulse, now=now_iso, gate_contradiction_check=gate_contradiction_check, act_context=act_context)
        return result

    traces = decision["traces"]
    produced = await _safe_produce(pulse_producer, traces=traces, stimulus=stimulus, arousal=decision["level"], mode="react")

    # Record the ignition regardless of producer success so arousal resets and
    # the refractory window applies (a failed producer must not spin the rhythm —
    # _safe_produce guarantees the producer never raises past this point).
    record_ignition(
        memory_dir,
        now=now_iso,
        level=decision["level"],
        trace_ids=[str(item.get("trace_id") or "") for item in traces],
    )

    if produced is not None:
        pulse = produced if isinstance(produced, Pulse) else Pulse.from_dict(produced)
        act_context = None
        if effector is not None or information_access is not None:
            pulse, act_result, access_results, act_context = await _reach_then_act(
                pulse,
                pulse_producer=pulse_producer,
                effector=effector,
                information_access=information_access,
                now_iso=now_iso,
            )
            result["act_executed"] = act_result
            result["information_accessed"] = access_results
        result["pulse_routed"] = route_pulse(
            memory_dir,
            pulse,
            now=now_iso,
            gate_contradiction_check=gate_contradiction_check,
            act_context=act_context,
        )
    return result
