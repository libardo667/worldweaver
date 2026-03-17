from __future__ import annotations

from src.identity.loader import LoopTuning, ResidentIdentity
from src.loops.fast import FastLoop
from src.loops.mail import MailLoop
from src.memory.provisional import ProvisionalScratchpad
from src.memory.reveries import ReverieDeck
from src.memory.voice import VoiceDeck
from src.memory.working import WorkingMemory
from src.runtime.signals import StimulusPacketQueue
from src.world.client import ChatMessage, DM


class _DummyWorldClient:
    pass


class _DummyInferenceClient:
    pass


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
