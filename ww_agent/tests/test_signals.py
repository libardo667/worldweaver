from __future__ import annotations

from src.runtime.signals import IntentQueue, StimulusPacketQueue


def test_stimulus_packet_queue_emits_and_updates_status(tmp_path):
    queue = StimulusPacketQueue(tmp_path / "packets.json", max_items=3)

    first = queue.emit(
        packet_type="chat_heard",
        source_loop="fast",
        location="Chinatown",
        payload={"speaker": "Sun Li"},
    )
    second = queue.emit(
        packet_type="grounding_update",
        source_loop="ground",
        payload={"weather": "foggy"},
    )

    pending = queue.pending()

    assert [item.packet_id for item in pending] == [first.packet_id, second.packet_id]

    updated = queue.mark_status(first.packet_id, "observed")

    assert updated is not None
    assert updated.status == "observed"
    assert [item.packet_id for item in queue.pending()] == [second.packet_id]


def test_stimulus_packet_queue_emit_once_dedupes_on_key(tmp_path):
    queue = StimulusPacketQueue(tmp_path / "packets.json", max_items=5)

    first = queue.emit_once(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-1",
        location="Chinatown",
        payload={"speaker": "Sun Li"},
    )
    second = queue.emit_once(
        packet_type="chat_heard",
        source_loop="fast",
        dedupe_key="chat-1",
        location="Chinatown",
        payload={"speaker": "Sun Li"},
    )

    assert first.packet_id == second.packet_id
    assert len(queue.all()) == 1


def test_intent_queue_claims_highest_priority_for_target_loop(tmp_path):
    queue = IntentQueue(tmp_path / "intents.json")
    low = queue.stage(
        intent_type="chat",
        target_loop="fast",
        priority=0.2,
        payload={"utterance": "Later."},
    )
    high = queue.stage(
        intent_type="move",
        target_loop="fast",
        priority=0.9,
        payload={"destination": "Tea House"},
    )
    queue.stage(
        intent_type="mail_draft",
        target_loop="mail",
        priority=1.0,
        payload={"recipient": "Sun Li"},
    )

    claimed = queue.claim_next(target_loop="fast")

    assert claimed is not None
    assert claimed.intent_id == high.intent_id
    assert claimed.status == "claimed"
    pending_fast = queue.pending(target_loop="fast")
    assert [item.intent_id for item in pending_fast] == [low.intent_id]


def test_queues_create_backing_files(tmp_path):
    packets = StimulusPacketQueue(tmp_path / "memory" / "packets.json")
    intents = IntentQueue(tmp_path / "memory" / "intents.json")

    packets.ensure_file()
    intents.ensure_file()

    assert (tmp_path / "memory" / "packets.json").read_text(encoding="utf-8").strip() == "[]"
    assert (tmp_path / "memory" / "intents.json").read_text(encoding="utf-8").strip() == "[]"
