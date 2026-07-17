from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

from src.identity.loader import LoopTuning, ResidentIdentity
from src.inference.client import InferenceError
from src.runtime.cognitive_core import CognitiveCore
from src.runtime.effectors import WorldEffector
from src.runtime.ledger import derive_packets, load_runtime_events
from src.runtime.perception import OVERHEARD_FLOOR, perceive
from src.runtime.pulse import Act
from src.runtime.pulse_engine import LLMPulseProducer, _pulse_contract
from src.runtime.prompt_context import PulseContext, render_pulse_context
from src.runtime.salience import stimulus_from_substrate
from src.runtime.signals import StimulusPacketQueue

T0 = datetime(2026, 6, 2, 12, 0, 0, tzinfo=timezone.utc)


def _identity(name: str = "sun_li") -> ResidentIdentity:
    return ResidentIdentity(
        name=name,
        actor_id="actor-123",
        soul="You are Sun Li, a watchful tea-seller in Chinatown.",
        canonical_soul="You are Sun Li, a watchful tea-seller in Chinatown.",
        growth_soul="",
        vibe="watchful",
        core="Keeps a small tea stall.",
        voice_seed=["Tea?"],
        tuning=LoopTuning(),
    )


def _events_by_type(memory_dir, event_type):
    return [e for e in load_runtime_events(memory_dir) if str(e.get("event_type") or "").strip() == event_type]


def _packets_of_type(memory_dir, packet_type):
    return [p for p in derive_packets(memory_dir) if str(p.get("packet_type") or "").strip() == packet_type]


class _Scene:
    def __init__(
        self,
        *,
        location="Chinatown",
        present=None,
        recent=None,
        ambient=None,
        traces=None,
    ):
        self.location = location
        self.present = present or []
        self.recent_events_here = recent or []
        self.location_graph = {"nodes": [], "edges": []}
        self.ambient_presence = ambient or []
        self.traces_here = traces or []
        self.affordances = []


class _Person:
    def __init__(self, name, *, actor_id="", session_id=""):
        self.name = name
        self.role = ""
        self.last_action = ""
        self.last_seen = ""
        self.actor_id = actor_id
        self.session_id = session_id


class _Event:
    def __init__(self, who, summary, *, event_id="event-1", event_type="freeform_action"):
        self.who = who
        self.summary = summary
        self.ts = ""
        self.event_id = event_id
        self.event_type = event_type


class _WorldTrace:
    def __init__(
        self,
        trace_id: str,
        body: str,
        *,
        author_name: str = "Mei",
        target: str = "the lintel",
    ):
        self.trace_id = trace_id
        self.source_id = trace_id
        self.author_session_id = "mei-1"
        self.author_name = author_name
        self.location = "Chinatown"
        self.target = target
        self.body = body
        self.created_at = "2026-06-02T11:00:00+00:00"
        self.expires_at = "2026-06-16T11:00:00+00:00"
        self.provenance = "physical_trace"
        self.freshness = "active"
        self.locality = "Chinatown"
        self.visibility = "local"
        self.selection_mode = "embodied_local"


class _Chat:
    def __init__(self, session_id, display_name, message, ts="2026-06-02T12:00:00+00:00", *, actor_id=""):
        self.id = 1
        self.session_id = session_id
        self.actor_id = actor_id
        self.display_name = display_name
        self.message = message
        self.ts = ts
        self.location = ""


class _Letter:
    def __init__(self, filename, body):
        self.filename = filename
        self.body = body


class _StubWorld:
    def __init__(
        self,
        scene: _Scene,
        *,
        local_chat=None,
        city_chat=None,
        inbox=None,
        grounding=None,
    ):
        self._scene = scene
        self._local_chat = local_chat or []
        self._city_chat = city_chat or []
        self._inbox = inbox or []
        self._grounding = grounding or {}
        self.location_chats: list[dict] = []
        self.actions: list[str] = []
        self.moves: list[str] = []
        self.letters: list[dict] = []
        self.world_traces: list[dict] = []
        self.place_names = {"North Beach", "Chinatown"}

    async def get_scene(self, session_id):
        return self._scene

    async def get_location_chat(self, location, since=None):
        return list(self._city_chat if location == "__city__" else self._local_chat)

    async def get_inbox(self, agent_name):
        return list(self._inbox)

    async def get_grounding(self):
        return dict(self._grounding)

    async def get_place_names(self):
        return set(self.place_names)

    async def post_location_chat(self, location, session_id, message, display_name=None):
        self.location_chats.append({"location": location, "message": message, "display_name": display_name})
        return {"id": 1}

    async def post_map_move(self, session_id, destination):
        self.moves.append(destination)
        return {"moved": True, "to_location": destination, "route_remaining": []}

    async def post_action(self, session_id, action):
        self.actions.append(action)
        return type("TR", (), {"narrative": f"{action}."})()

    async def post_world_trace(self, session_id, body, target=""):
        trace = {
            "trace_id": f"trace:{len(self.world_traces) + 1}",
            "location": self._scene.location,
            "target": target,
            "body": body,
            "expires_at": "2026-06-16T11:00:00+00:00",
        }
        self.world_traces.append(trace)
        return {"ok": True, "trace": trace}

    async def send_letter(self, from_name, to_agent, body, session_id, *, recipient_type="agent"):
        self.letters.append({"from_name": from_name, "to_agent": to_agent, "body": body})
        return {"ok": True}


