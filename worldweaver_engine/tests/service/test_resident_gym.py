# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from urllib.parse import quote

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.game import _state_managers
from src.database import Base, get_db
from src.models import DirectMessage, LocationChat, WorldEvent
from src.services.gym_presentation import (
    render_html,
    render_terminal,
    render_terminal_record,
    render_terminal_stream_footer,
    render_terminal_stream_header,
)
from src.services.resident_gym import (
    ProductionRuleGym,
    prepare_quiet_interval,
    run_first_conversation,
    run_quiet_interval,
    run_waiting_letter,
)
from src.services.session_service import _session_locks, get_state_manager


def _canonical_episode_snapshot(db_session):
    chats = [
        (row.display_name, row.location, row.message)
        for row in db_session.query(LocationChat).order_by(LocationChat.id).all()
    ]
    events = [
        (
            row.session_id,
            row.event_type,
            row.summary,
            row.world_state_delta,
        )
        for row in db_session.query(WorldEvent).order_by(WorldEvent.id).all()
    ]
    locations = {
        session_id: str(
            get_state_manager(session_id, db_session).get_variable("location") or ""
        )
        for session_id in ("gym-mara", "gym-ivo")
    }
    return {"chats": chats, "events": events, "locations": locations}


def _expect(response, status_code: int = 200):
    assert response.status_code == status_code, response.text
    return response.json()


def _signal_read(client, *, session_id, headers, cursor=None):
    params = {}
    if cursor is not None:
        params = {
            "after": cursor["after_id"],
            "cursor_shard": cursor["shard_id"],
            "cursor_location": cursor["location"],
        }
    return _expect(
        client.get(
            f"/api/world/session/{session_id}/signals",
            params=params,
            headers=headers,
        )
    )


def _http_speak(client, *, session_id, location, message, headers):
    return _expect(
        client.post(
            f"/api/world/location/{quote(location, safe='')}/chat",
            json={"session_id": session_id, "message": message},
            headers=headers,
        )
    )


def _http_move(client, *, session_id, destination, headers):
    return _expect(
        client.post(
            "/api/game/move",
            json={"session_id": session_id, "destination": destination},
            headers=headers,
        )
    )


def test_first_gym_conversation_uses_exact_place_production_signals(db_session):
    result = run_first_conversation(db_session)

    assert result.schema == "worldweaver.resident-gym.episode"
    assert result.schema_version == 9
    assert result.fidelity.engine_rules == "production_services"
    assert result.fidelity.resident_composition == "not_exercised"
    assert result.fidelity.participant_transport == "direct_scenario_calls"
    assert result.fidelity.resident_authorization == "not_exercised"
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


def test_gym_can_stream_each_record_as_the_production_boundary_returns(db_session):
    observed = []

    result = run_first_conversation(db_session, record_observer=observed.append)

    assert tuple(observed) == result.records
    assert [record.sequence for record in observed] == list(range(1, len(observed) + 1))
    assert "Live structural record" in render_terminal_stream_header(result.episode)
    assert "🧭" in render_terminal_record(observed[0])
    assert "Episode complete" in render_terminal_stream_footer(result)


def test_waiting_letter_survives_session_change_until_acknowledged(db_session):
    result = run_waiting_letter(db_session)

    assert result.episode == "The Waiting Letter"
    assert {participant.session_id for participant in result.participants} == {
        "gym-letter-mara",
        "gym-letter-ivo-after",
    }
    waiting = [record for record in result.records if record.kind == "letter_waiting"]
    assert len(waiting) == 2
    assert waiting[0].detail["message_id"] == waiting[1].detail["message_id"]
    assert [record.kind for record in result.records][-2:] == [
        "letter_acknowledged",
        "mailbox_empty",
    ]

    message = db_session.query(DirectMessage).one()
    assert message.recipient_actor_id == "gym-letter-actor-ivo"
    assert message.acknowledged_at is not None
    assert (
        db_session.query(WorldEvent)
        .filter(WorldEvent.event_type.like("%correspondence%"))
        .count()
        == 0
    )


def test_waiting_letter_view_has_a_fact_backed_post_trail(db_session):
    result = run_waiting_letter(db_session)

    terminal = render_terminal(result)
    page = render_html(result)

    assert "📬" in terminal
    assert "was offered message" in terminal
    assert "The post trail" in page
    assert "sent" in page and "waiting" in page and "acknowledged" in page
    assert "The moving envelope is only a visual key." in page


def test_quiet_interval_mixes_live_speech_with_a_two_day_rule(db_session):
    result = run_quiet_interval(db_session)

    assert result.schema_version == 9
    assert [
        record.kind
        for record in result.records
        if record.kind in {"sublocation_active", "sublocation_expired"}
    ] == ["sublocation_active", "sublocation_active", "sublocation_expired"]
    assert [
        record.detail["elapsed_seconds"]
        for record in result.records
        if record.kind == "time_advanced"
    ] == [47 * 3600, 2 * 3600]
    assert [
        record.detail["event_id"]
        for record in result.records
        if record.kind == "scheduled_event_offered"
    ] == ["scheduled-00000001", "scheduled-00000002"]
    assert [
        record.detail["event_ids"]
        for record in result.records
        if record.kind == "scheduled_event_acknowledged"
    ] == [["scheduled-00000001"], ["scheduled-00000002"]]
    heard = [record for record in result.records if record.kind == "heard"]
    assert [record.detail["message"] for record in heard] == [
        "I left a dry seat at the willow bench."
    ]
    assert result.records[0].occurred_at == "2026-07-20T12:00:00+00:00"
    assert result.records[-1].occurred_at == "2026-07-22T13:00:00+00:00"


