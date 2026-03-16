"""Tests for world memory API endpoints."""

import json
from datetime import datetime, timedelta, timezone

from src.models import WorldEvent


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
