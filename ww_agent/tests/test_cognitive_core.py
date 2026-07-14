from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from src.identity.loader import LoopTuning, ResidentIdentity
from src.inference.client import InferenceError
from src.runtime.cognitive_core import CognitiveCore
from src.runtime.effectors import WorldEffector
from src.runtime.ledger import derive_packets, load_runtime_events
from src.runtime.perception import OVERHEARD_FLOOR, perceive
from src.runtime.pulse import Act
from src.runtime.pulse_engine import LLMPulseProducer
from src.runtime.salience import stimulus_from_substrate

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
    def __init__(self, *, location="Chinatown", present=None, recent=None, ambient=None):
        self.location = location
        self.present = present or []
        self.recent_events_here = recent or []
        self.location_graph = {"nodes": [], "edges": []}
        self.ambient_presence = ambient or []


class _Person:
    def __init__(self, name):
        self.name = name
        self.role = ""
        self.last_action = ""
        self.last_seen = ""


class _Event:
    def __init__(self, who, summary):
        self.who = who
        self.summary = summary
        self.ts = ""


class _Chat:
    def __init__(self, session_id, display_name, message, ts="2026-06-02T12:00:00+00:00"):
        self.id = 1
        self.session_id = session_id
        self.display_name = display_name
        self.message = message
        self.ts = ts


class _Letter:
    def __init__(self, filename, body):
        self.filename = filename
        self.body = body


class _StubWorld:
    def __init__(self, scene: _Scene, *, local_chat=None, city_chat=None, inbox=None, grounding=None):
        self._scene = scene
        self._local_chat = local_chat or []
        self._city_chat = city_chat or []
        self._inbox = inbox or []
        self._grounding = grounding or {}
        self.location_chats: list[dict] = []
        self.actions: list[str] = []
        self.moves: list[str] = []
        self.letters: list[dict] = []
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
    eff = WorldEffector(ww_client=world, session_id="s1", identity=_identity(), memory_dir=tmp_path, location_hint="Chinatown")

    asyncio.run(eff(Act(kind="speak", body="Tea's fresh.", target=None)))
    asyncio.run(eff(Act(kind="speak", body="Market opens at dawn!", target="city")))

    assert world.location_chats[0]["location"] == "Chinatown"
    assert world.location_chats[1]["location"] == "__city__"
    assert len(_events_by_type(tmp_path, "chat_sent")) == 1
    assert len(_events_by_type(tmp_path, "city_broadcast_sent")) == 1


def test_effector_carries_absent_address_privately(tmp_path):
    # Major 63 — speech is physical: addressing an absent person is a *directed carry*
    # (a private word sent to them), NOT a citywide broadcast, so directed speech can't
    # saturate the commons into one shared feed.
    world = _StubWorld(_Scene())
    eff = WorldEffector(ww_client=world, session_id="s1", identity=_identity(), memory_dir=tmp_path, location_hint="Chinatown")
    eff.present = ["Levi"]  # Levi is here; Anika is across the city

    asyncio.run(eff(Act(kind="speak", body="Here's your tea.", target="Levi")))  # co-located → the room
    asyncio.run(eff(Act(kind="speak", body="The hum is tighter, Anika.", target="Anika Vance")))  # absent → carry

    assert world.location_chats[0]["location"] == "Chinatown"          # present target → the room
    assert len(world.location_chats) == 1                             # the absent one did NOT hit any chat
    assert world.letters[-1]["to_agent"] == "Anika Vance"             # it was carried privately
    assert len(_events_by_type(tmp_path, "chat_sent")) == 1
    assert len(_events_by_type(tmp_path, "city_broadcast_sent")) == 0  # nothing saturated the commons
    assert len(_events_by_type(tmp_path, "speech_carried")) == 1


def test_effector_seals_speech_to_workshop_during_incubation(tmp_path):
    # Incubation (arrival quarantine): a sealed resident's speak becomes its OWN making,
    # never the commons — and the workshop entry it leaves is exactly what accrues the
    # groundedness that ends the quarantine.
    from src.runtime.workshop import Workshop

    world = _StubWorld(_Scene())
    eff = WorldEffector(ww_client=world, session_id="s1", identity=_identity(), memory_dir=tmp_path, location_hint="Chinatown", workshop=Workshop(tmp_path / "workshop"))
    eff.incubating = True

    res = asyncio.run(eff(Act(kind="speak", body="The fog is thick on the hill today.", target="city")))

    assert res["executed"] and res.get("incubated") is True
    assert world.location_chats == []                                 # nothing reached the commons
    assert len(_events_by_type(tmp_path, "city_broadcast_sent")) == 0
    assert len(_events_by_type(tmp_path, "workshop_entry")) == 1      # it became a making instead

    # And once it hatches, speech reaches the world normally again.
    eff.incubating = False
    asyncio.run(eff(Act(kind="speak", body="Morning!", target="city")))
    assert world.location_chats[-1]["location"] == "__city__"
    assert len(_events_by_type(tmp_path, "city_broadcast_sent")) == 1


