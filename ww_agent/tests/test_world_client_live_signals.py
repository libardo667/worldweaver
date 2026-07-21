from __future__ import annotations

import json

import httpx
import pytest

from src.world.client import LiveSignalCursor, WorldWeaverClient


@pytest.mark.asyncio
async def test_world_client_establishes_and_advances_a_live_signal_cursor():
    requests: list[httpx.Request] = []
    responses = [
        {
            "version": 1,
            "cursor_status": "established",
            "retention": "complete",
            "cursor": {
                "shard_id": "alderbank",
                "location": "The Commons",
                "after_id": 12,
            },
            "events": [],
            "has_more": False,
        },
        {
            "version": 1,
            "cursor_status": "current",
            "retention": "complete",
            "cursor": {
                "shard_id": "alderbank",
                "location": "The Commons",
                "after_id": 13,
            },
            "events": [
                {
                    "id": 13,
                    "type": "local_speech",
                    "location": "The Commons",
                    "session_id": "speaker-session",
                    "actor_id": "actor-speaker",
                    "display_name": "Riley",
                    "message": "Hello, Levi.",
                    "occurred_at": "2026-07-20T12:00:00",
                }
            ],
            "has_more": False,
        },
    ]

    async def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=responses.pop(0))

    client = WorldWeaverClient(
        "https://city.example", transport=httpx.MockTransport(handle)
    )
    try:
        established = await client.wait_for_live_signals("resident-session")
        advanced = await client.wait_for_live_signals(
            "resident-session",
            cursor=established.cursor,
            wait_seconds=20,
        )
    finally:
        await client.close()

    assert established.cursor == LiveSignalCursor(
        shard_id="alderbank", location="The Commons", after_id=12
    )
    assert advanced.cursor.after_id == 13
    assert advanced.events[0].message == "Hello, Levi."
    assert requests[0].url.params["wait_seconds"] == "0.0"
    assert requests[1].url.params["after"] == "12"
    assert requests[1].url.params["cursor_location"] == "The Commons"
    assert requests[1].url.params["wait_seconds"] == "20.0"


@pytest.mark.asyncio
async def test_world_client_uses_actor_addressed_correspondence_routes():
    requests: list[httpx.Request] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "messages": [
                        {
                            "message_id": 9,
                            "sender_actor_id": "actor-riley",
                            "sender_name": "Riley",
                            "recipient_actor_id": "actor-levi",
                            "body": "Meet me at the footbridge.",
                            "sent_at": "2026-07-20T12:00:00",
                        }
                    ]
                },
            )
        if request.url.path.endswith("/acknowledge"):
            return httpx.Response(200, json={"acknowledged_ids": [9]})
        return httpx.Response(200, json={"success": True, "message_id": 10})

    client = WorldWeaverClient(
        "https://city.example", transport=httpx.MockTransport(handle)
    )
    try:
        pending = await client.get_pending_correspondence("levi-session")
        await client.acknowledge_correspondence("levi-session", [9])
        await client.send_correspondence(
            "levi-session", "actor-riley", "I will be there."
        )
    finally:
        await client.close()

    assert pending[0].sender_actor_id == "actor-riley"
    assert requests[0].url.path == "/api/world/session/levi-session/correspondence"
    assert requests[0].url.params["limit"] == "10"
    assert json.loads(requests[1].content) == {"message_ids": [9]}
    assert json.loads(requests[2].content) == {
        "session_id": "levi-session",
        "recipient_actor_id": "actor-riley",
        "body": "I will be there.",
    }
