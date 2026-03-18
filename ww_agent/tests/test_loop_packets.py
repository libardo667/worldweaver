from __future__ import annotations

import asyncio
import json
from typing import Any

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
from src.runtime.ledger import load_runtime_events, rebuild_runtime_artifacts, reduce_runtime_events
from src.runtime.mirror import ResidentRuntimeMirror
from src.runtime.rest import RestAssessment
from src.runtime.signals import IntentQueue, StimulusPacketQueue
from src.world.client import ChatMessage, DM


class _DummyWorldClient:
    def __init__(self):
        self.replies: list[tuple[str, str, str]] = []
        self.votes: list[tuple[str, str, str]] = []
        self.session_var_updates: list[tuple[str, dict]] = []
        self.location_chats: list[tuple[str, str, str, str | None]] = []
        self.session_vars_payload: dict[str, Any] = {"vars": {}}

    async def reply_letter(self, from_agent: str, to_session_id: str, body: str):
        self.replies.append((from_agent, to_session_id, body))
        return {"ok": True}

    async def cast_doula_vote(self, poll_id: str, voter_session_id: str, vote: str):
        self.votes.append((poll_id, voter_session_id, vote))
        return {"ok": True}

    async def send_letter(self, from_name: str, to_agent: str, body: str, session_id: str):
        return {"ok": True}

    async def update_session_vars(self, session_id: str, vars: dict[str, Any]):
        self.session_var_updates.append((session_id, dict(vars)))
        return {"session_id": session_id, "vars": vars}

    async def get_session_vars(self, session_id: str, prefix: str | None = None):
        return dict(self.session_vars_payload)

    async def post_location_chat(self, location: str, session_id: str, message: str, display_name: str | None = None):
        self.location_chats.append((location, session_id, message, display_name))
        return {"id": 1, "ts": "2026-03-18T00:00:00+00:00"}


class _DummyInferenceClient:
    async def complete_json(self, *args, **kwargs):
        return {"intents": []}

    async def complete(self, *args, **kwargs):
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
    action_entries = [entry for entry in recent if entry.get("type") == "action"]
    assert action_entries
    assert action_entries[-1]["action"] == "Mateo steps back, letting dusk settle around him."

    reduced = reduce_runtime_events(load_runtime_events(resident_dir / "memory"))
    facts = list(reduced.memory_projection.get("recent_experiences") or [])
    assert any(item.get("kind") == "utterance" for item in facts)


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
    assert "city_signal" in concern_kinds


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

    assert staged == []
    assert intent_queue.pending(target_loop="fast") == []


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
