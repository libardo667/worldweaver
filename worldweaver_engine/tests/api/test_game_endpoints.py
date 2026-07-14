"""Integration tests for core game API endpoints."""

from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from src.api.game import _state_managers
from src.models import ResidentIdentityGrowth, SessionVars, WorldEvent


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

    def test_session_bootstrap_persists_resident_actor_id(self, seeded_client, db_session):
        session_id = "resident-bootstrap-session"
        actor_id = "resident-actor-123"
        world_id = seeded_client.get("/api/world/id").json()["world_id"]

        response = seeded_client.post(
            "/api/session/bootstrap",
            json={
                "session_id": session_id,
                "actor_id": actor_id,
                "world_theme": "quiet harbor",
                "player_role": "Test Resident",
                "bootstrap_source": "worldweaver-agent",
                "world_id": world_id,
            },
        )
        assert response.status_code == 200

        sv = db_session.get(SessionVars, session_id)
        assert sv is not None
        assert sv.actor_id == actor_id
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

    def test_identity_growth_round_trip_uses_actor_scoped_row(self, seeded_client, db_session):
        session_id = "resident-growth-session"
        actor_id = "resident-growth-actor"
        world_id = seeded_client.get("/api/world/id").json()["world_id"]

        response = seeded_client.post(
            "/api/session/bootstrap",
            json={
                "session_id": session_id,
                "actor_id": actor_id,
                "world_theme": "quiet harbor",
                "player_role": "Test Resident",
                "bootstrap_source": "worldweaver-agent",
                "world_id": world_id,
            },
        )
        assert response.status_code == 200

        patch_response = seeded_client.post(
            f"/api/state/{session_id}/identity-growth",
            json={
                "growth_text": "Steadier under pressure.",
                "growth_metadata": {"promoted_at": "2026-03-18T12:00:00+00:00"},
                "note_records": [{"ts": "2026-03-18T04:00:00+00:00", "note": "I kept my footing."}],
                "growth_proposals": [
                    {
                        "proposal_key": "follow_through:positive",
                        "dimension": "follow_through",
                        "summary": "Shows a recurring pattern of carrying commitments through.",
                        "status": "proposed",
                    }
                ],
            },
        )
        assert patch_response.status_code == 200
        payload = patch_response.json()
        assert payload["actor_id"] == actor_id
        assert payload["growth_text"] == "Steadier under pressure."
        assert payload["growth_metadata"]["promoted_at"] == "2026-03-18T12:00:00+00:00"
        assert payload["note_records"][0]["note"] == "I kept my footing."
        assert payload["growth_proposals"][0]["proposal_key"] == "follow_through:positive"

        fetch_response = seeded_client.get(f"/api/state/{session_id}/identity-growth")
        assert fetch_response.status_code == 200
        fetched = fetch_response.json()
        assert fetched["actor_id"] == actor_id
        assert fetched["growth_text"] == "Steadier under pressure."
        assert fetched["growth_proposals"][0]["dimension"] == "follow_through"

        row = db_session.get(ResidentIdentityGrowth, actor_id)
        assert row is not None
        assert row.growth_text == "Steadier under pressure."
        assert row.growth_metadata["promoted_at"] == "2026-03-18T12:00:00+00:00"
        assert row.note_records[0]["note"] == "I kept my footing."
        assert row.growth_proposals[0]["proposal_key"] == "follow_through:positive"

    def test_session_bootstrap_prunes_stale_duplicate_agent_sessions(self, seeded_client, db_session):
        world_id = seeded_client.get("/api/world/id").json()["world_id"]
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
                "world_id": world_id,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["bootstrap_diagnostics"]["duplicate_agent_sessions_pruned"] == 1

        assert db_session.get(SessionVars, stale_session_id) is None
        assert db_session.get(SessionVars, fresh_session_id) is not None
        assert db_session.query(WorldEvent).filter(WorldEvent.session_id == stale_session_id).count() == 0

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
