from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import src.resident as resident_module
from src.familiar.local_world import LocalWorld
from src.familiar.config import HearthConfig
from src.identity.hearth_activation import (
    acquire_hearth_runtime,
    initialize_hearth_activation,
)
from src.identity.hearth_manifest import initialize_hearth_manifest
from src.identity.loader import LoopTuning, ResidentIdentity
from src.resident import Resident
from src.runtime.ledger import (
    load_resident_process_envelope,
    load_runtime_checkpoint,
    load_runtime_events,
)
from src.runtime.reference_core import ReferenceResidentCore
from src.runtime.travel import PendingShardTravel, TravelRequest
from src.runtime.world_clock import FixedWorldClock
from src.world.city_world import CityWorld
from src.world.client import LiveSignal, LiveSignalBatch, LiveSignalCursor


class _FakeCityClient:
    def __init__(
        self,
        *,
        leave_success: bool = True,
        base_url: str = "https://source.example",
    ) -> None:
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
    return [
        str(event.get("event_type") or "")
        for event in load_runtime_events(resident._resident_dir / "memory")
    ]


def test_confirmed_city_departure_enters_private_hearth_with_same_home(tmp_path):
    client = _FakeCityClient()
    resident = _resident(tmp_path, client)
    resident._identity.growth_soul = "I carry this change between worlds."
    growth_before = resident._identity.growth_soul
    city = resident._build_city_world(resident._active_session_id())

    hearth = asyncio.run(resident._apply_travel_request(city, TravelRequest("hearth")))

    assert isinstance(hearth, LocalWorld)
    assert hearth.home_dir == resident._resident_dir
    assert resident._attachment_kind == "hearth"
    assert resident._session_id is None
    assert resident._identity.growth_soul == growth_before
    assert client.left == ["test-resident-city-session"]
    assert not (resident._resident_dir / "session_id.txt").exists()
    transition_types = [
        event_type
        for event_type in _event_types(resident)
        if event_type.startswith("world_attachment_")
    ]
    assert transition_types[-2:] == [
        "world_attachment_transition_started",
        "world_attachment_changed",
    ]
    assert (
        load_resident_process_envelope(resident._resident_dir / "memory")["attachment"][
            "kind"
        ]
        == "hearth"
    )
    assert resident._restored_attachment_kind() == "hearth"


def test_bounded_stop_parks_city_session_at_hearth(tmp_path):
    client = _FakeCityClient()
    resident = _resident(tmp_path, client)

    class _Core:
        tick_seconds = 0.0

        async def tick_once(self, *, now=None, force_ignite=False):
            return {"ignited": False}

    resident._build_core = lambda world, session_id: _Core()

    asyncio.run(
        resident.run(
            max_ticks=1,
            pause_seconds=0.0,
            park_at_hearth_on_stop=True,
        )
    )

    assert client.left == ["test-resident-city-session"]
    assert resident._attachment_kind == "hearth"
    assert resident._session_id is None
    assert not (resident._resident_dir / "session_id.txt").exists()


def test_resident_host_passes_injected_world_time_to_normal_ticks(tmp_path):
    instant = datetime(2034, 5, 6, 7, 8, 9, tzinfo=timezone.utc)
    resident = _resident(tmp_path, _FakeCityClient())
    resident._world_clock = FixedWorldClock(instant)
    observed: list[datetime] = []

    class _Core:
        tick_seconds = 0.0

        async def tick_once(self, *, now=None, force_ignite=False):
            observed.append(now)
            return {"status": "idle", "choice": "none"}

    resident._build_core = lambda world, session_id: _Core()

    asyncio.run(resident.run(max_ticks=1, pause_seconds=0.0))

    assert observed == [instant]


