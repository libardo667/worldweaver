"""Integration tests for core game API endpoints."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from sqlalchemy import text
from src.api.game import _state_managers
from src.models import Storylet


class TestGameEndpoints:

    def test_next_returns_storylet(self, seeded_client):
        resp = seeded_client.post("/api/next", json={"session_id": "t1", "vars": {}})
        assert resp.status_code == 200
        data = resp.json()
        assert "text" in data and "choices" in data and "vars" in data

    def test_next_returns_valid_choices(self, seeded_client):
        for c in seeded_client.post("/api/next", json={"session_id": "t2", "vars": {}}).json()["choices"]:
            assert "label" in c and "set" in c

    def test_next_persists_vars_across_calls(self, seeded_client):
        sid = "t3-persist"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {"gold": 50}})
        assert seeded_client.post("/api/next", json={"session_id": sid, "vars": {}}).json()["vars"]["gold"] == 50

    def test_next_applies_client_vars(self, seeded_client):
        assert seeded_client.post("/api/next", json={"session_id": "t4", "vars": {"gold": 100}}).json()["vars"]["gold"] == 100

    def test_next_default_vars_applied(self, seeded_client):
        v = seeded_client.post("/api/next", json={"session_id": "t5", "vars": {}}).json()["vars"]
        assert v["name"] == "Adventurer" and v["danger"] == 0 and v["has_pickaxe"] is True

    def test_next_different_sessions_independent(self, seeded_client):
        seeded_client.post("/api/next", json={"session_id": "t6-a", "vars": {"quest": "dragon"}})
        assert "quest" not in seeded_client.post("/api/next", json={"session_id": "t6-b", "vars": {}}).json()["vars"]

    def test_state_summary_structure(self, seeded_client):
        seeded_client.post("/api/next", json={"session_id": "t7", "vars": {}})
        data = seeded_client.get("/api/state/t7").json()
        for key in ("session_id", "variables", "inventory", "relationships", "environment", "stats"):
            assert key in data

    def test_state_summary_reflects_changes(self, seeded_client):
        sid = "t8"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {"chapter": 3}})
        assert seeded_client.get(f"/api/state/{sid}").json()["variables"]["chapter"] == 3

    def test_state_unknown_session_returns_defaults(self, seeded_client):
        resp = seeded_client.get("/api/state/never-seen")
        assert resp.status_code == 200 and resp.json()["variables"]["name"] == "Adventurer"

    def test_create_relationship(self, seeded_client):
        sid = "t10-rel"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {}})
        resp = seeded_client.post(f"/api/state/{sid}/relationship", params={"entity_a": "player", "entity_b": "Greta"}, json={"trust": 50.0})
        assert resp.status_code == 200
        assert resp.json()["trust"] == 50.0 and resp.json()["interaction_count"] == 1

    def test_update_relationship_accumulates(self, seeded_client):
        sid = "t11-rel"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {}})
        seeded_client.post(f"/api/state/{sid}/relationship", params={"entity_a": "player", "entity_b": "Finn"}, json={"trust": 30.0})
        resp = seeded_client.post(f"/api/state/{sid}/relationship", params={"entity_a": "player", "entity_b": "Finn"}, json={"trust": 20.0})
        assert resp.json()["trust"] == 50.0

    def test_relationship_with_memory(self, seeded_client):
        sid = "t12-rel"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {}})
        resp = seeded_client.post(f"/api/state/{sid}/relationship", params={"entity_a": "player", "entity_b": "Elder", "memory": "Meal."}, json={"respect": 10.0})
        assert resp.json()["interaction_count"] == 1

    def test_add_item(self, seeded_client):
        sid = "t13-item"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {}})
        data = seeded_client.post(f"/api/state/{sid}/item", params={"item_id": "sword", "name": "Iron Sword"}).json()
        assert data["item_id"] == "sword" and data["quantity"] == 1 and data["condition"] == "good"

    def test_add_item_with_properties(self, seeded_client):
        sid = "t14-item"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {}})
        assert "use" in seeded_client.post(f"/api/state/{sid}/item", params={"item_id": "potion", "name": "Health Potion"}, json={"consumable": True}).json()["available_actions"]

    def test_add_item_increases_quantity(self, seeded_client):
        sid = "t15-item"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {}})
        seeded_client.post(f"/api/state/{sid}/item", params={"item_id": "arrow", "name": "Arrow", "quantity": 10})
        assert seeded_client.post(f"/api/state/{sid}/item", params={"item_id": "arrow", "name": "Arrow", "quantity": 5}).json()["quantity"] == 15

    def test_add_item_default_quantity(self, seeded_client):
        sid = "t16-item"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {}})
        assert seeded_client.post(f"/api/state/{sid}/item", params={"item_id": "gem", "name": "Ruby"}).json()["quantity"] == 1

    def test_update_environment(self, seeded_client):
        sid = "t17-env"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {}})
        resp = seeded_client.post(f"/api/state/{sid}/environment", json={"weather": "stormy"})
        assert resp.status_code == 200 and resp.json()["environment"]["weather"] == "stormy"

    def test_update_environment_danger(self, seeded_client):
        sid = "t18-env"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {}})
        assert seeded_client.post(f"/api/state/{sid}/environment", json={"danger_level": 7}).json()["environment"]["danger_level"] == 7

    def test_update_environment_mood_modifiers(self, seeded_client):
        sid = "t19-env"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {}})
        assert "tension" in seeded_client.post(f"/api/state/{sid}/environment", json={"weather": "stormy"}).json()["environment"]["mood_modifiers"]

    def test_cleanup_returns_success(self, seeded_client):
        data = seeded_client.post("/api/cleanup-sessions").json()
        assert data["success"] is True and "sessions_removed" in data

    def test_cleanup_preserves_fresh_sessions(self, seeded_client):
        sid = "t21-fresh"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {"alive": True}})
        seeded_client.post("/api/cleanup-sessions")
        assert seeded_client.post("/api/next", json={"session_id": sid, "vars": {}}).status_code == 200

    def test_cleanup_removes_stale_sessions(self, seeded_client, seeded_db):
        sid = "t22-stale"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {"old": True}})
        old_time = datetime.now(timezone.utc) - timedelta(hours=48)
        seeded_db.execute(text("UPDATE session_vars SET updated_at = :ts WHERE session_id = :sid"), {"ts": old_time.isoformat(), "sid": sid})
        seeded_db.commit()
        _state_managers.pop(sid, None)
        assert seeded_client.post("/api/cleanup-sessions").json()["sessions_removed"] >= 1

    def test_next_normalizes_choice_text_and_set_vars(self, client, db_session):
        storylet = Storylet(
            title="choice-normalization-regression",
            text_template="A prompt appears.",
            requires={},
            choices=[{"text": "Advance", "set_vars": {"gold": 9}}],
            weight=1.0,
        )
        db_session.add(storylet)
        db_session.commit()

        with patch("src.api.game.pick_storylet_enhanced", return_value=storylet):
            response = client.post(
                "/api/next",
                json={"session_id": "choice-normalization-session", "vars": {}},
            )
        assert response.status_code == 200
        assert response.json()["choices"] == [{"label": "Advance", "set": {"gold": 9}}]

    def test_spatial_navigation_accepts_legacy_json_requires(self, client, db_session):
        db_session.add(
            Storylet(
                title="json-requires-location-regression",
                text_template="Legacy storylet location.",
                requires='{"location":"start"}',
                choices=[{"label": "Continue", "set": {}}],
                weight=1.0,
                position={"x": 0, "y": 0},
            )
        )
        db_session.commit()

        session_id = "legacy-json-location"
        client.post("/api/next", json={"session_id": session_id, "vars": {}})
        response = client.get(f"/api/spatial/navigation/{session_id}")
        assert response.status_code == 200
