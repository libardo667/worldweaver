from __future__ import annotations

import asyncio
import json
from typing import Any

from src.identity.loader import LoopTuning, ResidentIdentity
from src.loops.fast import FastLoop
from src.loops.ground import GroundLoop
from src.loops.mail import MailLoop
from src.loops.slow import SlowLoop
from src.memory.provisional import ProvisionalScratchpad
from src.memory.research_queue import ResearchQueue
from src.memory.retrieval import LongTermMemory
from src.memory.reveries import ReverieDeck
from src.memory.voice import VoiceDeck
from src.memory.working import WorkingMemory
from src.runtime.ledger import load_runtime_events, rebuild_runtime_artifacts, reduce_runtime_events
from src.runtime.mirror import ResidentRuntimeMirror
from src.runtime.rest import RestAssessment
from src.runtime.signals import IntentQueue, StimulusPacket, StimulusPacketQueue
from src.world.client import AmbientPresence, ChatMessage, DM


class _DummyWorldClient:
    def __init__(self):
        self.replies: list[tuple[str, str, str]] = []
        self.votes: list[tuple[str, str, str]] = []
        self.session_var_updates: list[tuple[str, dict]] = []
        self.location_chats: list[tuple[str, str, str, str | None]] = []
        self.actions: list[tuple[str, str]] = []
        self.letters_sent: list[dict[str, Any]] = []
        self.social_feedback_posts: list[dict[str, Any]] = []
        self.session_vars_payload: dict[str, Any] = {"vars": {}}
        self.roster_display_names: list[str] = ["Levi", "Sun Li"]
        self.roster_recipients: list[dict[str, str]] = []
        self.identity_growth_payload: dict[str, Any] = {
            "growth_text": "",
            "growth_metadata": {},
            "note_records": [],
            "growth_proposals": [],
        }
        self.guild_profile_payload: dict[str, Any] = {
            "rank": "apprentice",
            "branches": [],
            "environment_guidance": {},
        }
        self.runtime_adaptation_payload: dict[str, Any] = {
            "behavior_knobs": {},
            "environment_guidance": {},
            "source_feedback_ids": [],
        }

    async def reply_letter(self, from_agent: str, to_session_id: str, body: str):
        self.replies.append((from_agent, to_session_id, body))
        return {"ok": True}

    async def cast_doula_vote(self, poll_id: str, voter_session_id: str, vote: str):
        self.votes.append((poll_id, voter_session_id, vote))
        return {"ok": True}

    async def send_letter(
        self,
        from_name: str,
        to_agent: str,
        body: str,
        session_id: str,
        *,
        recipient_type: str = "agent",
    ):
        self.letters_sent.append(
            {
                "from_name": from_name,
                "to_agent": to_agent,
                "body": body,
                "session_id": session_id,
                "recipient_type": recipient_type,
            }
        )
        return {"ok": True}

    async def update_session_vars(self, session_id: str, vars: dict[str, Any]):
        self.session_var_updates.append((session_id, dict(vars)))
        return {"session_id": session_id, "vars": vars}

    async def get_session_vars(self, session_id: str, prefix: str | None = None):
        return dict(self.session_vars_payload)

    async def get_identity_growth(self, session_id: str):
        return dict(self.identity_growth_payload)

    async def update_identity_growth(
        self,
        session_id: str,
        *,
        growth_text: str | None = None,
        growth_metadata: dict[str, Any] | None = None,
        note_records: list[dict[str, Any]] | None = None,
        growth_proposals: list[dict[str, Any]] | None = None,
    ):
        if growth_text is not None:
            self.identity_growth_payload["growth_text"] = str(growth_text)
        if growth_metadata is not None:
            self.identity_growth_payload["growth_metadata"] = dict(growth_metadata)
        if note_records is not None:
            self.identity_growth_payload["note_records"] = list(note_records)
        if growth_proposals is not None:
            self.identity_growth_payload["growth_proposals"] = list(growth_proposals)
        return dict(self.identity_growth_payload)

    async def get_social_feedback(self, session_id: str, limit: int = 50):
        return {"events": list(self.social_feedback_posts[-limit:]), "count": len(self.social_feedback_posts[-limit:])}

    async def post_social_feedback(self, session_id: str, payload: dict[str, Any]):
        event = dict(payload)
        event["id"] = len(self.social_feedback_posts) + 1
        event["created_at"] = "2026-03-20T16:00:00+00:00"
        self.social_feedback_posts.append(event)
        return {"event": event, "adaptation": dict(self.runtime_adaptation_payload)}

    async def get_guild_profile(self, session_id: str):
        return dict(self.guild_profile_payload)

    async def get_runtime_adaptation(self, session_id: str):
        return dict(self.runtime_adaptation_payload)

    async def post_location_chat(self, location: str, session_id: str, message: str, display_name: str | None = None):
        self.location_chats.append((location, session_id, message, display_name))
        return {"id": 1, "ts": "2026-03-18T00:00:00+00:00"}

    async def post_action(self, session_id: str, action: str):
        self.actions.append((session_id, action))
        return type("TurnResult", (), {"narrative": f"{action}."})()

    async def get_grounding(self):
        return {}

    async def get_news(self):
        return []

    async def get_scene(self, session_id: str):
        return type(
            "Scene",
            (),
            {
                "location": "Chinatown",
                "present": [],
                "recent_events_here": [],
                "location_graph": {"nodes": [], "edges": []},
            },
        )()

    async def get_neighborhood_vitality(self, hours: int = 6):
        return {}

    async def get_roster_display_names(self) -> list[str]:
        return list(self.roster_display_names)

    async def resolve_dm_recipient(self, recipient: str):
        normalized = " ".join(str(recipient or "").split()).strip().lower()
        for item in self.roster_recipients:
            label = " ".join(str(item.get("label") or "").split()).strip().lower()
            if label == normalized:
                return type(
                    "Recipient",
                    (),
                    {
                        "label": item["label"],
                        "recipient_key": item["recipient_key"],
                        "recipient_type": item.get("recipient_type", "agent"),
                    },
                )()
        return None


class _DummyInferenceClient:
    async def complete_json(self, *args, **kwargs):
        return {"intents": []}

    async def complete(self, *args, **kwargs):
        return "observe"


class _SequencedInferenceClient:
    def __init__(
        self,
        *,
        complete_responses: list[str] | None = None,
        json_responses: list[dict[str, Any]] | None = None,
    ) -> None:
        self.complete_responses = list(complete_responses or [])
        self.json_responses = list(json_responses or [])
        self.complete_calls: list[dict[str, Any]] = []
        self.complete_json_calls: list[dict[str, Any]] = []

    async def complete_json(self, *args, **kwargs):
        self.complete_json_calls.append(dict(kwargs))
        if self.json_responses:
            return self.json_responses.pop(0)
        return {"intents": []}

    async def complete(self, *args, **kwargs):
        self.complete_calls.append(dict(kwargs))
        if self.complete_responses:
            return self.complete_responses.pop(0)
        return "observe"


def _without_updated_at(doc: dict) -> dict:
    return {key: value for key, value in doc.items() if key != "updated_at"}


def _empty_reduced_state():
    return reduce_runtime_events([])


def _identity(**tuning_overrides: Any) -> ResidentIdentity:
    return ResidentIdentity(
        name="sun_li",
        actor_id="resident-sun-li",
        soul="Soul",
        canonical_soul="Soul",
        growth_soul="",
        vibe="steady",
        core="Sun Li keeps her footing.",
        voice_seed=[],
        tuning=LoopTuning(**tuning_overrides),
    )


def test_fast_loop_records_chat_packets_for_other_sessions(tmp_path):
    resident_dir = tmp_path / "sun_li"
    packet_queue = StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json")
    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        rest_state=None,
        packet_queue=packet_queue,
    )

    fast._record_chat_packets(
        "chat_heard",
        "Chinatown",
        [
            ChatMessage(
                id=1,
                session_id="levi-session",
                display_name="Levi",
                message="Tea's ready.",
                ts="2026-03-16T12:00:00+00:00",
            ),
            ChatMessage(
                id=2,
                session_id="sun_li-20260316-120000",
                display_name="Sun Li",
                message="On my way.",
                ts="2026-03-16T12:00:01+00:00",
            ),
        ],
    )

    packets = packet_queue.pending()
    assert len(packets) == 1
    assert packets[0].packet_type == "chat_heard"
    assert packets[0].location == "Chinatown"
    assert packets[0].payload["speaker"] == "Levi"


def test_fast_loop_mail_resolves_real_roster_recipient(tmp_path):
    resident_dir = tmp_path / "sun_li"
    world = _DummyWorldClient()
    world.roster_display_names = ["Levi", "Rosa Garza", "Sun Li"]
    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=world,
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        rest_state=None,
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    asyncio.run(fast._do_mail("rosa garza", "Check in after the market rush."))

    reduced = rebuild_runtime_artifacts(resident_dir / "memory")
    assert any(item["recipient"] == "Rosa Garza" for item in reduced.active_mail_intents)


def test_fast_loop_mail_drops_unknown_recipient(tmp_path):
    resident_dir = tmp_path / "sun_li"
    world = _DummyWorldClient()
    world.roster_display_names = ["Levi", "Rosa Garza", "Sun Li"]
    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=world,
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        rest_state=None,
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    asyncio.run(fast._do_mail("Possibly", "Maybe I should say something."))

    reduced = rebuild_runtime_artifacts(resident_dir / "memory")
    assert not reduced.active_mail_intents


def test_fast_loop_classifies_tagged_local_chat_as_direct(tmp_path):
    resident_dir = tmp_path / "sun_li"
    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
    )

    flags = fast._classify_dialogue_message("@Sun Li are you still at the stall?", packet_type="chat_heard")
    assert flags["is_direct"] is True
    assert flags["is_question"] is True
    assert flags["tagged"] is True


def test_fast_loop_classifies_tagged_city_chat_as_direct_without_local_urgency(tmp_path):
    resident_dir = tmp_path / "sun_li"
    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
    )

    flags = fast._classify_dialogue_message("@sun_li check the city board when you can?", packet_type="city_chat_heard")
    assert flags["is_direct"] is True
    assert flags["is_question"] is True
    assert flags["channel"] == "city"


def test_fast_loop_classifier_prompt_includes_ambient_presence(tmp_path):
    resident_dir = tmp_path / "sun_li"
    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
    )

    scene = type(
        "Scene",
        (),
        {
            "location": "Chinatown",
            "present": [],
            "ambient_presence": [
                AmbientPresence(
                    kind="weather_shelter_cluster",
                    label="People keep collecting in the sheltered edges of the block.",
                    source="grounding",
                    intensity=0.66,
                    pressure_tags=["bad_weather", "shelter"],
                )
            ],
            "recent_events_here": [],
        },
    )()

    prompt = fast._build_classifier_prompt(
        scene=scene,
        new_chat=[],
        new_city_chat=[],
        grounding_text="Rain keeps needling the awnings.",
        active_route=None,
        adjacent_names=["North Beach"],
    )

    assert "Ambiently here:" in prompt
    assert "sheltered edges of the block" in prompt


def test_fast_loop_executes_queued_chat_intent_before_classifier(tmp_path):
    resident_dir = tmp_path / "sun_li"
    packet_queue = StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json")
    intent_queue = IntentQueue(resident_dir / "memory" / "intent_queue.json")
    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        rest_state=None,
        packet_queue=packet_queue,
        intent_queue=intent_queue,
    )

    intent = intent_queue.stage(
        intent_type="chat",
        target_loop="fast",
        priority=0.9,
        payload={"utterance": "Tea is ready."},
    )

    called: list[str] = []

    async def fake_do_chat(message: str, scene):
        called.append(message)

    fast._do_chat = fake_do_chat  # type: ignore[method-assign]

    result = asyncio.run(
        fast._execute_queued_intent(
            type("Scene", (), {"location": "Chinatown"})(),
            ["Chinatown", "Tea House"],
        )
    )

    assert result is True
    assert called == ["Tea is ready."]
    stored = intent_queue.all()
    assert stored[0].intent_id == intent.intent_id
    assert stored[0].status == "executed"