def test_bounded_scheduled_return_uses_host_interval_and_releases_custody(tmp_path):
    resident = _resident(tmp_path, _FakeCityClient())
    resident._runtime_lease = acquire_hearth_runtime(resident._resident_dir)
    next_return = object()

    class _Core:
        tick_seconds = 0.0

        async def handle_scheduled_return(self, event_id, *, now):
            assert event_id == "return-1"
            assert now == datetime(2026, 7, 22, tzinfo=timezone.utc)
            return {"status": "processed", "event_id": event_id, "choice": "wait"}

        def scheduled_return(self):
            return next_return

    resident._build_core = lambda world, session_id: _Core()

    result, scheduled = asyncio.run(
        resident.run_scheduled_return(
            "return-1",
            now=datetime(2026, 7, 22, tzinfo=timezone.utc),
        )
    )

    assert result == {
        "status": "processed",
        "event_id": "return-1",
        "choice": "wait",
    }
    assert scheduled is next_return
    assert resident._runtime_lease is None
    assert _event_types(resident)[-2:] == [
        "reference_process_host_started",
        "reference_process_host_suspended",
    ]


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
    monkeypatch.setattr(
        resident_module.uuid,
        "uuid4",
        lambda: SimpleNamespace(hex="fresh1234567890"),
    )
    client = _FakeCityClient()
    resident = _resident(tmp_path, client)
    resident._world_clock = FixedWorldClock(
        datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)
    )
    resident._identity.growth_soul = "I carry this change between worlds."
    growth_before = resident._identity.growth_soul
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
    assert resident._identity.growth_soul == growth_before
    assert client.bootstrapped[0]["actor_id"] == "actor-test-resident"
    assert client.bootstrapped[0]["world_id"] == "test-world"
    transition_types = [
        event_type
        for event_type in _event_types(resident)
        if event_type.startswith("world_attachment_")
    ]
    assert transition_types[-2:] == [
        "world_attachment_transition_started",
        "world_attachment_changed",
    ]
    assert (
        load_resident_process_envelope(resident._resident_dir / "memory")["attachment"][
            "kind"
        ]
        == "city"
    )


def test_city_to_city_travel_retires_source_then_swaps_one_host_to_destination(
    tmp_path,
):
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
    resident._identity.growth_soul = "I carry this change between cities."
    growth_before = resident._identity.growth_soul
    resident._world_id = "source-world"
    resident._session_id = "source-session"
    resident._attachment_kind = "city"
    (resident._resident_dir / "memory").mkdir(parents=True)
    (resident._resident_dir / "session_id.txt").write_text(
        "source-session", encoding="utf-8"
    )
    city = resident._build_city_world("source-session")

    next_city = asyncio.run(
        resident._apply_travel_request(
            city,
            TravelRequest(
                "city", "rose-city-coop-1", "sf-portland", "rose-city-coop-1"
            ),
        )
    )

    assert isinstance(next_city, CityWorld)
    assert source.departures[0]["session_id"] == "source-session"
    assert source.departures[0]["destination_shard"] == "rose-city-coop-1"
    assert destination.arrivals[0]["travel_id"] == source.departures[0]["travel_id"]
    assert resident._ww is destination
    assert resident._attachment_kind == "city"
    assert resident._session_id == destination.arrivals[0]["session_id"]
    assert resident._identity.growth_soul == growth_before
    assert (resident._resident_dir / "session_id.txt").read_text(
        encoding="utf-8"
    ) == resident._session_id
    travel_types = [
        event_type
        for event_type in _event_types(resident)
        if event_type.startswith("inter_shard_")
    ]
    assert travel_types[-3:] == [
        "inter_shard_travel_started",
        "inter_shard_source_departed",
        "inter_shard_travel_arrived",
    ]
    process_events = [
        event
        for event in load_runtime_events(resident._resident_dir / "memory")
        if event["event_type"] == "reference_process_bound"
    ]
    assert [event["payload"]["attachment"]["kind"] for event in process_events] == [
        "traveling",
        "city",
    ]
    assert process_events[0]["payload"]["attachment"]["travel_id"]
    assert process_events[1]["payload"]["attachment"]["travel_id"] == ""


def test_city_profile_selects_local_sources_and_refreshes_after_attachment(tmp_path):
    class _AlderbankClient(_FakeCityClient):
        async def get_shard_experience(self) -> dict:
            return {
                "entry_disclosure": {
                    "capabilities": [
                        {"id": "durable_objects"},
                        {"id": "replenishing_materials"},
                        {"id": "making"},
                        {"id": "stoops"},
                    ]
                }
            }

        async def get_city_pack_preview(self) -> dict:
            return {"manifest": {"city_id": "alderbank"}}

    resident = _resident(tmp_path, _AlderbankClient())

    asyncio.run(resident._refresh_city_profile())
    city = resident._build_city_world(resident._active_session_id())

    assert resident._city_id == "alderbank"
    assert {"objects", "making", "stoops"}.issubset(city._sources.names)
    assert "eats" not in city._sources.names
    assert "news" not in city._sources.names


