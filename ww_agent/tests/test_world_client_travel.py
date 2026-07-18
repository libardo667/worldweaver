from __future__ import annotations

import asyncio

from src.world.client import WorldWeaverClient


class _Response:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _RecordingClient(WorldWeaverClient):
    def __init__(self) -> None:
        self._base_url = "https://source.example"
        self.calls: list[tuple[str, str, dict]] = []

    async def _get(self, path: str, **_kwargs) -> _Response:
        self.calls.append(("GET", path, {}))
        return _Response({"destinations": []})

    async def _post(self, path: str, payload: dict, **_kwargs) -> _Response:
        self.calls.append(("POST", path, payload))
        return _Response({"success": True})


def test_world_client_exposes_the_recoverable_travel_contract():
    client = _RecordingClient()

    asyncio.run(client.get_travel_destinations())
    asyncio.run(
        client.depart_session_for_travel(
            session_id="source-session",
            route_id="pdx-sf",
            destination_shard="bay-commons-1",
            travel_id="trip-001",
            reason="visit",
        )
    )
    asyncio.run(client.retry_travel_departure("trip-001"))
    asyncio.run(
        client.arrive_session_from_travel(
            travel_id="trip-001",
            session_id="destination-session",
        )
    )
    asyncio.run(client.retry_travel_arrival("trip-001"))
    asyncio.run(client.make_world_object("resident-1", "small_clay_cup", "make-1"))

    assert client.base_url == "https://source.example"
    assert client.calls == [
        ("GET", "/api/world/travel/destinations", {}),
        (
            "POST",
            "/api/session/travel/depart",
            {
                "session_id": "source-session",
                "route_id": "pdx-sf",
                "destination_shard": "bay-commons-1",
                "travel_id": "trip-001",
                "reason": "visit",
            },
        ),
        ("POST", "/api/session/travel/trip-001/retry-departure", {}),
        (
            "POST",
            "/api/session/travel/arrive",
            {"travel_id": "trip-001", "session_id": "destination-session"},
        ),
        ("POST", "/api/session/travel/trip-001/retry-arrival", {}),
        (
            "POST",
            "/api/world/make",
            {
                "session_id": "resident-1",
                "recipe_id": "small_clay_cup",
                "idempotency_key": "make-1",
            },
        ),
    ]
