"""The typed pulse contract and its back-prop routing layer (Major 49, Phase 1).

One ignition produces one ``Pulse``: the single LLM call returns JSON, which is
validated into the typed contract here and then *mechanically* routed. The
routing layer is pure mechanism — it fans each field to its region of the
substrate and never interprets prose as control:

- ``felt_sense`` is a logged readout only; it goes to the chronicle and is never
  read back as control.
- ``act`` is the only path to the world.
- ``expectations`` become the afterimage — a decaying top-down prediction stored
  as ledger events and read back via ``substrate.predict`` (see substrate.py).
- ``drive_nudges`` are transient reverie pulls, stored the same decaying way.
- ``self_delta`` must pass the Major 42 constitution gate before it can stage any
  identity change; the gate is enforced in code, never asked of the prompt.
- ``trace_verdicts`` record consolidate/release/watch judgements on traces.

Everything is routed through the one canonical ledger (``append_runtime_event``)
so the substrate stays a derived projection with full provenance.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from src.runtime.ledger import append_runtime_event
from src.runtime.memory import record_kept

# Calibration dials (Major 49 risks: afterimage half-life is a primary dial).
DEFAULT_AFTERIMAGE_HALF_LIFE_SECONDS = 600.0
DEFAULT_DRIVE_NUDGE_HALF_LIFE_SECONDS = 300.0

_ACT_KINDS = {"speak", "move", "do", "write"}
_TRACE_VERDICTS = {"consolidate", "release", "watch"}


class PulseValidationError(ValueError):
    """Raised when an LLM-emitted pulse payload does not satisfy the contract."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp01(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def _coerce_features(raw: Any) -> dict[str, float]:
    """Coerce a ``{tag: intensity}`` map, clamping intensities to ``0..1`` and
    dropping non-numeric or unnamed entries."""
    if not isinstance(raw, dict):
        return {}
    features: dict[str, float] = {}
    for tag, intensity in raw.items():
        name = str(tag or "").strip()
        value = _coerce_float(intensity)
        if not name or value is None:
            continue
        clamped = round(_clamp01(value), 4)
        if clamped <= 0.0:
            # A non-positive intensity carries no prediction; drop it as noise.
            continue
        features[name] = clamped
    return features


def _coerce_half_life(raw: Any, default: float) -> float:
    value = _coerce_float(raw)
    if value is None or value <= 0.0:
        return float(default)
    return float(value)


@dataclass(frozen=True)
class Act:
    """One outward move — the only field that reaches the world."""

    kind: str  # speak | move | do | write
    body: str
    target: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Act":
        if not isinstance(raw, dict):
            raise PulseValidationError("act must be an object")
        kind = str(raw.get("kind") or "").strip().lower()
        if kind not in _ACT_KINDS:
            raise PulseValidationError(f"act.kind must be one of {sorted(_ACT_KINDS)}, got {kind!r}")
        body = str(raw.get("body") or "").strip()
        if not body:
            raise PulseValidationError("act.body must be a non-empty string")
        target_raw = raw.get("target")
        target = str(target_raw).strip() if target_raw not in (None, "") else None
        return cls(kind=kind, body=body, target=target)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "body": self.body, "target": self.target}


@dataclass(frozen=True)
class Expectation:
    """A predicted feature field — one component of the afterimage."""

    features: dict[str, float]
    scope: str = "here"  # here | self | <character>
    confidence: float = 0.5
    half_life: float = DEFAULT_AFTERIMAGE_HALF_LIFE_SECONDS

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Expectation":
        if not isinstance(raw, dict):
            raise PulseValidationError("expectation must be an object")
        features = _coerce_features(raw.get("features"))
        if not features:
            raise PulseValidationError("expectation.features must contain at least one tag:intensity")
        scope = str(raw.get("scope") or "here").strip() or "here"
        confidence = _coerce_float(raw.get("confidence"))
        confidence = _clamp01(confidence) if confidence is not None else 0.5
        half_life = _coerce_half_life(raw.get("half_life"), DEFAULT_AFTERIMAGE_HALF_LIFE_SECONDS)
        return cls(features=features, scope=scope, confidence=confidence, half_life=half_life)

    def to_dict(self) -> dict[str, Any]:
        return {
            "features": dict(self.features),
            "scope": self.scope,
            "confidence": round(self.confidence, 4),
            "half_life": self.half_life,
        }