def test_city_profile_uses_top_level_id_when_no_pack_is_available(tmp_path):
    class _SyntheticClient(_FakeCityClient):
        async def get_shard_experience(self) -> dict:
            return {"entry_disclosure": {"capabilities": []}}

        async def get_city_pack_preview(self) -> dict:
            return {"available": False, "city_id": "resident_gym"}

    resident = _resident(tmp_path, _SyntheticClient())

    asyncio.run(resident._refresh_city_profile())
    city = resident._build_city_world(resident._active_session_id())

    assert resident.city_id == "resident_gym"
    assert resident.city_capabilities == ()
    assert city.information_source_names == ("recall", "measure", "places", "travel")


def test_city_to_city_travel_retries_the_same_destination_handoff(tmp_path):
    class _RecoveringDestination(_FakeCityClient):
        async def arrive_session_from_travel(self, **payload) -> dict:
            self.arrivals.append(payload)
            status = "session_booted" if len(self.arrivals) == 1 else "arrived"
            return {
                "success": status == "arrived",
                "recoverable": status != "arrived",
                "handoff": {"status": status},
            }

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
    (resident._resident_dir / "session_id.txt").write_text(
        "source-session", encoding="utf-8"
    )

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


def test_city_to_city_failure_before_source_retirement_keeps_local_life_running(
    tmp_path,
):
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
            TravelRequest(
                "city", "rose-city-coop-1", "sf-portland", "rose-city-coop-1"
            ),
        )
    )

    assert unchanged is city
    assert resident._attachment_kind == "city"
    assert resident._session_id == "test-resident-city-session"
    assert resident._pending_shard_travel() is None
    assert "inter_shard_travel_aborted" in _event_types(resident)
    assert (
        load_resident_process_envelope(resident._resident_dir / "memory")["attachment"][
            "kind"
        ]
        == "city"
    )


def test_unfinished_departed_trip_resumes_at_destination_without_rebooting_source(
    tmp_path,
):
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

    completed = asyncio.run(
        resident._resume_inter_shard_travel(resident._pending_shard_travel())
    )

    assert completed is True
    assert source.departures == []
    assert destination.arrivals == [
        {"travel_id": "trip-resume", "session_id": "destination-session"}
    ]
    assert resident._session_id == "destination-session"


def test_start_restores_departed_trip_without_booting_a_second_source_session(
    tmp_path, monkeypatch
):
    source = _FakeCityClient()
    resident = Resident(tmp_path / "resident", source, llm=object())
    resident._identity = _identity()
    (resident._resident_dir / "memory").mkdir(parents=True)
    (resident._resident_dir / "session_id.txt").write_text(
        "stale-source-session", encoding="utf-8"
    )
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
    monkeypatch.setattr(
        resident_module.IdentityLoader, "load", lambda _path: _identity()
    )

    asyncio.run(resident.start("source-world"))

    assert resident._attachment_kind == "traveling"
    assert resident._session_id is None
    assert source.bootstrapped == []
    assert not (resident._resident_dir / "session_id.txt").exists()


def test_world_swap_rebuilds_world_sources_without_city_leakage(tmp_path):
    resident = _resident(tmp_path, _FakeCityClient())

    city = resident._build_city_world(resident._active_session_id())
    hearth = resident._build_hearth_world()

    assert "chatter" not in city._sources.names
    assert "chatter" not in hearth.information_sources().names
    assert "eats" not in hearth.information_sources().names
    assert {"recall", "measure", "growth"} <= set(hearth.information_sources().names)
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

        async def tick_once(self, *, now=None, force_ignite=False):
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
    monkeypatch.setattr(
        resident_module.IdentityLoader, "load", lambda _path: _identity()
    )

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

        async def tick_once(self, *, now=None, force_ignite=False):
            return {"ignited": force_ignite}

    resident._build_core = lambda world, session_id: _Core()

    asyncio.run(resident.run(max_ticks=2, pause_seconds=0.0))

    assert observed == [("test_resident", 1), ("test_resident", 2)]


