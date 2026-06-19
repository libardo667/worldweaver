# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""The substrate's top-down prediction: the afterimage (Major 49, Phase 1).

The afterimage is the decaying top-down prediction the substrate is then
surprised against. The pulse casts ``afterimage_cast`` events into the one
canonical ledger; here we *derive* the current prediction at read time by
exponential decay, mirroring the existing ``derive_*`` reducer pattern in
ledger.py. Nothing is stored as a second source of truth — as the afterimage
decays, the world drifts from it on its own and surprise re-accumulates, which
(in Phase 2) fires the next pulse. The rhythm is self-generating.

``predict`` returns the current afterimage field. ``active_drive_nudges`` returns
the current transient reverie pulls, decayed the same way.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.runtime.ledger import load_runtime_events

# Below this decayed intensity an afterimage is considered faded and dropped.
AFTERIMAGE_EPSILON = 0.02

# The baseline is the resident's slow self-model — how it has habitually felt,
# learned from lived stimulus (salience.update_baseline). Where the afterimage is
# the fast top-down prediction the last pulse just cast and decays in minutes,
# the baseline is the slow ground beneath it: it decays in hours, so a self left
# unattended only fades gradually. Surprise is measured against max(afterimage,
# baseline), which is what lets a persistent stimulus stop surprising once it has
# been absorbed (habituation) while a change from the settled self still does.
BASELINE_DECAY_HALF_LIFE = 4 * 3600.0
BASELINE_EPSILON = 0.02


def _utc_now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _as_now(now: Any) -> datetime:
    return _parse_dt(now) or _utc_now_dt()


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _decay_factor(age_seconds: float, half_life: float) -> float:
    """Exponential decay with the given half-life. Clamped to ``[0, 1]``."""
    if half_life <= 0.0:
        return 0.0
    if age_seconds <= 0.0:
        return 1.0
    return float(0.5 ** (age_seconds / half_life))


def _decayed_field(
    events: list[dict[str, Any]],
    *,
    event_type: str,
    now: Any,
    use_confidence: bool,
) -> dict[str, Any]:
    """Shared decay reduction for afterimage / drive-nudge events."""
    now_dt = _as_now(now)
    active: list[dict[str, Any]] = []
    by_scope: dict[str, dict[str, float]] = {}

    for event in events:
        if str(event.get("event_type") or "").strip() != event_type:
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        features = payload.get("features")
        if not isinstance(features, dict) or not features:
            continue
        cast_dt = _parse_dt(payload.get("cast_ts")) or _parse_dt(event.get("ts"))
        if cast_dt is None:
            continue
        half_life = _coerce_float(payload.get("half_life")) or 0.0
        age_seconds = max(0.0, (now_dt - cast_dt).total_seconds())
        decay = _decay_factor(age_seconds, half_life)
        confidence = _coerce_float(payload.get("confidence")) if use_confidence else 1.0
        weight = (confidence if confidence is not None else 0.5) * decay
        scope = str(payload.get("scope") or "here").strip() or "here"

        contributions: dict[str, float] = {}
        for tag, intensity in features.items():
            name = str(tag or "").strip()
            value = _coerce_float(intensity)
            if not name or value is None:
                continue
            contributions[name] = round(max(0.0, min(value, 1.0)) * weight, 4)

        if not contributions or max(contributions.values()) < AFTERIMAGE_EPSILON:
            continue

        entry: dict[str, Any] = {
            "pulse_id": str(payload.get("pulse_id") or "").strip(),
            "scope": scope,
            "features": contributions,
            "age_seconds": round(age_seconds, 3),
            "half_life": half_life,
            "decay": round(decay, 4),
        }
        if use_confidence:
            entry["confidence"] = round(confidence if confidence is not None else 0.5, 4)
        active.append(entry)

        scope_field = by_scope.setdefault(scope, {})
        for name, value in contributions.items():
            if value < AFTERIMAGE_EPSILON:
                continue
            scope_field[name] = max(scope_field.get(name, 0.0), value)

    return {
        "computed_at": now_dt.isoformat(),
        "by_scope": {scope: tags for scope, tags in by_scope.items() if tags},
        "active": active,
    }


def derive_afterimage(events: list[dict[str, Any]], *, now: Any = None) -> dict[str, Any]:
    """Current afterimage field (the substrate's top-down prediction)."""
    return _decayed_field(events, event_type="afterimage_cast", now=now, use_confidence=True)


