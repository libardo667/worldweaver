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
    asyncio.run(client.place_world_object("resident-1", "cup-1", "place-1"))
    asyncio.run(client.pick_up_world_object("resident-1", "cup-1", "pick-up-1"))
    asyncio.run(client.give_world_object("resident-1", "cup-1", "resident-2", "give-1"))
    asyncio.run(client.get_object_exchanges("resident-1"))
    asyncio.run(
        client.offer_object_exchange(
            "resident-1", "resident-2", "cup-1", "token-1", "offer-1"
        )
    )
    asyncio.run(client.accept_object_exchange("resident-1", "exchange-1", "accept-1"))
    asyncio.run(client.decline_object_exchange("resident-1", "exchange-2", "decline-1"))
    asyncio.run(client.cancel_object_exchange("resident-1", "exchange-3", "cancel-1"))
    asyncio.run(client.get_space_access_status("resident-1", "Wayfarer Back Room"))
    asyncio.run(
        client.get_pending_space_access_requests("resident-1", "Wayfarer Back Room")
    )
    asyncio.run(
        client.request_space_access("resident-1", "Wayfarer Back Room", "request-1")
    )
    asyncio.run(
        client.resolve_space_access_request(
            "resident-1", "access-1", "admitted", "admit-1"
        )
    )
    asyncio.run(
        client.set_space_access_mode(
            "resident-1", "Wayfarer Back Room", "private", "mode-1"
        )
    )
    asyncio.run(
        client.invite_to_space(
            "resident-1", "resident-2", "Wayfarer Back Room", "invite-1"
        )
    )
    asyncio.run(
        client.revoke_space_access(
            "resident-1", "resident-2", "Wayfarer Back Room", "revoke-1"
        )
    )
    asyncio.run(
        client.leave_object_on_stoop("resident-1", "commons-stoop", "cup-1", "leave-1")
    )
    asyncio.run(client.take_object_from_stoop("resident-1", "entry-1", "take-1"))
    asyncio.run(
        client.withdraw_object_from_stoop("resident-1", "entry-2", "withdraw-1")
    )

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
        (
            "POST",
            "/api/world/objects/cup-1/place",
            {"session_id": "resident-1", "idempotency_key": "place-1"},
        ),
        (
            "POST",
            "/api/world/objects/cup-1/pick-up",
            {"session_id": "resident-1", "idempotency_key": "pick-up-1"},
        ),
        (
            "POST",
            "/api/world/objects/cup-1/give",
            {
                "session_id": "resident-1",
                "recipient_session_id": "resident-2",
                "idempotency_key": "give-1",
            },
        ),
        ("GET", "/api/world/exchanges", {}),
        (
            "POST",
            "/api/world/exchanges",
            {
                "session_id": "resident-1",
                "recipient_session_id": "resident-2",
                "offered_object_id": "cup-1",
                "requested_object_id": "token-1",
                "idempotency_key": "offer-1",
            },
        ),
        (
            "POST",
            "/api/world/exchanges/exchange-1/accept",
            {"session_id": "resident-1", "idempotency_key": "accept-1"},
        ),
        (
            "POST",
            "/api/world/exchanges/exchange-2/decline",
            {"session_id": "resident-1", "idempotency_key": "decline-1"},
        ),
        (
            "POST",
            "/api/world/exchanges/exchange-3/cancel",
            {"session_id": "resident-1", "idempotency_key": "cancel-1"},
        ),
        ("GET", "/api/world/access", {}),
        ("GET", "/api/world/access/requests", {}),
        (
            "POST",
            "/api/world/access/requests",
            {
                "session_id": "resident-1",
                "location": "Wayfarer Back Room",
                "idempotency_key": "request-1",
                "note": "",
            },
        ),
        (
            "POST",
            "/api/world/access/requests/access-1/resolve",
            {
                "session_id": "resident-1",
                "decision": "admitted",
                "idempotency_key": "admit-1",
            },
        ),
        (
            "POST",
            "/api/world/access/mode",
            {
                "session_id": "resident-1",
                "location": "Wayfarer Back Room",
                "mode": "private",
                "idempotency_key": "mode-1",
            },
        ),
        (
            "POST",
            "/api/world/access/invite",
            {
                "session_id": "resident-1",
                "recipient_session_id": "resident-2",
                "location": "Wayfarer Back Room",
                "idempotency_key": "invite-1",
            },
        ),
        (
            "POST",
            "/api/world/access/revoke",
            {
                "session_id": "resident-1",
                "recipient_session_id": "resident-2",
                "location": "Wayfarer Back Room",
                "idempotency_key": "revoke-1",
            },
        ),
        (
            "POST",
            "/api/world/stoops/commons-stoop/leave",
            {
                "session_id": "resident-1",
                "object_id": "cup-1",
                "idempotency_key": "leave-1",
            },
        ),
        (
            "POST",
            "/api/world/stoops/entries/entry-1/take",
            {"session_id": "resident-1", "idempotency_key": "take-1"},
        ),
        (
            "POST",
            "/api/world/stoops/entries/entry-2/withdraw",
            {"session_id": "resident-1", "idempotency_key": "withdraw-1"},
        ),
    ]
