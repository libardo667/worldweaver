"""Soul-domain retention measurement (Minor 57) — the addition-vs-displacement discriminator.

Unit-tests the measurement's core on a synthetic ledger with a *controlled* embedder
(clean orthogonal separation between the soul's domain and the shared-event topic — the
real ``DeterministicEmbedder`` hash-collides unrelated words, and a real semantic embedder
is what the live read uses). The *go/no-go* read needs a real shard run spanning a world
condition; this proves the metric itself separates addition from displacement.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from soul_domain_retention import resident_retention  # noqa: E402

T0 = datetime(2026, 6, 6, 12, 0, 0, tzinfo=timezone.utc)
_SOUL = "I tend the dahlia and the flower and the bloom at the stand."  # the resident's own domain
_START = T0 + timedelta(minutes=25)
_END = T0 + timedelta(minutes=50)

# A controlled bag-of-words embedder: shared words → high cosine, disjoint words → zero.
# The flower-soul resonates with flower anchors and is orthogonal to the storm topic.
_VOCAB = ["dahlia", "flower", "bloom", "stand", "storm", "drainage", "gutter"]


class _ControlledEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            low = str(t).lower()
            out.append([float(low.count(w)) for w in _VOCAB])
        return out


def _ev(minute: int, anchor: str, sal: float = 1.0):
    return (T0 + timedelta(minutes=minute), [{"anchor": anchor, "salience": sal}])


def test_addition_when_the_soul_domain_returns_after_the_event():
    events = [
        _ev(0, "the dahlia bloom"),
        _ev(10, "the flower stand"),
        _ev(30, "the storm drainage"),  # during — the city watches the rain
        _ev(40, "the storm drainage"),
        _ev(60, "the dahlia bloom"),  # after — returns to its own domain
        _ev(70, "the flower stand"),
    ]
    r = asyncio.run(resident_retention(_SOUL, events, embedder=_ControlledEmbedder(), event_start=_START, event_end=_END))
    assert r["verdict"] == "addition"
    assert r["windows"]["during"]["share"] < r["windows"]["before"]["share"]  # the topic was laid over
    assert r["windows"]["after"]["share"] >= r["windows"]["before"]["share"] * 0.8  # ...and the self returned


def test_displacement_when_the_soul_domain_does_not_return():
    events = [
        _ev(0, "the dahlia bloom"),
        _ev(10, "the flower stand"),
        _ev(30, "the storm drainage"),  # during
        _ev(60, "the storm drainage"),  # after — still on the shared topic
        _ev(70, "the storm gutter"),
    ]
    r = asyncio.run(resident_retention(_SOUL, events, embedder=_ControlledEmbedder(), event_start=_START, event_end=_END))
    assert r["verdict"] == "displacement"
    assert r["windows"]["after"]["share"] <= r["windows"]["before"]["share"] * 0.5


def test_no_baseline_when_there_were_no_soul_anchors_before():
    events = [_ev(30, "the storm drainage"), _ev(60, "the storm drainage")]
    r = asyncio.run(resident_retention(_SOUL, events, embedder=_ControlledEmbedder(), event_start=_START, event_end=_END))
    assert r["verdict"] == "no-baseline"  # nothing to retain — can't read addition vs displacement