def test_city_host_wakes_early_for_cursor_delivered_speech(tmp_path):
    client = _FakeCityClient()
    cursor = LiveSignalCursor(
        shard_id="alderbank", location="Alderbank Commons", after_id=4
    )
    advanced = LiveSignalCursor(
        shard_id="alderbank", location="Alderbank Commons", after_id=5
    )
    signal = LiveSignal(
        id=5,
        kind="local_speech",
        location="Alderbank Commons",
        session_id="riley-session",
        actor_id="actor-riley",
        display_name="Riley",
        message="Hello, Test Resident.",
        occurred_at="2026-07-20T12:00:00",
    )
    batches = [
        LiveSignalBatch(cursor, "established", "complete", (), False),
        LiveSignalBatch(cursor, "current", "complete", (), False),
        LiveSignalBatch(advanced, "current", "complete", (signal,), False),
    ]
    waits: list[tuple[LiveSignalCursor | None, float]] = []

    async def wait_for_live_signals(
        _session_id, *, cursor=None, wait_seconds=0.0, limit=10
    ):
        assert limit == 10
        waits.append((cursor, wait_seconds))
        return batches.pop(0)

    client.wait_for_live_signals = wait_for_live_signals
    resident = _resident(tmp_path, client)
    forced: list[bool] = []
    offered: list[LiveSignal] = []

    class _Core:
        tick_seconds = 20.0

        async def tick_once(self, *, now=None, force_ignite=False):
            forced.append(force_ignite)
            return {"status": "completed"}

        def offer_live_signals(self, events):
            offered.extend(events)

        def take_acknowledged_live_signal_ids(self):
            return tuple(event.id for event in offered)

        def has_seen_live_signals(self, _events):
            return False

    resident._build_core = lambda _world, _session_id: _Core()

    asyncio.run(resident.run(max_ticks=2, pause_seconds=20.0))

    assert forced == [False, False]
    assert offered == [signal]
    assert waits[0][0] is None
    assert waits[1][0] == cursor
    assert waits[1][1] > 0
    assert waits[2][0] == cursor
    cursor_events = [
        event
        for event in load_runtime_events(resident._resident_dir / "memory")
        if event["event_type"] == "live_signal_cursor_advanced"
    ]
    assert cursor_events[-1]["payload"] == {
        "version": 1,
        "session_id": "test-resident-city-session",
        "shard_id": "alderbank",
        "location": "Alderbank Commons",
        "after_id": 5,
        "status": "acknowledged",
        "delivered_count": 1,
    }


def test_live_signal_cursor_restores_only_for_the_same_city_session(tmp_path):
    resident = _resident(tmp_path, _FakeCityClient())
    resident._bind_reference_process(
        model_id="test/model",
        session_id="test-resident-city-session",
    )
    cursor = LiveSignalCursor(
        shard_id="alderbank", location="Alderbank Commons", after_id=19
    )
    resident._record_live_signal_cursor(
        previous=None,
        current=cursor,
        session_id="test-resident-city-session",
        status="acknowledged",
        delivered_count=2,
    )

    restored = resident._restore_live_signal_cursor("test-resident-city-session")
    new_attachment = resident._restore_live_signal_cursor("new-city-session")

    assert restored == cursor
    assert new_attachment is None


def test_reference_process_checkpoint_binds_identity_attachment_and_model(tmp_path):
    resident = _resident(tmp_path, _FakeCityClient())
    resident._hearth_shard_id = "hearth-test"
    resident._runtime_generation = 4

    resident._bind_reference_process(
        model_id="research/model-v1",
        session_id="test-resident-city-session",
    )
    resident._bind_reference_process(
        model_id="research/model-v1",
        session_id="test-resident-city-session",
    )

    envelope = load_resident_process_envelope(resident._resident_dir / "memory")
    checkpoint = load_runtime_checkpoint(resident._resident_dir / "memory")
    assert envelope is not None
    assert envelope["process_envelope_version"] == 1
    assert envelope["actor_id"] == "actor-test-resident"
    assert envelope["hearth"] == {
        "shard_id": "hearth-test",
        "runtime_generation": 4,
    }
    assert envelope["attachment"] == {
        "kind": "city",
        "world_id": "test-world",
        "city_id": "",
        "session_id": "test-resident-city-session",
        "travel_id": "",
    }
    assert envelope["adapter"] == {
        "id": "worldweaver.reference-resident",
        "version": 1,
    }
    assert envelope["model"] == {"id": "research/model-v1"}
    assert envelope["model_state"] == {
        "format": "none",
        "format_version": 1,
        "byte_length": 0,
        "max_bytes": 0,
    }
    assert checkpoint["state"]["runtime_projection"]["resident_process"] == envelope
    assert _event_types(resident).count("reference_process_bound") == 1