@dataclass(frozen=True)
class DriveNudge:
    """A transient pull on the drive vector (reverie-shaped, decaying)."""

    features: dict[str, float]
    half_life: float = DEFAULT_DRIVE_NUDGE_HALF_LIFE_SECONDS

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "DriveNudge":
        if not isinstance(raw, dict):
            raise PulseValidationError("drive_nudge must be an object")
        features = _coerce_features(raw.get("features"))
        if not features:
            raise PulseValidationError("drive_nudge.features must contain at least one tag:intensity")
        half_life = _coerce_half_life(raw.get("half_life"), DEFAULT_DRIVE_NUDGE_HALF_LIFE_SECONDS)
        return cls(features=features, half_life=half_life)

    def to_dict(self) -> dict[str, Any]:
        return {"features": dict(self.features), "half_life": self.half_life}


@dataclass(frozen=True)
class SelfDelta:
    """Slow-plasticity proposals; only staged after the constitution gate."""

    soul_edit: str | None = None
    new_reverie: str | None = None
    goal_update: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SelfDelta":
        if raw in (None, {}):
            return cls()
        if not isinstance(raw, dict):
            raise PulseValidationError("self_delta must be an object")

        def _opt(key: str) -> str | None:
            value = raw.get(key)
            text = str(value).strip() if value not in (None, "") else ""
            return text or None

        return cls(
            soul_edit=_opt("soul_edit"),
            new_reverie=_opt("new_reverie"),
            goal_update=_opt("goal_update"),
        )

    def edits(self) -> list[tuple[str, str]]:
        """Return ``(kind, body)`` pairs for each populated sub-edit."""
        pairs: list[tuple[str, str]] = []
        for kind in ("soul_edit", "new_reverie", "goal_update"):
            body = getattr(self, kind)
            if body:
                pairs.append((kind, body))
        return pairs

    def is_empty(self) -> bool:
        return not self.edits()

    def to_dict(self) -> dict[str, Any]:
        return {"soul_edit": self.soul_edit, "new_reverie": self.new_reverie, "goal_update": self.goal_update}


@dataclass(frozen=True)
class TraceVerdict:
    """A judgement on an igniting trace: consolidate, release, or watch."""

    trace_id: str
    verdict: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "TraceVerdict":
        if not isinstance(raw, dict):
            raise PulseValidationError("trace_verdict must be an object")
        trace_id = str(raw.get("trace_id") or "").strip()
        if not trace_id:
            raise PulseValidationError("trace_verdict.trace_id must be a non-empty string")
        verdict = str(raw.get("verdict") or "").strip().lower()
        if verdict not in _TRACE_VERDICTS:
            raise PulseValidationError(f"trace_verdict.verdict must be one of {sorted(_TRACE_VERDICTS)}, got {verdict!r}")
        return cls(trace_id=trace_id, verdict=verdict)

    def to_dict(self) -> dict[str, Any]:
        return {"trace_id": self.trace_id, "verdict": self.verdict}


@dataclass(frozen=True)
class Keepsake:
    """A short thing the resident chooses to remember past this moment — a fact
    about its keeper, a decision it's made, something learned. The seed of memory
    across days: kept to the ledger, surfaced back into later pulses."""

    note: str

    @classmethod
    def from_any(cls, raw: Any) -> "Keepsake":
        if isinstance(raw, dict):
            note = str(raw.get("note") or raw.get("text") or "").strip()
        else:
            note = str(raw or "").strip()
        if not note:
            raise PulseValidationError("keepsake note must be a non-empty string")
        return cls(note=note[:280])

    def to_dict(self) -> dict[str, Any]:
        return {"note": self.note}