class _StubLLM:
    def __init__(self, *, json_response=None, raise_inference=False):
        self.json_response = json_response
        self.raise_inference = raise_inference
        self.calls: list[dict] = []

    async def complete_json(self, system_prompt, user_prompt, **kwargs):
        self.calls.append({"system": system_prompt, "user": user_prompt, **kwargs})
        if self.raise_inference:
            raise InferenceError("boom")
        return dict(self.json_response or {})


# --- effectors ------------------------------------------------------------


def test_effector_speak_routes_local_and_city(tmp_path):
    world = _StubWorld(_Scene())
    eff = WorldEffector(
        ww_client=world,
        session_id="s1",
        identity=_identity(),
        memory_dir=tmp_path,
        location_hint="Chinatown",
    )
    eff.co_present = [{"actor_id": "actor-levi", "session_id": "levi-1", "name": "Levi"}]

    asyncio.run(eff(Act(kind="speak", body="Tea's fresh.", target=None)))
    asyncio.run(eff(Act(kind="speak", body="Market opens at dawn!", target="city")))

    assert world.location_chats[0]["location"] == "Chinatown"
    assert world.location_chats[1]["location"] == "__city__"
    assert len(_events_by_type(tmp_path, "chat_sent")) == 1
    assert len(_events_by_type(tmp_path, "city_broadcast_sent")) == 1
    local = _events_by_type(tmp_path, "chat_sent")[0]["payload"]
    assert local["edge_schema_version"] == 1
    assert local["actor_id"] == "actor-123"
    assert local["actor_session_id"] == "s1"
    assert local["co_present"] == ["actor-levi"]
    assert local["utterance_id"] == "chat:Chinatown:1"


def test_effector_carries_absent_address_privately(tmp_path):
    # Major 63 — speech is physical: addressing an absent person is a *directed carry*
    # (a private word sent to them), NOT a citywide broadcast, so directed speech can't
    # saturate the commons into one shared feed.
    world = _StubWorld(_Scene())
    eff = WorldEffector(
        ww_client=world,
        session_id="s1",
        identity=_identity(),
        memory_dir=tmp_path,
        location_hint="Chinatown",
    )
    eff.present = ["Levi"]  # Levi is here; Anika is across the city

    asyncio.run(eff(Act(kind="speak", body="Here's your tea.", target="Levi")))  # co-located → the room
    asyncio.run(eff(Act(kind="speak", body="The hum is tighter, Anika.", target="Anika Vance")))  # absent → carry

    assert world.location_chats[0]["location"] == "Chinatown"  # present target → the room
    assert len(world.location_chats) == 1  # the absent one did NOT hit any chat
    assert world.letters[-1]["to_agent"] == "Anika Vance"  # it was carried privately
    assert len(_events_by_type(tmp_path, "chat_sent")) == 1
    assert len(_events_by_type(tmp_path, "city_broadcast_sent")) == 0  # nothing saturated the commons
    assert len(_events_by_type(tmp_path, "speech_carried")) == 1


def test_effector_seals_speech_to_workshop_during_incubation(tmp_path):
    # Incubation (arrival quarantine): a sealed resident's speak becomes its OWN making,
    # never the commons — and the workshop entry it leaves is exactly what accrues the
    # groundedness that ends the quarantine.
    from src.runtime.workshop import Workshop

    world = _StubWorld(_Scene())
    eff = WorldEffector(
        ww_client=world,
        session_id="s1",
        identity=_identity(),
        memory_dir=tmp_path,
        location_hint="Chinatown",
        workshop=Workshop(tmp_path / "workshop"),
    )
    eff.incubating = True

    res = asyncio.run(eff(Act(kind="speak", body="The fog is thick on the hill today.", target="city")))

    assert res["executed"] and res.get("incubated") is True
    assert world.location_chats == []  # nothing reached the commons
    assert len(_events_by_type(tmp_path, "city_broadcast_sent")) == 0
    assert len(_events_by_type(tmp_path, "workshop_entry")) == 1  # it became a making instead

    # And once it hatches, speech reaches the world normally again.
    eff.incubating = False
    asyncio.run(eff(Act(kind="speak", body="Morning!", target="city")))
    assert world.location_chats[-1]["location"] == "__city__"
    assert len(_events_by_type(tmp_path, "city_broadcast_sent")) == 1


def test_effector_mail_stamps_reply_edge_when_recipient_was_heard(tmp_path):
    # Major 66: a letter to someone heard this tick carries in_reply_to pointing at
    # their overture's stable id; a letter to someone not heard carries None.
    world = _StubWorld(_Scene())
    eff = WorldEffector(
        ww_client=world,
        session_id="s1",
        identity=_identity(),
        memory_dir=tmp_path,
        location_hint="Chinatown",
    )
    eff.heard = [
        {
            "speaker": "Levi",
            "id": "msg-42",
            "source_id": "chat:Chinatown:msg-42",
            "message": "did the engine start?",
        }
    ]

    asyncio.run(eff(Act(kind="write", body="Not yet — needs a new coil.", target="Levi")))
    asyncio.run(eff(Act(kind="write", body="Thinking of you.", target="Anika Vance")))

    mail = _events_by_type(tmp_path, "mail_intent_sent")
    assert len(mail) == 2
    by_recipient = {e["payload"]["recipient"]: e["payload"].get("in_reply_to") for e in mail}
    assert by_recipient["Levi"] == "msg-42"  # heard this tick → reply-edge
    assert by_recipient["Anika Vance"] is None  # not heard → unprompted, no edge
    assert mail[0]["payload"]["reply_to_utterance_id"] == "chat:Chinatown:msg-42"


