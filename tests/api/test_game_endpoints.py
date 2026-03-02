"""Integration tests for core game API endpoints."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from sqlalchemy import text
from src.api.game import _state_managers
from src.models import Storylet
from src.services.command_interpreter import ActionResult


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

        with patch("src.api.game.story.pick_storylet_enhanced", return_value=storylet):
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

    def test_spatial_navigation_returns_ranked_leads_with_direction_bias(self, client, db_session):
        db_session.add_all(
            [
                Storylet(
                    title="dual-layer-start",
                    text_template="You stand at the crossroads.",
                    requires={"location": "start"},
                    choices=[{"label": "Wait", "set": {}}],
                    weight=1.0,
                    position={"x": 0, "y": 0},
                    embedding=[1.0, 0.0, 0.0],
                ),
                Storylet(
                    title="dual-layer-north",
                    text_template="Cold wind spills from the northern road.",
                    requires={},
                    choices=[{"label": "Continue", "set": {}}],
                    weight=1.0,
                    position={"x": 0, "y": -1},
                    embedding=[0.8, 0.0, 0.0],
                ),
                Storylet(
                    title="dual-layer-east",
                    text_template="Sparks drift from a busy forge to the east.",
                    requires={},
                    choices=[{"label": "Continue", "set": {}}],
                    weight=1.0,
                    position={"x": 1, "y": 0},
                    embedding=[0.9, 0.0, 0.0],
                ),
            ]
        )
        db_session.commit()

        session_id = "dual-layer-nav"
        client.post("/api/next", json={"session_id": session_id, "vars": {}})
        with patch("src.services.semantic_selector.compute_player_context_vector", return_value=[1.0, 0.0, 0.0]):
            response = client.get(f"/api/spatial/navigation/{session_id}?direction=north")

        assert response.status_code == 200
        payload = response.json()
        assert payload["leads"]
        assert payload["leads"][0]["direction"] in {"north", "northwest", "northeast"}

    def test_spatial_move_accepts_semantic_goal_direction(self, client, db_session):
        db_session.add_all(
            [
                Storylet(
                    title="semantic-move-start",
                    text_template="You are in the square.",
                    requires={"location": "start"},
                    choices=[{"label": "Wait", "set": {}}],
                    weight=1.0,
                    position={"x": 0, "y": 0},
                ),
                Storylet(
                    title="semantic-move-east",
                    text_template="A forge glows hot.",
                    requires={},
                    choices=[{"label": "Continue", "set": {}}],
                    weight=1.0,
                    position={"x": 1, "y": 0},
                ),
                Storylet(
                    title="semantic-move-filler",
                    text_template="A quiet lane.",
                    requires={},
                    choices=[{"label": "Continue", "set": {}}],
                    weight=1.0,
                    position={"x": 0, "y": 1},
                ),
            ]
        )
        db_session.commit()

        session_id = "semantic-move-session"
        client.post("/api/next", json={"session_id": session_id, "vars": {}})
        with patch(
            "src.services.spatial_navigator.SpatialNavigator.get_semantic_goal_hint",
            return_value={"direction": "east", "hint": "The sound of hammers rings from the East."},
        ):
            response = client.post(
                f"/api/spatial/move/{session_id}",
                json={"direction": "toward blacksmith"},
            )

        assert response.status_code == 200
        assert "Moved east" in response.json()["result"]

    def test_next_runtime_adaptation_mentions_previous_freeform_action(self, seeded_client):
        session_id = "runtime-adapt-history"
        seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})

        mocked_action = ActionResult(
            narrative_text="You cheat the merchant and pocket extra coin.",
            state_deltas={},
            should_trigger_storylet=False,
            follow_up_choices=[],
            plausible=True,
        )
        with patch(
            "src.services.command_interpreter.interpret_action",
            return_value=mocked_action,
        ):
            seeded_client.post(
                "/api/action",
                json={"session_id": session_id, "action": "I cheat the merchant"},
            )

        response = seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})
        assert response.status_code == 200
        text = response.json()["text"].lower()
        assert "merchant" in text or "cheat" in text

    def test_next_runtime_adaptation_reflects_weather_and_danger(self, seeded_client):
        session_id = "runtime-adapt-weather"
        seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})
        seeded_client.post(
            f"/api/state/{session_id}/environment",
            json={"weather": "stormy", "danger_level": 8},
        )

        response = seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})
        assert response.status_code == 200
        text = response.json()["text"].lower()
        assert "stormy" in text
        assert "danger" in text or "tension" in text

    def test_next_runtime_adaptation_resolves_unbound_template_placeholders(self, client, db_session):
        storylet = Storylet(
            title="runtime-adapt-placeholder",
            text_template="You follow {unwritten_clue} through the fog.",
            requires={},
            choices=[{"label": "Continue", "set": {}}],
            weight=1.0,
        )
        db_session.add(storylet)
        db_session.commit()

        with patch("src.api.game.story.pick_storylet_enhanced", return_value=storylet):
            response = client.post(
                "/api/next",
                json={"session_id": "runtime-adapt-placeholder-session", "vars": {}},
            )
        assert response.status_code == 200
        text = response.json()["text"]
        assert "{" not in text
        assert "}" not in text

    def test_next_sparse_context_synthesizes_runtime_storylet(self, client, db_session, monkeypatch):
        monkeypatch.setattr(
            "src.services.storylet_selector.settings.enable_runtime_storylet_synthesis",
            True,
        )
        monkeypatch.setattr(
            "src.services.storylet_selector.settings.runtime_synthesis_min_eligible_storylets",
            5,
        )
        monkeypatch.setattr(
            "src.services.storylet_selector.settings.runtime_synthesis_max_per_session",
            3,
        )

        with patch("src.api.game.story.ensure_storylets", return_value=None), patch(
            "src.services.world_memory.get_world_history",
            return_value=[],
        ), patch(
            "src.services.world_memory.get_recent_graph_fact_summaries",
            return_value=["The old beacon is unstable."],
        ), patch(
            "src.services.semantic_selector.compute_player_context_vector",
            return_value=[1.0, 0.0, 0.0],
        ), patch(
            "src.services.llm_service.generate_runtime_storylet_candidates",
            return_value=[
                {
                    "title": "Runtime lane",
                    "text_template": "A synthesized lead appears at the gate.",
                    "requires": {"location": "start"},
                    "choices": [{"label": "Pursue it", "set": {}}],
                    "weight": 1.0,
                }
            ],
        ), patch(
            "src.services.embedding_service.embed_storylet_payload",
            return_value=[1.0, 0.0, 0.0],
        ):
            response = client.post(
                "/api/next",
                json={"session_id": "runtime-sparse-api", "vars": {}},
            )

        assert response.status_code == 200
        assert response.json()["text"] != "The tunnel is quiet. Nothing compelling meets the eye."
        runtime_count = (
            db_session.query(Storylet)
            .filter(Storylet.source == "runtime_synthesis")
            .count()
        )
        assert runtime_count >= 1

    def test_next_feature_flag_disables_runtime_synthesis_without_breaking_endpoint(
        self,
        client,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "src.services.storylet_selector.settings.enable_runtime_storylet_synthesis",
            False,
        )

        with patch("src.api.game.story.ensure_storylets", return_value=None):
            response = client.post(
                "/api/next",
                json={"session_id": "runtime-disabled-api", "vars": {}},
            )

        assert response.status_code == 200
        assert response.json()["text"] == "The tunnel is quiet. Nothing compelling meets the eye."
