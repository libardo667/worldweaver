from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import src.resident as resident_module
from src.familiar.local_world import LocalWorld
from src.familiar.config import HearthConfig
from src.identity.loader import LoopTuning, ResidentIdentity
from src.resident import Resident
from src.runtime.ledger import load_runtime_events
from src.runtime.travel import PendingShardTravel, TravelRequest
from src.world.city_world import CityWorld


class _FakeCityClient:
    def __init__(self, *, leave_success: bool = True, base_url: str = "https://source.example") -> None:
        self.leave_success = leave_success
        self.base_url = base_url
        self.left: list[str] = []
        self.bootstrapped: list[dict] = []
        self.departures: list[dict] = []
        self.arrivals: list[dict] = []
        self.closed = False

    async def leave_session(self, session_id: str) -> dict:
        self.left.append(session_id)
        return {"success": self.leave_success, "session_id": session_id}

    async def get_world_id(self) -> str:
        return "test-world"

    async def bootstrap_session(self, **payload) -> dict:
        self.bootstrapped.append(payload)
        return {"success": True}

    async def depart_session_for_travel(self, **payload) -> dict:
        self.departures.append(payload)
        return {
            "success": True,
            "handoff": {
                "status": "traveling",
                "destination_url": "https://destination.example",
            },
        }

    async def arrive_session_from_travel(self, **payload) -> dict:
        self.arrivals.append(payload)
        return {"success": True, "handoff": {"status": "arrived"}}

    async def get_identity_growth(self, _session_id: str) -> dict:
        return {"growth_text": ""}

    async def close(self) -> None:
        self.closed = True


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
    return [str(event.get("event_type") or "") for event in load_runtime_events(resident._resident_dir / "memory")]


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

    unchanged = asyncio.run(resident._apply_travel_request(city, TravelRequest("hearth")))

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


def test_city_to_city_travel_retires_source_then_swaps_one_host_to_destination(tmp_path):
    source = _FakeCityClient()
    destination = _FakeCityClient(base_url="https://destination.example")
    resident = Resident(
        tmp_path / "resident",
        source,
        llm=object(),
        world_client_factory=lambda _url: destination,
        travel_retry_seconds=0,
    )
    resident._identity = _identity()
    resident._world_id = "source-world"
    resident._session_id = "source-session"
    resident._attachment_kind = "city"
    (resident._resident_dir / "memory").mkdir(parents=True)
    (resident._resident_dir / "session_id.txt").write_text("source-session", encoding="utf-8")
    city = resident._build_city_world("source-session")

    next_city = asyncio.run(
        resident._apply_travel_request(
            city,
            TravelRequest("city", "rose-city-coop-1", "sf-portland", "rose-city-coop-1"),
        )
    )

    assert isinstance(next_city, CityWorld)
    assert source.departures[0]["session_id"] == "source-session"
    assert source.departures[0]["destination_shard"] == "rose-city-coop-1"
    assert destination.arrivals[0]["travel_id"] == source.departures[0]["travel_id"]
    assert resident._ww is destination
    assert resident._attachment_kind == "city"
    assert resident._session_id == destination.arrivals[0]["session_id"]
    assert (resident._resident_dir / "session_id.txt").read_text(encoding="utf-8") == resident._session_id
    assert _event_types(resident)[-3:] == [
        "inter_shard_travel_started",
        "inter_shard_source_departed",
        "inter_shard_travel_arrived",
    ]


def test_city_to_city_travel_retries_the_same_destination_handoff(tmp_path):
    class _RecoveringDestination(_FakeCityClient):
        async def arrive_session_from_travel(self, **payload) -> dict:
            self.arrivals.append(payload)
            status = "session_booted" if len(self.arrivals) == 1 else "arrived"
            return {"success": status == "arrived", "recoverable": status != "arrived", "handoff": {"status": status}}

    source = _FakeCityClient()
    destination = _RecoveringDestination(base_url="https://destination.example")
    resident = Resident(
        tmp_path / "resident",
        source,
        llm=object(),
        world_client_factory=lambda _url: destination,
        travel_retry_seconds=0,
    )
    resident._identity = _identity()
    resident._world_id = "source-world"
    resident._session_id = "source-session"
    resident._attachment_kind = "city"
    (resident._resident_dir / "memory").mkdir(parents=True)
    (resident._resident_dir / "session_id.txt").write_text("source-session", encoding="utf-8")

    completed = asyncio.run(
        resident._resume_inter_shard_travel(
            PendingShardTravel(
                travel_id="trip-recover",
                transition_id="transition-recover",
                route_id="sf-portland",
                source_url="https://source.example",
                source_session_id="source-session",
                destination_shard="rose-city-coop-1",
                destination_url="",
                destination_session_id="destination-session",
            )
        )
    )

    assert completed is True
    assert destination.arrivals == [
        {"travel_id": "trip-recover", "session_id": "destination-session"},
        {"travel_id": "trip-recover", "session_id": "destination-session"},
    ]


def test_city_to_city_failure_before_source_retirement_keeps_local_life_running(tmp_path):
    class _UnavailableFederationClient(_FakeCityClient):
        async def depart_session_for_travel(self, **payload) -> dict:
            self.departures.append(payload)
            raise RuntimeError("federation unavailable")

        async def get_scene(self, _session_id: str):
            return object()

    source = _UnavailableFederationClient()
    resident = _resident(tmp_path, source)
    resident._travel_retry_seconds = 0
    city = resident._build_city_world(resident._active_session_id())

    unchanged = asyncio.run(
        resident._apply_travel_request(
            city,
            TravelRequest("city", "rose-city-coop-1", "sf-portland", "rose-city-coop-1"),
        )
    )

    assert unchanged is city
    assert resident._attachment_kind == "city"
    assert resident._session_id == "test-resident-city-session"
    assert resident._pending_shard_travel() is None
    assert _event_types(resident)[-1] == "inter_shard_travel_aborted"


