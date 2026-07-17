from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import src.resident as resident_module
from src.familiar.local_world import LocalWorld
from src.identity.loader import LoopTuning, ResidentIdentity
from src.resident import Resident
from src.runtime.ledger import load_runtime_events
from src.runtime.travel import TravelRequest
from src.world.city_world import CityWorld


class _FakeCityClient:
    def __init__(self, *, leave_success: bool = True) -> None:
        self.leave_success = leave_success
        self.left: list[str] = []
        self.bootstrapped: list[dict] = []

    async def leave_session(self, session_id: str) -> dict:
        self.left.append(session_id)
        return {"success": self.leave_success, "session_id": session_id}

    async def get_world_id(self) -> str:
        return "test-world"

    async def bootstrap_session(self, **payload) -> dict:
        self.bootstrapped.append(payload)
        return {"success": True}


def _identity() -> ResidentIdentity:
    return ResidentIdentity(
        name="test_resident",
        actor_id="actor-test-resident",
        soul="You are Test Resident.",
        canonical_soul="You are Test Resident.",
        growth_soul="",
        vibe="",
        core="",
        voice_seed=[],
        tuning=LoopTuning(),
    )


def _resident(tmp_path, client: _FakeCityClient) -> Resident:
    resident = Resident(tmp_path / "resident", client, llm=object())
    resident._identity = _identity()
    resident._world_id = "test-world"
    resident._session_id = "test-resident-city-session"
    resident._attachment_kind = "city"
    (resident._resident_dir / "memory").mkdir(parents=True)
    (resident._resident_dir / "session_id.txt").write_text(
        resident._session_id,
        encoding="utf-8",
    )
    return resident


def _event_types(resident: Resident) -> list[str]:
    return [
        str(event.get("event_type") or "")
        for event in load_runtime_events(resident._resident_dir / "memory")
    ]


def test_confirmed_city_departure_enters_private_hearth_with_same_home(tmp_path):
    client = _FakeCityClient()
    resident = _resident(tmp_path, client)
    city = resident._build_city_world(resident._active_session_id())

    hearth = asyncio.run(resident._apply_travel_request(city, TravelRequest("hearth")))

    assert isinstance(hearth, LocalWorld)
    assert hearth.home_dir == resident._resident_dir
    assert resident._attachment_kind == "hearth"
    assert resident._session_id is None
    assert client.left == ["test-resident-city-session"]
    assert not (resident._resident_dir / "session_id.txt").exists()
    assert _event_types(resident)[-2:] == [
        "world_attachment_transition_started",
        "world_attachment_changed",
    ]
    assert resident._restored_attachment_kind() == "hearth"


def test_unconfirmed_departure_cannot_activate_the_hearth(tmp_path):
    client = _FakeCityClient(leave_success=False)
    resident = _resident(tmp_path, client)
    city = resident._build_city_world(resident._active_session_id())

    unchanged = asyncio.run(
        resident._apply_travel_request(city, TravelRequest("hearth"))
    )

    assert unchanged is city
    assert resident._attachment_kind == "city"
    assert resident._session_id == "test-resident-city-session"
    assert _event_types(resident)[-2:] == [
        "world_attachment_transition_started",
        "world_attachment_transition_failed",
    ]


def test_hearth_return_bootstraps_a_fresh_city_session_for_same_actor(
    tmp_path,
    monkeypatch,
):
    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 17, 12, 0, 0, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(resident_module, "datetime", _FixedDateTime)
    monkeypatch.setattr(
        resident_module.uuid,
        "uuid4",
        lambda: SimpleNamespace(hex="fresh1234567890"),
    )
    client = _FakeCityClient()
    resident = _resident(tmp_path, client)
    resident._attachment_kind = "hearth"
    resident._session_id = None
    (resident._resident_dir / "session_id.txt").unlink(missing_ok=True)
    hearth = resident._build_hearth_world()
    retired_session_id = "test_resident-20260717-120000-deadbeef"

    city = asyncio.run(
        resident._apply_travel_request(
            hearth,
            TravelRequest("city", "city"),
        )
    )

    assert isinstance(city, CityWorld)
    assert resident._attachment_kind == "city"
    assert resident._session_id
    assert resident._session_id != retired_session_id
    assert resident._session_id == client.bootstrapped[0]["session_id"]
    assert client.bootstrapped[0]["actor_id"] == "actor-test-resident"
    assert client.bootstrapped[0]["world_id"] == "test-world"
    assert _event_types(resident)[-2:] == [
        "world_attachment_transition_started",
        "world_attachment_changed",
    ]


def test_world_swap_rebuilds_world_sources_without_city_leakage(tmp_path):
    resident = _resident(tmp_path, _FakeCityClient())

    city = resident._build_city_world(resident._active_session_id())
    hearth = resident._build_hearth_world()

    assert "chatter" in city._sources.names
    assert "chatter" not in hearth.information_sources().names
    assert "eats" not in hearth.information_sources().names
    assert {"recall", "measure"} <= set(hearth.information_sources().names)
    assert "keeper" not in hearth.situational_facts()


def test_host_replaces_the_core_after_travel_instead_of_running_two(tmp_path):
    resident = _resident(tmp_path, _FakeCityClient())
    built_for: list[str] = []

    class _Core:
        tick_seconds = 0.0

        def __init__(self, world, attachment_kind):
            self.world = world
            self.attachment_kind = attachment_kind

        async def tick_once(self):
            built_for.append(self.attachment_kind)
            if self.attachment_kind == "city":
                await self.world.post_map_move(
                    "test-resident-city-session",
                    "go home",
                )
                return
            raise asyncio.CancelledError

    resident._build_core = lambda world, session_id: _Core(
        world,
        resident._attachment_kind,
    )
    resident._start_runtime_mirror = lambda: None

    async def _run_until_hearth():
        try:
            await resident.run()
        except asyncio.CancelledError:
            pass

    asyncio.run(_run_until_hearth())

    assert built_for == ["city", "hearth"]
    assert resident._attachment_kind == "hearth"
