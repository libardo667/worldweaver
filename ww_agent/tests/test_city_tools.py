"""City source registry + CityWorld wiring: the resident's elective ecology."""

from __future__ import annotations

import asyncio
import json

from src.world.city_tools import build_city_source_registry
from src.world.city_world import CityWorld
from src.world.client import AmbientPresence, PresentCharacter, SceneData, TurnResult
from src.runtime.information import InformationSource, InformationSourceRegistry
from src.runtime.travel import TravelRequest


def _record_text(result: dict) -> str:
    return "\n".join(f"{item.get('title', '')}: {item.get('content', '')}" for item in result.get("records") or [])


# --- the eats source (false egress, local SF knowledge) ---


def test_eats_recommends_real_spots_for_a_known_neighborhood():
    result = asyncio.run(build_city_source_registry().read("eats", "the Mission"))
    assert "La Taqueria" in _record_text(result)
    assert all(record["locality"] == "mission" for record in result["records"])


def test_eats_handles_aliases_and_messy_input():
    registry = build_city_source_registry()
    assert asyncio.run(registry.read("eats", "telegraph hill"))["records"][0]["locality"] == "north beach"
    assert asyncio.run(registry.read("eats", "Outer Sunset District"))["records"][0]["locality"] == "sunset"
    assert asyncio.run(registry.read("eats", "24th and mission"))["records"][0]["locality"] == "mission"


def test_eats_requires_a_real_place_name():
    result = asyncio.run(build_city_source_registry().read("eats", "Atlantis"))
    assert result["ok"] is False
    assert result["reason"] == "unknown_neighborhood"
    assert result["records"] == []


def test_eats_with_no_arg_declines():
    result = asyncio.run(build_city_source_registry().read("eats", ""))
    assert result["ok"] is False
    assert result["reason"] == "unknown_neighborhood"
    assert result["records"] == []


def test_build_city_source_registry_carries_eats():
    registry = build_city_source_registry()
    assert isinstance(registry, InformationSourceRegistry)
    assert "eats" in registry.names
    assert "measure" in registry.names


# --- CityWorld wiring (typed affordance + private access) ---


class _FakeClient:
    """Minimal WorldClient stand-in: records post_action calls, returns a fixed scene."""

    def __init__(self):
        self.posted: list[str] = []
        self.sublocation_flags: list[bool] = []

    async def get_scene(self, session_id: str) -> SceneData:
        return SceneData(
            session_id=session_id,
            location="Mission",
            role="",
            present=[],
            recent_events_here=[],
            location_graph={},
        )

    async def post_action(self, session_id: str, action: str) -> TurnResult:
        self.posted.append(action)
        return TurnResult(narrative=f"[server resolved] {action}", choices=[], vars={})

    async def post_map_move(
        self,
        session_id: str,
        destination: str,
        *,
        allow_sublocation_create: bool = False,
    ) -> dict:
        self.posted.append(destination)
        self.sublocation_flags.append(allow_sublocation_create)
        return {"moved": True, "to_location": destination, "route_remaining": []}

    async def get_travel_destinations(self) -> dict:
        self.travel_discoveries = getattr(self, "travel_discoveries", 0) + 1
        return {
            "destinations": [
                {
                    "route_id": "sf-portland",
                    "nodes": [{"shard_id": "rose-city-coop-1", "shard_url": "https://pdx.example", "status": "healthy"}],
                }
            ]
        }


def test_city_world_intercepts_home_travel_before_the_backend():
    client = _FakeClient()
    world = CityWorld(client, build_city_source_registry())

    result = asyncio.run(world.post_map_move("resident-city", "go home"))

    assert result["travel_pending"] is True
    assert world.take_pending_travel() == TravelRequest("hearth")
    assert world.take_pending_travel() is None
    assert client.posted == []

    action = asyncio.run(world.post_action("resident-city", "go home"))
    assert action.travel_pending is True
    assert world.take_pending_travel() == TravelRequest("hearth")
    assert client.posted == []


def test_city_world_intercepts_an_explicit_live_node_before_the_backend():
    client = _FakeClient()
    world = CityWorld(client, build_city_source_registry())

    result = asyncio.run(world.post_map_move("resident-city", "travel to rose-city-coop-1"))

    assert result["travel_pending"] is True
    assert world.take_pending_travel() == TravelRequest("city", "rose-city-coop-1", "sf-portland", "rose-city-coop-1")
    assert client.posted == []