def test_effector_rations_the_megaphone(tmp_path):
    # Cost the megaphone: the first citywide broadcast goes through; a second inside the
    # cooldown lands in the ROOM instead (logged as a local chat_sent), so the loud
    # majority can't saturate the commons by sheer volume.
    world = _StubWorld(_Scene())
    eff = WorldEffector(
        ww_client=world,
        session_id="s1",
        identity=_identity(),
        memory_dir=tmp_path,
        location_hint="Chinatown",
    )
    eff._broadcast_refractory = 300.0

    asyncio.run(eff(Act(kind="speak", body="Hear me, city!", target="city")))  # 1st → broadcast
    asyncio.run(eff(Act(kind="speak", body="And again!", target="city")))  # 2nd → rationed to the room

    assert world.location_chats[0]["location"] == "__city__"
    assert world.location_chats[1]["location"] == "Chinatown"  # cooldown sent it to the room
    assert len(_events_by_type(tmp_path, "city_broadcast_sent")) == 1
    assert len(_events_by_type(tmp_path, "chat_sent")) == 1  # the rationed one logged as local


def test_effector_move_do_write(tmp_path):
    world = _StubWorld(_Scene())
    eff = WorldEffector(
        ww_client=world,
        session_id="s1",
        identity=_identity(),
        memory_dir=tmp_path,
        location_hint="Chinatown",
    )

    move = asyncio.run(eff(Act(kind="move", body="go north", target="North Beach")))
    do = asyncio.run(eff(Act(kind="do", body="straighten the tea cups", target=None)))
    write = asyncio.run(eff(Act(kind="write", body="Come by the stall.", target="Levi")))

    assert move["executed"] and world.moves == ["North Beach"]
    assert do["executed"] and world.actions == ["straighten the tea cups"]
    assert write["executed"] and world.letters[0]["to_agent"] == "Levi"
    assert len(_events_by_type(tmp_path, "move_executed")) == 1
    assert len(_events_by_type(tmp_path, "action_executed")) == 1
    assert len(_events_by_type(tmp_path, "mail_intent_sent")) == 1


def test_effector_leaves_a_narrator_free_physical_trace(tmp_path):
    world = _StubWorld(_Scene())
    eff = WorldEffector(ww_client=world, session_id="s1", identity=_identity(), memory_dir=tmp_path)

    result = asyncio.run(eff(Act(kind="mark", body="three blue chalk lines", target="the lintel")))

    assert result["executed"] is True
    assert world.world_traces[0]["body"] == "three blue chalk lines"
    assert world.actions == []
    assert _events_by_type(tmp_path, "world_trace_left")[0]["payload"]["trace_id"] == "trace:1"


def test_mark_is_advertised_only_when_the_world_has_a_trace_commons():
    assert "kind is exactly one of speak, move, do, write, mark" in _pulse_contract(can_mark_world=True)
    familiar_contract = _pulse_contract(can_mark_world=False)
    assert "kind is exactly one of speak, move, do, write." in familiar_contract
    assert "mark leaves a slow physical trace" not in familiar_contract


def test_pulse_contract_explains_the_physical_reach_of_speech():
    contract = _pulse_contract(can_mark_world=False)

    assert "speech without a target is heard only in your current room" in contract
    assert "carried privately when" in contract
    assert 'Use target "city" only when you mean to address everyone' in contract
    assert "not the way to reach one absent person" in contract


def test_effector_write_without_recipient_is_dropped(tmp_path):
    world = _StubWorld(_Scene())
    eff = WorldEffector(ww_client=world, session_id="s1", identity=_identity(), memory_dir=tmp_path)
    result = asyncio.run(eff(Act(kind="write", body="orphan letter", target=None)))
    assert result["executed"] is False and world.letters == []


# --- perception -----------------------------------------------------------


def test_perceive_emits_ambient_pressure_and_returns_brief(tmp_path):
    world = _StubWorld(
        _Scene(
            present=[
                _Person("Sun Li", actor_id="actor-123", session_id="sun-li-1"),
                _Person("Levi", actor_id="actor-levi", session_id="levi-1"),
                _Person("Mei", actor_id="actor-mei", session_id="mei-1"),
            ],
            recent=[_Event("Levi", "set down a crate")],
        )
    )
    brief = asyncio.run(perceive(ww_client=world, session_id="s1", memory_dir=tmp_path, self_name="Sun Li"))

    assert brief["location"] == "Chinatown"
    assert brief["present"] == ["Levi", "Mei"]  # self excluded
    assert [item["actor_id"] for item in brief["co_present"]] == ["actor-levi", "actor-mei"]
    assert len(_events_by_type(tmp_path, "ambient_pressure_observed")) == 1
    ambient = _events_by_type(tmp_path, "ambient_pressure_observed")[0]["payload"]
    assert ambient["co_present"] == ["actor-levi", "actor-mei"]
    # Crowding perturbation flows into the substrate as vigilance activation.
    stimulus = stimulus_from_substrate(tmp_path)
    assert stimulus["self"]["vigilance"] > 0.0


