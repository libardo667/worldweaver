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