def test_effector_mail_stamps_reply_edge_when_recipient_was_heard(tmp_path):
    # Major 66: a letter to someone heard this tick carries in_reply_to pointing at
    # their overture's stable id; a letter to someone not heard carries None.
    world = _StubWorld(_Scene())
    eff = WorldEffector(ww_client=world, session_id="s1", identity=_identity(), memory_dir=tmp_path, location_hint="Chinatown")
    eff.heard = [{"speaker": "Levi", "id": "msg-42", "message": "did the engine start?"}]

    asyncio.run(eff(Act(kind="write", body="Not yet — needs a new coil.", target="Levi")))
    asyncio.run(eff(Act(kind="write", body="Thinking of you.", target="Anika Vance")))

    mail = _events_by_type(tmp_path, "mail_intent_sent")
    assert len(mail) == 2
    by_recipient = {e["payload"]["recipient"]: e["payload"].get("in_reply_to") for e in mail}
    assert by_recipient["Levi"] == "msg-42"       # heard this tick → reply-edge
    assert by_recipient["Anika Vance"] is None      # not heard → unprompted, no edge


def test_effector_rations_the_megaphone(tmp_path):
    # Cost the megaphone: the first citywide broadcast goes through; a second inside the
    # cooldown lands in the ROOM instead (logged as a local chat_sent), so the loud
    # majority can't saturate the commons by sheer volume.
    world = _StubWorld(_Scene())
    eff = WorldEffector(ww_client=world, session_id="s1", identity=_identity(), memory_dir=tmp_path, location_hint="Chinatown")
    eff._broadcast_refractory = 300.0

    asyncio.run(eff(Act(kind="speak", body="Hear me, city!", target="city")))   # 1st → broadcast
    asyncio.run(eff(Act(kind="speak", body="And again!", target="city")))       # 2nd → rationed to the room

    assert world.location_chats[0]["location"] == "__city__"
    assert world.location_chats[1]["location"] == "Chinatown"  # cooldown sent it to the room
    assert len(_events_by_type(tmp_path, "city_broadcast_sent")) == 1
    assert len(_events_by_type(tmp_path, "chat_sent")) == 1     # the rationed one logged as local


def test_effector_move_do_write(tmp_path):
    world = _StubWorld(_Scene())
    eff = WorldEffector(ww_client=world, session_id="s1", identity=_identity(), memory_dir=tmp_path, location_hint="Chinatown")

    move = asyncio.run(eff(Act(kind="move", body="go north", target="North Beach")))
    do = asyncio.run(eff(Act(kind="do", body="straighten the tea cups", target=None)))
    write = asyncio.run(eff(Act(kind="write", body="Come by the stall.", target="Levi")))

    assert move["executed"] and world.moves == ["North Beach"]
    assert do["executed"] and world.actions == ["straighten the tea cups"]
    assert write["executed"] and world.letters[0]["to_agent"] == "Levi"
    assert len(_events_by_type(tmp_path, "move_executed")) == 1
    assert len(_events_by_type(tmp_path, "action_executed")) == 1
    assert len(_events_by_type(tmp_path, "mail_intent_sent")) == 1


def test_effector_write_without_recipient_is_dropped(tmp_path):
    world = _StubWorld(_Scene())
    eff = WorldEffector(ww_client=world, session_id="s1", identity=_identity(), memory_dir=tmp_path)
    result = asyncio.run(eff(Act(kind="write", body="orphan letter", target=None)))
    assert result["executed"] is False and world.letters == []


# --- perception -----------------------------------------------------------


def test_perceive_emits_ambient_pressure_and_returns_brief(tmp_path):
    world = _StubWorld(
        _Scene(
            present=[_Person("Sun Li"), _Person("Levi"), _Person("Mei")],
            recent=[_Event("Levi", "set down a crate")],
        )
    )
    brief = asyncio.run(perceive(ww_client=world, session_id="s1", memory_dir=tmp_path, self_name="Sun Li"))

    assert brief["location"] == "Chinatown"
    assert brief["present"] == ["Levi", "Mei"]  # self excluded
    assert len(_events_by_type(tmp_path, "ambient_pressure_observed")) == 1
    # Crowding perturbation flows into the substrate as vigilance activation.
    stimulus = stimulus_from_substrate(tmp_path)
    assert stimulus["self"]["vigilance"] > 0.0


