"""City tools + CityWorld wiring: the resident vocations."""

from __future__ import annotations

import asyncio
import json

from src.world.city_tools import CityToolScope, _eats, build_city_tool_scope
from src.world.city_world import CityWorld
from src.world.client import RecentEvent, SceneData, TurnResult


# --- the eats tool (false egress, local SF foodie guide) ---


def test_eats_recommends_real_spots_for_a_known_neighborhood():
    out = _eats("the Mission")
    assert "Mission" in out
    assert "La Taqueria" in out  # a real, long-running Mission spot from the local guide


def test_eats_handles_aliases_and_messy_input():
    assert "North Beach" in _eats("telegraph hill")  # alias → north beach
    assert "Sunset" in _eats("Outer Sunset District")  # strip "district", alias
    assert "Mission" in _eats("24th and mission")  # forgiving substring match


def test_eats_requires_a_real_place_name():
    out = _eats("Atlantis")
    assert "La Taqueria" not in out
    assert "neighborhood" in out.lower()  # declines, asks for a real SF neighborhood


def test_eats_with_no_arg_declines():
    out = _eats("")
    assert "neighborhood" in out.lower()


def test_build_city_tool_scope_carries_eats():
    scope = build_city_tool_scope()
    assert "eats" in scope.names


# --- CityWorld wiring (advertise + intercept) ---


class _FakeClient:
    """Minimal WorldClient stand-in: records post_action calls, returns a fixed scene."""

    def __init__(self):
        self.posted: list[str] = []

    async def get_scene(self, session_id: str) -> SceneData:
        return SceneData(session_id=session_id, location="Mission", role="", present=[], recent_events_here=[], location_graph={})

    async def post_action(self, session_id: str, action: str) -> TurnResult:
        self.posted.append(action)
        return TurnResult(narrative=f"[server resolved] {action}", choices=[], vars={})


def test_get_scene_advertises_the_tools():
    world = CityWorld(_FakeClient(), build_city_tool_scope())
    scene = asyncio.run(world.get_scene("sess-1"))
    blurbs = " ".join(e.summary for e in scene.recent_events_here)
    assert "USE a tool" in blurbs and "eats" in blurbs


def test_post_action_intercepts_a_tool_use_locally():
    client = _FakeClient()
    world = CityWorld(client, build_city_tool_scope())
    result = asyncio.run(world.post_action("sess-1", "use eats north beach"))
    assert "North Beach" in result.narrative
    assert client.posted == []  # the tool ran locally; the server was never touched


def test_post_action_delegates_a_real_action_to_the_client():
    client = _FakeClient()
    world = CityWorld(client, build_city_tool_scope())
    result = asyncio.run(world.post_action("sess-1", "examine the mural"))
    assert "[server resolved]" in result.narrative
    assert client.posted == ["examine the mural"]


def test_unknown_use_target_falls_through_to_the_world():
    client = _FakeClient()
    world = CityWorld(client, build_city_tool_scope())
    # "use the payphone" isn't a tool — it's a thing to do in the world
    result = asyncio.run(world.post_action("sess-1", "use the payphone"))
    assert "[server resolved]" in result.narrative
    assert client.posted == ["use the payphone"]


def test_getattr_delegates_unknown_methods_to_the_client():
    client = _FakeClient()
    client.some_helper = lambda: "delegated"  # type: ignore[attr-defined]
    world = CityWorld(client, build_city_tool_scope())
    assert world.some_helper() == "delegated"


# --- recall: the resident reads its own accrued ledger (local, read-only) ---


def test_recall_reads_the_residents_own_ledger(tmp_path):
    mem = tmp_path / "memory"
    mem.mkdir()
    (mem / "kept_memory.jsonl").write_text(
        json.dumps({"note": "the kettle is still warm"}) + "\n" + json.dumps({"note": "I stayed on the sill"}) + "\n",
        encoding="utf-8",
    )
    (mem / "runtime_ledger.jsonl").write_text(
        json.dumps({"event_type": "felt_sense_logged", "payload": {"felt_sense": "a quiet settling"}}) + "\n",
        encoding="utf-8",
    )
    scope = build_city_tool_scope(memory_dir=mem)
    assert "recall" in scope.names

    overview = asyncio.run(scope.call("recall", ""))["result"]
    assert "kettle" in overview or "sill" in overview
    assert "quiet settling" in overview

    matched = asyncio.run(scope.call("recall", "kettle"))["result"]
    assert "kettle" in matched

    miss = asyncio.run(scope.call("recall", "zebra"))["result"]
    assert "Nothing comes back" in miss


def test_recall_absent_without_a_memory_dir():
    scope = build_city_tool_scope()  # no memory dir → no recall tool granted
    assert "recall" not in scope.names


# --- world-facing tools: read the world through the client (the server DB) ---


class _WorldFact:
    def __init__(self, summary: str):
        self.summary = summary


class _ReadClient:
    async def get_news(self) -> list[str]:
        return ["Fog returns to the Sunset", "BART delays on the M-line"]

    async def get_nearby_landmarks(self, location: str, radius_km: float = 0.75) -> list[str]:
        return ["Dolores Park", "Mission Dolores"] if "mission" in location.lower() else []

    async def get_world_facts(self, query: str, session_id=None, limit: int = 5):
        return [_WorldFact(f"Someone was overheard talking about {query} at the taqueria.")] if query else []


