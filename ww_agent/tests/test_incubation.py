"""Incubation (arrival quarantine) — the lift logic and the citywide seam gates."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.runtime.incubation import (
    INCUBATION_GROUNDING_THRESHOLD,
    INCUBATION_MAX_SECONDS,
    INCUBATION_MIN_SECONDS,
    groundedness,
    is_incubating,
    is_incubating_projection,
)
from src.runtime.ledger import reduce_runtime_events


def _ev(ts: datetime, etype: str = "tick") -> dict:
    return {"ts": ts.isoformat(), "event_type": etype}


# ── lift logic ────────────────────────────────────────────────────────────────


def test_just_arrived_is_incubating():
    assert is_incubating([]) is True


def test_below_floor_holds_even_when_already_grounded():
    now = datetime.now(timezone.utc)
    arrival = now - timedelta(seconds=INCUBATION_MIN_SECONDS / 2)
    events = [_ev(arrival)] + [
        _ev(arrival, "workshop_entry")
        for _ in range(INCUBATION_GROUNDING_THRESHOLD + 3)
    ]
    assert is_incubating(events, now=now) is True  # the floor always buys a real beat


def test_above_ceiling_lifts_even_when_not_grounded():
    now = datetime.now(timezone.utc)
    arrival = now - timedelta(seconds=INCUBATION_MAX_SECONDS + 10)
    events = [_ev(arrival)]  # no self built at all
    assert is_incubating(events, now=now) is False  # never stuck quarantined


def test_between_floor_and_ceiling_lifts_once_grounded():
    now = datetime.now(timezone.utc)
    arrival = now - timedelta(
        seconds=(INCUBATION_MIN_SECONDS + INCUBATION_MAX_SECONDS) / 2
    )
    ungrounded = [_ev(arrival)]
    assert is_incubating(ungrounded, now=now) is True
    grounded = [_ev(arrival)] + [
        _ev(arrival, "workshop_entry") for _ in range(INCUBATION_GROUNDING_THRESHOLD)
    ]
    assert is_incubating(grounded, now=now) is False


def test_checkpoint_incubation_view_matches_event_history():
    now = datetime.now(timezone.utc)
    arrival = now - timedelta(
        seconds=(INCUBATION_MIN_SECONDS + INCUBATION_MAX_SECONDS) / 2
    )
    events = [_ev(arrival)] + [
        _ev(arrival, "workshop_entry") for _ in range(INCUBATION_GROUNDING_THRESHOLD)
    ]
    projection = reduce_runtime_events(events).runtime_projection

    assert is_incubating_projection(projection, now=now) == is_incubating(
        events, now=now
    )


def test_disabled_path_is_caller_side():
    # is_incubating itself never reads a flag — the core gates on self._incubation first.
    # Here we just confirm the grounding signal counts only self-made artifacts.
    now = datetime.now(timezone.utc)
    events = [
        _ev(now, "workshop_entry"),
        _ev(now, "memory_kept"),
        _ev(now, "workshop_drawing"),
        _ev(now, "chat_sent"),
        _ev(now, "ambient_pressure_observed"),
        _ev(now, "city_broadcast_sent"),
    ]
    assert groundedness(events) == 3


# ── CityWorld seals the chatter pull ────────────────────────────────────────────


class _FakeSource:
    def __init__(
        self, name: str, description: str, provenance: str = "local-knowledge"
    ):
        self.name = name
        self.description = description
        self.provenance = provenance
        self.freshness = "live"
        self.locality = "city"
        self.visibility = "private"
        self.selection_mode = "query"


class _FakeRegistry:
    def __init__(self, sources: list[_FakeSource]):
        self._sources = sources
        self.names = {source.name for source in sources}
        self.reads: list[tuple[str, str]] = []

    def list(self) -> list[_FakeSource]:
        return list(self._sources)

    async def read(self, name: str, arg: str) -> dict:
        self.reads.append((name, arg))
        return {
            "ok": True,
            "records": [{"record_id": f"{name}:one", "content": f"read {name}"}],
        }

    def bind_drive(self, drive) -> None:
        pass


class _FakeClient:
    async def get_scene(self, session_id: str):
        # A fresh scene each call (CityWorld appends typed affordances).
        return SimpleNamespace(recent_events_here=[], affordances=[])

    async def post_action(self, session_id: str, action: str):
        return SimpleNamespace(narrative="world action")


def _advert(scene) -> str:
    return " ".join(
        getattr(item, "description", "") for item in (scene.affordances or [])
    )


def test_cityworld_advertises_and_runs_chatter_when_not_incubating():
    from src.world.city_world import CityWorld

    registry = _FakeRegistry(
        [
            _FakeSource("chatter", "listen in on the citywide chatter"),
            _FakeSource("eats", "recommend a good bite nearby"),
        ]
    )
    world = CityWorld(_FakeClient(), registry)
    world.incubating = False

    scene = asyncio.run(world.get_scene("s1"))
    assert "citywide chatter" in _advert(scene)
    asyncio.run(world.access_information(kind="attend", source="chatter"))
    assert registry.reads == [("chatter", "")]


def test_cityworld_seals_chatter_during_incubation():
    from src.world.city_world import CityWorld

    registry = _FakeRegistry(
        [
            _FakeSource("chatter", "listen in on the citywide chatter"),
            _FakeSource("eats", "recommend a good bite nearby"),
        ]
    )
    world = CityWorld(_FakeClient(), registry)
    world.incubating = True

    scene = asyncio.run(world.get_scene("s1"))
    advert = _advert(scene)
    assert "citywide chatter" not in advert  # the citywide seam is closed
    assert "bite" in advert  # local-knowledge sources remain available

    res = asyncio.run(world.access_information(kind="attend", source="chatter"))
    assert registry.reads == []  # never reached the registry — refused
    assert res["ok"] is False
    assert res["reason"] == "incubating"
    assert res["records"] == []