def test_physical_trace_is_bounded_and_consume_on_prompt(tmp_path):
    world = _StubWorld(
        _Scene(
            traces=[
                _WorldTrace("trace:1", "three blue chalk lines"),
                _WorldTrace("trace:2", "a paper crane", target="the sill"),
            ]
        )
    )

    first = asyncio.run(perceive(ww_client=world, session_id="s1", memory_dir=tmp_path, identity=_identity()))
    second = asyncio.run(perceive(ww_client=world, session_id="s1", memory_dir=tmp_path, identity=_identity()))
    assert [item["trace_id"] for item in first["traces"]] == ["trace:1"]
    assert [item["trace_id"] for item in second["traces"]] == ["trace:1"]

    context = PulseContext.from_perception(first, mode="react")
    rendered = render_pulse_context(context)
    assert "three blue chalk lines" in rendered
    assert "a paper crane" not in rendered
    packet_id = context.prompted_packet_ids[0]
    StimulusPacketQueue(tmp_path / "stimulus_packets.json").mark_status(packet_id, "observed")

    third = asyncio.run(perceive(ww_client=world, session_id="s1", memory_dir=tmp_path, identity=_identity()))
    assert [item["trace_id"] for item in third["traces"]] == ["trace:2"]
    settling = PulseContext.from_perception(third, mode="settling")
    assert settling.selected_physical_traces == ()
    assert "a paper crane" not in render_pulse_context(settling)
    assert settling.prompted_packet_ids == []


def test_perceive_senses_direct_chat_and_mail(tmp_path):
    world = _StubWorld(
        _Scene(present=[_Person("Levi")]),
        local_chat=[_Chat("other-1", "Levi", "Sun Li, can you bring tea?", actor_id="actor-levi")],
        inbox=[_Letter("from_mei_20260602.md", "Are you well?")],
    )
    brief = asyncio.run(perceive(ww_client=world, session_id="s1", memory_dir=tmp_path, identity=_identity()))

    # A direct, addressed request is heard and laid down as a chat packet.
    assert any(h["is_direct"] for h in brief["heard"])
    assert brief["heard"][0]["speaker_actor_id"] == "actor-levi"
    assert brief["heard"][0]["speaker_session_id"] == "other-1"
    assert len(_packets_of_type(tmp_path, "chat_heard")) == 1
    # The inbox letter becomes a mail_received perturbation.
    assert brief["inbox_count"] == 1
    assert len(_packets_of_type(tmp_path, "mail_received")) == 1
    # Both light up the social/correspondence substrate as stimulus.
    stimulus = stimulus_from_substrate(tmp_path)
    assert stimulus["self"].get("social_pull", 0.0) > 0.0
    assert stimulus["self"].get("correspondence_pull", 0.0) > 0.0


def test_perceive_surfaces_reachable_destinations(tmp_path):
    graph = {
        "nodes": [
            {"key": "location:inner richmond", "name": "Inner Richmond"},
            {"key": "location:presidio", "name": "Presidio"},
            {"key": "location:laurel heights", "name": "Laurel Heights"},
            {"key": "location:castro", "name": "Castro"},
        ],
        "edges": [
            {"from": "location:inner richmond", "to": "location:presidio"},
            {"from": "location:laurel heights", "to": "location:inner richmond"},
            {"from": "location:castro", "to": "location:alamo square"},
        ],
    }
    world = _StubWorld(_Scene(location="Inner Richmond"))
    world._scene.location_graph = graph
    brief = asyncio.run(perceive(ww_client=world, session_id="s1", memory_dir=tmp_path, identity=_identity()))
    # Adjacency works in both edge directions; non-adjacent Castro is excluded.
    assert brief["reachable"] == ["Laurel Heights", "Presidio"]


def test_perceive_grounds_in_real_time_and_weather(tmp_path):
    world = _StubWorld(
        _Scene(),
        grounding={
            "time_of_day": "night",
            "weather": "Heavy Rain",
            "temperature_f": 52,
            "day_of_week": "Friday",
        },
    )
    brief = asyncio.run(perceive(ww_client=world, session_id="s1", memory_dir=tmp_path, identity=_identity()))

    assert brief["grounding"]["time_of_day"] == "night"
    assert brief["grounding"]["resting_hours"] is True
    # Rain raises vigilance (bad_weather); night raises the rest drive (circadian).
    stimulus = stimulus_from_substrate(tmp_path)
    assert stimulus["self"].get("vigilance", 0.0) > 0.0
    assert stimulus["self"].get("rest_drive", 0.0) > 0.0


def test_perceive_dedupes_repeated_chat_and_mail(tmp_path):
    world = _StubWorld(
        _Scene(),
        local_chat=[_Chat("other-1", "Levi", "Morning!")],
        inbox=[_Letter("from_levi_1.md", "hi")],
    )
    asyncio.run(perceive(ww_client=world, session_id="s1", memory_dir=tmp_path, identity=_identity()))
    asyncio.run(perceive(ww_client=world, session_id="s1", memory_dir=tmp_path, identity=_identity()))
    # Re-polling the same chat/mail does not double-emit (emit_once dedup).
    assert len(_packets_of_type(tmp_path, "chat_heard")) == 1
    assert len(_packets_of_type(tmp_path, "mail_received")) == 1