def test_unfinished_departed_trip_resumes_at_destination_without_rebooting_source(tmp_path):
    source = _FakeCityClient()
    destination = _FakeCityClient(base_url="https://destination.example")
    resident = Resident(
        tmp_path / "resident",
        source,
        llm=object(),
        world_client_factory=lambda _url: destination,
        travel_retry_seconds=0,
    )
    resident._identity = _identity()
    resident._world_id = "source-world"
    resident._attachment_kind = "traveling"
    memory = resident._resident_dir / "memory"
    memory.mkdir(parents=True)
    resident._record_transition(
        "inter_shard_travel_started",
        travel_id="trip-resume",
        transition_id="transition-resume",
        route_id="sf-portland",
        source_url="https://source.example",
        source_session_id="source-session",
        destination_shard="rose-city-coop-1",
        destination_url="",
        destination_session_id="destination-session",
    )
    resident._record_transition(
        "inter_shard_source_departed",
        travel_id="trip-resume",
        transition_id="transition-resume",
        destination_url="https://destination.example",
    )

    completed = asyncio.run(resident._resume_inter_shard_travel(resident._pending_shard_travel()))

    assert completed is True
    assert source.departures == []
    assert destination.arrivals == [{"travel_id": "trip-resume", "session_id": "destination-session"}]
    assert resident._session_id == "destination-session"


def test_start_restores_departed_trip_without_booting_a_second_source_session(tmp_path, monkeypatch):
    source = _FakeCityClient()
    resident = Resident(tmp_path / "resident", source, llm=object())
    resident._identity = _identity()
    (resident._resident_dir / "memory").mkdir(parents=True)
    (resident._resident_dir / "session_id.txt").write_text("stale-source-session", encoding="utf-8")
    resident._record_transition(
        "inter_shard_travel_started",
        travel_id="trip-restart",
        transition_id="transition-restart",
        route_id="sf-portland",
        source_url="https://source.example",
        source_session_id="source-session",
        destination_shard="rose-city-coop-1",
        destination_url="",
        destination_session_id="destination-session",
    )
    resident._record_transition(
        "inter_shard_source_departed",
        travel_id="trip-restart",
        transition_id="transition-restart",
        destination_url="https://destination.example",
    )
    resident._identity = None
    monkeypatch.setattr(resident_module.IdentityLoader, "load", lambda _path: _identity())

    asyncio.run(resident.start("source-world"))

    assert resident._attachment_kind == "traveling"
    assert resident._session_id is None
    assert source.bootstrapped == []
    assert not (resident._resident_dir / "session_id.txt").exists()


def test_world_swap_rebuilds_world_sources_without_city_leakage(tmp_path):
    resident = _resident(tmp_path, _FakeCityClient())

    city = resident._build_city_world(resident._active_session_id())
    hearth = resident._build_hearth_world()

    assert "chatter" in city._sources.names
    assert "chatter" not in hearth.information_sources().names
    assert "eats" not in hearth.information_sources().names
    assert {"recall", "measure"} <= set(hearth.information_sources().names)
    assert "keeper" not in hearth.situational_facts()


def test_shared_host_applies_only_explicit_hearth_grants(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    resident = _resident(tmp_path, _FakeCityClient())
    resident._hearth_config = HearthConfig(
        place="the window room",
        keeper="Levi",
        read_roots=(shared,),
        vision=True,
        gifts=True,
    )

    hearth = resident._build_hearth_world()

    assert hearth.place == "the window room"
    assert hearth.situational_facts()["keeper"] == "Levi"
    assert "files" in hearth.information_sources().names
    assert hearth._vision is True
    assert "gifts" in hearth.information_sources().names


def test_host_replaces_the_core_after_travel_instead_of_running_two(tmp_path):
    resident = _resident(tmp_path, _FakeCityClient())
    built_for: list[str] = []

    class _Core:
        tick_seconds = 0.0

        def __init__(self, world, attachment_kind):
            self.world = world
            self.attachment_kind = attachment_kind

        async def tick_once(self, *, force_ignite=False):
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


def test_fresh_single_resident_can_start_at_hearth_without_city_bootstrap(
    tmp_path,
    monkeypatch,
):
    client = _FakeCityClient()
    resident = Resident(tmp_path / "resident", client, llm=object())
    monkeypatch.setattr(resident_module.IdentityLoader, "load", lambda _path: _identity())

    asyncio.run(resident.start("", default_attachment="hearth"))

    assert resident._attachment_kind == "hearth"
    assert resident._session_id is None
    assert client.bootstrapped == []
    assert resident._restored_attachment_kind() == "hearth"


def test_host_tick_observer_uses_the_same_core_loop(tmp_path):
    observed: list[tuple[str, int]] = []

    async def observer(identity, world, core, result, tick):
        observed.append((identity.name, tick))

    resident = _resident(tmp_path, _FakeCityClient())
    resident._attachment_kind = "hearth"
    resident._session_id = None
    resident._tick_observer = observer

    class _Core:
        tick_seconds = 0.0

        async def tick_once(self, *, force_ignite=False):
            return {"ignited": force_ignite}

    resident._build_core = lambda world, session_id: _Core()
    resident._start_runtime_mirror = lambda: None

    asyncio.run(resident.run(max_ticks=2, pause_seconds=0.0))

    assert observed == [("test_resident", 1), ("test_resident", 2)]