def test_reference_process_uses_the_authoritative_active_hearth_generation(tmp_path):
    resident = _resident(tmp_path, _FakeCityClient())
    identity_dir = resident._resident_dir / "identity"
    identity_dir.mkdir(parents=True)
    (identity_dir / "resident_id.txt").write_text(
        "actor-test-resident\n",
        encoding="utf-8",
    )
    manifest = initialize_hearth_manifest(resident._resident_dir)
    initialize_hearth_activation(resident._resident_dir)
    resident._runtime_lease = acquire_hearth_runtime(resident._resident_dir)
    try:
        resident._load_active_hearth_coordinates()
        resident._bind_reference_process(
            model_id="test/model",
            session_id="test-resident-city-session",
        )
    finally:
        resident._release_runtime_lease()

    envelope = load_resident_process_envelope(resident._resident_dir / "memory")
    assert envelope["hearth"] == {
        "shard_id": manifest.hearth_shard_id,
        "runtime_generation": manifest.runtime_generation,
    }


def test_reference_process_restore_rejects_a_different_resident(tmp_path):
    resident = _resident(tmp_path, _FakeCityClient())
    resident._bind_reference_process(
        model_id="test/model",
        session_id="test-resident-city-session",
    )
    resident._identity = ResidentIdentity(
        name="other",
        actor_id="actor-other",
        soul="You are Other.",
        canonical_soul="You are Other.",
        growth_soul="",
        vibe="",
        core="",
        voice_seed=[],
        tuning=LoopTuning(),
    )

    with pytest.raises(RuntimeError, match="different actor"):
        resident._bind_reference_process(
            model_id="test/model",
            session_id="test-resident-city-session",
        )


def test_reference_process_restore_rejects_a_different_hearth(tmp_path):
    resident = _resident(tmp_path, _FakeCityClient())
    resident._hearth_shard_id = "hearth-original"
    resident._runtime_generation = 4
    resident._bind_reference_process(
        model_id="test/model",
        session_id="test-resident-city-session",
    )
    resident._hearth_shard_id = "hearth-other"

    with pytest.raises(RuntimeError, match="different hearth"):
        resident._bind_reference_process(
            model_id="test/model",
            session_id="test-resident-city-session",
        )


def test_reference_process_restore_rejects_a_generation_regression(tmp_path):
    resident = _resident(tmp_path, _FakeCityClient())
    resident._hearth_shard_id = "hearth-test"
    resident._runtime_generation = 5
    resident._bind_reference_process(
        model_id="test/model",
        session_id="test-resident-city-session",
    )
    resident._runtime_generation = 4

    with pytest.raises(RuntimeError, match="newer hearth generation"):
        resident._bind_reference_process(
            model_id="test/model",
            session_id="test-resident-city-session",
        )


def test_reference_process_generation_and_attachment_advance_without_losing_state(
    tmp_path,
):
    resident = _resident(tmp_path, _FakeCityClient())
    resident._hearth_shard_id = "hearth-test"
    resident._runtime_generation = 4
    resident._bind_reference_process(
        model_id="test/model",
        session_id="test-resident-city-session",
    )
    cursor = LiveSignalCursor(
        shard_id="alderbank", location="Alderbank Commons", after_id=21
    )
    resident._record_live_signal_cursor(
        previous=None,
        current=cursor,
        session_id="test-resident-city-session",
        status="acknowledged",
    )

    resident._runtime_generation = 5
    resident._bind_reference_process(
        model_id="test/model",
        session_id="test-resident-city-session",
    )

    advanced = load_resident_process_envelope(resident._resident_dir / "memory")
    assert advanced["hearth"]["runtime_generation"] == 5
    assert resident._restore_live_signal_cursor("test-resident-city-session") == cursor

    resident._attachment_kind = "hearth"
    resident._bind_reference_process(model_id="test/model", session_id="")

    at_hearth = load_resident_process_envelope(resident._resident_dir / "memory")
    assert at_hearth["attachment"]["kind"] == "hearth"
    assert at_hearth["event_cursor"] is None


