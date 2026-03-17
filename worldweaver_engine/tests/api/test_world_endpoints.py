"""Tests for world memory API endpoints."""

import json
from datetime import datetime, timedelta, timezone

from src.models import DirectMessage, LocationChat, SessionVars, WorldEvent, WorldFact, WorldProjection


class TestWorldHistoryEndpoint:

    def test_empty_history(self, client):
        resp = client.get("/api/world/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["events"] == []
        assert data["count"] == 0
        assert data["filters"] == {}

    def test_history_after_next(self, seeded_client):
        # Fire a storylet via POST /api/next
        resp = seeded_client.post("/api/next", json={"session_id": "world-test", "vars": {}})
        assert resp.status_code == 200

        # Check world history
        resp = seeded_client.get("/api/world/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        assert data["events"][0]["event_type"] == "storylet_fired"
        assert data["filters"] == {}

    def test_history_with_session_filter(self, seeded_client):
        seeded_client.post("/api/next", json={"session_id": "sess-a", "vars": {}})
        resp = seeded_client.get("/api/world/history?session_id=sess-a")
        assert resp.status_code == 200
        assert resp.json()["filters"] == {}
        for event in resp.json()["events"]:
            assert event["session_id"] == "sess-a"

    def test_history_filters_by_event_type(self, client, db_session):
        db_session.add_all(
            [
                WorldEvent(
                    session_id="event-filter-session",
                    event_type="storylet_fired",
                    summary="Storylet fired",
                    world_state_delta={},
                ),
                WorldEvent(
                    session_id="event-filter-session",
                    event_type="permanent_change",
                    summary="Bridge collapsed",
                    world_state_delta={"environment": {"bridge": "collapsed"}},
                ),
            ]
        )
        db_session.commit()

        resp = client.get("/api/world/history?session_id=event-filter-session&event_type=permanent_change")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["events"][0]["event_type"] == "permanent_change"
        assert data["filters"] == {"event_type": "permanent_change"}

    def test_history_filters_by_time_range(self, client, db_session):
        db_session.add_all(
            [
                WorldEvent(
                    session_id="time-filter-session",
                    event_type="system",
                    summary="Outside lower bound",
                    world_state_delta={},
                    created_at=datetime(2026, 1, 1, 10, 0, 0),
                ),
                WorldEvent(
                    session_id="time-filter-session",
                    event_type="system",
                    summary="Inside window",
                    world_state_delta={},
                    created_at=datetime(2026, 1, 1, 12, 0, 0),
                ),
                WorldEvent(
                    session_id="time-filter-session",
                    event_type="system",
                    summary="Outside upper bound",
                    world_state_delta={},
                    created_at=datetime(2026, 1, 1, 14, 0, 0),
                ),
            ]
        )
        db_session.commit()

        resp = client.get("/api/world/history?session_id=time-filter-session&" "since=2026-01-01T11:00:00Z&until=2026-01-01T13:00:00Z")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["events"][0]["summary"] == "Inside window"
        assert data["filters"]["since"].startswith("2026-01-01T11:00:00")
        assert data["filters"]["until"].startswith("2026-01-01T13:00:00")

    def test_history_invalid_timestamp_returns_422(self, client):
        resp = client.get("/api/world/history?since=not-a-timestamp")
        assert resp.status_code == 422
        detail = resp.json().get("detail", [])
        assert any(isinstance(item, dict) and any(str(part) == "since" for part in item.get("loc", [])) for item in detail)


class TestWorldFactsEndpoint:

    def test_facts_returns_shape(self, client):
        resp = client.get("/api/world/facts?query=bridge")
        assert resp.status_code == 200
        data = resp.json()
        assert "query" in data
        assert "facts" in data
        assert "count" in data
        assert data["query"] == "bridge"

    def test_facts_missing_query(self, client):
        resp = client.get("/api/world/facts")
        assert resp.status_code == 422


class TestWorldGraphEndpoints:

    def test_graph_facts_returns_shape(self, seeded_client):
        seeded_client.post("/api/next", json={"session_id": "graph-api", "vars": {}})
        seeded_client.post(
            "/api/action",
            json={
                "session_id": "graph-api",
                "action": "I break the bridge supports",
            },
        )

        resp = seeded_client.get("/api/world/graph/facts?query=bridge&session_id=graph-api")
        assert resp.status_code == 200
        data = resp.json()
        assert "query" in data
        assert "facts" in data
        assert "count" in data

    def test_graph_neighborhood_returns_shape(self, seeded_client):
        seeded_client.post("/api/next", json={"session_id": "graph-neighborhood", "vars": {}})
        seeded_client.post(
            "/api/action",
            json={
                "session_id": "graph-neighborhood",
                "action": "I damage the bridge",
            },
        )

        resp = seeded_client.get("/api/world/graph/neighborhood?node=bridge")
        assert resp.status_code == 200
        data = resp.json()
        assert "node" in data
        assert "edges" in data
        assert "facts" in data
        assert "count" in data

    def test_graph_location_returns_shape(self, seeded_client):
        seeded_client.post("/api/next", json={"session_id": "graph-location", "vars": {}})
        seeded_client.post(
            "/api/action",
            json={
                "session_id": "graph-location",
                "action": "I destroy the bridge",
            },
        )

        resp = seeded_client.get("/api/world/graph/location/bridge?session_id=graph-location")
        assert resp.status_code == 200
        data = resp.json()
        assert data["location"] == "bridge"
        assert "facts" in data
        assert "count" in data


class TestWorldProjectionEndpoint:

    def test_projection_returns_shape(self, seeded_client):
        seeded_client.post("/api/next", json={"session_id": "projection-api", "vars": {}})
        seeded_client.post(
            "/api/action",
            json={
                "session_id": "projection-api",
                "action": "I destroy the old bridge",
            },
        )

        resp = seeded_client.get("/api/world/projection")
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert "count" in data
        assert isinstance(data["entries"], list)
        if data["entries"]:
            first = data["entries"][0]
            assert "source_event_id" in first
            assert "source_event_type" in first
            assert "source_event_summary" in first
            assert "source_event_created_at" in first

    def test_projection_prefix_filter(self, seeded_client):
        seeded_client.post("/api/next", json={"session_id": "projection-prefix", "vars": {}})
        seeded_client.post(
            "/api/action",
            json={
                "session_id": "projection-prefix",
                "action": "I damage the bridge",
            },
        )

        resp = seeded_client.get("/api/world/projection?prefix=variables.")
        assert resp.status_code == 200
        data = resp.json()
        assert data["prefix"] == "variables."


class TestWorldRestMetricsEndpoint:

    def test_rest_metrics_reports_resting_sessions_and_tuning_overrides(
        self,
        seeded_client,
        monkeypatch,
        tmp_path,
    ):
        residents_dir = tmp_path / "residents"
        (residents_dir / "sun_li" / "identity").mkdir(parents=True)
        (residents_dir / "fei_fei" / "identity").mkdir(parents=True)
        (residents_dir / "sun_li" / "identity" / "tuning.json").write_text(
            json.dumps(
                {
                    "rest": {
                        "break_minutes": 30.0,
                        "wake_grace_minutes": 90.0,
                    }
                }
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr("src.api.game.world._WW_AGENT_RESIDENTS", residents_dir)

        resting_sid = "sun_li-20260316-120000"
        pending_sid = "levi-session"
        seeded_client.post("/api/next", json={"session_id": resting_sid, "vars": {}})
        seeded_client.post("/api/next", json={"session_id": pending_sid, "vars": {}})

        now = datetime.now(timezone.utc)
        rest_response = seeded_client.post(
            f"/api/state/{resting_sid}/vars",
            json={
                "vars": {
                    "location": "Tea House",
                    "_rest_state": "resting",
                    "_dormant_state": "dormant",
                    "_rest_reason": "needed quiet",
                    "_rest_location": "Tea House",
                    "_rest_started_at": (now - timedelta(minutes=10)).isoformat(),
                    "_rest_until": (now + timedelta(minutes=35)).isoformat(),
                }
            },
        )
        assert rest_response.status_code == 200

        pending_response = seeded_client.post(
            f"/api/state/{pending_sid}/vars",
            json={
                "vars": {
                    "location": "Cafe",
                    "_rest_pending_hits": 1,
                    "_rest_pending_reason": "needs air",
                    "_rest_pending_location": "Cafe",
                    "_rest_pending_since": now.isoformat(),
                    "player_role": "Levi — testing the city",
                }
            },
        )
        assert pending_response.status_code == 200

        response = seeded_client.get("/api/world/rest-metrics")
        assert response.status_code == 200
        payload = response.json()

        assert payload["counts"]["total"] >= 2
        assert payload["counts"]["resting"] == 1
        assert payload["counts"]["pending_confirmation"] >= 1
        assert payload["fractions"]["resting"] > 0
        assert payload["rest_config"]["resident_count"] == 2
        assert payload["rest_config"]["override_count"] == 1
        assert payload["rest_config"]["overrides"][0]["resident"] == "sun_li"

        sessions = {entry["session_id"]: entry for entry in payload["sessions"]}
        assert sessions[resting_sid]["status"] == "resting"
        assert sessions[resting_sid]["entity_type"] == "agent"
        assert sessions[resting_sid]["rest_reason"] == "needed quiet"
        assert sessions[resting_sid]["rest_location"] == "Tea House"
        assert sessions[resting_sid]["remaining_minutes"] is not None
        assert sessions[pending_sid]["entity_type"] == "human"
        assert sessions[pending_sid]["pending_hits"] == 1
        assert sessions[pending_sid]["pending_reason"] == "needs air"

    def test_rest_metrics_can_include_active_sessions(self, seeded_client):
        session_id = "active-rest-metrics"
        seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})

        response = seeded_client.get("/api/world/rest-metrics?include_active=true")
        assert response.status_code == 200
        payload = response.json()

        sessions = {entry["session_id"]: entry for entry in payload["sessions"]}
        assert sessions[session_id]["status"] == "active"

    def test_rest_metrics_excludes_stale_human_sessions(self, client, db_session):
        recent_human_sid = "ww-recent-human"
        stale_human_sid = "ww-stale-human"
        agent_sid = "sun_li-20260316-120000"
        now = datetime.now(timezone.utc)

        db_session.add_all(
            [
                SessionVars(
                    session_id=recent_human_sid,
                    vars={"player_role": "Levi — recent visitor", "location": "Tea House"},
                    updated_at=now - timedelta(minutes=10),
                ),
                SessionVars(
                    session_id=stale_human_sid,
                    vars={"player_role": "Levi — stale visitor", "location": "Tea House"},
                    updated_at=now - timedelta(hours=6),
                ),
                SessionVars(
                    session_id=agent_sid,
                    vars={"location": "Tea House"},
                    updated_at=now - timedelta(hours=6),
                ),
            ]
        )
        db_session.commit()

        response = client.get("/api/world/rest-metrics?include_active=true")
        assert response.status_code == 200
        payload = response.json()

        sessions = {entry["session_id"]: entry for entry in payload["sessions"]}
        assert recent_human_sid in sessions
        assert stale_human_sid not in sessions
        assert agent_sid in sessions
        assert payload["counts"]["total"] == 2


class TestNeighborhoodVitalityEndpoint:

    def test_vitality_rollup_reports_presence_chat_and_events(self, client, db_session):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db_session.add_all(
            [
                SessionVars(
                    session_id="sun_li-20260316-120000",
                    vars={"location": "Chinatown"},
                    updated_at=now,
                ),
                SessionVars(
                    session_id="levi-vitality",
                    vars={"location": "Chinatown", "player_role": "Levi — vitality test"},
                    updated_at=now,
                ),
                LocationChat(
                    location="Chinatown",
                    session_id="levi-vitality",
                    display_name="Levi",
                    message="Checking in from Chinatown.",
                ),
                WorldEvent(
                    session_id="sun_li-20260316-120000",
                    event_type="utterance",
                    summary="Sun Li checked the avenue.",
                    world_state_delta={"location": "Chinatown"},
                ),
            ]
        )
        db_session.commit()

        response = client.get("/api/world/vitality/neighborhoods?hours=6")
        assert response.status_code == 200
        payload = response.json()

        assert payload["available"] is True
        neighborhoods = {item["name"]: item for item in payload["neighborhoods"]}
        chinatown = neighborhoods["Chinatown"]
        assert chinatown["current_present"] >= 2
        assert chinatown["current_agents"] >= 1
        assert chinatown["current_humans"] >= 1
        assert chinatown["chat_messages_recent"] >= 1
        assert chinatown["unique_chat_speakers_recent"] >= 1
        assert chinatown["recent_event_count"] >= 1


class TestWorldEventLedgerEndpoints:

    def test_map_move_records_structured_facts_and_public_projection(self, client, db_session):
        from src.services.world_memory import seed_location_graph

        seed_location_graph(
            db_session,
            [
                {"name": "Tea House"},
                {"name": "Market Street"},
            ],
        )

        state_response = client.post(
            "/api/state/mover/vars",
            json={"vars": {"location": "Tea House", "player_role": "Levi — tester"}},
        )
        assert state_response.status_code == 200

        move_response = client.post(
            "/api/game/move",
            json={"session_id": "mover", "destination": "Market Street"},
        )
        assert move_response.status_code == 200
        assert move_response.json()["moved"] is True

        movement_event = (
            db_session.query(WorldEvent)
            .filter(WorldEvent.session_id == "mover", WorldEvent.event_type == "movement")
            .order_by(WorldEvent.id.desc())
            .first()
        )
        assert movement_event is not None
        assert movement_event.world_state_delta["origin"] == "Tea House"
        assert movement_event.world_state_delta["destination"] == "Market Street"
        assert movement_event.world_state_delta["__world_facts__"]["facts"][0]["predicate"] == "location"

        location_fact = (
            db_session.query(WorldFact)
            .filter(
                WorldFact.session_id == "mover",
                WorldFact.predicate == "location",
                WorldFact.is_active.is_(True),
            )
            .order_by(WorldFact.id.desc())
            .first()
        )
        assert location_fact is not None
        assert location_fact.value == "Market Street"

        destination_projection = (
            db_session.query(WorldProjection)
            .filter(WorldProjection.path == "locations.market_street.last_arrival_actor")
            .one_or_none()
        )
        assert destination_projection is not None
        assert destination_projection.value == "Levi"

        departure_projection = (
            db_session.query(WorldProjection)
            .filter(WorldProjection.path == "locations.tea_house.last_departure_to")
            .one_or_none()
        )
        assert departure_projection is not None
        assert departure_projection.value == "Market Street"

    def test_location_chat_records_low_noise_utterance_fact_and_public_projection(self, client, db_session):
        response = client.post(
            "/api/world/location/Cafe/chat",
            json={
                "session_id": "speaker-session",
                "display_name": "Levi",
                "message": "Hello from the counter.",
            },
        )
        assert response.status_code == 200

        utterance_event = (
            db_session.query(WorldEvent)
            .filter(WorldEvent.session_id == "speaker-session", WorldEvent.event_type == "utterance")
            .order_by(WorldEvent.id.desc())
            .first()
        )
        assert utterance_event is not None
        assert utterance_event.summary == "Levi said: Hello from the counter."
        assert utterance_event.world_state_delta["__world_facts__"]["facts"][0]["predicate"] == "spoke_at"

        utterance_fact = (
            db_session.query(WorldFact)
            .filter(
                WorldFact.session_id == "speaker-session",
                WorldFact.predicate == "spoke_at",
                WorldFact.is_active.is_(True),
            )
            .order_by(WorldFact.id.desc())
            .first()
        )
        assert utterance_fact is not None
        assert utterance_fact.value == "Cafe"

        utterance_projection = (
            db_session.query(WorldProjection)
            .filter(WorldProjection.path == "locations.cafe.last_public_utterance")
            .one_or_none()
        )
        assert utterance_projection is not None
        assert utterance_projection.value == "Hello from the counter."

        speaker_projection = (
            db_session.query(WorldProjection)
            .filter(WorldProjection.path == "locations.cafe.last_public_speaker")
            .one_or_none()
        )
        assert speaker_projection is not None
        assert speaker_projection.value == "Levi"

    def test_player_dm_stays_private_and_does_not_touch_public_ledger(self, client, db_session):
        response = client.post(
            "/api/world/dm",
            json={
                "to_agent": "sun_li",
                "from_name": "Levi",
                "body": "Private note.",
                "session_id": "ww-private-player",
            },
        )
        assert response.status_code == 200

        dm = db_session.query(DirectMessage).order_by(DirectMessage.id.desc()).first()
        assert dm is not None
        assert dm.to_name == "sun_li"
        assert dm.from_name == "Levi"
        assert dm.from_session_id == "ww-private-player"

        assert db_session.query(WorldEvent).count() == 0
        assert db_session.query(WorldFact).count() == 0
        assert db_session.query(WorldProjection).count() == 0

    def test_agent_dm_reply_stays_private_and_does_not_touch_public_ledger(self, client, db_session):
        response = client.post(
            "/api/world/dm/reply",
            json={
                "from_agent": "sun_li",
                "to_session_id": "ww-private-player",
                "body": "Private reply.",
            },
        )
        assert response.status_code == 200

        dm = db_session.query(DirectMessage).order_by(DirectMessage.id.desc()).first()
        assert dm is not None
        assert dm.to_name == "ww-private-player"
        assert dm.from_name == "Sun_li"

        assert db_session.query(WorldEvent).count() == 0
        assert db_session.query(WorldFact).count() == 0
        assert db_session.query(WorldProjection).count() == 0

    def test_event_ledger_endpoint_reports_fact_and_projection_fanout(self, client, db_session):
        from src.services.world_memory import seed_location_graph

        seed_location_graph(
            db_session,
            [
                {"name": "Tea House"},
                {"name": "Market Street"},
            ],
        )
        client.post(
            "/api/state/mover/vars",
            json={"vars": {"location": "Tea House", "player_role": "Levi — tester"}},
        )
        client.post("/api/game/move", json={"session_id": "mover", "destination": "Market Street"})
        client.post(
            "/api/world/location/Cafe/chat",
            json={
                "session_id": "speaker-session",
                "display_name": "Levi",
                "message": "Hello from the counter.",
            },
        )

        response = client.get("/api/world/event-ledger?limit=5")
        assert response.status_code == 200
        payload = response.json()

        entries = payload["entries"]
        assert len(entries) >= 2

        movement_entry = next(entry for entry in entries if entry["event_type"] == "movement")
        assert movement_entry["surface"] == "map_move"
        assert movement_entry["fact_count"] >= 2
        assert movement_entry["projection_count"] >= 2
        assert "locations.market_street.last_arrival_actor" in movement_entry["projection_paths"]

        utterance_entry = next(entry for entry in entries if entry["event_type"] == "utterance")
        assert utterance_entry["surface"] == "chat"
        assert utterance_entry["fact_count"] >= 1
        assert utterance_entry["projection_count"] >= 1
        assert "locations.cafe.last_public_utterance" in utterance_entry["projection_paths"]