def test_news_tool_reads_headlines():
    scope = build_city_tool_scope(client=_ReadClient())
    res = asyncio.run(scope.call("news", ""))
    assert res["ok"] and "Fog returns to the Sunset" in res["result"]


def test_places_tool_looks_around():
    scope = build_city_tool_scope(client=_ReadClient())
    assert "Dolores Park" in asyncio.run(scope.call("places", "the Mission"))["result"]
    assert "Name a place" in asyncio.run(scope.call("places", ""))["result"]


def test_investigate_tool_queries_the_world():
    scope = build_city_tool_scope(client=_ReadClient(), session_id="s1")
    res = asyncio.run(scope.call("investigate", "the rust"))
    assert "the rust" in res["result"] and "taqueria" in res["result"]


def test_full_context_grants_the_whole_catalog(tmp_path):
    mem = tmp_path / "m"
    mem.mkdir()
    scope = build_city_tool_scope(client=_ReadClient(), session_id="s1", memory_dir=mem)
    assert set(scope.names) >= {"eats", "recall", "news", "places", "investigate", "chatter"}


# --- chatter: the CHOSEN channel — a drive-filtered citywide pull (Major 60) ---

from src.runtime.drive import DeterministicEmbedder, DriveVector  # noqa: E402
from src.world.client import ChatMessage  # noqa: E402


def _msg(sid: str, name: str, text: str, ts: str = "2026-06-06T12:00:00+00:00") -> ChatMessage:
    return ChatMessage(id=0, session_id=sid, display_name=name, message=text, ts=ts)


class _CityChatClient:
    def __init__(self, messages: list[ChatMessage]):
        self._messages = messages

    async def get_location_chat(self, location: str, since=None) -> list[ChatMessage]:
        return list(self._messages) if location == "__city__" else []


def test_chatter_ranks_the_citywide_feed_by_soul_resonance():
    # An engine-loving soul, listening to a mixed citywide feed, is drawn to the
    # mechanic's line over the drains and the dahlias — curiosity rationing focus.
    msgs = [
        _msg("a", "Rosa", "the storm drains on Cesar Chavez are backing up again"),
        _msg("b", "Theo", "anyone know a good engine mechanic? my motor is dead"),
        _msg("c", "Mara", "the dahlias at the corner stand are extraordinary today"),
    ]
    scope = build_city_tool_scope(client=_CityChatClient(msgs), session_id="me")
    drive = asyncio.run(DriveVector.build(embedder=DeterministicEmbedder(), constitution="I mend broken engines with steady hands. I love a dead motor brought back to life."))
    scope.bind_drive(drive)
    res = asyncio.run(scope.call("chatter", ""))["result"]
    assert "Theo:" in res
    assert res.index("Theo:") < res.index("Mara:")  # the engine line outranks the dahlias


def test_chatter_follows_a_named_peer():
    # Following a specific resonant mind (the relational "we" as a curiosity subscription).
    msgs = [_msg("a", "Rosa", "the drains again"), _msg("b", "Theo", "my motor is dead"), _msg("a2", "Rosa", "and the gutters too")]
    scope = build_city_tool_scope(client=_CityChatClient(msgs), session_id="me")
    res = asyncio.run(scope.call("chatter", "Rosa"))["result"]
    assert "Following Rosa" in res
    assert "Theo" not in res  # following a peer filters the feed to just them


def test_chatter_falls_back_to_recency_without_a_drive_vector():
    # No embedder/drive bound → scores are zero → newest-first recency, never dark.
    msgs = [_msg("a", "Rosa", "first"), _msg("b", "Theo", "second"), _msg("c", "Mara", "third")]
    scope = build_city_tool_scope(client=_CityChatClient(msgs), session_id="me")
    res = asyncio.run(scope.call("chatter", ""))["result"]
    assert "Mara:" in res and "Rosa:" in res
    assert res.index("Mara:") < res.index("Rosa:")  # most-recent first


def test_chatter_excludes_the_resident_itself():
    msgs = [_msg("me", "Self", "talking to myself"), _msg("b", "Theo", "my motor is dead")]
    scope = build_city_tool_scope(client=_CityChatClient(msgs), session_id="me")
    res = asyncio.run(scope.call("chatter", ""))["result"]
    assert "Self" not in res and "Theo:" in res


# --- provenance-tagged tool affect: knowing vs reaching (Minor 56) ---


def test_tool_results_carry_a_local_knowledge_provenance_tag():
    scope = build_city_tool_scope(client=_ReadClient(), session_id="s1")
    assert asyncio.run(scope.call("news", ""))["provenance"] == "local-knowledge"
    assert asyncio.run(scope.call("eats", "the Mission"))["provenance"] == "local-knowledge"


def test_advertisement_frames_local_knowledge_tools_as_knowing():
    world = CityWorld(_FakeClient(), build_city_tool_scope())
    scene = asyncio.run(world.get_scene("sess-1"))
    blurbs = " ".join(e.summary for e in scene.recent_events_here)
    assert "USE a tool" in blurbs and "eats" in blurbs  # still advertised
    assert "your own knowing" in blurbs and "not as looking something up" in blurbs  # narrate as knowing
