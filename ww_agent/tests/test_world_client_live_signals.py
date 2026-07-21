from __future__ import annotations

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
