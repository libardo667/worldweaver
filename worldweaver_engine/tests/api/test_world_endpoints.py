"""Tests for world memory API endpoints."""

from datetime import datetime, timedelta, timezone

from src.models import DirectMessage, LocationChat, SessionVars, WorldEvent, WorldFact, WorldNode, WorldProjection


class TestWorldHistoryEndpoint:
    def test_empty_history(self, client):
        resp = client.get("/api/world/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["events"] == []
        assert data["count"] == 0
        assert data["filters"] == {}

    def test_history_after_recorded_world_event(self, seeded_client, db_session):
        db_session.add(
            WorldEvent(
                session_id="world-test",
                event_type="world_trace",
                summary="A public trace was left at the square.",
                world_state_delta={"location": "square"},
            )
        )
        db_session.commit()

        # Check world history
        resp = seeded_client.get("/api/world/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        assert data["events"][0]["event_type"] == "world_trace"
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
                    event_type="system",
                    summary="System event",
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

        resp = seeded_client.get("/api/world/graph/facts?query=bridge&session_id=graph-api")
        assert resp.status_code == 200
        data = resp.json()
        assert "query" in data
        assert "facts" in data
        assert "count" in data


class TestAgentSceneEndpoints:
    def test_digest_does_not_count_retired_resident_history_as_live_presence(self, seeded_client, db_session):
        db_session.add(
            WorldEvent(
                session_id="test_resident-20260316-120000",
                event_type="movement",
                summary="Test Resident arrived at The Mission.",
                world_state_delta={
                    "location": "Chinatown",
                    "destination": "The Mission",
                },
            )
        )
        db_session.commit()

        response = seeded_client.get("/api/world/digest")

        assert response.status_code == 200
        payload = response.json()
        assert payload["active_sessions"] == 0
        assert payload["roster"] == []
        assert all("Test Resident" not in node["agent_names"] and node["agent_count"] == 0 for node in payload["location_graph"]["nodes"])

    def test_scene_reads_presence_from_session_vars_without_state_manager(self, client, db_session, monkeypatch):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db_session.add_all(
            [
                SessionVars(
                    session_id="test_resident-20260316-120000",
                    vars={"location": "Chinatown"},
                    updated_at=now,
                ),
                SessionVars(
                    session_id="ww-levi-scene",
                    actor_id="actor-levi",
                    vars={"location": "Chinatown", "player_role": "Levi — visitor"},
                    updated_at=now,
                ),
                WorldEvent(
                    session_id="test_resident-20260316-120000",
                    event_type="utterance",
                    summary="Test Resident checked the avenue.",
                    world_state_delta={"location": "Chinatown"},
                    created_at=now,
                ),
            ]
        )
        db_session.commit()

        def _fail(*args, **kwargs):
            raise AssertionError("get_state_manager should not be used by scene endpoint")

        monkeypatch.setattr("src.services.session_service.get_state_manager", _fail)

        response = client.get("/api/world/scene/test_resident-20260316-120000")
        assert response.status_code == 200
        payload = response.json()

        present_names = {entry["name"] for entry in payload["present"]}
        assert "Levi" in present_names
        levi = next(entry for entry in payload["present"] if entry["name"] == "Levi")
        assert levi["actor_id"] == "actor-levi"
        assert levi["session_id"] == "ww-levi-scene"
        assert payload["recent_events_here"][0]["who"] == "Test Resident"
        assert payload["recent_events_here"][0]["event_type"] == "utterance"
        assert payload["recent_events_here"][0]["event_id"]

    def test_scene_last_action_prefers_observed_summary(self, client, db_session):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db_session.add_all(
            [
                SessionVars(
                    session_id="test_resident-20260316-120000",
                    vars={"location": "Chinatown"},
                    updated_at=now,
                ),
                SessionVars(
                    session_id="javier_reyes-20260316-120000",
                    vars={"location": "Chinatown", "player_role": "Javier Reyes — watcher"},
                    updated_at=now,
                ),
                WorldEvent(
                    session_id="javier_reyes-20260316-120000",
                    event_type="action",
                    summary="Player action: I scan the waterfront. Observed: Narrows focus, scanning the shifting light along the waterfront.",
                    world_state_delta={"location": "Chinatown"},
                    created_at=now,
                ),
            ]
        )
        db_session.commit()

        response = client.get("/api/world/scene/test_resident-20260316-120000")
        assert response.status_code == 200
        payload = response.json()
        javier = next(item for item in payload["present"] if item["name"] == "Javier Reyes")
        assert javier["last_action"] == "Narrows focus, scanning the shifting light along the waterfront."

    def test_scene_includes_derived_ambient_presence(self, client, db_session, monkeypatch):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db_session.add(
            SessionVars(
                session_id="test_resident-20260316-120000",
                vars={"location": "Chinatown"},
                updated_at=now,
            )
        )
        db_session.commit()

        monkeypatch.setattr(
            "src.services.grounding.get_city_time_context",
            lambda _city_id: {
                "time_of_day": "night",
                "weather": "light rain",
                "weather_description": "light rain, 54°F",
            },
        )

        response = client.get("/api/world/scene/test_resident-20260316-120000")
        assert response.status_code == 200
        payload = response.json()

        ambient = payload["ambient_presence"]
        assert ambient
        kinds = {item["kind"] for item in ambient}
        assert "weather_shelter_cluster" in kinds
        assert "night_presence" in kinds
        # Major 64 — the weather is no longer the only loud thing; the place's own
        # intrinsic character is present too (plural salience).
        assert "place_character" in kinds
        assert all("label" in item and item["label"] for item in ambient)


class TestPluralSalience:
    """Major 64 — the world offers more than one loud thing (dilution, not removal)."""

    def _ambient(self, vibe, weather="clear, 65°F", present=1, tod="afternoon"):
        from src.api.game.world import _derive_scene_ambient_presence

        return _derive_scene_ambient_presence(
            location="Somewhere",
            neighborhood={"vibe": vibe},
            current_present=present,
            recent_event_count=0,
            time_of_day=tod,
            weather_description=weather,
        )

    def test_solo_resident_in_clear_weather_still_has_a_loud_place_feature(self):
        items = self._ambient("Dragon gates, herbalists, dim sum, crowded streets")
        kinds = {i["kind"] for i in items}
        # Clear weather → no weather cluster; the place itself must be the loud thing.
        assert "weather_shelter_cluster" not in kinds
        place = next(i for i in items if i["kind"] == "place_character")
        assert place["intensity"] >= 0.54  # weather-competitive
        assert place["label"]

    def test_weather_does_not_remove_place_salience(self):
        items = self._ambient("Dragon gates, herbalists, dim sum", weather="clear, 65°F, 18 mph winds")
        kinds = {i["kind"] for i in items}
        # Dilution, not removal: both the weather AND the place are loud at once.
        assert "weather_shelter_cluster" in kinds
        assert "place_character" in kinds

    def test_different_neighborhoods_are_loud_about_different_things(self):
        chinatown = self._ambient("Dragon gates, herbalists, dim sum, crowded streets")
        embarcadero = self._ambient("Ferry Building, Bay Bridge views, the waterfront promenade")
        c = next(i for i in chinatown if i["kind"] == "place_character")
        e = next(i for i in embarcadero if i["kind"] == "place_character")
        assert c["label"] != e["label"]
        assert "commerce" in c["pressure_tags"]
        assert "maritime" in e["pressure_tags"]

    def test_featureless_neighborhood_has_no_place_character(self):
        items = self._ambient("")
        assert all(i["kind"] != "place_character" for i in items)


class TestRosterDirectoryEndpoint:
    def test_roster_directory_reads_recent_sessions_without_digest_state_manager(self, client, db_session, monkeypatch):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db_session.add_all(
            [
                SessionVars(
                    session_id="test_resident-20260316-120000",
                    vars={"location": "Chinatown"},
                    updated_at=now,
                ),
                SessionVars(
                    session_id="ww-levi",
                    vars={"location": "Chinatown", "player_role": "Levi — observer"},
                    updated_at=now,
                ),
            ]
        )
        db_session.commit()

        def _fail(*args, **kwargs):
            raise AssertionError("get_state_manager should not be used by roster directory endpoint")

        monkeypatch.setattr("src.services.session_service.get_state_manager", _fail)

        response = client.get("/api/world/roster-directory")
        assert response.status_code == 200
        payload = response.json()
        assert payload["count"] == 2

        roster = {(entry["recipient_type"], entry["recipient_key"]): entry for entry in payload["roster"]}
        assert ("agent", "test_resident") in roster
        assert roster[("agent", "test_resident")]["display_name"] == "Test Resident"
        assert ("player", "ww-levi") in roster
        assert roster[("player", "ww-levi")]["display_name"] == "Levi"

    def test_scene_graph_aliases_disconnected_place_name_to_connected_anchor(self, client, db_session, monkeypatch):
        from src.services import world_memory as world_memory_module
        from src.services.world_memory import seed_location_graph

        world_memory_module._LOCATION_GRAPH_CACHE.clear()
        monkeypatch.setattr(
            "src.services.city_pack_service.get_pack",
            lambda city_id=None: {
                "neighborhoods": [
                    {
                        "id": "anchor-neighborhood",
                        "name": "Anchor Neighborhood",
                        "adjacent_to": ["elsewhere"],
                        "lat": 37.78,
                        "lon": -122.42,
                    },
                    {
                        "id": "elsewhere",
                        "name": "Elsewhere",
                        "adjacent_to": ["anchor-neighborhood"],
                        "lat": 37.79,
                        "lon": -122.41,
                    },
                ]
            },
        )
        seed_location_graph(
            db_session,
            [
                {"name": "Anchor Neighborhood"},
                {"name": "Elsewhere"},
            ],
        )
        db_session.add_all(
            [
                WorldNode(
                    name="Quiet Park",
                    normalized_name="quiet_park",
                    node_type="location",
                    metadata_json={},
                ),
                WorldNode(
                    name="Quiet Park",
                    normalized_name="quiet_park",
                    node_type="landmark",
                    metadata_json={
                        "city_id": "san_francisco",
                        "source": "city_pack",
                        "neighborhood": "anchor-neighborhood",
                        "lat": 37.781,
                        "lon": -122.421,
                    },
                ),
                SessionVars(
                    session_id="test_resident-20260316-120000",
                    vars={"location": "Quiet Park"},
                    updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
                ),
            ]
        )
        db_session.commit()
        world_memory_module._LOCATION_GRAPH_CACHE.clear()

        response = client.get("/api/world/scene/test_resident-20260316-120000")

        assert response.status_code == 200
        payload = response.json()
        nodes = payload["location_graph"]["nodes"]
        edges = payload["location_graph"]["edges"]
        anchor_node = next(node for node in nodes if node["name"] == "Anchor Neighborhood")
        quiet_node = next(node for node in nodes if node["name"] == "Quiet Park")

        assert anchor_node["key"].startswith("location:")
        assert quiet_node["key"].startswith("location_alias:")
        assert {"from": quiet_node["key"], "to": anchor_node["key"]} in edges
        assert {"from": anchor_node["key"], "to": quiet_node["key"]} in edges

    def test_new_events_reads_location_from_session_vars_without_state_manager(self, client, db_session, monkeypatch):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db_session.add(
            SessionVars(
                session_id="test_resident-20260316-120000",
                vars={"location": "Chinatown"},
                updated_at=now,
            )
        )
        db_session.add_all(
            [
                WorldEvent(
                    session_id="levi-new-events",
                    event_type="utterance",
                    summary="Player action: Levi says hello. Result: Levi waved from the market.",
                    world_state_delta={"location": "Chinatown"},
                    created_at=now,
                ),
                WorldEvent(
                    session_id="levi-away",
                    event_type="utterance",
                    summary="Levi muttered in North Beach.",
                    world_state_delta={"location": "North Beach"},
                    created_at=now,
                ),
            ]
        )
        db_session.commit()

        def _fail(*args, **kwargs):
            raise AssertionError("get_state_manager should not be used by new-events endpoint")

        monkeypatch.setattr("src.services.session_service.get_state_manager", _fail)

        since = (now - timedelta(minutes=5)).replace(tzinfo=timezone.utc).isoformat()
        response = client.get(
            "/api/world/scene/test_resident-20260316-120000/new-events",
            params={"since": since},
        )
        assert response.status_code == 200
        payload = response.json()

        assert payload["count"] == 1
        assert payload["events"][0]["who"] == "levi-new-eve"
        assert payload["events"][0]["summary"] == "Levi waved from the market."
        assert payload["events"][0]["event_type"] == "utterance"
        assert payload["events"][0]["event_id"]


class TestWorldRestMetricsEndpoint:
    def test_rest_metrics_reports_substrate_derived_rest(self, seeded_client):
        resting_sid = "test_resident-20260316-120000"
        seeded_client.post("/api/next", json={"session_id": resting_sid, "vars": {}})

        now = datetime.now(timezone.utc)
        rest_response = seeded_client.post(
            f"/api/state/{resting_sid}/vars",
            json={
                "vars": {
                    "location": "Tea House",
                    "_resident_rest": {
                        "schema_version": 1,
                        "resting": True,
                        "since": (now - timedelta(minutes=10)).isoformat(),
                        "wakefulness": 0.28,
                        "effective_arousal": 0.04,
                        "reason": "deep_night_lull",
                    },
                }
            },
        )
        assert rest_response.status_code == 200

        response = seeded_client.get("/api/world/rest-metrics")
        assert response.status_code == 200
        payload = response.json()

        assert payload["counts"]["total"] >= 1
        assert payload["counts"]["resting"] == 1
        assert payload["fractions"]["resting"] > 0
        assert "rest_config" not in payload

        sessions = {entry["session_id"]: entry for entry in payload["sessions"]}
        assert sessions[resting_sid]["status"] == "resting"
        assert sessions[resting_sid]["entity_type"] == "agent"
        assert sessions[resting_sid]["rest_reason"] == "deep_night_lull"
        assert sessions[resting_sid]["rest_derived"] is True
        assert sessions[resting_sid]["wakefulness"] == 0.28
        assert sessions[resting_sid]["effective_arousal"] == 0.04
        assert sessions[resting_sid]["rest_started_at"] is not None
        assert sessions[resting_sid]["rest_until"] is None

    def test_rest_metrics_can_include_active_sessions(self, seeded_client, db_session):
        session_id = "active-rest-metrics"
        db_session.add(
            SessionVars(
                session_id=session_id,
                vars={"location": "Commons Bank", "player_role": "Visitor"},
                updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        db_session.commit()

        response = seeded_client.get("/api/world/rest-metrics?include_active=true")
        assert response.status_code == 200
        payload = response.json()

        sessions = {entry["session_id"]: entry for entry in payload["sessions"]}
        assert sessions[session_id]["status"] == "active"

    def test_rest_metrics_excludes_stale_human_sessions(self, client, db_session):
        recent_human_sid = "ww-recent-human"
        stale_human_sid = "ww-stale-human"
        agent_sid = "test_resident-20260316-120000"
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

    def test_rest_metrics_dedupes_agent_identity_to_freshest_session(self, client, db_session):
        now = datetime.now(timezone.utc)
        db_session.add_all(
            [
                SessionVars(
                    session_id="maya_chen-20260317-172249",
                    vars={"location": "Burlingame"},
                    updated_at=now - timedelta(hours=6),
                ),
                SessionVars(
                    session_id="maya_chen-20260318-000120",
                    vars={"location": "Cascade Southeast"},
                    updated_at=now - timedelta(minutes=2),
                ),
                SessionVars(
                    session_id="ruth_chen-20260317-172249",
                    vars={"location": "Arnold Creek"},
                    updated_at=now - timedelta(hours=6),
                ),
                SessionVars(
                    session_id="ruth_chen-20260317-235855",
                    vars={"location": "Arnada"},
                    updated_at=now - timedelta(minutes=1),
                ),
            ]
        )
        db_session.commit()

        response = client.get("/api/world/rest-metrics?include_active=true")
        assert response.status_code == 200
        payload = response.json()

        sessions = {entry["session_id"]: entry for entry in payload["sessions"]}
        assert "maya_chen-20260318-000120" in sessions
        assert "maya_chen-20260317-172249" not in sessions
        assert sessions["maya_chen-20260318-000120"]["location"] == "Cascade Southeast"
        assert "ruth_chen-20260317-235855" in sessions
        assert "ruth_chen-20260317-172249" not in sessions
        assert payload["counts"]["total"] == 2


class TestNeighborhoodVitalityEndpoint:
    def test_vitality_rollup_reports_presence_chat_and_events(self, client, db_session):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db_session.add_all(
            [
                SessionVars(
                    session_id="test_resident-20260316-120000",
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
                    session_id="test_resident-20260316-120000",
                    event_type="utterance",
                    summary="Test Resident checked the avenue.",
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

    def test_vitality_counts_resting_residents_in_total_occupancy(self, client, db_session):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db_session.add_all(
            [
                SessionVars(
                    session_id="test_resident-20260316-120000",
                    vars={"location": "Chinatown", "_rest_state": "resting"},
                    updated_at=now,
                ),
                WorldEvent(
                    session_id="world-test",
                    event_type="movement",
                    summary="Someone crossed Chinatown.",
                    world_state_delta={"location": "Chinatown"},
                    created_at=now,
                ),
            ]
        )
        db_session.commit()

        response = client.get("/api/world/vitality/neighborhoods?hours=6")
        assert response.status_code == 200
        payload = response.json()

        neighborhoods = {item["name"]: item for item in payload["neighborhoods"]}
        chinatown = neighborhoods["Chinatown"]
        assert chinatown["current_agents"] == 0
        assert chinatown["total_agents"] == 1
        assert chinatown["total_present"] == 1
        assert chinatown["needs_residents"] is False


class TestWorldMapQueryEndpoint:
    def test_alderbank_serves_a_small_generated_map_descriptor_and_verified_svg(self, client, monkeypatch):
        from src.config import settings
        from src.services import city_pack_service

        monkeypatch.setattr(settings, "city_id", "alderbank")
        city_pack_service._PACK_CACHE.pop("alderbank", None)

        descriptor_response = client.get("/api/world/map/generated")
        assert descriptor_response.status_code == 200
        descriptor = descriptor_response.json()
        assert descriptor["available"] is True
        assert descriptor["artifact"]["generator"]["id"] == "worldweaver.field-map"
        assert descriptor["artifact"]["section_count"] == 12
        assert "fields" not in descriptor["artifact"]

        svg_response = client.get("/api/world/map/generated.svg")
        assert svg_response.status_code == 200
        assert svg_response.headers["content-type"].startswith("image/svg+xml")
        assert svg_response.headers["etag"].strip('"') == descriptor["artifact"]["svg"]["sha256"]
        assert svg_response.text.startswith('<?xml version="1.0"')

    def test_world_map_query_returns_occupied_landmark_with_parent_edge(self, client, db_session):
        from src.services.world_memory import seed_location_graph
        from src.services import world_memory as world_memory_module

        world_memory_module._LOCATION_GRAPH_CACHE.clear()

        seed_location_graph(
            db_session,
            [
                {"name": "Inner Richmond", "lat": 37.7801, "lon": -122.4801},
                {"name": "Chinatown", "lat": 37.7941, "lon": -122.4078},
            ],
        )
        for name, lat, lon in (
            ("Inner Richmond", 37.7801, -122.4801),
            ("Chinatown", 37.7941, -122.4078),
        ):
            node = db_session.query(WorldNode).filter(WorldNode.name == name).one()
            node.metadata_json = {**(node.metadata_json or {}), "lat": lat, "lon": lon, "city_id": "san_francisco"}
        db_session.add(
            WorldNode(
                name="Clement Street",
                normalized_name="clement_street",
                node_type="landmark",
                metadata_json={
                    "lat": 37.7822,
                    "lon": -122.4812,
                    "description": "Busy commercial strip",
                    "neighborhood": "inner-richmond",
                    "city_id": "san_francisco",
                    "type": "food",
                },
            )
        )
        db_session.add(
            SessionVars(
                session_id="maya_chen-20260317-100000",
                vars={
                    "_v": 2,
                    "variables": {
                        "location": "Clement Street",
                        "_dormant_state": "active",
                    },
                },
            )
        )
        db_session.commit()

        response = client.get("/api/world/map/query?north=37.79&south=37.77&east=-122.40&west=-122.49&include_landmarks=true")
        assert response.status_code == 200
        payload = response.json()

        clement = next(node for node in payload["nodes"] if node["name"] == "Clement Street")
        assert clement["present_count"] == 1
        assert clement["present_names"] == []
        assert clement["player_names"] == []
        assert clement["agent_names"] == []
        parent_edge = next(edge for edge in payload["edges"] if edge["to"] == clement["key"])
        assert parent_edge["kind"] == "contains"
        parent = next(node for node in payload["nodes"] if node["key"] == parent_edge["from"])
        assert parent["name"] == "Inner Richmond"
        assert all(edge["kind"] in {"path", "contains"} for edge in payload["edges"])

        identified = client.get(
            "/api/world/map/query",
            params={
                "north": 37.79,
                "south": 37.77,
                "east": -122.40,
                "west": -122.49,
                "include_landmarks": True,
                "session_id": "maya_chen-20260317-100000",
            },
        ).json()
        identified_clement = next(node for node in identified["nodes"] if node["name"] == "Clement Street")
        assert identified_clement["present_names"] == ["Maya Chen"]

        local_presence = client.get("/api/world/location/Clement Street/presence").json()
        assert local_presence == {
            "location": "Clement Street",
            "present_count": 1,
            "present_names": ["Maya Chen"],
        }

    def test_world_map_query_dedupes_actor_identity_to_freshest_location(self, client, db_session):
        from src.services.world_memory import seed_location_graph
        from src.services import world_memory as world_memory_module

        world_memory_module._LOCATION_GRAPH_CACHE.clear()

        seed_location_graph(
            db_session,
            [
                {"name": "Inner Richmond", "lat": 37.7801, "lon": -122.4801},
                {"name": "Chinatown", "lat": 37.7941, "lon": -122.4078},
            ],
        )
        for name, lat, lon in (
            ("Inner Richmond", 37.7801, -122.4801),
            ("Chinatown", 37.7941, -122.4078),
        ):
            node = db_session.query(WorldNode).filter(WorldNode.name == name).one()
            node.metadata_json = {**(node.metadata_json or {}), "lat": lat, "lon": lon, "city_id": "san_francisco"}

        now = datetime.now(timezone.utc)
        db_session.add_all(
            [
                SessionVars(
                    session_id="maya_chen-20260317-172249",
                    actor_id="actor-maya",
                    vars={"location": "Chinatown"},
                    updated_at=now - timedelta(hours=2),
                ),
                SessionVars(
                    session_id="maya_chen-20260318-000120",
                    actor_id="actor-maya",
                    vars={"location": "Inner Richmond"},
                    updated_at=now - timedelta(minutes=2),
                ),
            ]
        )
        db_session.commit()

        response = client.get("/api/world/map/query?north=37.80&south=37.77&east=-122.40&west=-122.49&include_landmarks=true&session_id=maya_chen-20260318-000120")
        assert response.status_code == 200
        payload = response.json()

        nodes = {node["name"]: node for node in payload["nodes"]}
        assert nodes["Inner Richmond"]["present_names"] == ["Maya Chen"]
        assert nodes["Inner Richmond"]["present_count"] == 1
        assert nodes["Chinatown"]["present_count"] == 0

    def test_world_map_query_dedupes_agent_display_name_even_if_actor_ids_diverge(self, client, db_session):
        from src.services.world_memory import seed_location_graph
        from src.services import world_memory as world_memory_module

        world_memory_module._LOCATION_GRAPH_CACHE.clear()

        seed_location_graph(
            db_session,
            [
                {"name": "Inner Richmond", "lat": 37.7801, "lon": -122.4801},
                {"name": "Chinatown", "lat": 37.7941, "lon": -122.4078},
            ],
        )
        for name, lat, lon in (
            ("Inner Richmond", 37.7801, -122.4801),
            ("Chinatown", 37.7941, -122.4078),
        ):
            node = db_session.query(WorldNode).filter(WorldNode.name == name).one()
            node.metadata_json = {**(node.metadata_json or {}), "lat": lat, "lon": lon, "city_id": "san_francisco"}

        now = datetime.now(timezone.utc)
        db_session.add_all(
            [
                SessionVars(
                    session_id="maya_chen-20260317-172249",
                    actor_id="actor-maya-old",
                    vars={"location": "Chinatown"},
                    updated_at=now - timedelta(hours=2),
                ),
                SessionVars(
                    session_id="maya_chen-20260318-000120",
                    actor_id="actor-maya-new",
                    vars={"location": "Inner Richmond"},
                    updated_at=now - timedelta(minutes=2),
                ),
            ]
        )
        db_session.commit()

        response = client.get("/api/world/map/query?north=37.80&south=37.77&east=-122.40&west=-122.49&include_landmarks=true&session_id=maya_chen-20260318-000120")
        assert response.status_code == 200
        payload = response.json()

        nodes = {node["name"]: node for node in payload["nodes"]}
        assert nodes["Inner Richmond"]["present_names"] == ["Maya Chen"]
        assert nodes["Inner Richmond"]["present_count"] == 1
        assert nodes["Chinatown"]["present_count"] == 0

    def test_world_map_query_search_prefers_corridor_match_without_flooding_view(self, client, db_session):
        from src.services.world_memory import seed_location_graph
        from src.services import world_memory as world_memory_module

        world_memory_module._LOCATION_GRAPH_CACHE.clear()

        seed_location_graph(
            db_session,
            [
                {"name": "Inner Richmond", "lat": 37.7801, "lon": -122.4801},
                {"name": "Chinatown", "lat": 37.7941, "lon": -122.4078},
            ],
        )
        for name, lat, lon in (
            ("Inner Richmond", 37.7801, -122.4801),
            ("Chinatown", 37.7941, -122.4078),
        ):
            node = db_session.query(WorldNode).filter(WorldNode.name == name).one()
            node.metadata_json = {**(node.metadata_json or {}), "lat": lat, "lon": lon, "city_id": "san_francisco"}

        db_session.add_all(
            [
                WorldNode(
                    name="Clement Street",
                    normalized_name="clement_street_shadow",
                    node_type="location",
                    metadata_json={"source_event_id": 1},
                ),
                WorldNode(
                    name="Clement Street",
                    normalized_name="clement_street",
                    node_type="corridor",
                    metadata_json={
                        "lat": 37.7822,
                        "lon": -122.4812,
                        "description": "Busy commercial strip",
                        "neighborhood": "inner-richmond",
                        "city_id": "san_francisco",
                        "type": "food",
                    },
                ),
                WorldNode(
                    name="Dragon Gate",
                    normalized_name="dragon_gate",
                    node_type="landmark",
                    metadata_json={
                        "lat": 37.7902,
                        "lon": -122.4058,
                        "description": "Unrelated landmark",
                        "neighborhood": "chinatown",
                        "city_id": "san_francisco",
                        "type": "monument",
                    },
                ),
            ]
        )
        db_session.add(
            SessionVars(
                session_id="meiying-20260317-100000",
                vars={
                    "_v": 2,
                    "variables": {
                        "location": "Clement Street",
                        "_dormant_state": "active",
                    },
                },
            )
        )
        db_session.commit()

        response = client.get("/api/world/map/query?north=37.80&south=37.77&east=-122.40&west=-122.49&include_landmarks=true&query=Clement%20Street")
        assert response.status_code == 200
        payload = response.json()

        names = {node["name"]: node for node in payload["nodes"]}
        assert "Clement Street" in names
        assert names["Clement Street"]["node_type"] == "corridor"
        assert names["Clement Street"]["present_count"] == 1
        assert names["Clement Street"]["lat"] is not None
        assert "Dragon Gate" not in names
        assert len(payload["nodes"]) < 8

    def test_world_map_query_exact_location_search_prefers_route_context_over_description_matches(self, client, db_session):
        from src.services import world_memory as world_memory_module

        world_memory_module._LOCATION_GRAPH_CACHE.clear()
        db_session.add_all(
            [
                WorldNode(
                    name="Hayes Valley",
                    normalized_name="hayes valley",
                    node_type="location",
                    metadata_json={"city_id": "san_francisco"},
                ),
                WorldNode(
                    name="Western Addition",
                    normalized_name="western addition",
                    node_type="location",
                    metadata_json={},
                ),
                WorldNode(
                    name="Alamo Square",
                    normalized_name="alamo square",
                    node_type="location",
                    metadata_json={"description": "Between Western Addition and Hayes Valley", "city_id": "san_francisco"},
                ),
            ]
        )
        db_session.add(
            SessionVars(
                session_id="levi-test",
                vars={
                    "_v": 2,
                    "variables": {
                        "location": "Hayes Valley",
                        "_dormant_state": "active",
                    },
                },
            )
        )
        db_session.commit()

        response = client.get("/api/world/map/query?north=37.90&south=37.60&east=-122.30&west=-122.60&session_id=levi-test&include_landmarks=true&query=Western%20Addition")
        assert response.status_code == 200
        payload = response.json()
        names = {node["name"] for node in payload["nodes"]}

        assert "Western Addition" in names
        assert "Hayes Valley" in names
        assert len(names) <= 3


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

        movement_event = db_session.query(WorldEvent).filter(WorldEvent.session_id == "mover", WorldEvent.event_type == "movement").order_by(WorldEvent.id.desc()).first()
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

        destination_projection = db_session.query(WorldProjection).filter(WorldProjection.path == "locations.market_street.last_arrival_actor").one_or_none()
        assert destination_projection is not None
        assert destination_projection.value == "Levi"

        departure_projection = db_session.query(WorldProjection).filter(WorldProjection.path == "locations.tea_house.last_departure_to").one_or_none()
        assert departure_projection is not None
        assert departure_projection.value == "Market Street"

    def test_map_move_can_reach_landmark_via_parent_location(self, client, db_session):
        from src.services.world_memory import seed_location_graph

        seed_location_graph(
            db_session,
            [
                {"name": "Inner Richmond", "lat": 37.7801, "lon": -122.4801},
                {"name": "Chinatown", "lat": 37.7941, "lon": -122.4078},
            ],
        )
        db_session.add(
            WorldNode(
                name="Clement Street",
                normalized_name="clement_street",
                node_type="landmark",
                metadata_json={
                    "lat": 37.7822,
                    "lon": -122.4812,
                    "description": "Busy commercial strip",
                    "neighborhood": "inner-richmond",
                    "city_id": "san_francisco",
                    "type": "food",
                },
            )
        )
        db_session.commit()

        client.post(
            "/api/state/mover/vars",
            json={"vars": {"location": "Inner Richmond", "player_role": "Levi — tester"}},
        )

        response = client.post(
            "/api/game/move",
            json={"session_id": "mover", "destination": "Clement Street"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["moved"] is True
        assert payload["to_location"] == "Clement Street"
        assert payload["route"] == ["Inner Richmond", "Clement Street"]

    def test_resident_move_can_create_enter_and_leave_a_local_sublocation(
        self,
        client,
        db_session,
    ):
        from src.services.world_memory import get_location_graph, seed_location_graph

        seed_location_graph(
            db_session,
            [
                {"name": "Western Addition"},
                {"name": "Hayes Valley"},
            ],
        )
        client.post(
            "/api/state/resident-one/vars",
            json={
                "vars": {
                    "location": "Western Addition",
                    "player_role": "Resident One — neighbor",
                }
            },
        )

        refused = client.post(
            "/api/game/move",
            json={
                "session_id": "resident-one",
                "destination": "the duplex near Western Addition park",
            },
        )
        assert refused.status_code == 404

        entered = client.post(
            "/api/game/move",
            json={
                "session_id": "resident-one",
                "destination": "the duplex near Western Addition park",
                "allow_sublocation_create": True,
            },
        )
        assert entered.status_code == 200
        assert entered.json()["to_location"] == "the duplex near Western Addition park"

        # The durable neighborhood graph stays untouched.
        assert "the duplex near Western Addition park" not in {node["name"] for node in get_location_graph(db_session)["nodes"]}

        scene = client.get("/api/world/scene/resident-one").json()
        scene_names = {node["name"] for node in scene["location_graph"]["nodes"]}
        assert scene["location"] == "the duplex near Western Addition park"
        assert "Western Addition" in scene_names
        assert "the duplex near Western Addition park" in scene_names

        left = client.post(
            "/api/game/move",
            json={"session_id": "resident-one", "destination": "Hayes Valley"},
        )
        assert left.status_code == 200
        assert left.json()["from_location"] == "the duplex near Western Addition park"
        assert left.json()["to_location"] == "Hayes Valley"

    def test_sublocation_endpoint_is_parent_scoped_and_rejects_distant_name(
        self,
        client,
        db_session,
    ):
        from src.services.world_memory import seed_location_graph

        seed_location_graph(
            db_session,
            [{"name": "Western Addition"}, {"name": "Hayes Valley"}],
        )
        client.post(
            "/api/state/resident-one/vars",
            json={"vars": {"location": "Western Addition"}},
        )

        created = client.post(
            "/api/game/sublocations",
            json={
                "session_id": "resident-one",
                "label": "back booth",
                "ttl_seconds": 1800,
            },
        )
        assert created.status_code == 200
        assert created.json()["parent_location"] == "Western Addition"
        assert created.json()["persistence"] == "ephemeral"

        listed = client.get(
            "/api/world/sublocations",
            params={"parent_location": "Western Addition"},
        ).json()
        assert listed["count"] == 1
        assert listed["sublocations"][0]["label"] == "back booth"

        rejected = client.post(
            "/api/game/sublocations",
            json={"session_id": "resident-one", "label": "Seattle"},
        )
        assert rejected.status_code == 422

    def test_map_move_can_leave_disconnected_duplicate_place_via_anchor(self, client, db_session, monkeypatch):
        from src.services import world_memory as world_memory_module
        from src.services.world_memory import seed_location_graph

        world_memory_module._LOCATION_GRAPH_CACHE.clear()
        monkeypatch.setattr(
            "src.services.city_pack_service.get_pack",
            lambda city_id=None: {
                "neighborhoods": [
                    {
                        "id": "anchor-neighborhood",
                        "name": "Anchor Neighborhood",
                        "adjacent_to": ["elsewhere"],
                        "lat": 37.78,
                        "lon": -122.42,
                    },
                    {
                        "id": "elsewhere",
                        "name": "Elsewhere",
                        "adjacent_to": ["anchor-neighborhood"],
                        "lat": 37.79,
                        "lon": -122.41,
                    },
                ]
            },
        )
        seed_location_graph(
            db_session,
            [
                {"name": "Anchor Neighborhood"},
                {"name": "Elsewhere"},
            ],
        )
        db_session.add_all(
            [
                WorldNode(
                    name="Quiet Park",
                    normalized_name="quiet_park",
                    node_type="location",
                    metadata_json={},
                ),
                WorldNode(
                    name="Quiet Park",
                    normalized_name="quiet_park",
                    node_type="landmark",
                    metadata_json={
                        "city_id": "san_francisco",
                        "source": "city_pack",
                        "neighborhood": "anchor-neighborhood",
                        "lat": 37.781,
                        "lon": -122.421,
                    },
                ),
            ]
        )
        db_session.commit()
        world_memory_module._LOCATION_GRAPH_CACHE.clear()

        state_response = client.post(
            "/api/state/mover/vars",
            json={"vars": {"location": "Quiet Park", "player_role": "Levi — tester"}},
        )
        assert state_response.status_code == 200

        response = client.post(
            "/api/game/move",
            json={"session_id": "mover", "destination": "Elsewhere"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["moved"] is True
        assert payload["from_location"] == "Quiet Park"
        assert payload["to_location"] == "Elsewhere"
        assert payload["route"] == ["Quiet Park", "Elsewhere"]

    def test_location_chat_records_low_noise_utterance_fact_and_public_projection(self, client, db_session):
        db_session.add(
            SessionVars(
                session_id="speaker-session",
                actor_id="actor-speaker",
                vars={"location": "Cafe", "player_role": "Levi — visitor"},
            )
        )
        db_session.commit()
        response = client.post(
            "/api/world/location/Cafe/chat",
            json={
                "session_id": "speaker-session",
                "display_name": "Not Levi",
                "message": "Hello from the counter.",
            },
        )
        assert response.status_code == 200

        # Identified readers still get speaker ids (agents filter their own utterances by these).
        chat = client.get("/api/world/location/Cafe/chat", params={"session_id": "speaker-session"}).json()["messages"][-1]
        assert chat["actor_id"] == "actor-speaker"
        assert chat["session_id"] == "speaker-session"

        # Sessionless (public) readers get display name and text only.
        public_chat = client.get("/api/world/location/Cafe/chat").json()["messages"][-1]
        assert public_chat["display_name"] == "Levi"
        assert public_chat["message"] == "Hello from the counter."
        assert "session_id" not in public_chat
        assert "actor_id" not in public_chat

        # A made-up query parameter is still a public read, not an identity claim.
        untrusted_chat = client.get("/api/world/location/Cafe/chat", params={"session_id": "not-a-real-session"}).json()["messages"][-1]
        assert "session_id" not in untrusted_chat
        assert "actor_id" not in untrusted_chat

        remote_post = client.post(
            "/api/world/location/Elsewhere/chat",
            json={"session_id": "speaker-session", "display_name": "Levi", "message": "Remote words."},
        )
        assert remote_post.status_code == 409
        assert remote_post.json()["detail"] == "You can only speak where you are standing."

        missing_session_post = client.post(
            "/api/world/location/Cafe/chat",
            json={"session_id": "missing-session", "display_name": "Levi", "message": "Ghost words."},
        )
        assert missing_session_post.status_code == 404

        utterance_event = db_session.query(WorldEvent).filter(WorldEvent.session_id == "speaker-session", WorldEvent.event_type == "utterance").order_by(WorldEvent.id.desc()).first()
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

        utterance_projection = db_session.query(WorldProjection).filter(WorldProjection.path == "locations.cafe.last_public_utterance").one_or_none()
        assert utterance_projection is not None
        assert utterance_projection.value == "Hello from the counter."

        speaker_projection = db_session.query(WorldProjection).filter(WorldProjection.path == "locations.cafe.last_public_speaker").one_or_none()
        assert speaker_projection is not None
        assert speaker_projection.value == "Levi"

        # The author stays identifiable to another authenticated resident after
        # the author goes home and their temporary city session is retired.
        db_session.add(SessionVars(session_id="reader-session", actor_id="actor-reader", vars={"location": "Cafe"}))
        db_session.commit()
        leave = client.post("/api/session/leave", json={"session_id": "speaker-session"})
        assert leave.status_code == 200
        retired_chat = client.get("/api/world/location/Cafe/chat", params={"session_id": "reader-session"}).json()["messages"][-1]
        assert retired_chat["actor_id"] == "actor-speaker"
        assert retired_chat["session_id"] == "speaker-session"

    def test_player_dm_stays_private_and_does_not_touch_public_ledger(self, client, db_session):
        response = client.post(
            "/api/world/dm",
            json={
                "to_agent": "test_resident",
                "from_name": "Levi",
                "body": "Private note.",
                "session_id": "ww-private-player",
            },
        )
        assert response.status_code == 200

        dm = db_session.query(DirectMessage).order_by(DirectMessage.id.desc()).first()
        assert dm is not None
        assert dm.to_name == "test_resident"
        assert dm.from_name == "Levi"
        assert dm.from_session_id == "ww-private-player"

        assert db_session.query(WorldEvent).count() == 0
        assert db_session.query(WorldFact).count() == 0
        assert db_session.query(WorldProjection).count() == 0

    def test_agent_dm_reply_stays_private_and_does_not_touch_public_ledger(self, client, db_session):
        response = client.post(
            "/api/world/dm/reply",
            json={
                "from_agent": "test_resident",
                "to_session_id": "ww-private-player",
                "body": "Private reply.",
            },
        )
        assert response.status_code == 200

        dm = db_session.query(DirectMessage).order_by(DirectMessage.id.desc()).first()
        assert dm is not None
        assert dm.to_name == "ww-private-player"
        assert dm.from_name == "Test_resident"

        assert db_session.query(WorldEvent).count() == 0
        assert db_session.query(WorldFact).count() == 0
        assert db_session.query(WorldProjection).count() == 0

    def test_player_dm_threads_include_sent_and_received_messages(self, client, db_session):
        db_session.add_all(
            [
                DirectMessage(
                    from_name="Levi",
                    from_session_id="ww-private-player",
                    to_name="test_resident",
                    body="Meet me in Chinatown after close.",
                ),
                DirectMessage(
                    from_name="Test Resident",
                    from_session_id=None,
                    to_name="ww-private-player",
                    body="I'll come if the stall is quiet enough to leave.",
                ),
            ]
        )
        db_session.commit()

        response = client.get("/api/world/dm/my-threads/ww-private-player")
        assert response.status_code == 200
        payload = response.json()
        assert payload["count"] == 1
        thread = payload["threads"][0]
        assert thread["counterpart"] == "Test Resident"
        assert len(thread["messages"]) == 2
        assert thread["messages"][0]["direction"] == "outbound"
        assert thread["messages"][1]["direction"] == "inbound"

    def test_player_dm_can_target_another_player_session(self, client, db_session):
        db_session.add(
            SessionVars(
                session_id="ww-friend",
                vars={"player_role": "Darnell — friend", "location": "Chinatown"},
            )
        )
        db_session.commit()

        response = client.post(
            "/api/world/dm",
            json={
                "recipient": "ww-friend",
                "recipient_type": "player",
                "from_name": "Levi",
                "body": "Meet me by the tea house.",
                "session_id": "ww-private-player",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["recipient_type"] == "player"
        assert payload["recipient_key"] == "ww-friend"

        dm = db_session.query(DirectMessage).order_by(DirectMessage.id.desc()).first()
        assert dm is not None
        assert dm.to_name == "ww-friend"
        assert dm.from_name == "Levi"
        assert dm.from_session_id == "ww-private-player"

    def test_player_dm_threads_label_human_counterpart_from_session_vars(self, client, db_session):
        db_session.add(
            SessionVars(
                session_id="ww-friend",
                vars={"player_role": "Darnell — friend", "location": "Chinatown"},
            )
        )
        db_session.add(
            DirectMessage(
                from_name="Levi",
                from_session_id="ww-private-player",
                to_name="ww-friend",
                body="Meet me by the tea house.",
            )
        )
        db_session.commit()

        response = client.get("/api/world/dm/my-threads/ww-private-player")
        assert response.status_code == 200
        payload = response.json()
        assert payload["count"] == 1
        assert payload["threads"][0]["counterpart"] == "Darnell"

    def test_player_dm_thread_mark_read_marks_matching_inbound_messages(self, client, db_session):
        inbound_one = DirectMessage(
            from_name="Test Resident",
            from_session_id=None,
            to_name="ww-private-player",
            body="First note.",
        )
        inbound_two = DirectMessage(
            from_name="test_resident",
            from_session_id=None,
            to_name="ww-private-player",
            body="Second note.",
        )
        other = DirectMessage(
            from_name="Test Resident Two",
            from_session_id=None,
            to_name="ww-private-player",
            body="Elsewhere.",
        )
        db_session.add_all([inbound_one, inbound_two, other])
        db_session.commit()

        response = client.post("/api/world/dm/my-threads/ww-private-player/read/test_resident")
        assert response.status_code == 200
        payload = response.json()
        assert payload["marked_read"] == 2

        refreshed = db_session.query(DirectMessage).order_by(DirectMessage.id).all()
        assert refreshed[0].read_at is not None
        assert refreshed[1].read_at is not None
        assert refreshed[2].read_at is None


class TestPublicMapContext:
    def test_sessionless_context_alias_matches_session_path(self, client):
        aliased = client.get("/api/world/map/context", params={"location": "Clement Street"})
        legacy = client.get("/api/world/map/any-session/context", params={"location": "Clement Street"})
        assert aliased.status_code == 200
        assert legacy.status_code == 200
        assert aliased.json() == legacy.json()
        assert aliased.json()["location"] == "Clement Street"

    def test_context_alias_requires_location(self, client):
        response = client.get("/api/world/map/context")
        assert response.status_code == 422