def test_heard_chat_stays_pending_until_prompt_consumption(tmp_path):
    world = _StubWorld(
        _Scene(),
        local_chat=[_Chat("other-1", "Levi", "The kettle is ready.")],
    )

    first = asyncio.run(perceive(ww_client=world, session_id="s1", memory_dir=tmp_path, identity=_identity()))
    second = asyncio.run(perceive(ww_client=world, session_id="s1", memory_dir=tmp_path, identity=_identity()))

    # Re-polling does not manufacture a second encounter, but a quiet tick also
    # cannot erase the first one before any prompt has carried it.
    assert len(_packets_of_type(tmp_path, "chat_heard")) == 1
    assert second["heard"] == first["heard"]
    packet_id = first["heard"][0]["packet_id"]

    StimulusPacketQueue(tmp_path / "stimulus_packets.json").mark_status(packet_id, "observed")
    third = asyncio.run(perceive(ww_client=world, session_id="s1", memory_dir=tmp_path, identity=_identity()))

    assert third["heard"] == []
    assert _packets_of_type(tmp_path, "chat_heard")[0]["status"] == "observed"


def test_perceive_does_not_repeat_utterance_as_world_event(tmp_path):
    world = _StubWorld(
        _Scene(
            recent=[
                _Event("Levi", "Levi said hello.", event_id="41", event_type="utterance"),
                _Event(
                    "Mei",
                    "Mei entered the market.",
                    event_id="42",
                    event_type="movement",
                ),
            ]
        ),
        local_chat=[_Chat("other-1", "Levi", "hello")],
    )

    brief = asyncio.run(perceive(ww_client=world, session_id="s1", memory_dir=tmp_path, identity=_identity()))

    assert [event["event_id"] for event in brief["recent_events"]] == ["42"]
    assert brief["recent_events"][0]["event_type"] == "movement"
    assert [line["message"] for line in brief["heard"] if line["channel"] == "local"] == ["hello"]


def test_legacy_pending_chat_is_not_replayed_or_allowed_to_block_fresh_overhearing(
    tmp_path,
):
    packets = StimulusPacketQueue(tmp_path / "stimulus_packets.json")
    packets.emit(
        packet_type="city_chat_heard",
        source_loop="perceive",
        dedupe_key="legacy-city-line",
        location="__city__",
        payload={
            "speaker": "Old Voice",
            "message": "a line from before delivery tracking",
        },
    )
    world = _StubWorld(
        _Scene(),
        city_chat=[_Chat("fresh-1", "Mei", "Fresh oranges at the corner.")],
    )

    brief = asyncio.run(perceive(ww_client=world, session_id="s1", memory_dir=tmp_path, identity=_identity()))

    overheard = [line for line in brief["heard"] if line.get("overheard")]
    assert [line["message"] for line in overheard] == ["Fresh oranges at the corner."]
    assert all(line["speaker"] != "Old Voice" for line in brief["heard"])


# --- the unchosen channel: content-blind floor + traversal (Major 60) ---


def test_perceive_citywide_is_a_content_blind_floor_not_a_push(tmp_path):
    # The old behavior pushed ALL citywide messages into every mind every tick (the
    # topic-monoculture engine). A parked resident now overhears only a small,
    # content-blind slice — but it still lights up social_pull (the node mapping is unchanged).
    city = [_Chat(f"o{i}", f"Person{i}", f"citywide message number {i}") for i in range(12)]
    world = _StubWorld(_Scene(present=[_Person("Levi")]), city_chat=city)
    brief = asyncio.run(perceive(ww_client=world, session_id="s1", memory_dir=tmp_path, identity=_identity()))

    overheard = [h for h in brief["heard"] if h.get("overheard")]
    assert 0 < len(overheard) <= 3  # a small slice, never the whole 12-message feed
    assert len(_packets_of_type(tmp_path, "city_chat_heard")) == OVERHEARD_FLOOR  # parked → the floor
    stimulus = stimulus_from_substrate(tmp_path)
    assert stimulus["self"].get("social_pull", 0.0) > 0.0


def test_perceive_in_transit_overhears_more_of_the_unchosen(tmp_path):
    # Traversal rations diversity: a moving resident (crossed to a new place since the
    # last tick) overhears more of the un-chosen en route than a parked one.
    city = [_Chat(f"o{i}", f"Person{i}", f"message number {i}") for i in range(12)]
    world = _StubWorld(_Scene(location="Chinatown"), city_chat=city)
    asyncio.run(perceive(ww_client=world, session_id="s1", memory_dir=tmp_path, identity=_identity()))  # establishes location
    world._scene.location = "North Beach"  # crossed the city
    brief2 = asyncio.run(perceive(ww_client=world, session_id="s1", memory_dir=tmp_path, identity=_identity()))
    overheard2 = [h for h in brief2["heard"] if h.get("overheard")]
    assert len(overheard2) > OVERHEARD_FLOOR  # in transit overhears more than the parked floor


# --- pulse engine ---------------------------------------------------------


def test_pulse_engine_produces_valid_pulse(tmp_path):
    llm = _StubLLM(
        json_response={
            "felt_sense": "the stall feels exposed",
            "act": {"kind": "speak", "body": "Who's there?", "target": None},
            "expectations": [
                {
                    "features": {"vigilance": 0.8},
                    "scope": "self",
                    "confidence": 0.9,
                    "half_life": 600,
                }
            ],
        }
    )
    producer = LLMPulseProducer(llm=llm, identity=_identity(), memory_dir=tmp_path)
    producer.latest_perception = {
        "location": "Chinatown",
        "present": ["Levi"],
        "recent_events": [],
    }

    pulse = asyncio.run(
        producer(
            traces=[
                {
                    "trace_id": "tr-1",
                    "features": [
                        {
                            "scope": "self",
                            "tag": "vigilance",
                            "delta": 0.8,
                            "stimulus": 0.8,
                            "predicted": 0.0,
                        }
                    ],
                }
            ],
            stimulus={"self": {"vigilance": 0.8}},
            arousal=1.2,
        )
    )
    assert pulse is not None
    assert pulse.act.kind == "speak"
    assert pulse.expectations[0].features == {"vigilance": 0.8}
    # The igniting trace and the soul are both present in the assembled prompt.
    assert "vigilance" in llm.calls[0]["user"]
    assert "Sun Li" in llm.calls[0]["system"]