def test_city_world_does_not_poll_federation_for_an_ordinary_move():
    client = _FakeClient()
    world = CityWorld(client, build_city_source_registry())

    asyncio.run(world.post_map_move("resident-city", "move the cup to the table"))

    assert not hasattr(client, "travel_discoveries")
    assert client.sublocation_flags == [True]


def test_get_scene_advertises_the_sources():
    world = CityWorld(_FakeClient(), build_city_source_registry())
    scene = asyncio.run(world.get_scene("sess-1"))
    assert any(item.name == "eats" for item in scene.affordances)
    assert scene.recent_events_here == []  # a capability is not a fake recent happening


def test_access_information_resolves_a_named_source_locally():
    client = _FakeClient()
    world = CityWorld(client, build_city_source_registry())
    result = asyncio.run(world.access_information(kind="inspect", source="eats", query="north beach"))
    assert result["records"] and all(item["locality"] == "north beach" for item in result["records"])
    assert client.posted == []  # private access never touched the action endpoint


def test_city_world_accepts_the_shared_registry_without_a_city_subclass():
    registry = InformationSourceRegistry([InformationSource(name="plain", description="one shared provider", run=lambda _query: [])])
    world = CityWorld(_FakeClient(), registry)

    scene = asyncio.run(world.get_scene("sess-1"))

    assert [item.name for item in scene.affordances] == ["plain"]


def test_legacy_known_source_do_is_declined_not_narrated_as_world_action():
    client = _FakeClient()
    world = CityWorld(client, build_city_source_registry())
    result = asyncio.run(world.post_action("sess-1", "use eats north beach"))
    assert result.plausible is False
    assert "information source" in result.narrative
    assert client.posted == []


def test_post_action_delegates_a_real_action_to_the_client():
    client = _FakeClient()
    world = CityWorld(client, build_city_source_registry())
    result = asyncio.run(world.post_action("sess-1", "examine the mural"))
    assert "[server resolved]" in result.narrative
    assert client.posted == ["examine the mural"]


def test_unknown_use_target_falls_through_to_the_world():
    client = _FakeClient()
    world = CityWorld(client, build_city_source_registry())
    # "use the payphone" isn't a known source — it's a thing to do in the world
    result = asyncio.run(world.post_action("sess-1", "use the payphone"))
    assert "[server resolved]" in result.narrative
    assert client.posted == ["use the payphone"]


