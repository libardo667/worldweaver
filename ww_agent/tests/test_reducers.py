from __future__ import annotations

import json
from typing import Any

from src.identity.loader import LoopTuning, ResidentIdentity
from src.runtime.ledger import (
    append_runtime_event,
    load_runtime_events,
    reduce_runtime_events,
)
from src.runtime.signals import IntentQueue, StimulusPacketQueue, write_runtime_snapshot


class _DummyWorldClient:
    def __init__(self):
        self.replies: list[tuple[str, str, str]] = []
        self.votes: list[tuple[str, str, str]] = []
        self.location_chats: list[tuple[str, str, str, str | None]] = []
        self.actions: list[tuple[str, str]] = []
        self.letters_sent: list[dict[str, Any]] = []
        self.roster_display_names: list[str] = ["Levi", "Sun Li"]
        self.roster_recipients: list[dict[str, str]] = []

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

    async def post_location_chat(
        self,
        location: str,
        session_id: str,
        message: str,
        display_name: str | None = None,
    ):
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


def _queue_research(memory_dir, query, priority="normal", source=""):
    """Append a research_queued ledger event directly (the ledger is the only state;
    the loop-era ResearchQueue writer wrapper was removed in Major 83)."""
    append_runtime_event(
        memory_dir,
        event_type="research_queued",
        payload={"query": query, "priority": priority, "source": source},
    )
    write_runtime_snapshot(memory_dir)


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
    intent_queue.mark_status(
        intent.intent_id, status="failed", validation_state="invalid_payload"
    )
    _queue_research(
        memory_dir,
        "Clement Street farmers market hours",
        priority="high",
        source="fast_ground_intent",
    )

    snapshot = json.loads(
        (memory_dir / "runtime_snapshot.json").read_text(encoding="utf-8")
    )
    projection = json.loads(
        (memory_dir / "runtime_projection.json").read_text(encoding="utf-8")
    )
    ledger_lines = (
        (memory_dir / "runtime_ledger.jsonl")
        .read_text(encoding="utf-8")
        .strip()
        .splitlines()
    )
    assert snapshot["packet_counts"]["total"] == 1
    assert snapshot["packet_counts"]["observed"] == 1
    assert snapshot["intent_counts"]["failed"] == 1
    assert snapshot["research_queue"]["total"] == 1
    assert snapshot["research_queue"]["high"] == 1
    assert (
        snapshot["research_queue"]["pending_items"][0]["query"]
        == "Clement Street farmers market hours"
    )
    assert projection["ledger_event_count"] >= 4
    assert projection["event_counts"]["packet_emitted"] == 1
    assert projection["event_counts"]["intent_staged"] == 1
    assert projection["event_counts"]["intent_status_changed"] == 1
    assert projection["event_counts"]["research_queued"] == 1
    assert len(ledger_lines) >= 4
    assert snapshot["recent_failures"][0]["validation_state"] == "invalid_payload"
    assert snapshot["lineage"][0]["source_packet_ids"] == [packet.packet_id]


def test_signal_queues_rehydrate_from_ledger_when_projection_files_are_missing(
    tmp_path,
):
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
    intent_queue.mark_status(
        intent.intent_id, status="executed", validation_state="validated"
    )

    # Phase 0 made the queues pure ledger views — the json shadows may not exist.
    (memory_dir / "stimulus_packets.json").unlink(missing_ok=True)
    (memory_dir / "intent_queue.json").unlink(missing_ok=True)

    rehydrated_packets = packet_queue.all()
    rehydrated_intents = intent_queue.all()
    assert len(rehydrated_packets) == 1
    assert rehydrated_packets[0].status == "observed"
    assert len(rehydrated_intents) == 1
    assert rehydrated_intents[0].status == "executed"