def test_gym_observation_uses_the_production_scene_and_records_only_shape(db_session):
    gym = prepare_quiet_interval(db_session)

    scene = gym.observe("gym-afternoon-mara")

    assert scene["location"] == "Willow Court"
    assert [person["name"] for person in scene["present"]] == ["Ivo"]
    assert scene["ambient_presence"] == []
    assert scene["traces_here"] == []
    assert any(
        node["name"] == "willow bench" for node in scene["location_graph"]["nodes"]
    )
    record = gym.result().records[-1]
    assert record.kind == "observation_ready"
    assert record.detail == {
        "present_count": 1,
        "trace_count": 0,
        "route_count": len(scene["location_graph"]["edges"]),
        "place_count": len(scene["location_graph"]["nodes"]),
    }
    assert "dry seat" not in str(record.detail)


def test_quiet_interval_view_marks_clock_jumps_as_display_only(db_session):
    result = run_quiet_interval(db_session)

    terminal = render_terminal(result)
    page = render_html(result)

    assert "advanced 47 hours without sleeping" in terminal
    assert "The quiet interval" in page
    assert "No process slept through these hours." in page
    assert "Jul 22 13:00" in page


def test_first_gym_episode_matches_authenticated_http_rules(db_session, monkeypatch):
    run_first_conversation(db_session)
    service_snapshot = _canonical_episode_snapshot(db_session)

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    http_db = session_factory()

    from main import app

    def override_db():
        yield http_db

    monkeypatch.setattr("src.api.auth.routes.send_welcome_email", lambda *_a: None)
    monkeypatch.setattr("src.config.settings.require_email_verification", False)
    app.dependency_overrides[get_db] = override_db
    _state_managers.clear()
    _session_locks.clear()

    try:
        arranger = ProductionRuleGym(
            http_db,
            episode="The Footbridge Hello",
            world_id="gym-footbridge-world",
        )
        arranger.arrange_world(("Willow Court", "Footbridge"))

        with TestClient(app, raise_server_exceptions=False) as client:
            tokens = {}
            for name in ("Mara", "Ivo"):
                auth = _expect(
                    client.post(
                        "/api/auth/register",
                        json={
                            "email": f"gym-{name.lower()}@example.com",
                            "display_name": name,
                            "password": "gym-password-1",
                            "password_confirmation": "gym-password-1",
                            "terms_accepted": True,
                        },
                    )
                )
                tokens[name] = {"Authorization": f"Bearer {auth['token']}"}
                _expect(
                    client.post(
                        "/api/session/bootstrap",
                        json={
                            "session_id": f"gym-{name.lower()}",
                            "world_id": "gym-footbridge-world",
                            "player_role": name,
                            "bootstrap_source": "resident-gym-http",
                            "entry_location": "Willow Court",
                        },
                        headers=tokens[name],
                    )
                )

            anonymous = client.get("/api/world/session/gym-ivo/signals")
            _expect(anonymous, 401)

            mara_signal = _signal_read(
                client,
                session_id="gym-mara",
                headers=tokens["Mara"],
            )
            ivo_signal = _signal_read(
                client,
                session_id="gym-ivo",
                headers=tokens["Ivo"],
            )

            _http_speak(
                client,
                session_id="gym-mara",
                location="Willow Court",
                message="Good morning. Is the footbridge open?",
                headers=tokens["Mara"],
            )
            ivo_signal = _signal_read(
                client,
                session_id="gym-ivo",
                headers=tokens["Ivo"],
                cursor=ivo_signal["cursor"],
            )
            assert [item["message"] for item in ivo_signal["events"]] == [
                "Good morning. Is the footbridge open?"
            ]

            _http_speak(
                client,
                session_id="gym-ivo",
                location="Willow Court",
                message="I heard you. I can go and look.",
                headers=tokens["Ivo"],
            )
            mara_signal = _signal_read(
                client,
                session_id="gym-mara",
                headers=tokens["Mara"],
                cursor=mara_signal["cursor"],
            )
            assert [item["message"] for item in mara_signal["events"]] == [
                "I heard you. I can go and look."
            ]

            _http_move(
                client,
                session_id="gym-ivo",
                destination="Footbridge",
                headers=tokens["Ivo"],
            )
            ivo_signal = _signal_read(
                client,
                session_id="gym-ivo",
                headers=tokens["Ivo"],
                cursor=ivo_signal["cursor"],
            )
            assert ivo_signal["cursor_status"] == "scope_changed"

            _http_speak(
                client,
                session_id="gym-mara",
                location="Willow Court",
                message="Can you hear me from over there?",
                headers=tokens["Mara"],
            )
            ivo_signal = _signal_read(
                client,
                session_id="gym-ivo",
                headers=tokens["Ivo"],
                cursor=ivo_signal["cursor"],
            )
            assert ivo_signal["events"] == []

            _http_move(
                client,
                session_id="gym-mara",
                destination="Footbridge",
                headers=tokens["Mara"],
            )
            mara_signal = _signal_read(
                client,
                session_id="gym-mara",
                headers=tokens["Mara"],
                cursor=mara_signal["cursor"],
            )
            assert mara_signal["cursor_status"] == "scope_changed"

            _http_speak(
                client,
                session_id="gym-mara",
                location="Footbridge",
                message="There you are.",
                headers=tokens["Mara"],
            )
            ivo_signal = _signal_read(
                client,
                session_id="gym-ivo",
                headers=tokens["Ivo"],
                cursor=ivo_signal["cursor"],
            )
            assert [item["message"] for item in ivo_signal["events"]] == [
                "There you are."
            ]

        assert _canonical_episode_snapshot(http_db) == service_snapshot
    finally:
        app.dependency_overrides.pop(get_db, None)
        http_db.close()
        engine.dispose()
        _state_managers.clear()
        _session_locks.clear()