def test_getattr_delegates_unknown_methods_to_the_client():
    client = _FakeClient()
    client.some_helper = lambda: "delegated"  # type: ignore[attr-defined]
    world = CityWorld(client, build_city_source_registry())
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
        json.dumps(
            {
                "event_type": "felt_sense_logged",
                "payload": {"felt_sense": "a quiet settling"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    registry = build_city_source_registry(memory_dir=mem)
    assert "recall" in registry.names
    assert next(source for source in registry.list() if source.name == "recall").provenance == "self-memory"

    overview = _record_text(asyncio.run(registry.read("recall", "")))
    assert "kettle" in overview or "sill" in overview
    assert "quiet settling" in overview

    matched = _record_text(asyncio.run(registry.read("recall", "kettle")))
    assert "kettle" in matched

    miss = asyncio.run(registry.read("recall", "zebra"))
    assert miss["records"] == []


def test_recall_absent_without_a_memory_dir():
    registry = build_city_source_registry()  # no memory dir → no recall source granted
    assert "recall" not in registry.names


# --- world-facing sources: read the world through the client (the server DB) ---


class _WorldFact:
    def __init__(self, summary: str):
        self.summary = summary


class _ReadClient:
    async def get_place_names(self) -> set[str]:
        return {"Alderbank Commons", "Wayfarer Back Room"}

    async def get_news(self) -> list[str]:
        return ["Fog returns to the Sunset", "BART delays on the M-line"]

    async def get_nearby_landmarks(self, location: str, radius_km: float = 0.75) -> list[str]:
        return ["Dolores Park", "Mission Dolores"] if "mission" in location.lower() else []

    async def get_world_facts(self, query: str, session_id=None, limit: int = 5):
        return [_WorldFact(f"Someone was overheard talking about {query} at the taqueria.")] if query else []

    async def get_world_objects(self, session_id: str) -> dict:
        return {
            "objects": [
                {
                    "object_id": "cup-1",
                    "name": "Small clay cup",
                    "description": "A thumb-sized cup made from river clay.",
                    "object_kind": "clay_cup",
                    "relation": "carried",
                    "can_pick_up": False,
                    "revision": 1,
                },
                {
                    "object_id": "token-1",
                    "name": "Wooden token",
                    "description": "A smooth alder token.",
                    "object_kind": "wooden_token",
                    "relation": "here",
                    "can_pick_up": True,
                    "revision": 2,
                },
            ]
        }

    async def get_local_making(self, session_id: str) -> dict:
        return {
            "location": "Alderbank Workshop",
            "materials": [
                {
                    "material_id": "reclaimed_clay",
                    "title": "Reclaimed river clay",
                    "description": "Clay gathered from the riverbank.",
                    "available_units": 8,
                    "capacity_units": 10,
                }
            ],
            "recipes": [
                {
                    "recipe_id": "small_clay_cup",
                    "title": "Small clay cup",
                    "description": "Shape a small cup by hand.",
                    "inputs": {"reclaimed_clay": 2},
                    "can_make": True,
                }
            ],
        }

    async def get_object_exchanges(self, session_id: str) -> dict:
        return {
            "exchanges": [
                {
                    "exchange_id": "exchange-1",
                    "status": "open",
                    "proposer_actor_id": "actor-riley",
                    "recipient_actor_id": "actor-self",
                    "offered_object": {"object_id": "whistle-1", "name": "Reed whistle"},
                    "requested_object": {"object_id": "cup-1", "name": "Small clay cup"},
                    "viewer_role": "recipient",
                    "counterpart_present": True,
                    "can_accept": True,
                    "can_decline": True,
                    "can_cancel": False,
                }
            ],
            "offer_options": [
                {
                    "recipient_actor_id": "actor-riley",
                    "recipient_session_id": "resident-riley",
                    "requested_objects": [{"object_id": "token-riley", "name": "Riley's alder token"}],
                }
            ],
        }

    async def get_space_access_status(self, session_id: str, location: str) -> dict:
        assert location == "Wayfarer Back Room"
        return {
            "access": {
                "location": location,
                "mode": "private",
                "note": "Please knock before entering.",
                "is_controller": True,
                "can_enter": True,
                "can_request": False,
                "active_grants": [{"actor_id": "actor-riley", "session_id": "resident-riley"}],
            }
        }

    async def get_pending_space_access_requests(self, session_id: str, location: str) -> dict:
        return {
            "requests": [
                {
                    "request_id": "request-1",
                    "requester_actor_id": "actor-riley",
                    "requester_session_id": "resident-riley",
                    "note": "May I come in?",
                    "status": "pending",
                }
            ]
        }

    async def get_local_stoops(self, session_id: str) -> dict:
        return {
            "location": "Alderbank Commons",
            "stoops": [
                {
                    "stoop_id": "alderbank-commons-stoop",
                    "title": "The Commons Stoop",
                    "prompt": "Leave something useful or curious.",
                    "active_count": 1,
                }
            ],
        }

    async def browse_world_stoop(self, session_id: str, stoop_id: str) -> dict:
        assert stoop_id == "alderbank-commons-stoop"
        return {
            "entries": [
                {
                    "entry_id": "entry-1",
                    "object": {
                        "object_id": "reed-whistle-1",
                        "name": "Reed whistle",
                        "description": "A small whistle cut from a river reed.",
                    },
                    "can_take": True,
                    "can_withdraw": False,
                }
            ]
        }

    async def get_travel_destinations(self) -> dict:
        return {
            "registry": {"reachable": True},
            "destinations": [
                {
                    "route_id": "sf-portland-coast-starlight",
                    "to_city_id": "portland",
                    "mode": "train",
                    "duration_hours": 17.5,
                    "departure_hub_id": "emeryville-sf-transfer",
                    "departure_hub": "Emeryville / San Francisco transfer",
                    "arrival_hub_id": "portland-union-station",
                    "arrival_hub": "Portland Union Station",
                    "availability": "available",
                    "nodes": [
                        {
                            "shard_id": "rose-city-coop-1",
                            "shard_url": "https://portland.example",
                            "status": "healthy",
                        }
                    ],
                },
                {
                    "route_id": "sf-la-flight",
                    "to_city_id": "los_angeles",
                    "mode": "flight",
                    "departure_hub": "SFO",
                    "arrival_hub": "LAX",
                    "availability": "unhosted",
                    "nodes": [],
                },
            ],
        }

    async def get_scene(self, session_id: str) -> SceneData:
        return SceneData(
            session_id=session_id,
            location="Chinatown",
            role="",
            present=[
                PresentCharacter(
                    name="Riley",
                    role="Riley",
                    last_action="",
                    last_seen="2026-07-18T12:00:00Z",
                    actor_id="actor-riley",
                    session_id="resident-riley",
                )
            ],
            recent_events_here=[],
            location_graph={},
            ambient_presence=[
                AmbientPresence(
                    kind="place_character",
                    label="The street's commerce sets the pace here.",
                    source="neighborhood",
                    intensity=0.6,
                    pressure_tags=["place_character", "commerce"],
                    sensory_note="Steam trays, market calls, and goods changing hands.",
                ),
                AmbientPresence(
                    kind="weather_shelter_cluster",
                    label="People collect under the awnings.",
                    source="grounding",
                    intensity=0.54,
                    pressure_tags=["bad_weather", "shelter"],
                    sensory_note="Damp sleeves and umbrellas crowd the sheltered edge.",
                ),
            ],
        )


def test_news_source_reads_headlines():
    registry = build_city_source_registry(client=_ReadClient())
    res = asyncio.run(registry.read("news", ""))
    assert res["ok"] and "Fog returns to the Sunset" in _record_text(res)
    assert all(item["selection_mode"] == "chronological" for item in res["records"])


def test_places_source_looks_around():
    registry = build_city_source_registry(client=_ReadClient())
    assert "Dolores Park" in _record_text(asyncio.run(registry.read("places", "the Mission")))
    missing = asyncio.run(registry.read("places", ""))
    assert missing["ok"] is False and missing["reason"] == "query_required"


def test_surroundings_is_an_elective_local_perception_source():
    registry = build_city_source_registry(client=_ReadClient(), session_id="s1")

    result = asyncio.run(registry.read("surroundings", ""))

    assert len(result["records"]) == 2
    assert result["provenance"] == "local-perception"
    assert all(item["locality"] == "Chinatown" for item in result["records"])
    assert all(item["selection_mode"] == "embodied_local" for item in result["records"])
    assert "Steam trays" in _record_text(result)


def test_surroundings_can_focus_without_hiding_the_unfiltered_browse():
    registry = build_city_source_registry(client=_ReadClient(), session_id="s1")

    focused = asyncio.run(registry.read("surroundings", "shelter"))
    browse = asyncio.run(registry.read("surroundings", ""))

    assert len(focused["records"]) == 1
    assert focused["records"][0]["selection_mode"] == "text_match"
    assert {item["title"] for item in browse["records"]} == {
        "place character",
        "weather shelter cluster",
    }


def test_investigate_source_queries_the_world():
    registry = build_city_source_registry(client=_ReadClient(), session_id="s1")
    res = asyncio.run(registry.read("investigate", "the rust"))
    assert "the rust" in _record_text(res) and "taqueria" in _record_text(res)


def test_travel_source_shows_live_nodes_without_moving_the_resident():
    registry = build_city_source_registry(client=_ReadClient(), session_id="s1")

    result = asyncio.run(registry.read("travel", "portland"))

    assert len(result["records"]) == 1
    record = result["records"][0]
    assert record["title"] == "portland"
    assert "travel to rose-city-coop-1" in record["content"]
    assert record["metadata"]["route_id"] == "sf-portland-coast-starlight"
    assert record["metadata"]["destination_url"] == "https://portland.example"


def test_travel_source_keeps_unhosted_routes_honest():
    registry = build_city_source_registry(client=_ReadClient(), session_id="s1")

    result = asyncio.run(registry.read("travel", "los_angeles"))

    assert len(result["records"]) == 1
    assert "no destination node is currently available" in result["records"][0]["content"]
    assert result["records"][0]["metadata"]["availability"] == "unhosted"


def test_full_context_grants_the_whole_catalog(tmp_path):
    mem = tmp_path / "m"
    mem.mkdir()
    registry = build_city_source_registry(client=_ReadClient(), session_id="s1", memory_dir=mem)
    assert set(registry.names) >= {
        "eats",
        "recall",
        "news",
        "places",
        "surroundings",
        "investigate",
        "chatter",
        "travel",
    }


def test_alderbank_gets_its_declared_sources_without_san_francisco_material():
    registry = build_city_source_registry(
        client=_ReadClient(),
        session_id="s1",
        city_id="alderbank",
        capabilities={"durable_objects", "replenishing_materials", "making", "witnessed_exchange", "space_permissions", "stoops"},
    )

    assert {"objects", "making", "exchanges", "access", "stoops"}.issubset(registry.names)
    assert "eats" not in registry.names
    assert "news" not in registry.names


def test_objects_source_separates_carried_from_local_objects():
    registry = build_city_source_registry(
        client=_ReadClient(),
        session_id="s1",
        city_id="alderbank",
        capabilities={"durable_objects"},
    )

    result = asyncio.run(registry.read("objects", ""))

    assert {item["title"] for item in result["records"]} == {"Small clay cup", "Wooden token"}
    carried = next(item for item in result["records"] if item["title"] == "Small clay cup")
    assert carried["locality"] == "carried"
    assert carried["metadata"]["object_id"] == "cup-1"
    assert 'target "object-place:cup-1"' in carried["content"]
    assert 'target "object-give:cup-1:resident-riley"' in carried["content"]
    assert carried["metadata"]["give_recipients"] == [{"session_id": "resident-riley", "name": "Riley"}]
    placed = next(item for item in result["records"] if item["title"] == "Wooden token")
    assert 'target "object-pick-up:token-1"' in placed["content"]


def test_making_source_reports_local_availability_without_making_anything():
    registry = build_city_source_registry(
        client=_ReadClient(),
        session_id="s1",
        city_id="alderbank",
        capabilities={"replenishing_materials", "making"},
    )

    result = asyncio.run(registry.read("making", ""))

    assert "8 of 10 units" in _record_text(result)
    recipe = next(item for item in result["records"] if item["metadata"]["kind"] == "recipe")
    assert recipe["metadata"]["can_make"] is True
    assert 'target "recipe:small_clay_cup"' in recipe["content"]


def test_exchanges_source_exposes_exact_two_party_choices_without_moving_objects():
    registry = build_city_source_registry(
        client=_ReadClient(),
        session_id="s1",
        city_id="alderbank",
        capabilities={"durable_objects", "witnessed_exchange"},
    )

    result = asyncio.run(registry.read("exchanges", ""))

    incoming = next(item for item in result["records"] if item["record_id"] == "exchange:exchange-1")
    assert 'target "exchange-accept:exchange-1"' in incoming["content"]
    assert 'target "exchange-decline:exchange-1"' in incoming["content"]
    option = next(item for item in result["records"] if item["record_id"].startswith("exchange-option:"))
    assert "Nothing moves unless they later accept" in option["content"]
    assert 'target "exchange-offer:resident-riley:cup-1:token-riley"' in option["content"]


def test_access_source_requires_a_place_and_exposes_controller_decisions():
    registry = build_city_source_registry(
        client=_ReadClient(),
        session_id="s1",
        city_id="alderbank",
        capabilities={"space_permissions"},
    )

    missing = asyncio.run(registry.read("access", ""))
    result = asyncio.run(registry.read("access", "back room"))

    assert missing["reason"] == "exact_place_required"
    text = _record_text(result)
    assert 'target "access-mode:public:Wayfarer Back Room"' in text
    assert 'target "access-revoke:resident-riley:Wayfarer Back Room"' in text
    assert 'target "access-admit:request-1"' in text
    assert 'target "access-deny:request-1"' in text


def test_access_source_exposes_a_request_without_moving_the_resident():
    class _RequestableAccessClient(_ReadClient):
        async def get_space_access_status(self, session_id: str, location: str) -> dict:
            return {
                "access": {
                    "location": location,
                    "mode": "requestable",
                    "note": "Please ask first.",
                    "is_controller": False,
                    "can_enter": False,
                    "can_request": True,
                    "active_grants": [],
                }
            }

    registry = build_city_source_registry(
        client=_RequestableAccessClient(),
        session_id="s1",
        city_id="alderbank",
        capabilities={"space_permissions"},
    )

    result = asyncio.run(registry.read("access", "Wayfarer Back Room"))

    assert 'target "access-request:Wayfarer Back Room"' in _record_text(result)


def test_stoops_source_lists_before_opening_a_named_stoop():
    registry = build_city_source_registry(
        client=_ReadClient(),
        session_id="s1",
        city_id="alderbank",
        capabilities={"stoops"},
    )

    listed = asyncio.run(registry.read("stoops", ""))
    opened = asyncio.run(registry.read("stoops", "Commons"))

    assert {item["title"] for item in listed["records"]} == {"The Commons Stoop", "Leave Small clay cup"}
    assert "Name this stoop to look inside" in _record_text(listed)
    assert "explicit permission for another visitor" in _record_text(listed)
    assert [item["title"] for item in opened["records"]] == ["Reed whistle"]
    assert opened["records"][0]["metadata"]["can_take"] is True
    assert 'target "stoop-take:entry-1"' in opened["records"][0]["content"]


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
    registry = build_city_source_registry(client=_CityChatClient(msgs), session_id="me")
    drive = asyncio.run(
        DriveVector.build(
            embedder=DeterministicEmbedder(),
            constitution="I mend broken engines with steady hands. I love a dead motor brought back to life.",
        )
    )
    registry.bind_drive(drive)
    res = asyncio.run(registry.read("chatter", ""))
    speakers = [item["title"] for item in res["records"]]
    assert speakers.index("Theo") < speakers.index("Mara")  # engine line outranks dahlias
    assert res["records"][0]["selection_mode"] == "soul_resonance"


def test_chatter_follows_a_named_peer():
    # Following a specific resonant mind (the relational "we" as a curiosity subscription).
    msgs = [
        _msg("a", "Rosa", "the drains again"),
        _msg("b", "Theo", "my motor is dead"),
        _msg("a2", "Rosa", "and the gutters too"),
    ]
    registry = build_city_source_registry(client=_CityChatClient(msgs), session_id="me")
    res = asyncio.run(registry.read("chatter", "Rosa"))
    assert {item["title"] for item in res["records"]} == {"Rosa"}
    assert all(item["selection_mode"] == "named_peer" for item in res["records"])


def test_chatter_falls_back_to_recency_without_a_drive_vector():
    # No embedder/drive bound → scores are zero → newest-first recency, never dark.
    msgs = [
        _msg("a", "Rosa", "first"),
        _msg("b", "Theo", "second"),
        _msg("c", "Mara", "third"),
    ]
    registry = build_city_source_registry(client=_CityChatClient(msgs), session_id="me")
    res = asyncio.run(registry.read("chatter", ""))
    speakers = [item["title"] for item in res["records"]]
    assert speakers.index("Mara") < speakers.index("Rosa")  # most-recent first
    assert all(item["selection_mode"] == "chronological" for item in res["records"])


def test_chatter_excludes_the_resident_itself():
    msgs = [
        _msg("me", "Self", "talking to myself"),
        _msg("b", "Theo", "my motor is dead"),
    ]
    registry = build_city_source_registry(client=_CityChatClient(msgs), session_id="me")
    res = asyncio.run(registry.read("chatter", ""))
    assert [item["title"] for item in res["records"]] == ["Theo"]


# --- provenance-tagged source affect: knowing vs reaching (Minor 56) ---


def test_source_records_carry_a_local_knowledge_provenance_tag():
    registry = build_city_source_registry(client=_ReadClient(), session_id="s1")
    assert asyncio.run(registry.read("news", ""))["provenance"] == "local-knowledge"
    assert asyncio.run(registry.read("eats", "the Mission"))["provenance"] == "local-knowledge"


def test_advertisement_frames_local_knowledge_sources_as_knowing():
    world = CityWorld(_FakeClient(), build_city_source_registry())
    scene = asyncio.run(world.get_scene("sess-1"))
    eats = next(item for item in scene.affordances if item.name == "eats")
    assert eats.source_id == "source:eats"
    assert eats.provenance == "local-knowledge"
    assert (eats.freshness, eats.locality, eats.visibility, eats.selection_mode) == (
        "stable",
        "San Francisco",
        "private",
        "neighborhood_match",
    )