def test_cancelling_a_live_signal_wait_releases_the_hearth_lease(tmp_path):
    client = _FakeCityClient()
    wait_started = asyncio.Event()
    wait_cancelled = False
    calls = 0

    async def wait_for_live_signals(
        _session_id, *, cursor=None, wait_seconds=0.0, limit=10
    ):
        nonlocal calls, wait_cancelled
        calls += 1
        if cursor is None:
            return LiveSignalBatch(
                LiveSignalCursor(
                    shard_id="alderbank",
                    location="Alderbank Commons",
                    after_id=4,
                ),
                "established",
                "complete",
                (),
                False,
            )
        wait_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            wait_cancelled = True
            raise

    client.wait_for_live_signals = wait_for_live_signals
    resident = _resident(tmp_path, client)

    class _Core:
        tick_seconds = 20.0

        async def tick_once(self, *, now=None, force_ignite=False):
            return {"status": "completed"}

    resident._build_core = lambda _world, _session_id: _Core()

    async def run_and_cancel():
        task = asyncio.create_task(resident.run())
        await asyncio.wait_for(wait_started.wait(), timeout=1.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(run_and_cancel())

    assert calls == 2
    assert wait_cancelled is True
    assert resident._runtime_lease is None


def test_duration_bound_uses_elapsed_time_instead_of_a_tick_limit(tmp_path):
    observed: list[int] = []

    async def observer(_identity, _world, _core, _result, tick):
        observed.append(tick)

    resident = _resident(tmp_path, _FakeCityClient())
    resident._attachment_kind = "hearth"
    resident._session_id = None
    resident._tick_observer = observer

    class _Core:
        tick_seconds = 0.005

        async def tick_once(self, *, now=None, force_ignite=False):
            return {"ignited": force_ignite}

    resident._build_core = lambda world, session_id: _Core()

    asyncio.run(resident.run(max_duration_seconds=0.02))

    assert 1 < len(observed) < 20
    assert observed == list(range(1, len(observed) + 1))


def test_bounded_resident_run_records_a_clean_process_suspension(tmp_path):
    resident = _resident(tmp_path, _FakeCityClient())

    class _Core:
        tick_seconds = 0.0

        async def tick_once(self, *, now=None, force_ignite=False):
            return {"status": "completed"}

    resident._build_core = lambda _world, _session_id: _Core()

    asyncio.run(resident.run(max_ticks=1, pause_seconds=0.0))

    lifecycle_types = [
        event_type
        for event_type in _event_types(resident)
        if event_type.startswith("reference_process_host_")
    ]
    assert lifecycle_types == [
        "reference_process_host_started",
        "reference_process_host_suspended",
    ]
    hosting = load_resident_process_envelope(resident._resident_dir / "memory")[
        "hosting"
    ]
    assert hosting["state"] == "suspended"
    assert hosting["host_run_id"].startswith("host-")
    assert hosting["suspended_at"]
    assert resident._runtime_lease is None


def test_model_override_can_omit_temperature_without_rewriting_identity(
    tmp_path,
    monkeypatch,
):
    captured: dict = {}

    class _Core:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(resident_module, "ReferenceResidentCore", _Core)
    resident = Resident(
        tmp_path / "resident",
        _FakeCityClient(),
        llm=object(),
        pulse_model="research/model",
        pulse_temperature=None,
    )
    resident._identity = _identity()

    resident._build_core(object(), "session-test")

    assert captured["model"] == "research/model"
    assert captured["temperature"] is None
    assert resident.identity.tuning.fast_model is None


def test_resident_host_builds_and_runs_the_reference_core_at_hearth(tmp_path):
    class _WaitLLM:
        async def complete_json(self, *_args, **_kwargs):
            return {"choice": "wait"}

    resident = Resident(
        tmp_path / "resident",
        _FakeCityClient(),
        llm=_WaitLLM(),
    )
    resident._identity = _identity()
    resident._attachment_kind = "hearth"
    resident._session_id = None
    (resident._resident_dir / "memory").mkdir(parents=True)
    world = resident._build_hearth_world()

    core = resident._build_core(world, resident._active_session_id())
    result = asyncio.run(core.tick_once())

    assert isinstance(core, ReferenceResidentCore)
    assert result["choice"] == "wait"
    assert "pulse_emitted" not in _event_types(resident)
    assert _event_types(resident)[-1] == "reference_activation_outcome"