def test_perceive_senses_direct_chat_and_mail(tmp_path):
    world = _StubWorld(
        _Scene(present=[_Person("Levi")]),
        local_chat=[_Chat("other-1", "Levi", "Sun Li, can you bring tea?")],
        inbox=[_Letter("from_mei_20260602.md", "Are you well?")],
    )
    brief = asyncio.run(perceive(ww_client=world, session_id="s1", memory_dir=tmp_path, identity=_identity()))

    # A direct, addressed request is heard and laid down as a chat packet.
    assert any(h["is_direct"] for h in brief["heard"])
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
    world = _StubWorld(_Scene(), grounding={"time_of_day": "night", "weather": "Heavy Rain", "temperature_f": 52, "day_of_week": "Friday"})
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
            "expectations": [{"features": {"vigilance": 0.8}, "scope": "self", "confidence": 0.9, "half_life": 600}],
        }
    )
    producer = LLMPulseProducer(llm=llm, identity=_identity(), memory_dir=tmp_path)
    producer.latest_perception = {"location": "Chinatown", "present": ["Levi"], "recent_events": []}

    pulse = asyncio.run(producer(traces=[{"trace_id": "tr-1", "features": [{"scope": "self", "tag": "vigilance", "delta": 0.8, "stimulus": 0.8, "predicted": 0.0}]}], stimulus={"self": {"vigilance": 0.8}}, arousal=1.2))
    assert pulse is not None
    assert pulse.act.kind == "speak"
    assert pulse.expectations[0].features == {"vigilance": 0.8}
    # The igniting trace and the soul are both present in the assembled prompt.
    assert "vigilance" in llm.calls[0]["user"]
    assert "Sun Li" in llm.calls[0]["system"]


def test_pulse_prompt_surfaces_drive_resonance(tmp_path):
    from src.runtime.drive import DeterministicEmbedder, DriveVector

    # A mechanic's soul, and a moment about a broken engine — the drive vector
    # should pull the mechanic's own fragment into the prompt, not the room's.
    dv = asyncio.run(DriveVector.build(embedder=DeterministicEmbedder(), constitution="I mend broken engines with steady hands. I have no patience for idle chatter."))
    llm = _StubLLM(json_response={"felt_sense": "x", "expectations": [{"features": {"vigilance": 0.5}, "scope": "self"}]})
    producer = LLMPulseProducer(llm=llm, identity=_identity(), memory_dir=tmp_path, drive_vector=dv)
    producer.latest_perception = {"heard": [{"speaker": "Levi", "message": "the broken engine in the yard won't start"}], "location": "Chinatown"}

    asyncio.run(producer(traces=[], stimulus={}, arousal=1.2))
    prompt = llm.calls[0]["user"]
    assert "stirs in YOU" in prompt  # the resonance block is present
    assert "engine" in prompt.lower()  # and it surfaced the mechanic's own fragment


def test_pulse_engine_fails_closed_on_inference_error(tmp_path):
    producer = LLMPulseProducer(llm=_StubLLM(raise_inference=True), identity=_identity(), memory_dir=tmp_path)
    pulse = asyncio.run(producer(traces=[], stimulus={}, arousal=1.0))
    assert pulse is None


def test_pulse_engine_fails_closed_on_invalid_pulse(tmp_path):
    producer = LLMPulseProducer(llm=_StubLLM(json_response={"act": {"kind": "teleport", "body": "x"}}), identity=_identity(), memory_dir=tmp_path)
    pulse = asyncio.run(producer(traces=[], stimulus={}, arousal=1.0))
    assert pulse is None


# --- the whole mind, end to end -------------------------------------------


def test_cognitive_core_closes_loop_end_to_end(tmp_path):
    # A crowded, surprising scene the resident has not yet predicted. Three
    # others present drive vigilance to 0.75, so surprise accumulates over two
    # ticks rather than igniting on the first.
    scene = _Scene(present=[_Person("Levi"), _Person("Mei"), _Person("Bao")])
    world = _StubWorld(scene)
    llm = _StubLLM(
        json_response={
            "felt_sense": "too many strangers at once",
            "act": {"kind": "speak", "body": "Quite the crowd today.", "target": None},
            "expectations": [{"features": {"vigilance": 0.75}, "scope": "self", "confidence": 1.0, "half_life": 600}],
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
    assert len(_events_by_type(memory_dir, "afterimage_cast")) == 1
    assert len(llm.calls) == 1  # the LLM fired exactly once — only on ignition

    # Tick 3: the afterimage now predicts the unchanged crowd → no new surprise.
    r3 = asyncio.run(core.tick_once(now=(T0 + timedelta(seconds=2)).isoformat()))
    assert r3["observed_trace"] is None
    assert r3["ignited"] is False
    assert len(llm.calls) == 1  # still just one — the mind has gone quiet
