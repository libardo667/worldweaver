# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from datetime import datetime, timedelta, timezone

import pytest

from src.models import (
    DirectMessage,
    SessionVars,
    WorldEvent,
    WorldFact,
    WorldProjection,
)
from src.services.correspondence import (
    CorrespondenceError,
    SendCorrespondenceCommand,
    acknowledge_correspondence,
    correspondence_threads,
    pending_correspondence,
    send_correspondence,
)
from src.services.session_lifecycle import retire_session_presence


def _add_actor(db_session, *, session_id: str, actor_id: str, name: str) -> None:
    db_session.add(
        SessionVars(
            session_id=session_id,
            actor_id=actor_id,
            vars={"name": name, "location": "Willow Court"},
        )
    )
    db_session.commit()


def test_correspondence_waits_for_acknowledgement_and_follows_the_actor(db_session):
    sent_at = datetime(2032, 4, 5, 6, 7, tzinfo=timezone.utc)
    _add_actor(
        db_session,
        session_id="sender-session",
        actor_id="actor-sender",
        name="Mara",
    )
    _add_actor(
        db_session,
        session_id="recipient-session-one",
        actor_id="actor-recipient",
        name="Ivo",
    )

    receipt = send_correspondence(
        db_session,
        command=SendCorrespondenceCommand(
            sender_session_id="sender-session",
            recipient_actor_id="actor-recipient",
            body="I left the gate key with Rowan.",
        ),
        now=sent_at,
    )

    first_offer = pending_correspondence(db_session, session_id="recipient-session-one")
    second_offer = pending_correspondence(
        db_session, session_id="recipient-session-one"
    )
    assert first_offer == second_offer
    assert [item.message_id for item in first_offer.messages] == [receipt.message_id]
    assert first_offer.messages[0].sender_actor_id == "actor-sender"
    assert first_offer.messages[0].sender_name == "Mara"
    assert first_offer.messages[0].body == "I left the gate key with Rowan."
    assert db_session.get(DirectMessage, receipt.message_id).acknowledged_at is None

    retire_session_presence(db_session, session_id="recipient-session-one")
    _add_actor(
        db_session,
        session_id="recipient-session-two",
        actor_id="actor-recipient",
        name="Ivo",
    )
    after_reattachment = pending_correspondence(
        db_session, session_id="recipient-session-two"
    )
    assert [item.message_id for item in after_reattachment.messages] == [
        receipt.message_id
    ]

    acknowledgement = acknowledge_correspondence(
        db_session,
        session_id="recipient-session-two",
        message_ids=[receipt.message_id],
        now=sent_at + timedelta(days=2),
    )
    assert acknowledgement.acknowledged_ids == (receipt.message_id,)
    assert (
        pending_correspondence(db_session, session_id="recipient-session-two").messages
        == ()
    )
    row = db_session.get(DirectMessage, receipt.message_id)
    assert row.sent_at == sent_at.replace(tzinfo=None)
    assert row.acknowledged_at == (sent_at + timedelta(days=2)).replace(tzinfo=None)
    assert row.read_at == row.acknowledged_at


def test_correspondence_refuses_cross_actor_acknowledgement(db_session):
    _add_actor(
        db_session,
        session_id="sender-session",
        actor_id="actor-sender",
        name="Mara",
    )
    _add_actor(
        db_session,
        session_id="recipient-session",
        actor_id="actor-recipient",
        name="Ivo",
    )
    _add_actor(
        db_session,
        session_id="other-session",
        actor_id="actor-other",
        name="Sana",
    )
    receipt = send_correspondence(
        db_session,
        command=SendCorrespondenceCommand(
            sender_session_id="sender-session",
            recipient_actor_id="actor-recipient",
            body="Private for Ivo.",
        ),
    )

    with pytest.raises(CorrespondenceError) as captured:
        acknowledge_correspondence(
            db_session,
            session_id="other-session",
            message_ids=[receipt.message_id],
        )

    assert captured.value.code == "message_not_owned"
    assert db_session.get(DirectMessage, receipt.message_id).acknowledged_at is None


def test_correspondence_is_private_and_threads_use_actor_ids(db_session):
    _add_actor(
        db_session,
        session_id="sender-session",
        actor_id="actor-sender",
        name="Mara",
    )
    _add_actor(
        db_session,
        session_id="recipient-session",
        actor_id="actor-recipient",
        name="Ivo",
    )
    send_correspondence(
        db_session,
        command=SendCorrespondenceCommand(
            sender_session_id="sender-session",
            recipient_actor_id="actor-recipient",
            body="First note.",
        ),
    )
    send_correspondence(
        db_session,
        command=SendCorrespondenceCommand(
            sender_session_id="recipient-session",
            recipient_actor_id="actor-sender",
            body="Reply note.",
        ),
    )

    threads = correspondence_threads(db_session, session_id="sender-session")
    assert len(threads) == 1
    assert threads[0]["counterpart_actor_id"] == "actor-recipient"
    assert [message["direction"] for message in threads[0]["messages"]] == [
        "outbound",
        "inbound",
    ]
    assert db_session.query(WorldEvent).count() == 0
    assert db_session.query(WorldFact).count() == 0
    assert db_session.query(WorldProjection).count() == 0