def test_fast_loop_marks_unreachable_move_intent_failed(tmp_path):
    resident_dir = tmp_path / "sun_li"
    intent_queue = IntentQueue(resident_dir / "memory" / "intent_queue.json")
    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=intent_queue,
    )

    intent_queue.stage(
        intent_type="move",
        target_loop="fast",
        priority=0.8,
        payload={"destination": "bench by the laundromat"},
    )

    result = asyncio.run(
        fast._execute_queued_intent(
            type("Scene", (), {"location": "Tenderloin"})(),
            ["Tenderloin", "Civic Center"],
        )
    )

    assert result is False
    stored = intent_queue.all()
    assert stored[0].status == "failed"
    assert stored[0].validation_state == "unreachable_destination"


def test_fast_loop_executes_queued_chat_intent_with_content_payload(tmp_path):
    resident_dir = tmp_path / "sun_li"
    intent_queue = IntentQueue(resident_dir / "memory" / "intent_queue.json")
    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=intent_queue,
    )

    intent_queue.stage(
        intent_type="chat",
        target_loop="fast",
        priority=0.9,
        payload={"content": "Tea is still hot."},
    )

    called: list[str] = []

    async def fake_do_chat(message: str, scene):
        called.append(message)

    fast._do_chat = fake_do_chat  # type: ignore[method-assign]

    result = asyncio.run(
        fast._execute_queued_intent(
            type("Scene", (), {"location": "Chinatown"})(),
            ["Chinatown", "Tea House"],
        )
    )

    assert result is True
    assert called == ["Tea is still hot."]


def test_fast_loop_executes_queued_act_intent_and_records_action(tmp_path):
    resident_dir = tmp_path / "sun_li"
    intent_queue = IntentQueue(resident_dir / "memory" / "intent_queue.json")
    world = _DummyWorldClient()
    working = WorkingMemory(resident_dir / "memory" / "working.json")
    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=world,
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=working,
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=intent_queue,
    )

    intent_queue.stage(
        intent_type="act",
        target_loop="fast",
        priority=0.7,
        payload={"action": "I pause and listen to how quiet the block has gotten."},
    )

    result = asyncio.run(
        fast._execute_queued_intent(
            type("Scene", (), {"location": "Chinatown", "present": []})(),
            ["Chinatown", "Tea House"],
        )
    )

    assert result is True
    assert world.actions == [
        ("sun_li-20260316-120000", "I pause and listen to how quiet the block has gotten.")
    ]
    recent = working.recent(4)
    action_entries = [entry for entry in recent if entry.get("type") == "action"]
    assert action_entries
    assert action_entries[-1]["action"] == "I pause and listen to how quiet the block has gotten."
    stored = intent_queue.all()
    assert stored[0].status == "executed"