@dataclass(frozen=True)
class Pulse:
    """The single typed output of one ignition."""

    felt_sense: str = ""
    act: Act | None = None
    expectations: list[Expectation] = field(default_factory=list)
    drive_nudges: list[DriveNudge] = field(default_factory=list)
    self_delta: SelfDelta = field(default_factory=SelfDelta)
    trace_verdicts: list[TraceVerdict] = field(default_factory=list)
    keepsakes: list[Keepsake] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Pulse":
        if not isinstance(raw, dict):
            raise PulseValidationError("pulse must be an object")

        def _list(key: str) -> list[Any]:
            value = raw.get(key)
            if value in (None, ""):
                return []
            if not isinstance(value, list):
                raise PulseValidationError(f"{key} must be a list")
            return value

        def _soft(key: str, parser) -> list[Any]:
            # Soft internal fields degrade gracefully: a single malformed item
            # (e.g. an empty drive_nudge) is dropped rather than failing the
            # whole pulse. Only ``act`` — the path to the world — is strict, so a
            # good action is never lost to a cosmetic slip in the inner fields.
            parsed: list[Any] = []
            for item in _list(key):
                try:
                    parsed.append(parser(item))
                except PulseValidationError:
                    continue
            return parsed

        act_raw = raw.get("act")
        act = Act.from_dict(act_raw) if isinstance(act_raw, dict) and act_raw else None

        # ``keep`` may be a single string or a list of strings/objects.
        keep_raw = raw.get("keep")
        if isinstance(keep_raw, (str, dict)):
            keep_raw = [keep_raw]
        keepsakes: list[Keepsake] = []
        if isinstance(keep_raw, list):
            for item in keep_raw:
                try:
                    keepsakes.append(Keepsake.from_any(item))
                except PulseValidationError:
                    continue

        return cls(
            felt_sense=str(raw.get("felt_sense") or "").strip(),
            act=act,
            expectations=_soft("expectations", Expectation.from_dict),
            drive_nudges=_soft("drive_nudges", DriveNudge.from_dict),
            self_delta=SelfDelta.from_dict(raw.get("self_delta")),
            trace_verdicts=_soft("trace_verdicts", TraceVerdict.from_dict),
            keepsakes=keepsakes,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "felt_sense": self.felt_sense,
            "act": self.act.to_dict() if self.act is not None else None,
            "expectations": [item.to_dict() for item in self.expectations],
            "drive_nudges": [item.to_dict() for item in self.drive_nudges],
            "self_delta": self.self_delta.to_dict(),
            "trace_verdicts": [item.to_dict() for item in self.trace_verdicts],
            "keepsakes": [item.to_dict() for item in self.keepsakes],
        }


# A contradiction check returns one of {None, "clamp", "drop"} for a proposed
# self-edit. Phase 4 wires in the real check (drive-vector cosine alignment
# against the immutable constitution); until then the default is structural-only.
ContradictionCheck = Callable[[str, str], str | None]


@dataclass(frozen=True)
class GateDecision:
    """The constitution gate's ruling on one self-edit."""

    kind: str  # soul_edit | new_reverie | goal_update
    body: str
    verdict: str  # accepted | clamped | dropped
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "body": self.body, "verdict": self.verdict, "reason": self.reason}


def constitution_gate(
    self_delta: SelfDelta,
    *,
    contradiction_check: ContradictionCheck | None = None,
) -> list[GateDecision]:
    """Rule on each self-edit before it can stage any identity change.

    The hard, always-on Major 42 invariant is structural: this gate never writes
    canonical identity (``SOUL.canonical.md``). Every accepted edit is staged
    only as a *candidate* for the matured-growth pipeline; single pulses can
    never rewrite the constitution. The semantic clamp — dropping anything that
    contradicts an immutable direction — arrives in Phase 4 via the drive vector;
    ``contradiction_check`` is the seam where it plugs in.
    """
    decisions: list[GateDecision] = []
    for kind, body in self_delta.edits():
        verdict, reason = "accepted", "staged_as_candidate"
        if contradiction_check is not None:
            ruling = contradiction_check(kind, body)
            if ruling == "drop":
                verdict, reason = "dropped", "contradicts_immutable_direction"
            elif ruling == "clamp":
                verdict, reason = "clamped", "tempered_against_immutable_direction"
        decisions.append(GateDecision(kind=kind, body=body, verdict=verdict, reason=reason))
    return decisions


