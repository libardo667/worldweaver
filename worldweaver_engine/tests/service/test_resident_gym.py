# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from src.models import LocationChat, WorldEvent
from src.services.gym_presentation import render_html, render_terminal
from src.services.resident_gym import run_first_conversation


def test_first_gym_conversation_uses_exact_place_production_signals(db_session):
    result = run_first_conversation(db_session)

    assert result.schema == "worldweaver.resident-gym.episode"
    assert result.locations == ("Willow Court", "Footbridge")
    assert result.final_locations == {"Mara": "Footbridge", "Ivo": "Footbridge"}
    assert {item.implementation for item in result.participants} == {
        "scripted_actor",
        "mechanical_listener",
    }

    heard = [record for record in result.records if record.kind == "heard"]
    assert [record.actor for record in heard] == ["Ivo", "Mara", "Ivo"]
    assert [record.detail["message"] for record in heard] == [
        "Good morning. Is the footbridge open?",
        "I heard you. I can go and look.",
        "There you are.",
    ]
    assert all(
        record.detail.get("message") != "Can you hear me from over there?"
        for record in heard
    )
    assert any(
        record.kind == "heard_nothing_new"
        and record.actor == "Ivo"
        and record.location == "Footbridge"
        for record in result.records
    )

    assert db_session.query(LocationChat).count() == 4
    assert (
        db_session.query(WorldEvent)
        .filter(WorldEvent.event_type == "utterance")
        .count()
        == 4
    )
    assert (
        db_session.query(WorldEvent).filter(WorldEvent.event_type == "movement").count()
        == 2
    )


def test_gym_views_label_the_mechanical_baseline_and_do_not_add_story(db_session):
    result = run_first_conversation(db_session)

    terminal = render_terminal(result)
    page = render_html(result)

    assert "mechanical baseline" in terminal
    assert "Every line above comes from a service receipt or signal read." in terminal
    assert "mechanical listener" in page
    assert "The display adds layout and icons, not narration." in page
    assert "Good morning. Is the footbridge open?" in terminal
    assert "Good morning. Is the footbridge open?" in page
