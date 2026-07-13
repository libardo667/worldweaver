"""Offline proof of the record -> replay choke-point mechanic (no live server).

Records world-client calls through an httpx MockTransport, then feeds the
recording to a ReplayClient and asserts the real, unmodified client code parses
byte-identical dataclasses on replay — and that writes are captured, not sent.

Follows the repo convention (test_drive.py): sync tests driving async calls via
asyncio.run, so it runs regardless of pytest-asyncio mode.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "ww_agent"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # probes dir, for `from pen_swap...`

from pen_swap.replay_client import RecordingClient, ReplayClient  # noqa: E402

SESSION = "sess-anton"
SCENE_BODY = {
    "location": "Dogpatch",
    "role": "resident",
    "present": [{"name": "Layla", "role": "muralist", "last_action": "painting", "last_seen": "now"}],
    "ambient_presence": [{"kind": "weather", "label": "salt fog", "source": "env", "intensity": 0.4, "ttl_seconds": 60, "pressure_tags": ["damp"], "sensory_note": "the air tastes of brine"}],
    "recent_events_here": [{"who": "Layla", "summary": "set up an easel", "ts": "t0"}],
    "location_graph": {"Dogpatch": ["Mission"]},
}
CHAT_BODY = {"messages": [{"id": 7, "session_id": "sess-layla", "display_name": "Layla", "message": "the ochre won't dry", "ts": "t1"}]}


def _mock_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == f"/api/world/scene/{SESSION}":
        return httpx.Response(200, json=SCENE_BODY)
    if path.startswith("/api/world/location/") and path.endswith("/chat") and request.method == "GET":
        return httpx.Response(200, json=CHAT_BODY)
    if request.method == "POST":
        return httpx.Response(200, json={"ok": True})
    return httpx.Response(200, json={})


def _record(rec_path: Path) -> RecordingClient:
    recorder = RecordingClient("http://test.invalid", recording_path=rec_path)
    recorder._client = httpx.AsyncClient(base_url="http://test.invalid", transport=httpx.MockTransport(_mock_handler))
    return recorder


def test_record_then_replay_roundtrip(tmp_path):
    rec_path = tmp_path / "keep.jsonl"

    async def _go():
        recorder = _record(rec_path)
        recorder.set_tick(0)
        scene_live = await recorder.get_scene(SESSION)
        chat_live = await recorder.get_location_chat("Dogpatch")
        await recorder.post_location_chat(location="Dogpatch", session_id=SESSION, message="I'm here.", display_name="Anton")
        await recorder.close()

        lines = [ln for ln in rec_path.read_text().splitlines() if ln.strip()]
        assert len(lines) == 3  # 2 reads + 1 write

        replay = ReplayClient.from_recording(rec_path)
        scene_replay = await replay.get_scene(SESSION)
        chat_replay = await replay.get_location_chat("Dogpatch")

        # Faithful parse: replayed dataclasses equal the live-parsed ones.
        assert scene_replay.location == scene_live.location == "Dogpatch"
        assert [p.name for p in scene_replay.present] == [p.name for p in scene_live.present] == ["Layla"]
        assert scene_replay.ambient_presence[0].label == "salt fog"
        assert scene_replay.recent_events_here[0].who == "Layla"
        assert [m.message for m in chat_replay] == [m.message for m in chat_live] == ["the ochre won't dry"]

        # Writes are captured + suppressed, not sent.
        captured = await replay.post_location_chat(location="Dogpatch", session_id=SESSION, message="different pen speaks", display_name="Anton")
        assert captured == {"ok": True}  # recorded shape reused
        assert len(replay.captured_writes) == 1
        assert replay.captured_writes[0].payload["message"] == "different pen speaks"
        assert replay.misses == []
        await replay.close()

    asyncio.run(_go())


def test_replay_is_deterministic(tmp_path):
    rec_path = tmp_path / "keep.jsonl"

    async def _go():
        recorder = _record(rec_path)
        await recorder.get_scene(SESSION)
        await recorder.close()
        a = await ReplayClient.from_recording(rec_path).get_scene(SESSION)
        b = await ReplayClient.from_recording(rec_path).get_scene(SESSION)
        assert a.location == b.location
        assert [p.name for p in a.present] == [p.name for p in b.present]

    asyncio.run(_go())


def test_offrecording_read_is_a_counted_miss(tmp_path):
    rec_path = tmp_path / "keep.jsonl"

    async def _go():
        recorder = _record(rec_path)
        await recorder.get_scene(SESSION)
        await recorder.close()
        replay = ReplayClient.from_recording(rec_path)
        await replay.get_scene(SESSION)  # matched
        await replay.get_location_chat("SomewhereElse")  # no recording -> miss (strayed off the recorded world)
        assert len(replay.misses) == 1
        assert replay.misses[0][1].endswith("/chat")
        await replay.close()

    asyncio.run(_go())