def test_runtime_snapshot_rehydrates_research_queue_from_ledger(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    _queue_research(
        memory_dir,
        "ASL organizations in Chinatown",
        priority="high",
        source="fast_ground_intent",
    )

    write_runtime_snapshot(memory_dir)
    snapshot = json.loads(
        (memory_dir / "runtime_snapshot.json").read_text(encoding="utf-8")
    )
    assert snapshot["research_queue"]["total"] == 1
    assert (
        snapshot["research_queue"]["pending_items"][0]["query"]
        == "ASL organizations in Chinatown"
    )
    assert snapshot["research_queue"]["pending_items"][0]["priority"] == "high"


def test_runtime_reducer_matches_ledger_history(tmp_path):
    resident_dir = tmp_path / "sun_li"
    memory_dir = resident_dir / "memory"
    packet_queue = StimulusPacketQueue(memory_dir / "stimulus_packets.json")

    packet_queue.emit(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-levi-direct-reduce",
        location="Chinatown",
        payload={"speaker": "Levi", "message": "Tea's ready."},
    )
    _queue_research(
        memory_dir, "Chinatown tea houses", priority="normal", source="slow_reflection"
    )

    events = load_runtime_events(memory_dir)
    reduced = reduce_runtime_events(events)

    assert len(events) == reduced.runtime_projection["ledger_event_count"]
    assert reduced.packets[0]["packet_type"] == "chat_heard"
    assert reduced.research_queue[0]["query"] == "Chinatown tea houses"
    predicates = {
        (fact["predicate"], fact["object"])
        for fact in reduced.subjective_facts["facts"]
    }
    assert ("engaged_with", "Levi") in predicates
    assert ("curious_about", "Chinatown tea houses") in predicates


def test_relationship_projection_requires_prompt_delivery_and_exact_reply_edge():
    packet_only = reduce_runtime_events(
        [
            {
                "event_id": "evt-polled",
                "ts": "2026-07-17T12:00:00+00:00",
                "event_type": "packet_emitted",
                "payload": {
                    "packet_id": "packet-polled",
                    "packet_type": "chat_heard",
                    "status": "pending",
                    "speaker": "Bea",
                },
            }
        ]
    )
    assert (
        packet_only.subjective_projection["relationship_projection"]["relationships"]
        == []
    )
    assert not [
        fact
        for fact in packet_only.subjective_facts["facts"]
        if fact.get("source") == "relationship_projection_v1"
    ]

    reduced = reduce_runtime_events(
        [
            {
                "event_id": "evt-perceived",
                "ts": "2026-07-17T12:01:00+00:00",
                "event_type": "utterance_perceived",
                "payload": {
                    "edge_schema_version": 1,
                    "actor_id": "actor-sun",
                    "actor_session_id": "sun-1",
                    "location": "Market",
                    "utterance_id": "chat:Market:101",
                    "speaker_actor_id": "actor-bea",
                    "speaker_session_id": "bea-1",
                    "speaker_name": "Bea",
                    "channel": "local",
                },
            },
            {
                "event_id": "evt-replied",
                "ts": "2026-07-17T12:02:00+00:00",
                "event_type": "chat_sent",
                "payload": {
                    "edge_schema_version": 1,
                    "actor_id": "actor-sun",
                    "reply_to_utterance_id": "chat:Market:101",
                },
            },
        ]
    )

    relationship = reduced.subjective_projection["relationship_projection"][
        "relationships"
    ][0]
    assert relationship["counterpart_actor_id"] == "actor-bea"
    assert relationship["counterpart_name"] == "Bea"
    assert relationship["state"] == "replied"
    assert relationship["revision"] == 2
    assert relationship["evidence_event_ids"] == ["evt-perceived", "evt-replied"]

    claim = next(
        fact
        for fact in reduced.subjective_facts["facts"]
        if fact.get("claim_id") == relationship["claim_id"]
    )
    assert claim == {
        "claim_id": "claim:relationship:actor-bea:current_exchange",
        "status": "active",
        "revision": 2,
        "supersedes_revision": 1,
        "subject": "self",
        "predicate": "has_replied_to",
        "object": "Bea",
        "object_actor_id": "actor-bea",
        "confidence": 0.9,
        "observed_at": "2026-07-17T12:02:00+00:00",
        "evidence_event_ids": ["evt-perceived", "evt-replied"],
        "source": "relationship_projection_v1",
    }


def test_later_perception_supersedes_current_relationship_claim():
    reduced = reduce_runtime_events(
        [
            {
                "event_id": "evt-perceived-first",
                "ts": "2026-07-17T12:01:00+00:00",
                "event_type": "utterance_perceived",
                "payload": {
                    "edge_schema_version": 1,
                    "utterance_id": "chat:Market:101",
                    "speaker_actor_id": "actor-bea",
                    "speaker_name": "Bea",
                },
            },
            {
                "event_id": "evt-replied-first",
                "ts": "2026-07-17T12:02:00+00:00",
                "event_type": "chat_sent",
                "payload": {
                    "edge_schema_version": 1,
                    "reply_to_utterance_id": "chat:Market:101",
                },
            },
            {
                "event_id": "evt-perceived-second",
                "ts": "2026-07-17T12:03:00+00:00",
                "event_type": "utterance_perceived",
                "payload": {
                    "edge_schema_version": 1,
                    "utterance_id": "chat:Market:102",
                    "speaker_actor_id": "actor-bea",
                    "speaker_name": "Bea",
                },
            },
        ]
    )

    relationship = reduced.subjective_projection["relationship_projection"][
        "relationships"
    ][0]
    assert relationship["state"] == "perceived"
    assert relationship["revision"] == 3
    assert relationship["supersedes_revision"] == 2
    assert relationship["evidence_event_ids"] == ["evt-perceived-second"]
    claim = next(
        fact
        for fact in reduced.subjective_facts["facts"]
        if fact.get("claim_id") == relationship["claim_id"]
    )
    assert claim["predicate"] == "has_perceived_utterance_from"
    assert claim["revision"] == 3
    assert claim["supersedes_revision"] == 2


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
    predicates = {
        (fact["predicate"], fact["object"])
        for fact in reduced.subjective_facts["facts"]
    }
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
    predicates = {
        (fact["predicate"], fact["object"])
        for fact in reduced.subjective_facts["facts"]
    }
    assert ("owes_reply_to", "Fei Fei") not in predicates


def test_subjective_projection_tracks_mail_pressure_and_city_context_separately(
    tmp_path,
):
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


def test_subjective_projection_promotes_tagged_city_signal_without_fake_partner(
    tmp_path,
):
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
    assert (
        reduced.subjective_projection["active_social_threads"][0]["name"] == "Fei Fei"
    )
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
                        {
                            "kind": "tension",
                            "label": "heightened tension",
                            "level": 0.7,
                        },
                    ],
                    "raw": {"energy": 0.2, "danger_level": 2.0},
                    "context": {"time_of_day": "night", "weather": "rainy"},
                },
            }
        ]
    )
    pressure = reduced.subjective_projection["state_pressure"]
    assert pressure["signals"][0]["kind"] == "fatigue"
    predicates = {
        (fact["predicate"], fact["object"])
        for fact in reduced.subjective_facts["facts"]
    }
    assert ("pressed_by", "low energy") in predicates