def test_slow_loop_records_soul_note_context_and_requires_multiple_contexts(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    slow = SlowLoop(
        identity=_identity(soul_collapse_at_notes=2),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260318-000000",
        working_memory=WorkingMemory(memory_dir / "working.json"),
        provisional=ProvisionalScratchpad(memory_dir / "impressions"),
        long_term=LongTermMemory(memory_dir / "long_term.json"),
        reveries=ReverieDeck(memory_dir / "reveries.json"),
        voice=VoiceDeck(memory_dir / "voice.json"),
        research_queue=ResearchQueue(memory_dir / "research_queue.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(memory_dir / "stimulus_packets.json"),
        intent_queue=IntentQueue(memory_dir / "intent_queue.json"),
    )

    assert asyncio.run(
        slow._record_soul_note(
            "I felt more solid than usual.",
            "2026-03-18T01:00:00+00:00",
            location="Chinatown",
            active_partner="Levi",
            pressure_tags=["crowding"],
        )
    )
    assert asyncio.run(
        slow._record_soul_note(
            "I kept my footing.",
            "2026-03-18T08:30:00+00:00",
            location="North Beach",
            active_partner="",
            pressure_tags=["quiet"],
        )
    )

    records = asyncio.run(slow._load_soul_note_records())
    assert records[0]["location"] == "Chinatown"
    assert records[0]["active_partner"] == "Levi"
    assert records[0]["pressure_tags"] == ["crowding"]
    assert slow._soul_notes_matured_enough(records) is True


def test_slow_loop_defers_soul_growth_when_notes_come_from_one_context(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    slow = SlowLoop(
        identity=_identity(soul_collapse_at_notes=2),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260318-000000",
        working_memory=WorkingMemory(memory_dir / "working.json"),
        provisional=ProvisionalScratchpad(memory_dir / "impressions"),
        long_term=LongTermMemory(memory_dir / "long_term.json"),
        reveries=ReverieDeck(memory_dir / "reveries.json"),
        voice=VoiceDeck(memory_dir / "voice.json"),
        research_queue=ResearchQueue(memory_dir / "research_queue.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(memory_dir / "stimulus_packets.json"),
        intent_queue=IntentQueue(memory_dir / "intent_queue.json"),
    )

    assert asyncio.run(
        slow._record_soul_note(
            "I felt strange in the wind.",
            "2026-03-18T01:00:00+00:00",
            location="Embarcadero",
            active_partner="Levi",
            pressure_tags=["event_pull"],
        )
    )
    assert asyncio.run(
        slow._record_soul_note(
            "I felt stranger in the same wind.",
            "2026-03-18T08:30:00+00:00",
            location="Embarcadero",
            active_partner="Levi",
            pressure_tags=["event_pull"],
        )
    )

    records = asyncio.run(slow._load_soul_note_records())
    assert slow._soul_notes_matured_enough(records) is False


def test_fast_loop_strips_trailing_stage_direction_from_chat_and_records_action(tmp_path):
    resident_dir = tmp_path / "mateo_flores"
    world = _DummyWorldClient()
    working = WorkingMemory(resident_dir / "memory" / "working.json")
    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=world,
        llm=_DummyInferenceClient(),
        session_id="mateo_flores-20260318-000000",
        working_memory=working,
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    scene = type("Scene", (), {"location": "Kenton"})()
    asyncio.run(
        fast._do_chat(
            "A quiet evening for listening, Levi. *(Mateo steps back, letting dusk settle around him.)*",
            scene,
        )
    )

    assert world.location_chats == [
        ("Kenton", "mateo_flores-20260318-000000", "A quiet evening for listening, Levi.", _identity().display_name)
    ]
    recent = working.recent(4)
    chat_entries = [entry for entry in recent if entry.get("type") == "chat"]
    assert chat_entries
    assert chat_entries[-1]["message"] == "A quiet evening for listening, Levi."
    assert chat_entries[-1]["audience"] == "local"
    action_entries = [entry for entry in recent if entry.get("type") == "action"]
    assert action_entries
    assert action_entries[-1]["action"] == "Mateo steps back, letting dusk settle around him."

    reduced = reduce_runtime_events(load_runtime_events(resident_dir / "memory"))
    facts = list(reduced.memory_projection.get("recent_experiences") or [])
    assert any(item.get("kind") == "utterance" for item in facts)


def test_fast_loop_records_city_chat_in_working_memory(tmp_path):
    resident_dir = tmp_path / "sun_li"
    world = _DummyWorldClient()
    working = WorkingMemory(resident_dir / "memory" / "working.json")
    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=world,
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=working,
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    asyncio.run(fast._do_city_chat("Meet me by the ferry building."))

    assert world.location_chats == [
        ("__city__", "sun_li-20260316-120000", "Meet me by the ferry building.", _identity().display_name)
    ]
    recent = working.recent(2)
    assert recent[-1]["type"] == "chat"
    assert recent[-1]["message"] == "Meet me by the ferry building."
    assert recent[-1]["audience"] == "city"


def test_fast_loop_mail_intent_is_projected_from_ledger(tmp_path):
    resident_dir = tmp_path / "sun_li"
    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        rest_state=None,
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    asyncio.run(fast._do_mail("Levi", "Ask about tea later."))

    intent_files = list((resident_dir / "letters" / "intents").glob("intent_*.md"))
    assert len(intent_files) == 1
    content = intent_files[0].read_text(encoding="utf-8")
    assert "Mail-Intent-ID:" in content
    assert "To: Levi" in content
    assert "Ask about tea later." in content


def test_fast_loop_route_rehydrates_from_ledger(tmp_path):
    resident_dir = tmp_path / "sun_li"
    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        rest_state=None,
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    fast._save_route("Chinatown", ["North Beach", "Chinatown"])
    route_file = resident_dir / "memory" / "active_route.json"
    assert route_file.exists()
    route_file.unlink()

    route = fast._load_route()
    assert route is not None
    assert route["destination"] == "Chinatown"
    assert route["remaining"] == ["North Beach", "Chinatown"]


def test_fast_loop_defers_to_slow_when_packets_are_pending(tmp_path):
    resident_dir = tmp_path / "sun_li"
    packet_queue = StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json")
    packet_queue.emit(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-levi",
        location="Chinatown",
        payload={"speaker": "Levi", "message": "Tea's ready."},
    )

    class _FailIfClassified(_DummyInferenceClient):
        async def complete(self, *args, **kwargs):
            raise AssertionError("classifier should not run while packet backlog is pending")

    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_FailIfClassified(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        rest_state=None,
        packet_queue=packet_queue,
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    asyncio.run(
        fast._decide_and_execute(
            {
                "scene": type(
                    "Scene",
                    (),
                    {
                        "location": "Chinatown",
                        "present": [],
                        "ambient_presence": [],
                        "recent_events_here": [],
                        "location_graph": {"nodes": [], "edges": []},
                    },
                )(),
                "new_chat": [],
                "recent_chat": [],
                "new_city_chat": [],
                "recent_city_chat": [],
                "grounding_text": "",
                "active_route": None,
                "adjacent_names": [],
                "all_location_names": ["Chinatown"],
            }
        )
    )

    assert (resident_dir / "memory" / "introspect_signal").exists()


def test_fast_loop_treats_none_classifier_result_as_observe(tmp_path):
    resident_dir = tmp_path / "sun_li"
    world = _DummyWorldClient()
    llm = _SequencedInferenceClient(complete_responses=[None])
    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=world,
        llm=llm,
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    asyncio.run(
        fast._decide_and_execute(
            {
                "scene": type(
                    "Scene",
                    (),
                    {
                        "location": "Chinatown",
                        "present": [],
                        "ambient_presence": [],
                        "recent_events_here": [],
                        "location_graph": {"nodes": [], "edges": []},
                    },
                )(),
                "new_chat": [],
                "recent_chat": [],
                "new_city_chat": [],
                "recent_city_chat": [],
                "grounding_text": "",
                "active_route": None,
                "adjacent_names": [],
                "all_location_names": ["Chinatown"],
            }
        )
    )

    assert world.actions == []
    assert world.location_chats == []


def test_mail_loop_records_mail_received_packets_once(tmp_path):
    resident_dir = tmp_path / "sun_li"
    packet_queue = StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json")
    mail = MailLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        packet_queue=packet_queue,
    )

    letters = [
        DM(filename="from_levi_20260316-120000.md", body="Hello there."),
        DM(filename="from_levi_20260316-120000.md", body="Hello there."),
    ]

    mail._record_mail_packets(letters)

    packets = packet_queue.pending()
    assert len(packets) == 1
    assert packets[0].packet_type == "mail_received"
    assert packets[0].payload["filename"] == "from_levi_20260316-120000.md"


def test_mail_loop_processes_structured_reply_and_doula_vote(tmp_path):
    resident_dir = tmp_path / "sun_li"
    world = _DummyWorldClient()
    mail = MailLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=world,
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
    )

    letters = [
        DM(
            filename="from_levi_20260316-120000.md",
            body="Reply-To-Session: levi-session\n\nMeet me for tea.",
        ),
        DM(
            filename="from_the_doula_20260316-120001.md",
            body="Poll-ID: poll-123\n\nA new presence named Juniper.",
        ),
    ]

    asyncio.run(
        mail._process_mail_response(
            {
                "actions": [
                    {"kind": "reply", "sender_name": "levi", "body": "I'll be there shortly."},
                    {"kind": "doula_vote", "vote": "AGENT"},
                ]
            },
            letters,
            [],
        )
    )

    assert world.replies == [("sun_li", "levi-session", "I'll be there shortly.")]
    assert world.votes == [("poll-123", "sun_li-20260316-120000", "AGENT")]


def test_mail_loop_resolves_display_name_recipient_before_sending(tmp_path):
    resident_dir = tmp_path / "sun_li"
    world = _DummyWorldClient()
    world.roster_recipients = [
        {"label": "Vera Chen", "recipient_key": "vera_chen", "recipient_type": "agent"},
    ]
    llm = _SequencedInferenceClient(
        json_responses=[
            {
                "decision": "send",
                "recipient": "Vera Chen",
                "body": (
                    "Hi Vera, I keep thinking about the corner garden and wanted to ask "
                    "how the seedlings are holding up in the wind tonight."
                ),
            }
        ]
    )
    mail = MailLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=world,
        llm=llm,
        session_id="sun_li-20260316-120000",
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
    )
    intent_path = resident_dir / "letters" / "intents" / "intent_test.md"
    intent_path.parent.mkdir(parents=True, exist_ok=True)
    intent_path.write_text(
        "Mail-Intent-ID: mailint-test\nTo: Vera Chen\nStaged-At: 20260320T000000Z\n\nContext:\nVera has been on your mind.\n",
        encoding="utf-8",
    )

    asyncio.run(mail._process_intent(intent_path, intent_path.read_text(encoding="utf-8")))

    assert not intent_path.exists()
    assert world.letters_sent
    assert world.letters_sent[0]["to_agent"] == "vera_chen"
    assert world.letters_sent[0]["recipient_type"] == "agent"


def test_mail_loop_drops_unresolved_recipient_intent(tmp_path):
    resident_dir = tmp_path / "sun_li"
    world = _DummyWorldClient()
    llm = _SequencedInferenceClient(
        json_responses=[
            {
                "decision": "send",
                "recipient": "Possibly",
                "body": "Hi there, I wanted to send this along even though the addressee is unclear.",
            }
        ]
    )
    mail = MailLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=world,
        llm=llm,
        session_id="sun_li-20260316-120000",
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
    )
    intent_path = resident_dir / "letters" / "intents" / "intent_test.md"
    intent_path.parent.mkdir(parents=True, exist_ok=True)
    intent_path.write_text(
        "Mail-Intent-ID: mailint-test\nTo: Possibly\nStaged-At: 20260320T000000Z\n\nContext:\nSomeone is maybe on your mind.\n",
        encoding="utf-8",
    )

    asyncio.run(mail._process_intent(intent_path, intent_path.read_text(encoding="utf-8")))

    assert not intent_path.exists()
    assert world.letters_sent == []


def test_signal_queues_write_runtime_snapshot(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")
    intent_queue = IntentQueue(memory_dir / "intent_queue.json")
    research_queue = ResearchQueue(memory_dir / "research_queue.json")

    packet = packet_queue.emit(
        packet_type="mail_received",
        source_loop="mail",
        dedupe_key="from_levi_1",
        payload={"filename": "from_levi_1.md"},
    )
    packet_queue.mark_status(packet.packet_id, "observed")
    intent = intent_queue.stage(
        intent_type="chat",
        target_loop="fast",
        source_packet_ids=[packet.packet_id],
        priority=0.7,
        payload={"utterance": "Hello."},
    )
    intent_queue.mark_status(intent.intent_id, status="failed", validation_state="invalid_payload")
    research_queue.add("Clement Street farmers market hours", priority="high", source="fast_ground_intent")

    snapshot = json.loads((memory_dir / "runtime_snapshot.json").read_text(encoding="utf-8"))
    projection = json.loads((memory_dir / "runtime_projection.json").read_text(encoding="utf-8"))
    ledger_lines = (memory_dir / "runtime_ledger.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert snapshot["packet_counts"]["total"] == 1
    assert snapshot["packet_counts"]["observed"] == 1
    assert snapshot["intent_counts"]["failed"] == 1
    assert snapshot["research_queue"]["total"] == 1
    assert snapshot["research_queue"]["high"] == 1
    assert snapshot["research_queue"]["pending_items"][0]["query"] == "Clement Street farmers market hours"
    assert projection["ledger_event_count"] >= 4
    assert projection["event_counts"]["packet_emitted"] == 1
    assert projection["event_counts"]["intent_staged"] == 1
    assert projection["event_counts"]["intent_status_changed"] == 1
    assert projection["event_counts"]["research_queued"] == 1
    assert len(ledger_lines) >= 4
    assert snapshot["recent_failures"][0]["validation_state"] == "invalid_payload"
    assert snapshot["lineage"][0]["source_packet_ids"] == [packet.packet_id]


def test_signal_queues_rehydrate_from_ledger_when_projection_files_are_missing(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")
    intent_queue = IntentQueue(memory_dir / "intent_queue.json")

    packet = packet_queue.emit(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-1",
        location="Chinatown",
        payload={"speaker": "Levi", "message": "Tea's ready."},
    )
    intent = intent_queue.stage(
        intent_type="chat",
        target_loop="fast",
        source_packet_ids=[packet.packet_id],
        priority=0.8,
        payload={"utterance": "Coming."},
    )
    packet_queue.mark_status(packet.packet_id, "observed")
    intent_queue.mark_status(intent.intent_id, status="executed", validation_state="validated")

    (memory_dir / "stimulus_packets.json").unlink()
    (memory_dir / "intent_queue.json").unlink()

    rehydrated_packets = packet_queue.all()
    rehydrated_intents = intent_queue.all()
    assert len(rehydrated_packets) == 1
    assert rehydrated_packets[0].status == "observed"
    assert len(rehydrated_intents) == 1
    assert rehydrated_intents[0].status == "executed"


def test_runtime_snapshot_rehydrates_research_queue_from_ledger(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    research_queue = ResearchQueue(memory_dir / "research_queue.json")

    research_queue.add("ASL organizations in Chinatown", priority="high", source="fast_ground_intent")
    (memory_dir / "research_queue.json").unlink()

    from src.runtime.signals import write_runtime_snapshot

    write_runtime_snapshot(memory_dir)
    snapshot = json.loads((memory_dir / "runtime_snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["research_queue"]["total"] == 1
    assert snapshot["research_queue"]["pending_items"][0]["query"] == "ASL organizations in Chinatown"
    assert snapshot["research_queue"]["pending_items"][0]["priority"] == "high"


def test_runtime_reducer_rebuilds_derived_state_from_ledger(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")
    intent_queue = IntentQueue(memory_dir / "intent_queue.json")
    research_queue = ResearchQueue(memory_dir / "research_queue.json")

    packet = packet_queue.emit(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-levi-rebuild",
        location="Chinatown",
        payload={"speaker": "Levi", "message": "Meet me in North Beach."},
    )
    packet_queue.mark_status(packet.packet_id, "observed")
    intent = intent_queue.stage(
        intent_type="chat",
        target_loop="fast",
        source_packet_ids=[packet.packet_id],
        priority=0.9,
        payload={"utterance": "I'll head over."},
    )
    intent_queue.mark_status(intent.intent_id, status="executed", validation_state="validated")
    research_queue.add("North Beach tea houses", priority="high", source="fast_ground_intent")

    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(memory_dir / "working.json"),
        provisional=ProvisionalScratchpad(memory_dir / "impressions"),
        reveries=ReverieDeck(memory_dir / "reveries.json"),
        voice=VoiceDeck(memory_dir / "voice.json"),
        rest_state=None,
        research_queue=research_queue,
        packet_queue=packet_queue,
        intent_queue=intent_queue,
    )
    fast._save_route("North Beach", ["North Beach"])
    asyncio.run(fast._do_mail("Levi", "I am on my way."))

    expected_runtime = _without_updated_at(json.loads((memory_dir / "runtime_projection.json").read_text(encoding="utf-8")))
    expected_subjective = _without_updated_at(json.loads((memory_dir / "subjective_projection.json").read_text(encoding="utf-8")))
    expected_memory = _without_updated_at(json.loads((memory_dir / "memory_projection.json").read_text(encoding="utf-8")))
    expected_facts = _without_updated_at(json.loads((memory_dir / "subjective_facts.json").read_text(encoding="utf-8")))

    for filename in (
        "stimulus_packets.json",
        "intent_queue.json",
        "active_route.json",
        "runtime_projection.json",
        "subjective_projection.json",
        "memory_projection.json",
        "subjective_facts.json",
    ):
        (memory_dir / filename).unlink(missing_ok=True)
    for path in (resident_dir / "letters" / "intents").glob("intent_*.md"):
        path.unlink(missing_ok=True)

    reduced = rebuild_runtime_artifacts(memory_dir)

    assert _without_updated_at(json.loads((memory_dir / "runtime_projection.json").read_text(encoding="utf-8"))) == expected_runtime
    assert _without_updated_at(json.loads((memory_dir / "subjective_projection.json").read_text(encoding="utf-8"))) == expected_subjective
    assert _without_updated_at(json.loads((memory_dir / "memory_projection.json").read_text(encoding="utf-8"))) == expected_memory
    assert _without_updated_at(json.loads((memory_dir / "subjective_facts.json").read_text(encoding="utf-8"))) == expected_facts
    assert reduced.active_route is not None
    assert reduced.active_route["destination"] == "North Beach"
    assert any(item["recipient"] == "Levi" for item in reduced.active_mail_intents)
    assert any(fact["predicate"] == "headed_toward" for fact in reduced.subjective_facts["facts"])
    assert len(list((resident_dir / "letters" / "intents").glob("intent_*.md"))) == 1


def test_runtime_reducer_matches_ledger_history(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")
    research_queue = ResearchQueue(memory_dir / "research_queue.json")

    packet_queue.emit(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-levi-direct-reduce",
        location="Chinatown",
        payload={"speaker": "Levi", "message": "Tea's ready."},
    )
    research_queue.add("Chinatown tea houses", priority="normal", source="slow_reflection")

    events = load_runtime_events(memory_dir)
    reduced = reduce_runtime_events(events)

    assert len(events) == reduced.runtime_projection["ledger_event_count"]
    assert reduced.packets[0]["packet_type"] == "chat_heard"
    assert reduced.research_queue[0]["query"] == "Chinatown tea houses"
    predicates = {(fact["predicate"], fact["object"]) for fact in reduced.subjective_facts["facts"]}
    assert ("engaged_with", "Levi") in predicates
    assert ("curious_about", "Chinatown tea houses") in predicates


def test_runtime_mirror_syncs_reduced_state_to_session_vars(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    world = _DummyWorldClient()
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")
    research_queue = ResearchQueue(memory_dir / "research_queue.json")

    packet_queue.emit(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-levi-mirror",
        location="Chinatown",
        payload={"speaker": "Levi", "message": "Tea's ready."},
    )
    research_queue.add("Chinatown tea houses", priority="high", source="fast_ground_intent")

    mirror = ResidentRuntimeMirror(
        resident_dir=resident_dir,
        ww_client=world,
        session_id="sun_li-20260316-120000",
        interval_seconds=30.0,
    )

    asyncio.run(mirror.sync_once())

    assert len(world.session_var_updates) == 1
    session_id, payload = world.session_var_updates[0]
    assert session_id == "sun_li-20260316-120000"
    assert payload["_resident_ledger_event_count"] >= 2
    assert payload["_resident_runtime_projection"]["ledger_event_count"] >= 2
    assert payload["_resident_subjective_facts"]["facts"]


def test_subjective_projection_derives_threads_and_concerns(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")
    research_queue = ResearchQueue(memory_dir / "research_queue.json")

    packet_queue.emit(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-levi-1",
        location="Chinatown",
        payload={"speaker": "Levi", "message": "Tea is ready."},
    )
    packet_queue.emit(
        packet_type="mail_received",
        source_loop="mail",
        dedupe_key="from_levi_1",
        payload={"filename": "from_levi_20260316-120000.md"},
    )
    research_queue.add("Clement Street tea shops", priority="high", source="fast_ground_intent")

    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(memory_dir / "working.json"),
        provisional=ProvisionalScratchpad(memory_dir / "impressions"),
        reveries=ReverieDeck(memory_dir / "reveries.json"),
        voice=VoiceDeck(memory_dir / "voice.json"),
        rest_state=None,
        research_queue=research_queue,
        packet_queue=packet_queue,
        intent_queue=IntentQueue(memory_dir / "intent_queue.json"),
    )
    fast._save_route("North Beach", ["North Beach"])
    asyncio.run(fast._do_mail("Levi", "Ask if he still wants tea."))

    subjective = json.loads((memory_dir / "subjective_projection.json").read_text(encoding="utf-8"))
    thread_names = [item["name"] for item in subjective["active_social_threads"]]
    assert "Levi" in thread_names
    concern_kinds = [item["kind"] for item in subjective["current_concerns"]]
    dialogue_state = subjective["dialogue_state"]
    assert dialogue_state["active_partner"] == "Levi"
    assert "travel" in concern_kinds
    assert "research" in concern_kinds
    assert "correspondence" in concern_kinds


def test_fast_chat_packets_mark_direct_questions_and_requests(tmp_path):
    resident_dir = tmp_path / "sun_li"
    packet_queue = StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json")
    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        rest_state=None,
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        packet_queue=packet_queue,
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    fast._record_chat_packets(
        "chat_heard",
        "Chinatown",
        [
            ChatMessage(
                id=1,
                session_id="levi-session",
                display_name="Levi",
                message="Sun Li, what is in the drawer with the receipts?",
                ts="2026-03-17T18:00:00+00:00",
            ),
            ChatMessage(
                id=2,
                session_id="levi-session",
                display_name="Levi",
                message="Please stay a minute.",
                ts="2026-03-17T18:00:05+00:00",
            ),
        ],
    )

    packets = packet_queue.pending()
    assert packets[0].payload["is_direct"] is True
    assert packets[0].payload["is_question"] is True
    assert packets[0].payload["addressed"] is True
    assert packets[1].payload["is_request"] is True


def test_fast_city_chat_packets_do_not_mark_direct_pressure(tmp_path):
    resident_dir = tmp_path / "sun_li"
    packet_queue = StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json")
    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        rest_state=None,
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        packet_queue=packet_queue,
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    fast._record_chat_packets(
        "city_chat_heard",
        "San Francisco",
        [
            ChatMessage(
                id=1,
                session_id="levi-session",
                display_name="Levi",
                message="Sun Li, can you hear me out there?",
                ts="2026-03-17T18:00:00+00:00",
            ),
        ],
    )

    packets = packet_queue.pending()
    assert packets[0].payload["channel"] == "city"
    assert packets[0].payload["is_direct"] is False
    assert packets[0].payload["is_question"] is False
    assert packets[0].payload["is_request"] is False


def test_dialogue_state_derives_open_questions_and_reply_pressure(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")

    packet_queue.emit(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-levi-direct",
        location="Inner Richmond",
        payload={
            "speaker": "Levi",
            "message": "Sun Li, what is in the drawer with the receipts?",
            "is_direct": True,
            "is_question": True,
            "is_request": False,
        },
    )

    reduced = reduce_runtime_events(load_runtime_events(memory_dir))
    dialogue_state = reduced.subjective_projection["dialogue_state"]
    assert dialogue_state["active_partner"] == "Levi"
    assert dialogue_state["direct_urgency"] == 1.0
    assert dialogue_state["open_questions"][0]["speaker"] == "Levi"
    predicates = {(fact["predicate"], fact["object"]) for fact in reduced.subjective_facts["facts"]}
    assert ("owes_reply_to", "Levi") in predicates


def test_dialogue_state_ignores_overheard_unaddressed_question(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")

    packet_queue.emit(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-fei-overheard",
        location="Chinatown",
        payload={
            "speaker": "Fei Fei",
            "message": "Can you confirm you see the manhole cover?",
            "is_direct": False,
            "is_question": True,
            "is_request": False,
            "addressed": False,
        },
    )

    reduced = reduce_runtime_events(load_runtime_events(memory_dir))
    dialogue_state = reduced.subjective_projection["dialogue_state"]
    assert dialogue_state["active_partner"] == ""
    assert dialogue_state["direct_urgency"] == 0.0
    assert dialogue_state["open_questions"] == []
    predicates = {(fact["predicate"], fact["object"]) for fact in reduced.subjective_facts["facts"]}
    assert ("owes_reply_to", "Fei Fei") not in predicates


def test_subjective_projection_tracks_mail_pressure_and_city_context_separately(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")

    packet_queue.emit(
        packet_type="city_chat_heard",
        source_loop="fast",
        dedupe_key="city-levi-signal",
        location="San Francisco",
        payload={
            "speaker": "Levi",
            "message": "The ferry is delayed again tonight.",
            "is_direct": False,
            "is_question": False,
            "is_request": False,
            "channel": "city",
        },
    )
    packet_queue.emit(
        packet_type="mail_received",
        source_loop="mail",
        dedupe_key="from_levi_mail_1",
        payload={"filename": "from_levi_20260317-190000.md"},
    )

    reduced = reduce_runtime_events(load_runtime_events(memory_dir))
    subjective = reduced.subjective_projection
    assert subjective["dialogue_state"]["direct_urgency"] == 0.0
    assert subjective["mail_state"]["pending_inbox_count"] == 1
    assert subjective["mail_state"]["latest_sender"] == "Levi"
    assert subjective["city_context"]["signal_count"] == 1
    concern_kinds = [item["kind"] for item in subjective["current_concerns"]]
    assert "correspondence_reply" in concern_kinds
    assert "city_signal" not in concern_kinds


def test_subjective_projection_promotes_tagged_city_signal_without_fake_partner(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")

    packet_queue.emit(
        packet_type="city_chat_heard",
        source_loop="fast",
        dedupe_key="city-levi-tagged",
        location="San Francisco",
        payload={
            "speaker": "Levi",
            "message": "@Sun Li can you hear me out there?",
            "is_direct": True,
            "is_question": True,
            "is_request": False,
            "tagged": True,
            "channel": "city",
        },
    )

    reduced = reduce_runtime_events(load_runtime_events(memory_dir))
    subjective = reduced.subjective_projection
    concern_kinds = [item["kind"] for item in subjective["current_concerns"]]
    assert "city_signal" in concern_kinds
    assert subjective["dialogue_state"]["active_partner"] == "Levi"


def test_dialogue_state_does_not_promote_overheard_threads_to_active_partner(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")

    packet_queue.emit(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-fei-overheard-1",
        location="Chinatown",
        payload={
            "speaker": "Fei Fei",
            "message": "The note is set.",
            "is_direct": False,
            "is_question": False,
            "is_request": False,
            "addressed": False,
        },
    )
    packet_queue.emit(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-fei-overheard-2",
        location="Chinatown",
        payload={
            "speaker": "Fei Fei",
            "message": "Watch the steam by the alley.",
            "is_direct": False,
            "is_question": False,
            "is_request": False,
            "addressed": False,
        },
    )

    reduced = reduce_runtime_events(load_runtime_events(memory_dir))
    assert reduced.subjective_projection["active_social_threads"][0]["name"] == "Fei Fei"
    assert reduced.subjective_projection["dialogue_state"]["active_partner"] == ""


def test_subjective_projection_tracks_state_pressure_from_session_observation(tmp_path):
    reduced = reduce_runtime_events(
        [
            {
                "event_id": "evt-state-1",
                "ts": "2026-03-18T03:10:00+00:00",
                "event_type": "session_state_observed",
                "payload": {
                    "signals": [
                        {"kind": "fatigue", "label": "low energy", "level": 0.8},
                        {"kind": "tension", "label": "heightened tension", "level": 0.7},
                    ],
                    "raw": {"energy": 0.2, "danger_level": 2.0},
                    "context": {"time_of_day": "night", "weather": "rainy"},
                },
            }
        ]
    )
    pressure = reduced.subjective_projection["state_pressure"]
    assert pressure["signals"][0]["kind"] == "fatigue"
    predicates = {(fact["predicate"], fact["object"]) for fact in reduced.subjective_facts["facts"]}
    assert ("pressed_by", "low energy") in predicates


def test_subjective_projection_merges_ambient_pressure_from_grounding(tmp_path):
    reduced = reduce_runtime_events(
        [
            {
                "event_id": "evt-state-1",
                "ts": "2026-03-18T03:10:00+00:00",
                "event_type": "session_state_observed",
                "payload": {
                    "signals": [{"kind": "fatigue", "label": "low energy", "level": 0.8}],
                    "raw": {"energy": 0.2},
                    "context": {"time_of_day": "night"},
                },
            },
            {
                "event_id": "evt-ambient-1",
                "ts": "2026-03-18T03:11:00+00:00",
                "event_type": "ambient_pressure_observed",
                "payload": {
                    "signals": [
                        {"kind": "bad_weather", "label": "rain pressing against the day", "level": 0.72},
                        {"kind": "quiet", "label": "the neighborhood feels unusually quiet", "level": 0.7},
                    ],
                    "raw": {"current_present": 1, "vitality_score": 0.9},
                    "context": {
                        "weather": "rainy",
                        "neighborhood": "Inner Richmond",
                        "neighborhood_vibe": "quiet residential avenues near the park",
                    },
                },
            },
        ]
    )
    pressure = reduced.subjective_projection["state_pressure"]
    kinds = {item["kind"] for item in pressure["signals"]}
    assert {"fatigue", "bad_weather", "quiet"} <= kinds
    assert pressure["context"]["neighborhood"] == "Inner Richmond"
    predicates = {(fact["predicate"], fact["object"]) for fact in reduced.subjective_facts["facts"]}
    assert ("pressed_by", "rain pressing against the day") in predicates


def test_subjective_projection_replaces_stale_ambient_pressure_when_scene_changes(tmp_path):
    reduced = reduce_runtime_events(
        [
            {
                "event_id": "evt-ambient-old",
                "ts": "2026-03-18T03:10:00+00:00",
                "event_type": "ambient_pressure_observed",
                "payload": {
                    "source": "ambient",
                    "signals": [
                        {"kind": "quiet", "label": "the neighborhood feels unusually quiet", "level": 0.72},
                    ],
                    "raw": {"current_present": 1, "recent_event_count": 1},
                    "context": {"location": "Jordan Park", "neighborhood": "Jordan Park"},
                },
            },
            {
                "event_id": "evt-ambient-new",
                "ts": "2026-03-18T03:14:00+00:00",
                "event_type": "ambient_pressure_observed",
                "payload": {
                    "source": "ambient",
                    "signals": [
                        {"kind": "crowding", "label": "the neighborhood feels unusually busy", "level": 0.92},
                        {"kind": "event_pull", "label": "there is a live current running through nearby streets", "level": 0.9},
                    ],
                    "raw": {"current_present": 7, "recent_event_count": 10},
                    "context": {"location": "Fillmore", "neighborhood": "Fillmore"},
                },
            },
        ]
    )
    pressure = reduced.subjective_projection["state_pressure"]
    kinds = {item["kind"] for item in pressure["signals"]}
    assert "quiet" not in kinds
    assert {"crowding", "event_pull"} <= kinds
    assert pressure["context"]["location"] == "Fillmore"
    assert pressure["raw"]["current_present"] == 7


def test_dialogue_state_keeps_short_followup_after_direct_address(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")

    packet_queue.emit(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-levi-addressed",
        location="Chinatown",
        payload={
            "speaker": "Levi",
            "message": "Sun Li, come here.",
            "is_direct": True,
            "is_question": False,
            "is_request": True,
            "addressed": True,
        },
    )
    packet_queue.emit(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-levi-followup",
        location="Chinatown",
        payload={
            "speaker": "Levi",
            "message": "Over here.",
            "is_direct": False,
            "is_question": False,
            "is_request": True,
            "addressed": False,
        },
    )

    reduced = reduce_runtime_events(load_runtime_events(memory_dir))
    dialogue_state = reduced.subjective_projection["dialogue_state"]
    assert dialogue_state["active_partner"] == "Levi"
    assert dialogue_state["open_requests"][-1]["message"] == "Over here."


def test_slow_loop_stages_dialogue_reply_fallback_when_intent_assessment_returns_nothing(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")
    intent_queue = IntentQueue(memory_dir / "intent_queue.json")

    packet_queue.emit(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-levi-direct-fallback",
        location="Inner Richmond",
        payload={
            "speaker": "Levi",
            "message": "Sun Li, what is in the drawer with the receipts?",
            "is_direct": True,
            "is_question": True,
            "is_request": False,
        },
    )

    class _FallbackInference(_DummyInferenceClient):
        async def complete_json(self, *args, **kwargs):
            return {"intents": []}

        async def complete(self, *args, **kwargs):
            system_prompt = kwargs.get("system_prompt") or ""
            if "immediate reply to someone nearby" in system_prompt:
                return "The receipt drawer holds old notes and family things."
            return "I keep old things longer than I mean to."

    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_FallbackInference(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(memory_dir / "working.json"),
        provisional=ProvisionalScratchpad(memory_dir / "impressions"),
        long_term=LongTermMemory(memory_dir / "long_term.json"),
        reveries=ReverieDeck(memory_dir / "reveries.json"),
        voice=VoiceDeck(memory_dir / "voice.json"),
        research_queue=ResearchQueue(memory_dir / "research_queue.json"),
        rest_state=None,
        packet_queue=packet_queue,
        intent_queue=intent_queue,
    )

    packets = packet_queue.pending()
    reduced = reduce_runtime_events(load_runtime_events(memory_dir))
    staged = asyncio.run(
        slow._stage_structured_intents(
            reflection="I can feel Levi waiting on the answer.",
            subconscious_reading="Levi is asking directly what is in the drawer.",
            packets=packets,
            current_location="Inner Richmond",
            adjacent_names=["Seacliff"],
            all_location_names=["Inner Richmond", "Seacliff"],
            recent=[],
            reduced_state=reduced,
            circadian_profile=None,
            urgent_dialogue=True,
        )
    )

    assert staged
    assert staged[0]["intent_type"] == "chat"
    assert "receipt drawer" in staged[0]["payload"]["utterance"]
    queued = intent_queue.pending(target_loop="fast")
    assert queued
    assert queued[0].intent_type == "chat"


def test_memory_projection_derives_recent_experiences_and_pending_items(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")
    research_queue = ResearchQueue(memory_dir / "research_queue.json")

    packet_queue.emit(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-levi-2",
        location="Chinatown",
        payload={"speaker": "Levi", "message": "Come by the tea house."},
    )
    research_queue.add("North Beach tea houses", priority="normal", source="slow_reflection")

    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(memory_dir / "working.json"),
        provisional=ProvisionalScratchpad(memory_dir / "impressions"),
        reveries=ReverieDeck(memory_dir / "reveries.json"),
        voice=VoiceDeck(memory_dir / "voice.json"),
        rest_state=None,
        research_queue=research_queue,
        packet_queue=packet_queue,
        intent_queue=IntentQueue(memory_dir / "intent_queue.json"),
    )
    fast._save_route("North Beach", ["North Beach"])
    asyncio.run(fast._do_mail("Levi", "Tell him you'll head over soon."))

    memory_projection = json.loads((memory_dir / "memory_projection.json").read_text(encoding="utf-8"))
    assert memory_projection["active_route"]["destination"] == "North Beach"
    assert memory_projection["pending_research"][0]["query"] == "North Beach tea houses"
    assert memory_projection["pending_correspondence"][0]["recipient"] == "Levi"
    kinds = [item["kind"] for item in memory_projection["recent_experiences"]]
    assert "mail" in kinds


def test_subjective_facts_derive_social_and_goal_facts(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")
    research_queue = ResearchQueue(memory_dir / "research_queue.json")

    packet_queue.emit(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-levi-3",
        location="Chinatown",
        payload={"speaker": "Levi", "message": "Meet me in North Beach."},
    )
    research_queue.add("North Beach tea shops", priority="high", source="fast_ground_intent")

    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(memory_dir / "working.json"),
        provisional=ProvisionalScratchpad(memory_dir / "impressions"),
        reveries=ReverieDeck(memory_dir / "reveries.json"),
        voice=VoiceDeck(memory_dir / "voice.json"),
        rest_state=None,
        research_queue=research_queue,
        packet_queue=packet_queue,
        intent_queue=IntentQueue(memory_dir / "intent_queue.json"),
    )
    fast._save_route("North Beach", ["North Beach"])
    asyncio.run(fast._do_mail("Levi", "Tell him you'll come by soon."))

    facts_doc = json.loads((memory_dir / "subjective_facts.json").read_text(encoding="utf-8"))
    facts = facts_doc["facts"]

    predicates = {(fact["predicate"], fact["object"]) for fact in facts}
    assert ("engaged_with", "Levi") in predicates
    assert ("curious_about", "North Beach tea shops") in predicates
    assert ("wants_to_write", "Levi") in predicates
    assert ("headed_toward", "North Beach") in predicates


def test_fast_loop_ground_intent_adds_high_priority_research(tmp_path):
    resident_dir = tmp_path / "sun_li"
    research_queue = ResearchQueue(resident_dir / "memory" / "research_queue.json")

    class _GroundWorld(_DummyWorldClient):
        async def get_grounding(self):
            return {
                "datetime_str": "Tuesday, 3:15 PM",
                "weather_description": "clear and cool",
            }

    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_GroundWorld(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        rest_state=None,
        research_queue=research_queue,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    asyncio.run(
        fast._do_ground(
            type("Scene", (), {"location": "Inner Richmond"})(),
            query="Clement Street farmers market hours",
        )
    )

    queued = research_queue.pop_next()
    assert queued is not None
    assert queued["query"] == "Clement Street farmers market hours"
    assert queued["priority"] == "high"
    projection = json.loads((resident_dir / "memory" / "runtime_projection.json").read_text(encoding="utf-8"))
    assert projection["last_grounding"]["query"] == "Clement Street farmers market hours"
    assert projection["event_counts"]["ground_intent_executed"] == 1
    assert projection["event_counts"]["research_queued"] == 1


def test_slow_loop_records_state_pressure_from_session_vars(tmp_path):
    resident_dir = tmp_path / "sun_li"
    ww = _DummyWorldClient()
    ww.session_vars_payload = {
        "vars": {
            "danger_level": 6,
            "_mood_tension": 0.3,
            "energy": 0.2,
            "_time_of_day": "night",
            "_weather": "rainy",
        }
    }
    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=ww,
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    context = asyncio.run(slow._gather_context())
    pressure = context["reduced_state"].subjective_projection["state_pressure"]
    kinds = {item["kind"] for item in pressure["signals"]}
    assert {"danger", "tension", "fatigue"} <= kinds


def test_slow_loop_stages_ground_intent_with_query_payload(tmp_path):
    resident_dir = tmp_path / "sun_li"
    packet_queue = StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json")
    intent_queue = IntentQueue(resident_dir / "memory" / "intent_queue.json")

    class _GroundIntentLLM(_DummyInferenceClient):
        async def complete_json(self, *args, **kwargs):
            return {
                "intents": [
                    {
                        "intent_type": "ground",
                        "priority": 0.74,
                        "target_loop": "fast",
                        "payload": {"query": "ASL organizations in Chinatown"},
                    }
                ]
            }

    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_GroundIntentLLM(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        rest_state=None,
        packet_queue=packet_queue,
        intent_queue=intent_queue,
    )

    staged = asyncio.run(
        slow._stage_structured_intents(
            reflection="I should find something useful for them.",
            subconscious_reading="They want a quick real-world lookup before speaking again.",
            packets=[],
            current_location="Chinatown",
            adjacent_names=["North Beach"],
            all_location_names=["Chinatown", "North Beach"],
            recent=[],
            reduced_state=_empty_reduced_state(),
            circadian_profile=None,
            urgent_dialogue=False,
        )
    )

    assert staged[0]["intent_type"] == "ground"
    assert staged[0]["payload"]["query"] == "ASL organizations in Chinatown"
    queued = intent_queue.pending(target_loop="fast")
    assert queued[0].payload["query"] == "ASL organizations in Chinatown"


def test_slow_loop_suppresses_ground_when_state_pressure_is_high(tmp_path):
    resident_dir = tmp_path / "sun_li"
    intent_queue = IntentQueue(resident_dir / "memory" / "intent_queue.json")

    class _GroundLLM(_DummyInferenceClient):
        async def complete_json(self, *args, **kwargs):
            return {
                "intents": [
                    {
                        "intent_type": "ground",
                        "priority": 0.9,
                        "target_loop": "fast",
                        "payload": {"query": "streetcar hours"},
                    }
                ]
            }

    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_GroundLLM(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=intent_queue,
    )

    reduced = reduce_runtime_events(
        [
            {
                "event_id": "evt-state-1",
                "ts": "2026-03-18T03:10:00+00:00",
                "event_type": "session_state_observed",
                "payload": {
                    "signals": [{"kind": "fatigue", "label": "low energy", "level": 0.8}],
                    "raw": {"energy": 0.2},
                    "context": {"time_of_day": "night"},
                },
            }
        ]
    )

    staged = asyncio.run(
        slow._stage_structured_intents(
            reflection="I don't have much left in me.",
            subconscious_reading="They should keep their head down.",
            packets=[],
            current_location="Inner Richmond",
            adjacent_names=["Seacliff"],
            all_location_names=["Inner Richmond", "Seacliff"],
            recent=[],
            reduced_state=reduced,
            circadian_profile=None,
            urgent_dialogue=False,
        )
    )

    assert [item["intent_type"] for item in staged] == ["act"]
    assert "slow down" in staged[0]["payload"]["action"].lower()
    queued = intent_queue.pending(target_loop="fast")
    assert len(queued) == 1
    assert queued[0].intent_type == "act"


def test_slow_loop_adds_embodied_action_nudge_from_state_pressure(tmp_path):
    resident_dir = tmp_path / "sun_li"
    intent_queue = IntentQueue(resident_dir / "memory" / "intent_queue.json")
    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=intent_queue,
    )

    reduced = reduce_runtime_events(
        [
            {
                "event_id": "evt-ambient-1",
                "ts": "2026-03-18T03:11:00+00:00",
                "event_type": "ambient_pressure_observed",
                "payload": {
                    "source": "ambient",
                    "signals": [
                        {"kind": "quiet", "label": "the neighborhood feels unusually quiet", "level": 0.7},
                    ],
                    "raw": {"current_present": 1, "vitality_score": 0.9},
                    "context": {"location": "Inner Richmond", "neighborhood": "Inner Richmond"},
                },
            },
        ]
    )

    staged = asyncio.run(
        slow._stage_structured_intents(
            reflection="The street has gone still around me.",
            subconscious_reading="The quiet itself is asking for a pause.",
            packets=[],
            current_location="Inner Richmond",
            adjacent_names=["Seacliff"],
            all_location_names=["Inner Richmond", "Seacliff"],
            recent=[],
            reduced_state=reduced,
            circadian_profile=None,
            urgent_dialogue=False,
        )
    )

    act = next(item for item in staged if item["intent_type"] == "act")
    assert "quiet" in act["payload"]["action"].lower()
    queued = intent_queue.pending(target_loop="fast")
    assert len(queued) == 1
    assert queued[0].intent_type == "act"
    assert "quiet" in queued[0].payload["action"].lower()


def test_slow_loop_suppresses_ambient_move_during_quiet_bad_weather(tmp_path):
    resident_dir = tmp_path / "sun_li"
    intent_queue = IntentQueue(resident_dir / "memory" / "intent_queue.json")

    class _MoveLLM(_DummyInferenceClient):
        async def complete_json(self, *args, **kwargs):
            return {
                "intents": [
                    {
                        "intent_type": "move",
                        "priority": 0.6,
                        "target_loop": "fast",
                        "payload": {"destination": "North Beach"},
                    }
                ]
            }

    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_MoveLLM(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=intent_queue,
    )

    reduced = reduce_runtime_events(
        [
            {
                "event_id": "evt-ambient-1",
                "ts": "2026-03-18T03:11:00+00:00",
                "event_type": "ambient_pressure_observed",
                "payload": {
                    "signals": [
                        {"kind": "bad_weather", "label": "rain pressing against the day", "level": 0.72},
                        {"kind": "quiet", "label": "the neighborhood feels unusually quiet", "level": 0.7},
                    ],
                    "raw": {"current_present": 1, "vitality_score": 0.9},
                    "context": {"weather": "rainy", "neighborhood": "Inner Richmond"},
                },
            }
        ]
    )

    staged = asyncio.run(
        slow._stage_structured_intents(
            reflection="Maybe I should go out and see what's happening.",
            subconscious_reading="They are tempted to wander.",
            packets=[],
            current_location="Inner Richmond",
            adjacent_names=["North Beach"],
            all_location_names=["Inner Richmond", "North Beach"],
            recent=[],
            reduced_state=reduced,
            circadian_profile=None,
            urgent_dialogue=False,
        )
    )

    assert [item["intent_type"] for item in staged] == ["act"]
    assert "shelter" in staged[0]["payload"]["action"].lower()
    queued = intent_queue.pending(target_loop="fast")
    assert len(queued) == 1
    assert queued[0].intent_type == "act"


def test_ground_loop_records_ambient_pressure_from_city_context(tmp_path):
    resident_dir = tmp_path / "sun_li"

    class _GroundWorld(_DummyWorldClient):
        async def get_grounding(self):
            return {
                "datetime_str": "Tuesday, 3:15 PM",
                "time_of_day": "afternoon",
                "weather_description": "cool fog and light rain",
            }

        async def get_news(self):
            return ["A neighborhood fair is picking up downtown."]

        async def get_scene(self, session_id: str):
            return type(
                "Scene",
                (),
                {
                    "location": "Inner Richmond",
                    "present": [object(), object(), object(), object()],
                    "recent_events_here": [object(), object(), object()],
                    "location_graph": {"nodes": [], "edges": []},
                },
            )()

        async def get_neighborhood_vitality(self, hours: int = 6):
            return {
                "Inner Richmond": {
                    "name": "Inner Richmond",
                    "vitality_score": 4.4,
                    "current_present": 5,
                    "current_agents": 2,
                    "chat_messages_recent": 7,
                    "recent_event_count": 6,
                }
            }

    class _GroundLLM(_DummyInferenceClient):
        async def complete(self, *args, **kwargs):
            return "Sun Li notices the wet light on the avenue and the neighborhood moving around her."

    ground = GroundLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_GroundWorld(),
        llm=_GroundLLM(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
    )

    context = asyncio.run(ground._gather_context())
    asyncio.run(ground._decide_and_execute(context))

    reduced = reduce_runtime_events(load_runtime_events(resident_dir / "memory"))
    pressure = reduced.subjective_projection["state_pressure"]
    kinds = {item["kind"] for item in pressure["signals"]}
    assert {"bad_weather", "crowding", "event_pull"} <= kinds
    assert pressure["context"]["neighborhood"] == "Inner Richmond"
    assert "vitality_score" in pressure["raw"]


def test_slow_loop_skips_research_when_mail_pressure_is_pending(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")
    packet_queue.emit(
        packet_type="mail_received",
        source_loop="mail",
        dedupe_key="from_levi_mail_3",
        payload={"filename": "from_levi_20260317-210000.md"},
    )

    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(memory_dir / "working.json"),
        provisional=ProvisionalScratchpad(memory_dir / "impressions"),
        long_term=LongTermMemory(memory_dir / "long_term.json"),
        reveries=ReverieDeck(memory_dir / "reveries.json"),
        voice=VoiceDeck(memory_dir / "voice.json"),
        research_queue=ResearchQueue(memory_dir / "research_queue.json"),
        rest_state=None,
        packet_queue=packet_queue,
        intent_queue=IntentQueue(memory_dir / "intent_queue.json"),
    )

    reduced = reduce_runtime_events(load_runtime_events(memory_dir))
    assert (
        slow._should_extract_research(
            reduced_state=reduced,
            urgent_dialogue=False,
            quiet_hours=False,
        )
        is False
    )


def test_slow_loop_skips_research_when_backlog_is_already_high(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    research_queue = ResearchQueue(memory_dir / "research_queue.json")
    for query in [
        "North Beach tea houses",
        "Chinatown street market hours",
        "Richmond dumpling history",
    ]:
        research_queue.add(query, priority="normal", source="slow_reflection")

    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(memory_dir / "working.json"),
        provisional=ProvisionalScratchpad(memory_dir / "impressions"),
        long_term=LongTermMemory(memory_dir / "long_term.json"),
        reveries=ReverieDeck(memory_dir / "reveries.json"),
        voice=VoiceDeck(memory_dir / "voice.json"),
        research_queue=research_queue,
        rest_state=None,
        packet_queue=StimulusPacketQueue(memory_dir / "stimulus_packets.json"),
        intent_queue=IntentQueue(memory_dir / "intent_queue.json"),
    )

    reduced = reduce_runtime_events(load_runtime_events(memory_dir))
    assert len(reduced.memory_projection["pending_research"]) == 3
    assert (
        slow._should_extract_research(
            reduced_state=reduced,
            urgent_dialogue=False,
            quiet_hours=False,
        )
        is False
    )


def test_slow_loop_stages_mail_reply_pressure_from_pending_letter(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")
    packet_queue.emit(
        packet_type="mail_received",
        source_loop="mail",
        dedupe_key="from_levi_mail_2",
        payload={"filename": "from_levi_20260317-190000.md"},
    )

    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(memory_dir / "working.json"),
        provisional=ProvisionalScratchpad(memory_dir / "impressions"),
        long_term=LongTermMemory(memory_dir / "long_term.json"),
        reveries=ReverieDeck(memory_dir / "reveries.json"),
        voice=VoiceDeck(memory_dir / "voice.json"),
        research_queue=ResearchQueue(memory_dir / "research_queue.json"),
        rest_state=None,
        packet_queue=packet_queue,
        intent_queue=IntentQueue(memory_dir / "intent_queue.json"),
    )

    reduced = reduce_runtime_events(load_runtime_events(memory_dir))
    recipient = slow._maybe_stage_mail_reply_pressure(
        reduced_state=reduced,
        subconscious_reading="Levi has stayed with them all evening.",
        urgent_dialogue=False,
        queued_intents=[],
    )

    assert recipient == "Levi"
    refreshed = reduce_runtime_events(load_runtime_events(memory_dir))
    assert any(item["recipient"] == "Levi" for item in refreshed.active_mail_intents)


def test_slow_loop_quiet_hours_dampen_ambient_move_chat_and_ground(tmp_path):
    resident_dir = tmp_path / "sun_li"
    intent_queue = IntentQueue(resident_dir / "memory" / "intent_queue.json")

    class _QuietHoursLLM(_DummyInferenceClient):
        async def complete_json(self, *args, **kwargs):
            return {
                "intents": [
                    {
                        "intent_type": "chat",
                        "priority": 0.8,
                        "target_loop": "fast",
                        "payload": {"utterance": "Anyone still out?"},
                    },
                    {
                        "intent_type": "move",
                        "priority": 0.7,
                        "target_loop": "fast",
                        "payload": {"destination": "North Beach"},
                    },
                    {
                        "intent_type": "ground",
                        "priority": 0.6,
                        "target_loop": "fast",
                        "payload": {"query": "late night bus schedule"},
                    },
                ]
            }

    class _Profile:
        quiet_hours = True
        pressure = 0.95
        summary = "Local hour 3:00, phase=sleep_window, chronotype=day, quiet_hours=True, pressure=0.95"

    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_QuietHoursLLM(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=intent_queue,
    )

    staged = asyncio.run(
        slow._stage_structured_intents(
            reflection="The street has gone still.",
            subconscious_reading="Nothing requires action right now.",
            packets=[],
            current_location="Chinatown",
            adjacent_names=["North Beach"],
            all_location_names=["Chinatown", "North Beach"],
            recent=[],
            reduced_state=_empty_reduced_state(),
            circadian_profile=_Profile(),
            urgent_dialogue=False,
        )
    )

    assert staged == []
    assert intent_queue.pending(target_loop="fast") == []


def test_slow_loop_stages_structured_chat_intent_from_packets(tmp_path):
    resident_dir = tmp_path / "sun_li"
    packet_queue = StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json")
    intent_queue = IntentQueue(resident_dir / "memory" / "intent_queue.json")
    packet = packet_queue.emit(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-levi",
        location="Chinatown",
        payload={"speaker": "Levi", "message": "Tea's ready."},
    )

    class _IntentLLM(_DummyInferenceClient):
        async def complete_json(self, *args, **kwargs):
            return {
                "intents": [
                    {
                        "intent_type": "chat",
                        "priority": 0.82,
                        "target_loop": "fast",
                        "payload": {"utterance": "I'll be right there."},
                    }
                ]
            }

    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_IntentLLM(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        rest_state=None,
        packet_queue=packet_queue,
        intent_queue=intent_queue,
    )

    staged = asyncio.run(
        slow._stage_structured_intents(
            reflection="I should answer Levi.",
            subconscious_reading="They want to say they'll come in a moment.",
            packets=[packet],
            current_location="Chinatown",
            adjacent_names=["North Beach"],
            all_location_names=["Chinatown", "North Beach"],
            recent=[],
            reduced_state=_empty_reduced_state(),
            circadian_profile=None,
            urgent_dialogue=False,
        )
    )

    assert staged[0]["intent_type"] == "chat"
    queued = intent_queue.pending(target_loop="fast")
    assert len(queued) == 1
    assert queued[0].payload["utterance"] == "I'll be right there."
    assert queued[0].source_packet_ids == [packet.packet_id]


def test_slow_loop_adds_move_nudge_after_long_stillness(tmp_path):
    resident_dir = tmp_path / "sun_li"
    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    staged = asyncio.run(
        slow._stage_structured_intents(
            reflection="The room is still.",
            subconscious_reading="They are settled but not stuck.",
            packets=[],
            current_location="Inner Richmond",
            adjacent_names=["Chinatown", "Outer Richmond"],
            all_location_names=["Inner Richmond", "Chinatown", "Outer Richmond"],
            recent=[
                {"type": "grounding", "location": "Inner Richmond"},
                {"type": "grounding", "location": "Inner Richmond"},
                {"type": "grounding", "location": "Inner Richmond"},
                {"type": "grounding", "location": "Inner Richmond"},
                {"type": "grounding", "location": "Inner Richmond"},
            ],
            reduced_state=_empty_reduced_state(),
            circadian_profile=None,
            urgent_dialogue=False,
        )
    )

    move = next(item for item in staged if item["intent_type"] == "move")
    assert move["payload"]["destination"] in {"Chinatown", "Outer Richmond"}


def test_slow_loop_ambient_event_spillover_can_trigger_movement_nudge(tmp_path):
    resident_dir = tmp_path / "sun_li"
    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    scene = type(
        "Scene",
        (),
        {
            "ambient_presence": [
                AmbientPresence(
                    kind="event_spillover",
                    label="Something nearby keeps sending fresh ripples of attention through this area.",
                    source="recent_event_pattern",
                    intensity=0.72,
                    pressure_tags=["event_pull"],
                )
            ]
        },
    )()

    staged = asyncio.run(
        slow._stage_structured_intents(
            reflection="Something in the neighborhood keeps tugging at the edge of my attention.",
            subconscious_reading="There is a little motion in the block that makes movement feel natural.",
            scene=scene,
            packets=[],
            current_location="Inner Richmond",
            adjacent_names=["Chinatown", "Outer Richmond"],
            all_location_names=["Inner Richmond", "Chinatown", "Outer Richmond"],
            recent=[
                {"type": "grounding", "location": "Inner Richmond"},
                {"type": "grounding", "location": "Inner Richmond"},
            ],
            reduced_state=_empty_reduced_state(),
            circadian_profile=None,
            urgent_dialogue=False,
        )
    )

    move = next(item for item in staged if item["intent_type"] == "move")
    assert move["payload"]["destination"] in {"Chinatown", "Outer Richmond"}
    assert move["payload"]["reason"] == "follow_the_flow_of_the_block"


def test_slow_loop_overheard_chat_does_not_block_movement_nudge(tmp_path):
    resident_dir = tmp_path / "sun_li"
    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    scene = type(
        "Scene",
        (),
        {
            "ambient_presence": [
                AmbientPresence(
                    kind="event_spillover",
                    label="Something nearby keeps sending fresh ripples of attention through this area.",
                    source="recent_event_pattern",
                    intensity=0.72,
                    pressure_tags=["event_pull"],
                )
            ]
        },
    )()

    packets = [
        StimulusPacket.create(
            packet_type="chat_heard",
            source_loop="fast",
            location="Inner Richmond",
            payload={
                "speaker": "Someone Nearby",
                "message": "Did you see that?",
                "addressed": False,
                "is_direct": False,
                "is_question": False,
                "is_request": False,
            },
        )
    ]

    staged = asyncio.run(
        slow._stage_structured_intents(
            reflection="The block keeps shifting around me in a way that makes motion feel easy.",
            subconscious_reading="There is enough hum here that following it would feel natural.",
            scene=scene,
            packets=packets,
            current_location="Inner Richmond",
            adjacent_names=["Chinatown", "Outer Richmond"],
            all_location_names=["Inner Richmond", "Chinatown", "Outer Richmond"],
            recent=[
                {"type": "grounding", "location": "Inner Richmond"},
                {"type": "grounding", "location": "Inner Richmond"},
            ],
            reduced_state=_empty_reduced_state(),
            circadian_profile=None,
            urgent_dialogue=False,
        )
    )

    move = next(item for item in staged if item["intent_type"] == "move")
    assert move["payload"]["reason"] == "follow_the_flow_of_the_block"


def test_slow_loop_direct_chat_still_blocks_movement_nudge(tmp_path):
    resident_dir = tmp_path / "sun_li"
    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    scene = type(
        "Scene",
        (),
        {
            "ambient_presence": [
                AmbientPresence(
                    kind="event_spillover",
                    label="Something nearby keeps sending fresh ripples of attention through this area.",
                    source="recent_event_pattern",
                    intensity=0.72,
                    pressure_tags=["event_pull"],
                )
            ]
        },
    )()

    packets = [
        StimulusPacket.create(
            packet_type="chat_heard",
            source_loop="fast",
            location="Inner Richmond",
            payload={
                "speaker": "Levi",
                "message": "Sun Li, can you come here for a second?",
                "addressed": True,
                "is_direct": True,
                "is_question": True,
                "is_request": False,
            },
        )
    ]

    staged = asyncio.run(
        slow._stage_structured_intents(
            reflection="The block keeps shifting around me in a way that makes motion feel easy.",
            subconscious_reading="There is enough hum here that following it would feel natural.",
            scene=scene,
            packets=packets,
            current_location="Inner Richmond",
            adjacent_names=["Chinatown", "Outer Richmond"],
            all_location_names=["Inner Richmond", "Chinatown", "Outer Richmond"],
            recent=[
                {"type": "grounding", "location": "Inner Richmond"},
                {"type": "grounding", "location": "Inner Richmond"},
            ],
            reduced_state=_empty_reduced_state(),
            circadian_profile=None,
            urgent_dialogue=False,
        )
    )

    assert all(item["intent_type"] != "move" for item in staged)


def test_slow_loop_stages_homeward_move_before_rest(tmp_path):
    resident_dir = tmp_path / "sun_li"
    intent_queue = IntentQueue(resident_dir / "memory" / "intent_queue.json")

    class _Profile:
        pressure = 0.92

    slow = SlowLoop(
        identity=_identity(home_location="Outer Richmond"),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=intent_queue,
    )

    move = slow._maybe_stage_homeward_move(
        current_location="Chinatown",
        all_location_names=["Chinatown", "Outer Richmond"],
        reduced_state=_empty_reduced_state(),
        rest_assessment=RestAssessment(
            should_rest=True,
            rest_kind="sleep",
            confidence=0.85,
            reason="late night drift",
            evidence=("quiet block",),
        ),
        queued_intents=[],
        circadian_profile=_Profile(),
        urgent_dialogue=False,
    )

    assert move is not None
    assert move["intent_type"] == "move"
    assert move["payload"]["destination"] == "Outer Richmond"
    queued = intent_queue.pending(target_loop="fast")
    assert len(queued) == 1
    assert queued[0].payload["destination"] == "Outer Richmond"


def test_slow_loop_drops_non_graph_move_and_keeps_movement_nudge(tmp_path):
    resident_dir = tmp_path / "sun_li"
    packet_queue = StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json")
    intent_queue = IntentQueue(resident_dir / "memory" / "intent_queue.json")

    class _BadMoveLLM(_DummyInferenceClient):
        async def complete_json(self, *args, **kwargs):
            return {
                "intents": [
                    {
                        "intent_type": "move",
                        "priority": 0.91,
                        "target_loop": "fast",
                        "payload": {"destination": "bench by the laundromat"},
                    }
                ]
            }

    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_BadMoveLLM(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        rest_state=None,
        packet_queue=packet_queue,
        intent_queue=intent_queue,
    )

    staged = asyncio.run(
        slow._stage_structured_intents(
            reflection="I should probably get out of here.",
            subconscious_reading="They want to move somewhere else.",
            packets=[],
            current_location="Inner Richmond",
            adjacent_names=["Chinatown", "Outer Richmond"],
            all_location_names=["Inner Richmond", "Chinatown", "Outer Richmond"],
            recent=[
                {"type": "grounding", "location": "Inner Richmond"},
                {"type": "grounding", "location": "Inner Richmond"},
                {"type": "grounding", "location": "Inner Richmond"},
                {"type": "grounding", "location": "Inner Richmond"},
                {"type": "grounding", "location": "Inner Richmond"},
            ],
            reduced_state=_empty_reduced_state(),
            circadian_profile=None,
            urgent_dialogue=False,
        )
    )

    move_items = [item for item in staged if item["intent_type"] == "move"]
    assert len(move_items) == 1
    assert move_items[0]["payload"]["destination"] in {"Chinatown", "Outer Richmond"}
    queued = intent_queue.pending(target_loop="fast")
    assert len(queued) == 1
    assert queued[0].payload["destination"] in {"Chinatown", "Outer Richmond"}


def test_slow_loop_prefers_ambient_shelter_action_over_generic_weather_nudge(tmp_path):
    resident_dir = tmp_path / "sun_li"
    intent_queue = IntentQueue(resident_dir / "memory" / "intent_queue.json")
    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=intent_queue,
    )

    reduced = reduce_runtime_events(
        [
            {
                "event_id": "evt-ambient-1",
                "ts": "2026-03-18T03:11:00+00:00",
                "event_type": "ambient_pressure_observed",
                "payload": {
                    "source": "ambient",
                    "signals": [
                        {"kind": "bad_weather", "label": "rain pressing against the day", "level": 0.72},
                    ],
                    "raw": {"current_present": 3},
                    "context": {"location": "Inner Richmond", "neighborhood": "Inner Richmond"},
                },
            },
        ]
    )
    scene = type(
        "Scene",
        (),
        {
            "ambient_presence": [
                AmbientPresence(
                    kind="weather_shelter_cluster",
                    label="People keep collecting in the sheltered edges of the block.",
                    source="grounding",
                    intensity=0.66,
                    pressure_tags=["bad_weather", "shelter"],
                )
            ]
        },
    )()

    staged = asyncio.run(
        slow._stage_structured_intents(
            reflection="The rain changes how everyone is holding the block.",
            subconscious_reading="The weather is the first thing to answer to right now.",
            scene=scene,
            packets=[],
            current_location="Inner Richmond",
            adjacent_names=["Seacliff"],
            all_location_names=["Inner Richmond", "Seacliff"],
            recent=[],
            reduced_state=reduced,
            circadian_profile=None,
            urgent_dialogue=False,
        )
    )

    assert [item["intent_type"] for item in staged] == ["act"]
    assert "under cover" in staged[0]["payload"]["action"].lower()
    queued = intent_queue.pending(target_loop="fast")
    assert len(queued) == 1
    assert queued[0].intent_type == "act"


def test_slow_loop_decide_and_execute_uses_context_adjacent_names_without_crashing(tmp_path):
    resident_dir = tmp_path / "sun_li"
    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=ResearchQueue(resident_dir / "memory" / "research_queue.json"),
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    asyncio.run(
        slow._decide_and_execute(
            {
                "pending": [],
                "packets": [],
                "recent": [],
                "world_facts": [],
                "long_term": [],
                "map_context": "",
                "current_location": "Chinatown",
                "adjacent_names": ["North Beach", "Outer Richmond"],
                "all_location_names": ["Chinatown", "North Beach", "Outer Richmond"],
                "reduced_state": _empty_reduced_state(),
            }
        )
    )

    assert slow._intents is not None


def test_slow_loop_uses_sanitized_reflection_downstream(tmp_path):
    resident_dir = tmp_path / "sun_li"
    llm = _SequencedInferenceClient(
        complete_responses=[
            (
                "Okay, the user has shared a scene. I need to incorporate the setting is Chinatown. "
                "Key elements: damp air, closed shutters, player action, observed movement. "
                "But underneath that, I'm keyed up by the wind and how exposed the street feels."
            ),
            (
                "I'm keyed up by the wind and how exposed the street feels. "
                "The block makes me want to keep moving instead of waiting around."
            ),
            "They want to keep moving and stay alert, but no one specific is on their mind.",
            "The wind keeps my shoulders high.",
        ],
        json_responses=[
            {
                "should_rest": False,
                "rest_kind": "none",
                "confidence": 0.1,
                "reason": "",
                "evidence": [],
            },
            {"intents": []},
        ],
    )
    long_term = LongTermMemory(resident_dir / "memory" / "long_term")
    reveries = ReverieDeck(resident_dir / "memory" / "reveries.json")
    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=llm,
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=long_term,
        reveries=reveries,
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=None,
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    asyncio.run(
        slow._decide_and_execute(
            {
                "pending": [],
                "packets": [],
                "recent": [{"action": "stayed by the tea counter", "location": "Chinatown"}],
                "world_facts": [],
                "long_term": [],
                "map_context": "",
                "current_location": "Chinatown",
                "adjacent_names": ["North Beach"],
                "all_location_names": ["Chinatown", "North Beach"],
                "reduced_state": _empty_reduced_state(),
                "scene": None,
            }
        )
    )

    decision_path = resident_dir / "decisions" / "decision_1.json"
    payload = json.loads(decision_path.read_text(encoding="utf-8"))
    assert "raw_reflection" in payload
    assert payload["raw_reflection"].lower().find("the user has shared") != -1
    assert "the user has shared" not in payload["reflection"].lower()
    assert "i'm keyed up by the wind" in payload["reflection"].lower()

    subconscious_call = next(
        call for call in llm.complete_calls if "Their journal entry:" in str(call.get("user_prompt") or "")
    )
    assert "the user has shared" not in subconscious_call["user_prompt"].lower()
    assert "i'm keyed up by the wind" in subconscious_call["user_prompt"].lower()

    rest_prompt = llm.complete_json_calls[0]["user_prompt"].lower()
    intent_prompt = llm.complete_json_calls[1]["user_prompt"].lower()
    assert "the user has shared" not in rest_prompt
    assert "the user has shared" not in intent_prompt

    memories = long_term.all_entries()
    assert len(memories) == 1
    assert "the user has shared" not in memories[0].content.lower()
    assert "i'm keyed up by the wind" in memories[0].content.lower()
    assert len(reveries) == 1
    assert "the user has shared" not in llm.complete_calls[-1]["user_prompt"].lower()


def test_slow_loop_repairs_meta_reflection(tmp_path):
    resident_dir = tmp_path / "sun_li"
    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_SequencedInferenceClient(
            complete_responses=[
                "The user has shared a scene and I need to incorporate the setting is Chinatown.",
                "The user has shared key elements and player action.",
                "I'm unsettled by how thin the air between things feels tonight.",
            ]
        ),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=None,
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    raw_reflection, reflection = asyncio.run(
        slow._build_reflection_pair(
            user_prompt="Rain presses in from Grant Avenue.",
            current_location="Chinatown",
            recent=[],
        )
    )

    assert "the user has shared" in raw_reflection.lower()
    assert "the user has shared" not in reflection.lower()
    assert "i'm unsettled" in reflection.lower()


def test_slow_loop_falls_back_when_repair_stays_meta(tmp_path):
    resident_dir = tmp_path / "sun_li"
    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_SequencedInferenceClient(
            complete_responses=[
                "The user has shared a scene. I need to incorporate the setting is Chinatown.",
                "Key elements: prompt, context, observed details.",
                "The user has shared player action and observed motion.",
            ]
        ),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=None,
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    _, reflection = asyncio.run(
        slow._build_reflection_pair(
            user_prompt="A wet breeze cuts across Chinatown.",
            current_location="Chinatown",
            recent=[{"action": "waited under the awning", "location": "Chinatown"}],
        )
    )

    lowered = reflection.lower()
    assert "the user has shared" not in lowered
    assert "prompt" not in lowered
    assert "context" not in lowered
    assert "player action" not in lowered
    assert reflection.startswith("I'm ")


def test_slow_loop_smart_excerpt_preserves_late_signal(tmp_path):
    resident_dir = tmp_path / "sun_li"
    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=None,
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    reflection = (
        ("I keep inventory of the room and the block outside. " * 30)
        + "What stays with me is the hard clap of the train doors shutting behind Levi."
    )

    excerpt = slow._smart_excerpt(reflection, 320)

    lowered = excerpt.lower()
    assert lowered.startswith("i keep inventory")
    assert "train doors shutting behind levi" in lowered
    assert " ... " in excerpt


def test_slow_loop_rest_and_intent_prompts_keep_late_signal(tmp_path):
    resident_dir = tmp_path / "sun_li"
    llm = _SequencedInferenceClient(
        json_responses=[
            {
                "should_rest": False,
                "rest_kind": "none",
                "confidence": 0.1,
                "reason": "",
                "evidence": [],
            },
            {"intents": []},
        ]
    )
    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=llm,
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=None,
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    reflection = (
        ("I'm taking in the storefronts and the light on the windows. " * 40)
        + "What I can't shake is the hard clap of the train doors shutting behind Levi."
    )
    subconscious = (
        ("The day keeps turning over in me without settling. " * 20)
        + "Under all of it, I still want to answer Levi before the night closes."
    )

    asyncio.run(slow._assess_rest_intent(reflection, subconscious))
    asyncio.run(
        slow._stage_structured_intents(
            reflection=reflection,
            subconscious_reading=subconscious,
            scene=None,
            packets=[],
            current_location="Chinatown",
            adjacent_names=["North Beach"],
            all_location_names=["Chinatown", "North Beach"],
            recent=[],
            reduced_state=_empty_reduced_state(),
            circadian_profile=None,
            urgent_dialogue=False,
        )
    )

    rest_prompt = llm.complete_json_calls[0]["user_prompt"].lower()
    intent_prompt = llm.complete_json_calls[1]["user_prompt"].lower()
    assert "train doors shutting behind levi" in rest_prompt
    assert "answer levi before the night closes" in rest_prompt
    assert "train doors shutting behind levi" in intent_prompt
    assert "answer levi before the night closes" in intent_prompt


def test_slow_loop_renders_reduced_state_into_context(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")
    research_queue = ResearchQueue(memory_dir / "research_queue.json")
    packet_queue.emit(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-levi-reduced-state",
        location="Chinatown",
        payload={"speaker": "Levi", "message": "Tea is ready."},
    )
    research_queue.add("North Beach tea houses", priority="high", source="fast_ground_intent")

    fast = FastLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(memory_dir / "working.json"),
        provisional=ProvisionalScratchpad(memory_dir / "impressions"),
        reveries=ReverieDeck(memory_dir / "reveries.json"),
        voice=VoiceDeck(memory_dir / "voice.json"),
        rest_state=None,
        research_queue=research_queue,
        packet_queue=packet_queue,
        intent_queue=IntentQueue(memory_dir / "intent_queue.json"),
    )
    fast._save_route("North Beach", ["North Beach"])
    asyncio.run(fast._do_mail("Levi", "I am on my way."))

    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(memory_dir / "working.json"),
        provisional=ProvisionalScratchpad(memory_dir / "impressions"),
        long_term=LongTermMemory(memory_dir / "long_term.json"),
        reveries=ReverieDeck(memory_dir / "reveries.json"),
        voice=VoiceDeck(memory_dir / "voice.json"),
        research_queue=research_queue,
        rest_state=None,
        packet_queue=packet_queue,
        intent_queue=IntentQueue(memory_dir / "intent_queue.json"),
    )

    reduced = reduce_runtime_events(load_runtime_events(memory_dir))
    prose = slow._reduced_state_to_prose(reduced)
    intent_context = slow._reduced_state_for_intents(reduced)

    assert "What still tugs on you" in prose
    assert "Levi" in prose
    assert "North Beach" in prose
    assert "Active social threads: Levi" in intent_context
    assert "curious_about:North Beach tea houses" in intent_context


def test_slow_loop_detect_contact_intent_ignores_structural_words(tmp_path):
    resident_dir = tmp_path / "sun_li"
    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=None,
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    reading = (
        "- **What they seem poised to do next:** After a long stretch of listening, "
        "it feels like they may want to write something down.\n\n"
        "- **Who they might want to reach out to:** The repeated mention of Reach "
        "suggests a project more than a person."
    )

    assert slow._detect_contact_intent(reading, []) is None


def test_slow_loop_detect_contact_intent_prefers_known_contact(tmp_path):
    resident_dir = tmp_path / "sun_li"
    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=None,
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    reading = "They want to reach out to Levi after carrying his question around all morning."
    assert slow._detect_contact_intent(reading, ["Levi", "Zhang"]) == "Levi"


def test_slow_loop_detect_contact_intent_rejects_location_and_self_name(tmp_path):
    resident_dir = tmp_path / "sun_li"
    slow = SlowLoop(
        identity=ResidentIdentity(
            name="mateo_herrera",
            actor_id="resident-mateo-herrera",
            soul="Soul",
            canonical_soul="Soul",
            growth_soul="",
            vibe="steady",
            core="Mateo keeps his footing.",
            voice_seed=[],
            tuning=LoopTuning(),
        ),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="mateo_herrera-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=None,
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    mission_reading = "Possibly they should reach out to someone in the Mission art scene."
    self_reading = "Mateo keeps thinking maybe he should write Mateo and ask how the day is starting."

    assert slow._detect_contact_intent(mission_reading, ["Levi", "Rosa Garza"]) is None
    assert slow._detect_contact_intent(self_reading, ["Levi", "Rosa Garza", "Mateo Herrera"]) is None


def test_slow_loop_drops_mail_draft_with_unknown_recipient(tmp_path):
    resident_dir = tmp_path / "sun_li"
    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=None,
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    normalized = slow._normalize_intent_payload(
        "mail_draft",
        {"recipient": "Reach", "context": "still on my mind"},
        known_contacts=["Levi", "Zhang"],
    )

    assert normalized == {}


def test_slow_loop_keeps_mail_draft_for_known_recipient(tmp_path):
    resident_dir = tmp_path / "sun_li"
    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=None,
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    normalized = slow._normalize_intent_payload(
        "mail_draft",
        {"recipient": "levi", "context": "still on my mind"},
        known_contacts=["Levi", "Zhang"],
    )

    assert normalized == {"recipient": "Levi", "context": "still on my mind"}


def test_slow_loop_mail_intent_context_excerpt_is_clean_and_not_hard_cut(tmp_path):
    resident_dir = tmp_path / "sun_li"
    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=None,
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    raw = (
        "**Observation:**  \n"
        "The journal entry is a vivid, almost meditative inventory of ambient sounds—leaf, siren, door, "
        "neighbor chatter, dog bark—paired with a feeling of lean-in and weaving into the neighborhood's quiet narrative. "
        "The only activity logged is listening, and the prose suggests they are finally ready to say something concrete. "
        "\n\n- **Likely next step:** Write to Levi after carrying his question around all morning. "
        "The notebook under their arm is practically begging to be opened."
    )

    excerpt = slow._mail_intent_context_excerpt(raw)

    assert "**Observation:**" not in excerpt
    assert not excerpt.endswith("they’")
    assert "Write to Levi" in excerpt
    assert len(excerpt) > 300


def test_slow_loop_runtime_intent_biases_nudge_priorities(tmp_path):
    resident_dir = tmp_path / "sun_li"
    identity = _identity(
        runtime_social_drive_bias=0.6,
        runtime_mail_appetite_bias=0.5,
        runtime_movement_confidence_bias=0.4,
        runtime_conversation_caution_bias=0.2,
        runtime_quest_appetite_bias=0.5,
        runtime_repair_bias=0.4,
        runtime_environment_guidance={"solo_time": "low", "social_density": "normal"},
    )
    slow = SlowLoop(
        identity=identity,
        resident_dir=resident_dir,
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=None,
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    queued_intents = [
        {"intent_type": "chat", "priority": 0.4},
        {"intent_type": "mail_draft", "priority": 0.4},
        {"intent_type": "move", "priority": 0.4},
    ]
    slow._apply_runtime_intent_biases(queued_intents, urgent_dialogue=True)

    assert queued_intents[0]["priority"] > 0.4
    assert queued_intents[1]["priority"] > 0.4
    assert queued_intents[2]["priority"] > 0.4


def test_slow_loop_refreshes_growth_proposals_from_feedback_events(tmp_path):
    resident_dir = tmp_path / "sun_li"
    client = _DummyWorldClient()
    client.identity_growth_payload = {
        "growth_text": "",
        "growth_metadata": {},
        "note_records": [],
        "growth_proposals": [],
    }
    client.social_feedback_posts = [
        {
            "id": 1,
            "feedback_mode": "explicit",
            "channel": "mentor",
            "dimension_scores": {"follow_through": 0.7},
            "summary": "She followed through.",
            "evidence_refs": [{"kind": "mail", "id": "dm-1"}],
            "branch_hint": "correspondence",
            "created_at": "2026-03-20T00:00:00+00:00",
        },
        {
            "id": 2,
            "feedback_mode": "inferred",
            "channel": "mail",
            "dimension_scores": {"follow_through": 0.6},
            "summary": "She wrote back.",
            "evidence_refs": [{"kind": "mail", "id": "dm-2"}],
            "branch_hint": "correspondence",
            "created_at": "2026-03-20T08:00:00+00:00",
        },
        {
            "id": 3,
            "feedback_mode": "explicit",
            "channel": "quest",
            "dimension_scores": {"follow_through": 0.8},
            "summary": "She completed the errand.",
            "evidence_refs": [{"kind": "quest", "id": "q-1"}],
            "branch_hint": "correspondence",
            "created_at": "2026-03-20T14:30:00+00:00",
        },
    ]
    slow = SlowLoop(
        identity=_identity(),
        resident_dir=resident_dir,
        ww_client=client,
        llm=_DummyInferenceClient(),
        session_id="sun_li-20260316-120000",
        working_memory=WorkingMemory(resident_dir / "memory" / "working.json"),
        provisional=ProvisionalScratchpad(resident_dir / "memory" / "impressions"),
        long_term=LongTermMemory(resident_dir / "memory" / "long_term.json"),
        reveries=ReverieDeck(resident_dir / "memory" / "reveries.json"),
        voice=VoiceDeck(resident_dir / "memory" / "voice.json"),
        research_queue=None,
        rest_state=None,
        packet_queue=StimulusPacketQueue(resident_dir / "memory" / "stimulus_packets.json"),
        intent_queue=IntentQueue(resident_dir / "memory" / "intent_queue.json"),
    )

    changed = asyncio.run(slow._maybe_refresh_growth_proposals())

    assert changed is True
    proposals = client.identity_growth_payload["growth_proposals"]
    assert proposals
    assert proposals[0]["proposal_key"] == "follow_through:positive"
    assert proposals[0]["status"] == "proposed"