def route_pulse(
    memory_dir,
    pulse: Pulse,
    *,
    now: str | None = None,
    gate_contradiction_check: ContradictionCheck | None = None,
) -> dict[str, Any]:
    """Fan a validated pulse to its regions of the substrate (pure mechanism).

    Returns a routing summary for provenance/inspection. All effects land as
    ledger events so the substrate remains a derived projection.
    """
    cast_ts = str(now).strip() if now else _utc_now_iso()
    pulse_id = f"pls-{uuid.uuid4().hex[:12]}"

    # Full provenance: the exact validated pulse that fired.
    append_runtime_event(
        memory_dir,
        event_type="pulse_emitted",
        payload={"pulse_id": pulse_id, "cast_ts": cast_ts, "pulse": pulse.to_dict()},
    )

    # felt_sense — readout only, to the chronicle; never routed as control.
    append_runtime_event(
        memory_dir,
        event_type="felt_sense_logged",
        payload={"pulse_id": pulse_id, "felt_sense": pulse.felt_sense},
    )

    # act — the one and only path to the world.
    act_routed = False
    if pulse.act is not None:
        append_runtime_event(
            memory_dir,
            event_type="pulse_act_emitted",
            payload={"pulse_id": pulse_id, **pulse.act.to_dict()},
        )
        act_routed = True

    # expectations — the afterimage; decaying top-down prediction.
    for expectation in pulse.expectations:
        append_runtime_event(
            memory_dir,
            event_type="afterimage_cast",
            payload={"pulse_id": pulse_id, "cast_ts": cast_ts, **expectation.to_dict()},
        )

    # drive_nudges — transient reverie pulls, decaying the same way.
    for nudge in pulse.drive_nudges:
        append_runtime_event(
            memory_dir,
            event_type="drive_nudge_cast",
            payload={"pulse_id": pulse_id, "cast_ts": cast_ts, **nudge.to_dict()},
        )

    # self_delta — through the constitution gate; staged as candidate only.
    gate_decisions = constitution_gate(pulse.self_delta, contradiction_check=gate_contradiction_check)
    for decision in gate_decisions:
        append_runtime_event(
            memory_dir,
            event_type="self_delta_staged",
            payload={"pulse_id": pulse_id, "cast_ts": cast_ts, **decision.to_dict()},
        )

    # trace_verdicts — recorded judgements on igniting traces.
    for trace_verdict in pulse.trace_verdicts:
        append_runtime_event(
            memory_dir,
            event_type="trace_verdict_recorded",
            payload={"pulse_id": pulse_id, **trace_verdict.to_dict()},
        )

    # keepsakes — what the resident chose to remember across days. The ledger event
    # is provenance; the DURABLE write (memory.record_kept) is the real home, because
    # the ledger is hard-capped and would otherwise evict the memory within hours.
    for keepsake in pulse.keepsakes:
        append_runtime_event(
            memory_dir,
            event_type="memory_kept",
            payload={"pulse_id": pulse_id, "kept_ts": cast_ts, "note": keepsake.note},
        )
        record_kept(memory_dir, keepsake.note, kept_ts=cast_ts)

    return {
        "pulse_id": pulse_id,
        "cast_ts": cast_ts,
        "felt_sense_logged": True,
        "act_routed": act_routed,
        "afterimages_cast": len(pulse.expectations),
        "drive_nudges_cast": len(pulse.drive_nudges),
        "gate_decisions": [decision.to_dict() for decision in gate_decisions],
        "trace_verdicts_recorded": len(pulse.trace_verdicts),
        "memories_kept": len(pulse.keepsakes),
    }
