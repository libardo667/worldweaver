"""A per-resident day/night rhythm (Major 50).

Habituation gave residents the capacity to go quiet; the circadian gear gives the
world a natural *reason* to. Each resident carries a stable **chronotype** — a
phase offset that makes some early risers and some night owls — and from the
locale's real hour it derives two things:

- ``wakefulness`` — high mid-afternoon, low in the small hours. It scales arousal
  (in salience), so at night a resident stops igniting at ambient noise and slips
  below the repose ceiling, which is what lets settling finally fire: the town
  goes reflective after dark. A sustained, strong surprise still accumulates past
  threshold, so a resident can still be woken — this dampens reactivity, it does
  not switch it off.
- ``rest_pressure`` — the felt pull toward rest, emitted as a ``fatigue`` signal
  that drives the ``rest_drive`` node, so the resident *feels* the late hour.

Pure functions over (hour, chronotype); no I/O. The chronotype is derived
deterministically from identity so it is a stable trait, never a scripted
schedule — Saoirse is simply a lark and always will be, the way she is in life.
"""

from __future__ import annotations

import hashlib
import math
import os
from typing import Any

# Chronotype spread: a resident's wakefulness peak is shifted by up to this many
# hours either way. Negative = lark (peaks/sleeps earlier), positive = owl.
# Default 3.0 is the realistic lark/owl spread; WW_CHRONOTYPE_SPREAD_HOURS can widen
# it for a test (e.g. 12.0 fully inverts the tails, so the extreme owls/larks are
# awake even in the small hours — a way to rouse a cold cohort without faking the clock).
CHRONOTYPE_SPREAD_HOURS = float(os.environ.get("WW_CHRONOTYPE_SPREAD_HOURS") or "3.0")

# Subjective hour at which alertness peaks; the trough sits 12h opposite (~03:30).
WAKE_PEAK_HOUR = 15.5

# Wakefulness never reaches zero — a deep sleeper can still be roused by enough.
WAKEFULNESS_FLOOR = 0.25

# How sharply rest pressure climbs into the night (>1 keeps the day-time pull low
# and lets it rise steeply after dusk).
REST_CURVE_EXPONENT = 1.4


def _identity_key(identity_or_name: Any) -> str:
    name = getattr(identity_or_name, "name", None)
    if name is None:
        name = identity_or_name
    return str(name or "").strip().lower()


def chronotype(identity_or_name: Any, *, explicit: float | None = None) -> float:
    """The resident's stable phase offset in hours (lark −, owl +).

    An explicit value (e.g. set by the doula at birth) wins; otherwise it is
    derived deterministically from identity so it never drifts between runs.
    """
    if explicit is not None:
        return round(max(-CHRONOTYPE_SPREAD_HOURS, min(CHRONOTYPE_SPREAD_HOURS, float(explicit))), 2)
    key = _identity_key(identity_or_name)
    if not key:
        return 0.0
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    frac = (int(digest[:8], 16) % 100000) / 100000.0  # stable in [0, 1)
    return round((frac * 2.0 - 1.0) * CHRONOTYPE_SPREAD_HOURS, 2)


def _phase_label(subjective_hour: float) -> str:
    h = subjective_hour % 24.0
    if h < 5 or h >= 22:
        return "deep night"
    if h < 8:
        return "early morning"
    if h < 12:
        return "morning"
    if h < 17:
        return "afternoon"
    if h < 20:
        return "evening"
    return "late evening"


def circadian_state(hour: float, chronotype: float = 0.0) -> dict[str, Any]:
    """Wakefulness and rest pressure for a given locale hour and chronotype.

    The subjective hour is the locale hour shifted by the chronotype: an owl
    (positive offset) experiences the clock as running ahead of them, so their
    alert peak lands later in real time and they are still up after midnight.
    """
    subjective = (float(hour) - float(chronotype)) % 24.0
    # Cosine alertness: +1 at the subjective peak, -1 twelve hours away.
    phase = math.cos((subjective - WAKE_PEAK_HOUR) / 24.0 * 2.0 * math.pi)
    wake_norm = (phase + 1.0) / 2.0  # [0, 1]
    wakefulness = round(WAKEFULNESS_FLOOR + (1.0 - WAKEFULNESS_FLOOR) * wake_norm, 3)
    rest_pressure = round((1.0 - wake_norm) ** REST_CURVE_EXPONENT, 3)
    return {
        "hour": round(float(hour) % 24.0, 2),
        "subjective_hour": round(subjective, 2),
        "chronotype": round(float(chronotype), 2),
        "wakefulness": wakefulness,
        "rest_pressure": rest_pressure,
        "phase_label": _phase_label(subjective),
    }
