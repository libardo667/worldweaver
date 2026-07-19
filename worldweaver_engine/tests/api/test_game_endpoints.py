"""Integration tests for core game API endpoints."""

from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import text
from src.api.game import _state_managers
from src.models import ResidentIdentityGrowth, SessionVars, ShardTravelHandoff, WorldEvent


class TestGameEndpoints:
    def test_state_unknown_session_returns_defaults(self, seeded_client):
        resp = seeded_client.get("/api/state/never-seen")
        assert resp.status_code == 200 and resp.json()["variables"]["name"] == "Adventurer"

    def test_cleanup_returns_success(self, seeded_client):
        data = seeded_client.post("/api/cleanup-sessions").json()
        assert data["success"] is True and "sessions_removed" in data

    def test_cleanup_removes_stale_sessions(self, seeded_client, seeded_db):
        sid = "t22-stale"
        seeded_db.add(SessionVars(session_id=sid, vars={"old": True}))
        seeded_db.commit()
        old_time = (datetime.now(timezone.utc) - timedelta(hours=48)).replace(tzinfo=None)
        seeded_db.execute(
            text("UPDATE session_vars SET updated_at = :ts WHERE session_id = :sid"),
            {"ts": old_time, "sid": sid},
        )
        seeded_db.commit()
        _state_managers.pop(sid, None)
        response = seeded_client.post("/api/cleanup-sessions")
        assert response.status_code == 200
        assert response.json()["sessions_removed"] >= 1

    def test_dev_hard_reset_disabled_by_default(self, seeded_client, monkeypatch):
        monkeypatch.setattr("src.api.game.state.settings.enable_dev_reset", False)
        response = seeded_client.post("/api/dev/hard-reset")
        assert response.status_code == 404

    def test_session_bootstrap_persists_resident_actor_id(self, seeded_client, seeded_world_id, db_session):
        session_id = "resident-bootstrap-session"
        actor_id = "resident-actor-123"

        response = seeded_client.post(
            "/api/session/bootstrap",
            json={
                "session_id": session_id,
                "actor_id": actor_id,
                "world_theme": "quiet harbor",
                "player_role": "Test Resident",
                "bootstrap_source": "worldweaver-agent",
                "world_id": seeded_world_id,
            },
        )
        assert response.status_code == 200

        sv = db_session.get(SessionVars, session_id)
        assert sv is not None
        assert sv.actor_id == actor_id
        assert sv.vars["variables"]["name"] == "Test Resident"
        bootstrap_event = (
            db_session.query(WorldEvent)
            .filter(
                WorldEvent.session_id == session_id,
                WorldEvent.event_type == "session_bootstrap",
            )
            .one()
        )
        assert bootstrap_event.summary.startswith("Test Resident arrived at ")
        assert bootstrap_event.embedding is not None
        assert bootstrap_event.world_state_delta["__action_meta__"]["surface"] == "session_bootstrap"

    def test_identity_growth_endpoint_preserves_legacy_data_without_rewriting_identity(
        self,
        seeded_client,
        seeded_world_id,
        db_session,
    ):
        session_id = "resident-growth-session"
        actor_id = "resident-growth-actor"

        response = seeded_client.post(
            "/api/session/bootstrap",
            json={
                "session_id": session_id,
                "actor_id": actor_id,
                "world_theme": "quiet harbor",
                "player_role": "Test Resident",
                "bootstrap_source": "worldweaver-agent",
                "world_id": seeded_world_id,
            },
        )
        assert response.status_code == 200

        db_session.add(
            ResidentIdentityGrowth(
                actor_id=actor_id,
                growth_text="Steadier under pressure.",
                growth_metadata={"promoted_at": "2026-03-18T12:00:00+00:00"},
                note_records=[
                    {
                        "ts": "2026-03-18T04:00:00+00:00",
                        "note": "I kept my footing.",
                    }
                ],
                growth_proposals=[],
            )
        )
        db_session.commit()

        rejected_rewrite = seeded_client.post(
            f"/api/state/{session_id}/identity-growth",
            json={
                "growth_text": "The city says I am someone else.",
            },
        )
        assert rejected_rewrite.status_code == 409

        proposal_response = seeded_client.post(
            f"/api/state/{session_id}/identity-growth",
            json={
                "growth_proposals": [
                    {
                        "pulse_id": "legacy-pulse-1",
                        "body": "A proposal retained during an upgrade.",
                    }
                ],
            },
        )
        assert proposal_response.status_code == 200
        payload = proposal_response.json()
        assert payload["actor_id"] == actor_id
        assert payload["growth_text"] == "Steadier under pressure."
        assert payload["growth_metadata"]["promoted_at"] == "2026-03-18T12:00:00+00:00"
        assert payload["note_records"][0]["note"] == "I kept my footing."
        assert payload["growth_proposals"][0]["pulse_id"] == "legacy-pulse-1"
        assert payload["promotion"] == {"status": "resident_owned", "promoted": 0}

        fetch_response = seeded_client.get(f"/api/state/{session_id}/identity-growth")
        assert fetch_response.status_code == 200
        fetched = fetch_response.json()
        assert fetched["actor_id"] == actor_id
        assert fetched["growth_text"] == "Steadier under pressure."
        assert fetched["growth_proposals"][0]["body"] == "A proposal retained during an upgrade."

        row = db_session.get(ResidentIdentityGrowth, actor_id)
        assert row is not None
        assert row.growth_text == "Steadier under pressure."
        assert row.growth_metadata["promoted_at"] == "2026-03-18T12:00:00+00:00"
        assert row.note_records[0]["note"] == "I kept my footing."
        assert row.growth_proposals[0]["pulse_id"] == "legacy-pulse-1"

    def test_session_bootstrap_prunes_stale_duplicate_agent_sessions(self, seeded_client, seeded_world_id, db_session):
        stale_session_id = "test_resident-20260317-010101"
        fresh_session_id = "test_resident-20260318-020202"

        db_session.add(
            SessionVars(
                session_id=stale_session_id,
                actor_id="resident-sun-li-old",
                vars={"location": "Chinatown"},
                updated_at=datetime.now(timezone.utc) - timedelta(hours=6),
            )
        )
        db_session.add(
            WorldEvent(
                session_id=stale_session_id,
                event_type="session_bootstrap",
                summary="Test Resident arrived earlier.",
                world_state_delta={"location": "Chinatown"},
            )
        )
        db_session.commit()

        response = seeded_client.post(
            "/api/session/bootstrap",
            json={
                "session_id": fresh_session_id,
                "actor_id": "resident-sun-li-new",
                "world_theme": "quiet harbor",
                "player_role": "Test Resident",
                "bootstrap_source": "worldweaver-agent",
                "world_id": seeded_world_id,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["bootstrap_diagnostics"]["duplicate_agent_sessions_pruned"] == 1

        assert db_session.get(SessionVars, stale_session_id) is None
        assert db_session.get(SessionVars, fresh_session_id) is not None
        assert db_session.query(WorldEvent).filter(WorldEvent.session_id == stale_session_id).count() == 0

    def test_session_leave_retires_presence_without_erasing_history(
        self,
        seeded_client,
        seeded_world_id,
        db_session,
    ):
        session_id = "resident-leaving-city"
        bootstrap = seeded_client.post(
            "/api/session/bootstrap",
            json={
                "session_id": session_id,
                "actor_id": "resident-leaving-actor",
                "player_role": "Leaving Resident",
                "world_id": seeded_world_id,
            },
        )
        assert bootstrap.status_code == 200
        event_ids = [row.id for row in db_session.query(WorldEvent).filter(WorldEvent.session_id == session_id).all()]
        assert event_ids

        response = seeded_client.post(
            "/api/session/leave",
            json={"session_id": session_id},
        )

        assert response.status_code == 200
        assert response.json()["deleted"] == {"sessions": 1}
        assert db_session.get(SessionVars, session_id) is None
        assert [row.id for row in db_session.query(WorldEvent).filter(WorldEvent.session_id == session_id).all()] == event_ids

    def test_session_travel_departure_retires_presence_and_is_idempotent(
        self,
        seeded_client,
        seeded_world_id,
        db_session,
        monkeypatch,
    ):
        session_id = "resident-cross-node-departure"
        bootstrap = seeded_client.post(
            "/api/session/bootstrap",
            json={
                "session_id": session_id,
                "actor_id": "actor-cross-node-departure",
                "player_role": "Traveling Resident",
                "world_id": seeded_world_id,
                "entry_location": "Embarcadero",
            },
        )
        assert bootstrap.status_code == 200
        monkeypatch.setattr(
            "src.api.game.state.federation_discovery.get_travel_destinations",
            lambda: {
                "registry": {"reachable": True},
                "destinations": [
                    {
                        "route_id": "sf-pdx",
                        "departure_hub_id": "emeryville-sf-transfer",
                        "departure_hub": "Emeryville / San Francisco transfer",
                        "arrival_hub_id": "portland-union-station",
                        "arrival_hub": "Portland Union Station",
                        "nodes": [
                            {
                                "shard_id": "rose-city-coop-1",
                                "shard_url": "https://rose.example",
                                "client_url": "https://play.rose.example",
                                "status": "healthy",
                            }
                        ],
                    }
                ],
            },
        )
        starts = []
        departures = []
        monkeypatch.setattr(
            "src.api.game.state.federation_travel.start_federated_travel",
            lambda **kwargs: starts.append(kwargs) or {"travel": {"status": "departing"}, "idempotent": False},
        )
        monkeypatch.setattr(
            "src.api.game.state.federation_travel.confirm_federated_departure",
            lambda **kwargs: departures.append(kwargs) or {"travel": {"status": "traveling"}, "idempotent": False},
        )
        request = {
            "travel_id": "trip-local-001",
            "session_id": session_id,
            "route_id": "sf-pdx",
            "destination_shard": "rose-city-coop-1",
            "reason": "visit",
        }

        response = seeded_client.post("/api/session/travel/depart", json=request)
        repeated = seeded_client.post("/api/session/travel/depart", json=request)

        assert response.status_code == 200
        assert response.json()["handoff"]["status"] == "traveling"
        assert response.json()["handoff"]["destination_url"] == "https://rose.example"
        assert response.json()["handoff"]["destination_client_url"] == "https://play.rose.example"
        assert repeated.status_code == 200
        assert repeated.json()["idempotent"] is True
        assert len(starts) == 1
        assert starts[0]["departure_hub_id"] == "emeryville-sf-transfer"
        assert starts[0]["arrival_hub_id"] == "portland-union-station"
        assert len(departures) == 1
        assert db_session.get(SessionVars, session_id) is None
        handoff = db_session.get(ShardTravelHandoff, "trip-local-001")
        assert handoff is not None and handoff.status == "traveling"
        assert handoff.departure_hub_id == "emeryville-sf-transfer"
        assert handoff.arrival_hub_id == "portland-union-station"
        departure_events = db_session.query(WorldEvent).filter(WorldEvent.event_type == "cross_shard_departure").all()
        assert len(departure_events) == 1

    def test_session_travel_departure_can_recover_after_federation_confirmation_fails(
        self,
        seeded_client,
        seeded_world_id,
        db_session,
        monkeypatch,
    ):
        session_id = "resident-recovering-departure"
        bootstrap = seeded_client.post(
            "/api/session/bootstrap",
            json={
                "session_id": session_id,
                "actor_id": "actor-recovering-departure",
                "player_role": "Recovering Traveler",
                "world_id": seeded_world_id,
                "entry_location": "Embarcadero",
            },
        )
        assert bootstrap.status_code == 200
        monkeypatch.setattr(
            "src.api.game.state.federation_discovery.get_travel_destinations",
            lambda: {
                "registry": {"reachable": True},
                "destinations": [
                    {
                        "route_id": "sf-pdx",
                        "departure_hub_id": "emeryville-sf-transfer",
                        "departure_hub": "Emeryville / San Francisco transfer",
                        "arrival_hub_id": "portland-union-station",
                        "arrival_hub": "Portland Union Station",
                        "nodes": [{"shard_id": "rose-city-coop-1", "shard_url": "https://rose.example", "client_url": "https://play.rose.example", "status": "healthy"}],
                    }
                ],
            },
        )
        monkeypatch.setattr(
            "src.api.game.state.federation_travel.start_federated_travel",
            lambda **_kwargs: {"travel": {"status": "departing"}},
        )

        def unavailable_departure(**_kwargs):
            raise HTTPException(status_code=503, detail="federation unavailable")

        monkeypatch.setattr(
            "src.api.game.state.federation_travel.confirm_federated_departure",
            unavailable_departure,
        )
        response = seeded_client.post(
            "/api/session/travel/depart",
            json={
                "travel_id": "trip-local-002",
                "session_id": session_id,
                "route_id": "sf-pdx",
                "destination_shard": "rose-city-coop-1",
            },
        )

        assert response.status_code == 202
        assert response.json()["recoverable"] is True
        assert response.json()["handoff"]["status"] == "session_retired"
        assert db_session.get(SessionVars, session_id) is None

        monkeypatch.setattr(
            "src.api.game.state.federation_travel.confirm_federated_departure",
            lambda **_kwargs: {"travel": {"status": "traveling"}, "idempotent": True},
        )
        retry = seeded_client.post("/api/session/travel/trip-local-002/retry-departure")

        assert retry.status_code == 200
        assert retry.json()["handoff"]["status"] == "traveling"
        assert db_session.get(ShardTravelHandoff, "trip-local-002").last_error is None

    def test_session_travel_departure_requires_presence_at_the_route_hub(
        self,
        seeded_client,
        seeded_world_id,
        db_session,
        monkeypatch,
    ):
        session_id = "resident-away-from-departure"
        bootstrap = seeded_client.post(
            "/api/session/bootstrap",
            json={
                "session_id": session_id,
                "actor_id": "actor-away-from-departure",
                "player_role": "Misplaced Traveler",
                "world_id": seeded_world_id,
                "entry_location": "Chinatown",
            },
        )
        assert bootstrap.status_code == 200
        monkeypatch.setattr(
            "src.api.game.state.federation_discovery.get_travel_destinations",
            lambda: {
                "registry": {"reachable": True},
                "destinations": [
                    {
                        "route_id": "sf-pdx",
                        "departure_hub_id": "emeryville-sf-transfer",
                        "departure_hub": "Emeryville / San Francisco transfer",
                        "arrival_hub_id": "portland-union-station",
                        "arrival_hub": "Portland Union Station",
                        "nodes": [
                            {
                                "shard_id": "rose-city-coop-1",
                                "shard_url": "https://rose.example",
                                "client_url": "https://play.rose.example",
                                "status": "healthy",
                            }
                        ],
                    }
                ],
            },
        )

        response = seeded_client.post(
            "/api/session/travel/depart",
            json={
                "travel_id": "trip-wrong-place",
                "session_id": session_id,
                "route_id": "sf-pdx",
                "destination_shard": "rose-city-coop-1",
            },
        )

        assert response.status_code == 409
        assert "departs from Embarcadero" in response.json()["detail"]
        assert db_session.get(SessionVars, session_id) is not None
        assert db_session.get(ShardTravelHandoff, "trip-wrong-place") is None

    def test_session_travel_arrival_uses_destination_pack_and_preserves_actor_id(
        self,
        seeded_client,
        seeded_world_id,
        db_session,
        monkeypatch,
    ):
        trip = {
            "travel_id": "trip-arrival-001",
            "actor_id": "actor-arriving-resident",
            "actor_type": "agent",
            "name": "Arriving Resident",
            "source_shard": "rose-city-coop-1",
            "destination_shard": "bay-commons-1",
            "departure_hub_id": "portland-union-station",
            "departure_hub": "Portland Union Station",
            "arrival_hub_id": "emeryville-sf-transfer",
            "arrival_hub": "Emeryville / San Francisco transfer",
            "status": "traveling",
        }
        monkeypatch.setattr("src.api.game.state.current_shard_id", lambda: "bay-commons-1")
        monkeypatch.setattr(
            "src.api.game.state.federation_travel.get_federated_travel",
            lambda **_kwargs: {"travel": trip},
        )
        confirmations = []
        monkeypatch.setattr(
            "src.api.game.state.federation_travel.confirm_federated_arrival",
            lambda **kwargs: confirmations.append(kwargs) or {"travel": {"status": "arrived"}, "idempotent": False},
        )
        request = {"travel_id": trip["travel_id"], "session_id": "arriving-resident-session"}

        response = seeded_client.post("/api/session/travel/arrive", json=request)
        repeated = seeded_client.post("/api/session/travel/arrive", json=request)

        assert response.status_code == 200
        assert response.json()["handoff"]["status"] == "arrived"
        assert response.json()["handoff"]["arrival_hub_id"] == "emeryville-sf-transfer"
        assert response.json()["place"] == "Embarcadero"
        assert repeated.status_code == 200
        assert repeated.json()["idempotent"] is True
        assert confirmations == [{"travel_id": "trip-arrival-001", "destination_shard": "bay-commons-1"}]

        session = db_session.get(SessionVars, "arriving-resident-session")
        assert session is not None
        assert session.actor_id == "actor-arriving-resident"
        assert session.vars["variables"]["location"] == "Embarcadero"
        events = db_session.query(WorldEvent).filter(WorldEvent.session_id == "arriving-resident-session").all()
        assert [event.event_type for event in events].count("session_bootstrap") == 1
        assert [event.event_type for event in events].count("cross_shard_arrival") == 1

    def test_session_travel_arrival_retries_confirmation_without_rebooting(
        self,
        seeded_client,
        seeded_world_id,
        db_session,
        monkeypatch,
    ):
        trip = {
            "travel_id": "trip-arrival-002",
            "actor_id": "actor-recovering-arrival",
            "actor_type": "agent",
            "name": "Recovering Arrival",
            "source_shard": "rose-city-coop-1",
            "destination_shard": "bay-commons-1",
            "arrival_hub_id": "emeryville-sf-transfer",
            "arrival_hub": "Emeryville / San Francisco transfer",
            "status": "traveling",
        }
        monkeypatch.setattr("src.api.game.state.current_shard_id", lambda: "bay-commons-1")
        monkeypatch.setattr(
            "src.api.game.state.federation_travel.get_federated_travel",
            lambda **_kwargs: {"travel": trip},
        )

        def unavailable_arrival(**_kwargs):
            raise HTTPException(status_code=503, detail="federation unavailable")

        monkeypatch.setattr(
            "src.api.game.state.federation_travel.confirm_federated_arrival",
            unavailable_arrival,
        )
        response = seeded_client.post(
            "/api/session/travel/arrive",
            json={"travel_id": trip["travel_id"], "session_id": "recovering-arrival-session"},
        )

        assert response.status_code == 202
        assert response.json()["recoverable"] is True
        assert response.json()["handoff"]["status"] == "session_booted"
        assert db_session.get(SessionVars, "recovering-arrival-session") is not None

        monkeypatch.setattr(
            "src.api.game.state.federation_travel.confirm_federated_arrival",
            lambda **_kwargs: {"travel": {"status": "arrived"}, "idempotent": True},
        )
        retry = seeded_client.post("/api/session/travel/trip-arrival-002/retry-arrival")

        assert retry.status_code == 200
        assert retry.json()["handoff"]["status"] == "arrived"
        events = db_session.query(WorldEvent).filter(WorldEvent.session_id == "recovering-arrival-session").all()
        assert [event.event_type for event in events].count("session_bootstrap") == 1
        assert [event.event_type for event in events].count("cross_shard_arrival") == 1

    def test_session_travel_arrival_rejects_unknown_local_hub(
        self,
        seeded_client,
        seeded_world_id,
        db_session,
        monkeypatch,
    ):
        monkeypatch.setattr("src.api.game.state.current_shard_id", lambda: "bay-commons-1")
        monkeypatch.setattr(
            "src.api.game.state.federation_travel.get_federated_travel",
            lambda **_kwargs: {
                "travel": {
                    "travel_id": "trip-arrival-003",
                    "actor_id": "actor-misrouted-arrival",
                    "actor_type": "agent",
                    "name": "Misrouted Arrival",
                    "source_shard": "rose-city-coop-1",
                    "destination_shard": "bay-commons-1",
                    "arrival_hub_id": "not-in-this-city",
                    "status": "traveling",
                }
            },
        )

        response = seeded_client.post(
            "/api/session/travel/arrive",
            json={"travel_id": "trip-arrival-003", "session_id": "misrouted-arrival-session"},
        )

        assert response.status_code == 409
        assert "does not exist in city pack" in response.json()["detail"]
        assert db_session.get(SessionVars, "misrouted-arrival-session") is None
        assert db_session.get(ShardTravelHandoff, "trip-arrival-003") is None

    def test_prune_duplicate_agent_sessions_endpoint_keeps_freshest_agent(self, client, db_session):
        older = "maya_chen-20260317-172249"
        newer = "maya_chen-20260318-000120"
        now = datetime.now(timezone.utc)

        db_session.add_all(
            [
                SessionVars(
                    session_id=older,
                    actor_id="actor-maya-old",
                    vars={"location": "Arnada"},
                    updated_at=now - timedelta(hours=2),
                ),
                SessionVars(
                    session_id=newer,
                    actor_id="actor-maya-new",
                    vars={"location": "Carter Park"},
                    updated_at=now - timedelta(minutes=2),
                ),
                WorldEvent(
                    session_id=older,
                    event_type="session_bootstrap",
                    summary="Maya Chen arrived in Arnada.",
                    world_state_delta={"location": "Arnada"},
                ),
            ]
        )
        db_session.commit()

        response = client.post("/api/session/prune-duplicate-agents", json={"display_name": "Maya Chen"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["pruned_count"] == 1
        assert payload["kept"][0]["session_id"] == newer
        assert payload["pruned"][0]["session_id"] == older

        assert db_session.get(SessionVars, older) is None
        assert db_session.get(SessionVars, newer) is not None
        assert db_session.query(WorldEvent).filter(WorldEvent.session_id == older).count() == 0

    # ── Major 109: turn_source / pipeline_mode diagnostics ──────────────────