def test_pulse_engine_records_exact_private_prompt_trace_outside_ledger(tmp_path, monkeypatch):
    monkeypatch.delenv("WW_PROMPT_TRACE", raising=False)
    llm = _StubLLM(json_response={"felt_sense": "steam and footsteps", "act": None})
    producer = LLMPulseProducer(
        llm=llm,
        identity=_identity(),
        memory_dir=tmp_path,
        model="test/model",
        temperature=0.42,
    )
    producer.latest_perception = {
        "location": "Chinatown",
        "heard": [{"id": "msg-7", "speaker": "Mei", "message": "Tea?", "channel": "local"}],
        "recent_events": [{"event_id": "world-9", "summary": "A cart arrived."}],
    }
    traces = [
        {
            "trace_id": "tr-1",
            "features": [
                {
                    "scope": "self",
                    "tag": "social_pull",
                    "delta": 0.6,
                    "stimulus": 0.6,
                    "predicted": 0.0,
                }
            ],
        }
    ]

    pulse = asyncio.run(producer(traces=traces, stimulus={"self": {"social_pull": 0.6}}, arousal=1.1))

    assert pulse is not None
    records = [json.loads(line) for line in (tmp_path / "prompt_traces.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [record["record_type"] for record in records] == [
        "prompt_assembled",
        "completion_received",
    ]
    prompt, completion = records
    assert prompt["prompt_trace_id"] == completion["prompt_trace_id"]
    assert prompt["messages"] == [
        {"role": "system", "content": llm.calls[0]["system"]},
        {"role": "user", "content": llm.calls[0]["user"]},
    ]
    assert prompt["inference"]["model"] == "test/model"
    assert prompt["inference"]["temperature"] == 0.42
    assert prompt["source_context"]["perception"]["heard"][0]["id"] == "msg-7"
    assert prompt["source_context"]["traces"][0]["trace_id"] == "tr-1"
    assert completion["raw_response"]["felt_sense"] == "steam and footsteps"
    assert load_runtime_events(tmp_path) == []  # diagnostics never enter the cognitive ledger


def test_prompt_trace_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("WW_PROMPT_TRACE", "0")
    producer = LLMPulseProducer(llm=_StubLLM(json_response={}), identity=_identity(), memory_dir=tmp_path)

    assert asyncio.run(producer(traces=[], stimulus={}, arousal=1.0)) is not None
    assert not (tmp_path / "prompt_traces.jsonl").exists()


def test_settling_prompt_withholds_rolling_social_and_event_material(tmp_path):
    llm = _StubLLM(json_response={"felt_sense": "the quiet belongs to me", "act": None})
    producer = LLMPulseProducer(llm=llm, identity=_identity(), memory_dir=tmp_path)
    producer.latest_perception = {
        "location": "Chinatown",
        "present": ["Levi"],
        "grounding": {"time_of_day": "evening"},
        "reachable": ["North Beach"],
        "affordances": [
            {
                "source_id": "source:eats",
                "name": "eats",
                "description": "recommend a good bite nearby — use eats <place>",
                "provenance": "local-knowledge",
            }
        ],
        "inbox_count": 2,
        "heard": [
            {
                "packet_id": "pkt-social-1",
                "source_id": "chat:Chinatown:8",
                "id": "8",
                "speaker": "Levi",
                "message": "The conduit fault is spreading.",
                "channel": "local",
            }
        ],
        "recent_events": [
            {
                "event_id": "event-9",
                "event_type": "freeform_action",
                "who": "Mei",
                "summary": "Mei inspected the civic relay.",
            }
        ],
        "anchors": [{"anchor": "the civic relay", "salience": 0.8}],
    }

    asyncio.run(producer(traces=[], stimulus={}, arousal=0.0, mode="settling"))

    prompt = llm.calls[0]["user"]
    assert "Chinatown" in prompt and "It is evening" in prompt
    assert "North Beach" in prompt  # concrete movement remains available
    assert "recommend a good bite nearby" in prompt  # typed capability, not a recent event
    assert '"reach": null OR' in prompt
    assert "conduit fault" not in prompt
    assert "civic relay" not in prompt
    assert "Letters waiting" not in prompt
    assert producer.take_prompted_packet_ids() == []

    trace = json.loads((tmp_path / "prompt_traces.jsonl").read_text(encoding="utf-8").splitlines()[0])
    context = trace["source_context"]["prompt_context"]
    assert context["policy"]["include_heard"] is False
    assert context["selected"]["heard"] == []
    assert context["selected"]["affordances"][0]["source_id"] == "source:eats"
    assert context["withheld"]["heard"][0]["packet_id"] == "pkt-social-1"
    assert context["withheld"]["recent_events"][0]["event_id"] == "event-9"


def test_reactive_prompt_selects_only_rendered_encounter_ids(tmp_path):
    llm = _StubLLM(json_response={"felt_sense": "several voices", "act": None})
    producer = LLMPulseProducer(llm=llm, identity=_identity(), memory_dir=tmp_path)
    producer.latest_perception = {
        "location": "Chinatown",
        "heard": [
            {
                "packet_id": f"pkt-{index}",
                "source_id": f"chat:Chinatown:{index}",
                "id": str(index),
                "speaker": f"Person {index}",
                "message": f"line {index}",
                "channel": "local",
            }
            for index in range(5)
        ],
    }

    asyncio.run(producer(traces=[], stimulus={}, arousal=1.0, mode="react"))

    assert "line 0" not in llm.calls[0]["user"]
    assert all(f"line {index}" in llm.calls[0]["user"] for index in range(1, 5))
    assert producer.take_prompted_packet_ids() == ["pkt-1", "pkt-2", "pkt-3", "pkt-4"]
    trace = json.loads((tmp_path / "prompt_traces.jsonl").read_text(encoding="utf-8").splitlines()[0])
    context = trace["source_context"]["prompt_context"]
    assert [item["packet_id"] for item in context["withheld"]["heard"]] == ["pkt-0"]


def test_reach_continuation_returns_chosen_result_without_reperception(tmp_path):
    llm = _StubLLM(json_response={"felt_sense": "the market answer is enough", "act": None})
    producer = LLMPulseProducer(llm=llm, identity=_identity(), memory_dir=tmp_path)
    producer.latest_perception = {
        "affordances": [
            {
                "source_id": "source:eats",
                "name": "eats",
                "description": "find a bite nearby",
                "provenance": "local-knowledge",
            },
            {
                "source_id": "source:places",
                "name": "places",
                "description": "inspect nearby landmarks",
                "provenance": "local-knowledge",
            },
        ]
    }

    pulse = asyncio.run(
        producer.continue_reach(
            request={"kind": "inspect", "source": "eats", "query": "North Beach"},
            result={
                "detail": "[eats | neighborhood_match | stable] Grant Bakery\nopens at six",
                "records": [
                    {
                        "record_id": "eats:north-beach:grant-bakery",
                        "source": "eats",
                        "title": "Grant Bakery",
                        "content": "opens at six",
                        "provenance": "local-knowledge",
                        "freshness": "stable",
                        "locality": "North Beach",
                        "visibility": "private",
                        "selection_mode": "neighborhood_match",
                    }
                ],
            },
            prior_felt="hungry and curious",
        )
    )

    assert pulse is not None and pulse.act is None and pulse.reach is None
    prompt = llm.calls[0]["user"]
    assert "source: eats" in prompt
    assert "query: North Beach" in prompt
    assert "Grant Bakery" in prompt and "opens at six" in prompt
    assert 'source "places": inspect nearby landmarks' in prompt
    records = [json.loads(line) for line in (tmp_path / "prompt_traces.jsonl").read_text(encoding="utf-8").splitlines()]
    assert records[0]["phase"] == "reach_continue"
    assert records[0]["source_context"]["request"]["source"] == "eats"
    assert records[0]["source_context"]["result"]["records"][0]["selection_mode"] == "neighborhood_match"
    assert [item["name"] for item in records[0]["source_context"]["available_sources"]] == ["eats", "places"]


def test_reach_continuation_frames_scoped_file_result_as_read_not_known(tmp_path):
    llm = _StubLLM(json_response={"felt_sense": "the page is in view", "act": None})
    producer = LLMPulseProducer(llm=llm, identity=_identity(), memory_dir=tmp_path)
    producer.latest_perception = {
        "affordances": [
            {
                "source_id": "source:files",
                "name": "files",
                "description": "read an authorized file",
                "provenance": "scoped-reading",
            }
        ]
    }

    pulse = asyncio.run(
        producer.continue_reach(
            request={"kind": "read", "source": "files", "query": "notes.md"},
            result={
                "provenance": "scoped-reading",
                "detail": "[files | exact_path | live] notes.md\na private page",
                "records": [],
            },
            prior_felt="curious",
        )
    )

    assert pulse is not None
    prompt = llm.calls[0]["user"]
    assert "authorized artifact you deliberately read" in prompt
    assert "rather than already knowing it" in prompt
    assert "speak it as your own knowing" not in prompt


def test_pulse_prompt_surfaces_drive_resonance(tmp_path):
    from src.runtime.drive import DeterministicEmbedder, DriveVector

    # A mechanic's soul, and a moment about a broken engine — the drive vector
    # should pull the mechanic's own fragment into the prompt, not the room's.
    dv = asyncio.run(
        DriveVector.build(
            embedder=DeterministicEmbedder(),
            constitution="I mend broken engines with steady hands. I have no patience for idle chatter.",
        )
    )
    llm = _StubLLM(
        json_response={
            "felt_sense": "x",
            "expectations": [{"features": {"vigilance": 0.5}, "scope": "self"}],
        }
    )
    producer = LLMPulseProducer(llm=llm, identity=_identity(), memory_dir=tmp_path, drive_vector=dv)
    producer.latest_perception = {
        "heard": [{"speaker": "Levi", "message": "the broken engine in the yard won't start"}],
        "location": "Chinatown",
    }

    asyncio.run(producer(traces=[], stimulus={}, arousal=1.2))
    prompt = llm.calls[0]["user"]
    assert "stirs in YOU" in prompt  # the resonance block is present
    assert "engine" in prompt.lower()  # and it surfaced the mechanic's own fragment


def test_pulse_engine_fails_closed_on_inference_error(tmp_path):
    producer = LLMPulseProducer(llm=_StubLLM(raise_inference=True), identity=_identity(), memory_dir=tmp_path)
    pulse = asyncio.run(producer(traces=[], stimulus={}, arousal=1.0))
    assert pulse is None


def test_pulse_engine_fails_closed_on_invalid_pulse(tmp_path):
    producer = LLMPulseProducer(
        llm=_StubLLM(json_response={"act": {"kind": "teleport", "body": "x"}}),
        identity=_identity(),
        memory_dir=tmp_path,
    )
    pulse = asyncio.run(producer(traces=[], stimulus={}, arousal=1.0))
    assert pulse is None


# --- the whole mind, end to end -------------------------------------------


def test_cognitive_core_closes_loop_end_to_end(tmp_path):
    # A crowded, surprising scene the resident has not yet predicted. Three
    # others present drive vigilance to 0.75, so surprise accumulates over two
    # ticks rather than igniting on the first.
    scene = _Scene(
        present=[
            _Person("Levi", actor_id="actor-levi", session_id="levi-1"),
            _Person("Mei", actor_id="actor-mei", session_id="mei-1"),
            _Person("Bao", actor_id="actor-bao", session_id="bao-1"),
        ]
    )
    world = _StubWorld(scene)
    llm = _StubLLM(
        json_response={
            "felt_sense": "too many strangers at once",
            "act": {"kind": "speak", "body": "Quite the crowd today.", "target": None},
            "expectations": [
                {
                    "features": {"vigilance": 0.75},
                    "scope": "self",
                    "confidence": 1.0,
                    "half_life": 600,
                }
            ],
        }
    )
    core = CognitiveCore(
        identity=_identity(),
        resident_dir=tmp_path,
        ww_client=world,
        llm=llm,
        session_id="sun_li-1",
    )
    memory_dir = tmp_path / "memory"

    # Tick 1: perceive crowding → surprise recorded, arousal still climbing.
    r1 = asyncio.run(core.tick_once(now=T0.isoformat()))
    assert r1["observed_trace"] is not None
    assert r1["ignited"] is False

    # Tick 2: arousal crosses threshold → the one LLM pulse fires → act reaches
    # the world → an afterimage is cast.
    r2 = asyncio.run(core.tick_once(now=(T0 + timedelta(seconds=1)).isoformat()))
    assert r2["ignited"] is True
    assert r2["act_executed"]["executed"] is True
    assert world.location_chats[-1]["message"] == "Quite the crowd today."
    assert len(_events_by_type(memory_dir, "pulse_emitted")) == 1
    pulse_act = _events_by_type(memory_dir, "pulse_act_emitted")[0]["payload"]
    assert pulse_act["actor_id"] == "actor-123"
    assert pulse_act["co_present"] == ["actor-bao", "actor-levi", "actor-mei"]
    assert len(_events_by_type(memory_dir, "afterimage_cast")) == 1
    assert len(llm.calls) == 1  # the LLM fired exactly once — only on ignition

    # Tick 3: the afterimage now predicts the unchanged crowd → no new surprise.
    r3 = asyncio.run(core.tick_once(now=(T0 + timedelta(seconds=2)).isoformat()))
    assert r3["observed_trace"] is None
    assert r3["ignited"] is False
    assert len(llm.calls) == 1  # still just one — the mind has gone quiet


def test_cognitive_core_observes_only_chat_included_in_a_prompt(tmp_path):
    world = _StubWorld(
        _Scene(present=[_Person("Levi", actor_id="actor-levi", session_id="other-1")]),
        local_chat=[_Chat("other-1", "Levi", "The blue cup is yours.", actor_id="actor-levi")],
    )
    llm = _StubLLM(json_response={"felt_sense": "Levi's offer lands", "act": None})
    core = CognitiveCore(
        identity=_identity(),
        resident_dir=tmp_path,
        ww_client=world,
        llm=llm,
        session_id="sun_li-1",
    )
    memory_dir = tmp_path / "memory"

    asyncio.run(core.tick_once(now=T0.isoformat(), force_ignite=True))
    packet = _packets_of_type(memory_dir, "chat_heard")[0]

    assert packet["status"] == "observed"
    assert "The blue cup is yours." in llm.calls[0]["user"]
    perceived = _events_by_type(memory_dir, "utterance_perceived")
    assert len(perceived) == 1
    assert perceived[0]["payload"] == {
        "edge_schema_version": 1,
        "actor_id": "actor-123",
        "actor_session_id": "sun_li-1",
        "location": "Chinatown",
        "co_present": ["actor-levi"],
        "packet_id": packet["packet_id"],
        "utterance_id": "chat:Chinatown:1",
        "transport_id": "1",
        "speaker_actor_id": "actor-levi",
        "speaker_session_id": "other-1",
        "speaker_name": "Levi",
        "channel": "local",
        "is_direct": False,
    }

    # The server still returns the same rolling-window line, but its stable
    # encounter is already consumed and therefore absent from the next prompt.
    asyncio.run(core.tick_once(now=(T0 + timedelta(seconds=1)).isoformat(), force_ignite=True))
    assert len(_packets_of_type(memory_dir, "chat_heard")) == 1
    assert "The blue cup is yours." not in llm.calls[1]["user"]
    assert len(_events_by_type(memory_dir, "utterance_perceived")) == 1
