from __future__ import annotations

import asyncio
import json

from src.identity.loader import LoopTuning, ResidentIdentity
from src.loops.fast import FastLoop
from src.loops.mail import MailLoop
from src.loops.slow import SlowLoop
from src.memory.provisional import ProvisionalScratchpad
from src.memory.research_queue import ResearchQueue
from src.memory.retrieval import LongTermMemory
from src.memory.reveries import ReverieDeck
from src.memory.voice import VoiceDeck
from src.memory.working import WorkingMemory
from src.runtime.signals import IntentQueue, StimulusPacketQueue
from src.world.client import ChatMessage, DM


class _DummyWorldClient:
    def __init__(self):
        self.replies: list[tuple[str, str, str]] = []
        self.votes: list[tuple[str, str, str]] = []

    async def reply_letter(self, from_agent: str, to_session_id: str, body: str):
        self.replies.append((from_agent, to_session_id, body))
        return {"ok": True}

    async def cast_doula_vote(self, poll_id: str, voter_session_id: str, vote: str):
        self.votes.append((poll_id, voter_session_id, vote))
        return {"ok": True}

    async def send_letter(self, from_name: str, to_agent: str, body: str, session_id: str):
        return {"ok": True}


class _DummyInferenceClient:
    async def complete_json(self, *args, **kwargs):
        return {"intents": []}

    async def complete(self, *args, **kwargs):
        return "observe"


def _identity() -> ResidentIdentity:
    return ResidentIdentity(
        name="sun_li",
        soul="Soul",
        vibe="steady",
        core="Sun Li keeps her footing.",
        voice_seed=[],
        tuning=LoopTuning(),
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
                "scene": type("Scene", (), {"location": "Chinatown"})(),
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


def test_signal_queues_write_runtime_snapshot(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")
    intent_queue = IntentQueue(memory_dir / "intent_queue.json")

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

    snapshot = json.loads((memory_dir / "runtime_snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["packet_counts"]["total"] == 1
    assert snapshot["packet_counts"]["observed"] == 1
    assert snapshot["intent_counts"]["failed"] == 1
    assert snapshot["recent_failures"][0]["validation_state"] == "invalid_payload"
    assert snapshot["lineage"][0]["source_packet_ids"] == [packet.packet_id]


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
        )
    )

    move = next(item for item in staged if item["intent_type"] == "move")
    assert move["payload"]["destination"] in {"Chinatown", "Outer Richmond"}


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
        )
    )

    move_items = [item for item in staged if item["intent_type"] == "move"]
    assert len(move_items) == 1
    assert move_items[0]["payload"]["destination"] in {"Chinatown", "Outer Richmond"}
    queued = intent_queue.pending(target_loop="fast")
    assert len(queued) == 1
    assert queued[0].payload["destination"] in {"Chinatown", "Outer Richmond"}


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
            }
        )
    )

    assert slow._intents is not None
