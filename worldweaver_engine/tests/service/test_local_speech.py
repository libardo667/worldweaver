# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

import pytest

from src.models import LocationChat, SessionVars, WorldEvent, WorldFact, WorldProjection
from src.services import local_speech as local_speech_module
from src.services.local_speech import LocalSpeechError, post_local_speech


def _add_speaker(db_session, *, session_id: str = "speaker-session") -> None:
    db_session.add(
        SessionVars(
            session_id=session_id,
            actor_id="actor-speaker",
            vars={"location": "Cafe", "player_role": "Levi — visitor"},
        )
    )
    db_session.commit()


def test_post_local_speech_records_chat_event_projection_and_fact(db_session):
    _add_speaker(db_session)

    receipt = post_local_speech(
        db_session,
        session_id="speaker-session",
        location="Cafe",
        message="  Hello from the counter.  ",
    )

    assert receipt.success is True
    chat = db_session.query(LocationChat).one()
    assert receipt.id == chat.id
    assert chat.actor_id == "actor-speaker"
    assert chat.display_name == "Levi"
    assert chat.message == "Hello from the counter."

    event = db_session.query(WorldEvent).one()
    assert event.event_type == "utterance"
    assert event.summary == "Levi said: Hello from the counter."

    projection = (
        db_session.query(WorldProjection)
        .filter(WorldProjection.path == "locations.cafe.last_public_utterance")
        .one()
    )
    assert projection.value == "Hello from the counter."

    fact = db_session.query(WorldFact).filter(WorldFact.predicate == "spoke_at").one()
    assert fact.value == "Cafe"


def test_post_local_speech_rolls_back_every_record_when_event_write_fails(
    db_session, monkeypatch
):
    _add_speaker(db_session)
    notified = False

    def fail_event_write(*_args, **_kwargs):
        raise RuntimeError("event write failed")

    def record_notification():
        nonlocal notified
        notified = True

    monkeypatch.setattr(local_speech_module, "submit_world_event", fail_event_write)
    monkeypatch.setattr(local_speech_module, "notify_live_signal", record_notification)

    with pytest.raises(LocalSpeechError) as captured:
        post_local_speech(
            db_session,
            session_id="speaker-session",
            location="Cafe",
            message="This must not become half-visible.",
        )

    assert captured.value.code == "speech_persistence_failed"
    assert captured.value.status_code == 503
    assert db_session.query(LocationChat).count() == 0
    assert db_session.query(WorldEvent).count() == 0
    assert notified is False


def test_post_local_speech_notifies_only_after_the_records_are_committed(
    db_session, monkeypatch
):
    _add_speaker(db_session)
    observed_counts: list[tuple[int, int]] = []

    def inspect_committed_records():
        observed_counts.append(
            (
                db_session.query(LocationChat).count(),
                db_session.query(WorldEvent).count(),
            )
        )

    monkeypatch.setattr(
        local_speech_module, "notify_live_signal", inspect_committed_records
    )

    post_local_speech(
        db_session,
        session_id="speaker-session",
        location="Cafe",
        message="The durable record comes first.",
    )

    assert observed_counts == [(1, 1)]