def derive_drive_nudges(events: list[dict[str, Any]], *, now: Any = None) -> dict[str, Any]:
    """Current transient drive pulls, decayed from ``drive_nudge_cast`` events."""
    return _decayed_field(events, event_type="drive_nudge_cast", now=now, use_confidence=False)


def predict(memory_dir: Path, *, now: Any = None) -> dict[str, Any]:
    """What the substrate predicts right now — the live, decayed afterimage."""
    return derive_afterimage(load_runtime_events(memory_dir), now=now)


def active_drive_nudges(memory_dir: Path, *, now: Any = None) -> dict[str, Any]:
    return derive_drive_nudges(load_runtime_events(memory_dir), now=now)


def derive_baseline(events: list[dict[str, Any]], *, now: Any = None) -> dict[str, Any]:
    """The resident's slow self-model: how it has habitually felt over time.

    Read as the latest ``baseline_updated`` snapshot, gently decayed toward zero
    by its age so a self left unattended fades over hours rather than holding a
    stale value forever. This is the steady ground the resident is surprised
    against — its felt sense of "how I usually am."
    """
    now_dt = _as_now(now)
    latest_payload: dict[str, Any] | None = None
    latest_dt: datetime | None = None
    for event in events:
        if str(event.get("event_type") or "").strip() != "baseline_updated":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        ts = _parse_dt(payload.get("updated_ts")) or _parse_dt(event.get("ts"))
        if ts is None:
            continue
        if latest_dt is None or ts > latest_dt:
            latest_dt, latest_payload = ts, payload

    by_scope: dict[str, dict[str, float]] = {}
    if latest_payload is not None and isinstance(latest_payload.get("by_scope"), dict):
        age_seconds = max(0.0, (now_dt - latest_dt).total_seconds()) if latest_dt else 0.0
        decay = _decay_factor(age_seconds, BASELINE_DECAY_HALF_LIFE)
        for scope, tags in latest_payload["by_scope"].items():
            if not isinstance(tags, dict):
                continue
            scope_field: dict[str, float] = {}
            for tag, value in tags.items():
                num = _coerce_float(value)
                if num is None:
                    continue
                decayed = round(max(0.0, min(num, 1.0)) * decay, 4)
                name = str(tag or "").strip()
                if name and decayed >= BASELINE_EPSILON:
                    scope_field[name] = decayed
            if scope_field:
                by_scope[str(scope or "self").strip() or "self"] = scope_field

    return {
        "computed_at": now_dt.isoformat(),
        "by_scope": by_scope,
        "updated_at": latest_dt.isoformat() if latest_dt else None,
    }


def baseline(memory_dir: Path, *, now: Any = None) -> dict[str, Any]:
    """The resident's current slow self-model (the live, decayed baseline)."""
    return derive_baseline(load_runtime_events(memory_dir), now=now)


def predict_combined(memory_dir: Path, *, now: Any = None) -> dict[str, Any]:
    """The full prediction the substrate is surprised against: the fast afterimage
    laid over the slow baseline, ``max`` per feature.

    The afterimage is the resident's fresh, specific intention ("I expect this");
    the baseline is its settled normal ("this is how things usually are"). Taking
    the max means a stimulus must exceed both to surprise — so once the baseline
    has absorbed a persistent feature, that feature stops surprising even as the
    afterimage fades, which is habituation. A novel feature, or a change away from
    the settled self, still rises above the prediction and wakes the resident.
    """
    events = load_runtime_events(memory_dir)
    afterimage = derive_afterimage(events, now=now)["by_scope"]
    base = derive_baseline(events, now=now)["by_scope"]
    by_scope: dict[str, dict[str, float]] = {}
    for scope in set(afterimage) | set(base):
        fast = afterimage.get(scope, {})
        slow = base.get(scope, {})
        merged: dict[str, float] = {}
        for tag in set(fast) | set(slow):
            merged[tag] = round(max(float(fast.get(tag, 0.0)), float(slow.get(tag, 0.0))), 4)
        if merged:
            by_scope[scope] = merged
    return {
        "computed_at": _as_now(now).isoformat(),
        "by_scope": by_scope,
        "afterimage": afterimage,
        "baseline": base,
    }