def test_subjective_projection_merges_ambient_pressure_from_grounding(tmp_path):
    reduced = reduce_runtime_events(
        [
            {
                "event_id": "evt-state-1",
                "ts": "2026-03-18T03:10:00+00:00",
                "event_type": "session_state_observed",
                "payload": {
                    "signals": [
                        {"kind": "fatigue", "label": "low energy", "level": 0.8}
                    ],
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
                        {
                            "kind": "bad_weather",
                            "label": "rain pressing against the day",
                            "level": 0.72,
                        },
                        {
                            "kind": "quiet",
                            "label": "the neighborhood feels unusually quiet",
                            "level": 0.7,
                        },
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
    predicates = {
        (fact["predicate"], fact["object"])
        for fact in reduced.subjective_facts["facts"]
    }
    assert ("pressed_by", "rain pressing against the day") in predicates


def test_subjective_projection_replaces_stale_ambient_pressure_when_scene_changes(
    tmp_path,
):
    reduced = reduce_runtime_events(
        [
            {
                "event_id": "evt-ambient-old",
                "ts": "2026-03-18T03:10:00+00:00",
                "event_type": "ambient_pressure_observed",
                "payload": {
                    "source": "ambient",
                    "signals": [
                        {
                            "kind": "quiet",
                            "label": "the neighborhood feels unusually quiet",
                            "level": 0.72,
                            "source": "time_of_day_routine",
                        },
                        {
                            "kind": "place_character",
                            "label": "Jordan Park keeps a domestic rhythm",
                            "level": 0.6,
                            "source": "neighborhood",
                        },
                    ],
                    "raw": {"current_present": 1, "recent_event_count": 1},
                    "context": {
                        "location": "Jordan Park",
                        "neighborhood": "Jordan Park",
                    },
                },
            },
            {
                "event_id": "evt-ambient-new",
                "ts": "2026-03-18T03:14:00+00:00",
                "event_type": "ambient_pressure_observed",
                "payload": {
                    "source": "ambient",
                    "signals": [
                        {
                            "kind": "crowding",
                            "label": "the neighborhood feels unusually busy",
                            "level": 0.92,
                            "source": "co_presence",
                        },
                        {
                            "kind": "event_pull",
                            "label": "there is a live current running through nearby streets",
                            "level": 0.9,
                            "source": "local_world_events",
                        },
                        {
                            "kind": "place_character",
                            "label": "Fillmore's storefronts set the pace",
                            "level": 0.6,
                            "source": "neighborhood",
                        },
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
    labels = {item["label"] for item in pressure["signals"]}
    assert "Jordan Park keeps a domestic rhythm" not in labels
    assert "Fillmore's storefronts set the pace" in labels
    assert pressure["context"]["location"] == "Fillmore"
    assert pressure["raw"]["current_present"] == 7
    salience = reduced.subjective_projection["world_salience"]
    assert salience["location"] == "Fillmore"
    assert salience["feature_count"] == 3
    assert salience["independent_source_count"] == 3
    assert salience["plural"] is True
    assert 0.0 < salience["dominant_share"] < 1.0
    assert salience["effective_feature_count"] > 2.0


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
