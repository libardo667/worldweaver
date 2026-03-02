"""Integration tests for core game API endpoints.

Uses FastAPI TestClient against an isolated temp database. No external
dependencies (no OpenAI key) required.
"""

import os
import tempfile

# Point at a fresh temp DB before importing anything that touches the DB.
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DW_DB_PATH"] = _tmp_db.name

from datetime import datetime, timedelta, timezone  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from src.database import create_tables, SessionLocal  # noqa: E402
from src.models import SessionVars  # noqa: E402

# Ensure tables exist before the app or TestClient touch the DB.
create_tables()

from main import app  # noqa: E402
from src.api.game import _state_managers  # noqa: E402

client = TestClient(app)


class TestGameEndpoints:
    """Integration tests for the 6 game endpoint groups."""

    def setup_method(self):
        _state_managers.clear()

    # ------------------------------------------------------------------
    # Group 1: POST /api/next
    # ------------------------------------------------------------------

    def test_next_returns_storylet(self):
        resp = client.post("/api/next", json={"session_id": "t1", "vars": {}})
        assert resp.status_code == 200
        data = resp.json()
        assert "text" in data
        assert "choices" in data
        assert "vars" in data
        assert isinstance(data["text"], str)
        assert len(data["text"]) > 0

    def test_next_returns_valid_choices(self):
        resp = client.post("/api/next", json={"session_id": "t2", "vars": {}})
        data = resp.json()
        assert isinstance(data["choices"], list)
        for choice in data["choices"]:
            assert "label" in choice
            assert "set" in choice

    def test_next_persists_vars_across_calls(self):
        sid = "t3-persist"
        client.post("/api/next", json={"session_id": sid, "vars": {"gold": 50}})
        resp = client.post("/api/next", json={"session_id": sid, "vars": {}})
        assert resp.json()["vars"]["gold"] == 50

    def test_next_applies_client_vars(self):
        resp = client.post(
            "/api/next", json={"session_id": "t4-vars", "vars": {"gold": 100}}
        )
        assert resp.json()["vars"]["gold"] == 100

    def test_next_default_vars_applied(self):
        resp = client.post(
            "/api/next", json={"session_id": "t5-defaults", "vars": {}}
        )
        v = resp.json()["vars"]
        assert v["name"] == "Adventurer"
        assert v["danger"] == 0
        assert v["has_pickaxe"] is True

    def test_next_different_sessions_independent(self):
        client.post(
            "/api/next", json={"session_id": "t6-a", "vars": {"quest": "dragon"}}
        )
        resp_b = client.post(
            "/api/next", json={"session_id": "t6-b", "vars": {}}
        )
        assert "quest" not in resp_b.json()["vars"]

    # ------------------------------------------------------------------
    # Group 2: GET /api/state/{session_id}
    # ------------------------------------------------------------------

    def test_state_summary_structure(self):
        # Ensure session exists first.
        client.post("/api/next", json={"session_id": "t7-state", "vars": {}})
        resp = client.get("/api/state/t7-state")
        assert resp.status_code == 200
        data = resp.json()
        for key in ("session_id", "variables", "inventory", "relationships", "environment", "stats"):
            assert key in data, f"Missing key: {key}"

    def test_state_summary_reflects_changes(self):
        sid = "t8-reflect"
        client.post("/api/next", json={"session_id": sid, "vars": {"chapter": 3}})
        resp = client.get(f"/api/state/{sid}")
        assert resp.json()["variables"]["chapter"] == 3

    def test_state_unknown_session_returns_defaults(self):
        resp = client.get("/api/state/never-seen-before")
        assert resp.status_code == 200
        data = resp.json()
        assert data["variables"]["name"] == "Adventurer"

    # ------------------------------------------------------------------
    # Group 3: POST /api/state/{session_id}/relationship
    # ------------------------------------------------------------------

    def test_create_relationship(self):
        sid = "t10-rel"
        # Initialise session.
        client.post("/api/next", json={"session_id": sid, "vars": {}})
        resp = client.post(
            f"/api/state/{sid}/relationship",
            params={"entity_a": "player", "entity_b": "Greta"},
            json={"trust": 50.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["relationship"] == "player-Greta"
        assert data["trust"] == 50.0
        assert data["interaction_count"] == 1

    def test_update_relationship_accumulates(self):
        sid = "t11-rel-acc"
        client.post("/api/next", json={"session_id": sid, "vars": {}})
        client.post(
            f"/api/state/{sid}/relationship",
            params={"entity_a": "player", "entity_b": "Finn"},
            json={"trust": 30.0},
        )
        resp = client.post(
            f"/api/state/{sid}/relationship",
            params={"entity_a": "player", "entity_b": "Finn"},
            json={"trust": 20.0},
        )
        assert resp.json()["trust"] == 50.0

    def test_relationship_with_memory(self):
        sid = "t12-rel-mem"
        client.post("/api/next", json={"session_id": sid, "vars": {}})
        resp = client.post(
            f"/api/state/{sid}/relationship",
            params={
                "entity_a": "player",
                "entity_b": "Elder",
                "memory": "Shared a meal by the fire.",
            },
            json={"respect": 10.0},
        )
        assert resp.json()["interaction_count"] == 1

    # ------------------------------------------------------------------
    # Group 4: POST /api/state/{session_id}/item
    # ------------------------------------------------------------------

    def test_add_item(self):
        sid = "t13-item"
        client.post("/api/next", json={"session_id": sid, "vars": {}})
        resp = client.post(
            f"/api/state/{sid}/item",
            params={"item_id": "sword", "name": "Iron Sword"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["item_id"] == "sword"
        assert data["name"] == "Iron Sword"
        assert data["quantity"] == 1
        assert data["condition"] == "good"

    def test_add_item_with_properties(self):
        sid = "t14-item-prop"
        client.post("/api/next", json={"session_id": sid, "vars": {}})
        resp = client.post(
            f"/api/state/{sid}/item",
            params={"item_id": "potion", "name": "Health Potion"},
            json={"consumable": True},
        )
        data = resp.json()
        assert "use" in data["available_actions"]

    def test_add_item_increases_quantity(self):
        sid = "t15-item-qty"
        client.post("/api/next", json={"session_id": sid, "vars": {}})
        client.post(
            f"/api/state/{sid}/item",
            params={"item_id": "arrow", "name": "Arrow", "quantity": 10},
        )
        resp = client.post(
            f"/api/state/{sid}/item",
            params={"item_id": "arrow", "name": "Arrow", "quantity": 5},
        )
        assert resp.json()["quantity"] == 15

    def test_add_item_default_quantity(self):
        sid = "t16-item-default"
        client.post("/api/next", json={"session_id": sid, "vars": {}})
        resp = client.post(
            f"/api/state/{sid}/item",
            params={"item_id": "gem", "name": "Ruby"},
        )
        assert resp.json()["quantity"] == 1

    # ------------------------------------------------------------------
    # Group 5: POST /api/state/{session_id}/environment
    # ------------------------------------------------------------------

    def test_update_environment(self):
        sid = "t17-env"
        client.post("/api/next", json={"session_id": sid, "vars": {}})
        resp = client.post(
            f"/api/state/{sid}/environment", json={"weather": "stormy"}
        )
        assert resp.status_code == 200
        assert resp.json()["environment"]["weather"] == "stormy"

    def test_update_environment_danger(self):
        sid = "t18-env-danger"
        client.post("/api/next", json={"session_id": sid, "vars": {}})
        resp = client.post(
            f"/api/state/{sid}/environment", json={"danger_level": 7}
        )
        assert resp.json()["environment"]["danger_level"] == 7

    def test_update_environment_mood_modifiers(self):
        sid = "t19-env-mood"
        client.post("/api/next", json={"session_id": sid, "vars": {}})
        resp = client.post(
            f"/api/state/{sid}/environment", json={"weather": "stormy"}
        )
        mood = resp.json()["environment"]["mood_modifiers"]
        assert "tension" in mood

    # ------------------------------------------------------------------
    # Group 6: POST /api/cleanup-sessions
    # ------------------------------------------------------------------

    def test_cleanup_returns_success(self):
        resp = client.post("/api/cleanup-sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "sessions_removed" in data
        assert "cache_entries_removed" in data
        assert "message" in data

    def test_cleanup_preserves_fresh_sessions(self):
        sid = "t21-fresh"
        client.post("/api/next", json={"session_id": sid, "vars": {"alive": True}})
        client.post("/api/cleanup-sessions")
        # Session should still work after cleanup.
        resp = client.post("/api/next", json={"session_id": sid, "vars": {}})
        assert resp.status_code == 200

    def test_cleanup_removes_stale_sessions(self):
        sid = "t22-stale"
        # Create the session via the API so it gets saved.
        client.post("/api/next", json={"session_id": sid, "vars": {"old": True}})
        # Manually backdate updated_at to simulate a stale session.
        db = SessionLocal()
        try:
            old_time = datetime.now(timezone.utc) - timedelta(hours=48)
            db.execute(
                text("UPDATE session_vars SET updated_at = :ts WHERE session_id = :sid"),
                {"ts": old_time.isoformat(), "sid": sid},
            )
            db.commit()
        finally:
            db.close()
        # Evict from in-memory cache so cleanup can target the DB row.
        _state_managers.pop(sid, None)
        resp = client.post("/api/cleanup-sessions")
        data = resp.json()
        assert data["sessions_removed"] >= 1
