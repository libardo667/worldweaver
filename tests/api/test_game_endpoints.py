"""Integration tests for core game API endpoints."""

from datetime import datetime, timedelta, timezone
import json
from unittest.mock import AsyncMock, patch
from sqlalchemy import text
from src.api.game import _state_managers
from src.models import SessionVars, Storylet, WorldEvent, WorldProjection
from src.services.command_interpreter import ActionResult
from src.services import runtime_metrics


class TestGameEndpoints:

    def test_next_returns_storylet(self, seeded_client):
        resp = seeded_client.post("/api/next", json={"session_id": "t1", "vars": {}})
        assert resp.status_code == 200
        data = resp.json()
        assert "text" in data and "choices" in data and "vars" in data

    def test_next_includes_trace_id_header(self, seeded_client):
        resp = seeded_client.post("/api/next", json={"session_id": "t1-trace", "vars": {}})
        assert resp.status_code == 200
        assert resp.headers.get("X-WW-Trace-Id")

    def test_debug_metrics_endpoint_reports_next_and_action_aggregates(self, seeded_client):
        runtime_metrics.reset_metrics()
        session_id = "debug-metrics-session"
        seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})
        seeded_client.post(
            "/api/action",
            json={"session_id": session_id, "action": "inspect the scene"},
        )

        response = seeded_client.get("/api/debug/metrics")
        assert response.status_code == 200
        payload = response.json()
        assert payload["event"] == "runtime_metrics_snapshot"
        assert "/api/next" in payload["routes"]
        assert "/api/action" in payload["routes"]
        assert payload["routes"]["/api/next"]["requests"] >= 1
        assert payload["routes"]["/api/action"]["requests"] >= 1
        assert "api_key" not in json.dumps(payload).lower()

    def test_next_schedules_prefetch_without_breaking_response(self, seeded_client):
        with patch("src.api.game.story.schedule_frontier_prefetch", return_value=True) as mock_schedule:
            resp = seeded_client.post("/api/next", json={"session_id": "t1-prefetch", "vars": {}})

        assert resp.status_code == 200
        mock_schedule.assert_called_once()
        assert mock_schedule.call_args.args[0] == "t1-prefetch"

    def test_next_returns_valid_choices(self, seeded_client):
        for c in seeded_client.post("/api/next", json={"session_id": "t2", "vars": {}}).json()["choices"]:
            assert "label" in c and "set" in c

    def test_next_debug_scores_header_exposes_breakdown_without_body_changes(self, client, db_session):
        storylet = Storylet(
            title="debug-next-storylet",
            text_template="A deterministic scene.",
            requires={},
            choices=[{"label": "Continue", "set": {}}],
            weight=1.0,
            embedding=[1.0, 0.0, 0.0],
        )
        db_session.add(storylet)
        db_session.commit()

        def _pick_with_debug(_db, _state_manager, debug_selection=None):
            if isinstance(debug_selection, dict):
                debug_selection.update(
                    {
                        "selection_mode": "semantic_weighted",
                        "selected_storylet_id": int(storylet.id),
                        "selected_storylet_title": str(storylet.title),
                        "scored_candidates": [
                            {
                                "rank": 1,
                                "storylet_id": int(storylet.id),
                                "title": str(storylet.title),
                                "similarity": 1.0,
                                "floored_similarity": 1.0,
                                "weight": 1.0,
                                "spatial_modifier": 1.0,
                                "recency_multiplier": 1.0,
                                "is_recent": False,
                                "final_score": 1.0,
                                "floor_probability": 0.05,
                            }
                        ],
                        "top_score": 1.0,
                        "eligible_count": 1,
                        "embedded_count": 1,
                        "recent_storylet_ids": [],
                    }
                )
            return storylet

        with (
            patch("src.api.game.story.ensure_storylets", return_value=None),
            patch(
                "src.api.game.story.pick_storylet_enhanced",
                side_effect=_pick_with_debug,
            ),
            patch(
                "src.api.game.story.adapt_storylet_to_context",
                return_value={
                    "text": "A deterministic scene.",
                    "choices": [{"label": "Continue", "set": {}}],
                },
            ),
        ):
            debug_resp = client.post(
                "/api/next?debug_scores=true",
                json={"session_id": "next-debug-a", "vars": {}},
            )
            plain_resp = client.post(
                "/api/next",
                json={"session_id": "next-debug-b", "vars": {}},
            )

        assert debug_resp.status_code == 200
        assert plain_resp.status_code == 200
        assert debug_resp.json() == plain_resp.json()
        assert "X-WorldWeaver-Score-Debug" in debug_resp.headers
        debug_payload = json.loads(debug_resp.headers["X-WorldWeaver-Score-Debug"])
        assert debug_payload["selection_mode"] == "semantic_weighted"
        assert debug_payload["scored_candidates"][0]["title"] == "debug-next-storylet"
        assert "X-WorldWeaver-Score-Debug" not in plain_resp.headers

    def test_next_passes_scene_goal_and_motif_context_to_adaptation(self, client, db_session):
        storylet = Storylet(
            title="context-next-storylet",
            text_template="A deterministic context scene.",
            requires={},
            choices=[{"label": "Continue", "set": {}}],
            weight=1.0,
        )
        db_session.add(storylet)
        db_session.commit()

        captured_context = {}

        def _adapt(_storylet, context):
            captured_context.update(context)
            return {
                "text": "A deterministic context scene.",
                "choices": [{"label": "Continue", "set": {}}],
            }

        with (
            patch("src.api.game.story.ensure_storylets", return_value=None),
            patch("src.api.game.story.pick_storylet_enhanced", return_value=storylet),
            patch("src.api.game.story.adapt_storylet_to_context", side_effect=_adapt),
        ):
            response = client.post(
                "/api/next",
                json={"session_id": "next-context-a", "vars": {}},
            )

        assert response.status_code == 200
        assert isinstance(captured_context.get("scene_card_now"), dict)
        assert isinstance(captured_context.get("goal_lens"), dict)
        assert isinstance(captured_context.get("motifs_recent"), list)
        assert isinstance(captured_context.get("sensory_palette"), dict)

    def test_next_passes_selected_and_contrast_projection_stubs_to_adaptation(self, client, db_session):
        from src.services.prefetch_service import set_prefetched_stubs_for_session

        storylet = Storylet(
            title="projection-seed-storylet",
            text_template="Projection seeded scene.",
            requires={},
            choices=[{"label": "Continue", "set": {}}],
            weight=1.0,
        )
        contrast_storylet = Storylet(
            title="projection-contrast-storylet",
            text_template="Contrast seeded scene.",
            requires={},
            choices=[{"label": "Continue", "set": {}}],
            weight=1.0,
        )
        db_session.add(storylet)
        db_session.add(contrast_storylet)
        db_session.commit()

        session_id = "next-projection-context"
        set_prefetched_stubs_for_session(
            session_id,
            stubs=[
                {
                    "storylet_id": int(storylet.id),
                    "title": str(storylet.title),
                    "premise": "A prepared lead from the eastern bridge.",
                    "requires": {},
                    "choices": [],
                    "location": "east_bridge",
                    "projection_depth": 2,
                    "semantic_score": 0.85,
                },
                {
                    "storylet_id": int(contrast_storylet.id),
                    "title": str(contrast_storylet.title),
                    "premise": "A competing lead from the flooded tunnel.",
                    "requires": {},
                    "choices": [],
                    "location": "flooded_tunnel",
                    "projection_depth": 1,
                    "semantic_score": 0.61,
                },
            ],
            context_summary={"source": "test"},
        )

        captured_context = {}

        def _adapt(_storylet, context):
            captured_context.update(context)
            return {
                "text": "Projection seeded scene.",
                "choices": [{"label": "Continue", "set": {}}],
            }

        with (
            patch("src.services.turn_service.settings.enable_v3_projection_seeded_narration", True),
            patch("src.api.game.story.ensure_storylets", return_value=None),
            patch("src.api.game.story.pick_storylet_enhanced", return_value=storylet),
            patch("src.api.game.story.adapt_storylet_to_context", side_effect=_adapt),
        ):
            response = client.post(
                "/api/next",
                json={"session_id": session_id, "vars": {}},
            )

        assert response.status_code == 200
        selected_stub = captured_context.get("selected_projection_stub")
        contrast_stub = captured_context.get("contrast_projection_stub")
        assert isinstance(selected_stub, dict)
        assert selected_stub.get("storylet_id") == int(storylet.id)
        assert isinstance(contrast_stub, dict)
        assert contrast_stub.get("storylet_id") == int(contrast_storylet.id)

    def test_next_emits_player_hint_channel_and_clarity_without_projection_tree_leak(self, client, db_session):
        from src.services.prefetch_service import set_prefetched_stubs_for_session

        storylet = Storylet(
            title="projection-hint-storylet",
            text_template="Projection hint scene.",
            requires={},
            choices=[{"label": "Continue", "set": {}}],
            weight=1.0,
        )
        db_session.add(storylet)
        db_session.commit()

        session_id = "next-projection-hint"
        set_prefetched_stubs_for_session(
            session_id,
            stubs=[
                {
                    "storylet_id": int(storylet.id),
                    "title": str(storylet.title),
                    "premise": "A prepared path bends toward the signal tower.",
                    "requires": {},
                    "choices": [],
                    "location": "signal_tower",
                    "projection_depth": 2,
                }
            ],
            context_summary={"source": "test"},
        )

        with (
            patch("src.services.turn_service.settings.enable_v3_projection_seeded_narration", True),
            patch("src.services.turn_service.settings.enable_v3_player_hint_channel", True),
            patch("src.api.game.story.ensure_storylets", return_value=None),
            patch("src.api.game.story.pick_storylet_enhanced", return_value=storylet),
            patch(
                "src.api.game.story.adapt_storylet_to_context",
                return_value={
                    "text": "Projection hint scene.",
                    "choices": [{"label": "Continue", "set": {}}],
                },
            ),
            patch("src.api.game.story.schedule_prefetch_async_best_effort", new=AsyncMock()),
        ):
            response = client.post(
                "/api/next",
                json={"session_id": session_id, "vars": {}},
            )

        assert response.status_code == 200
        vars_payload = response.json()["vars"]
        diag = vars_payload.get("_ww_diag", {})
        hint = vars_payload.get("_ww_hint", {})
        top_level_diag = response.json().get("diagnostics", {})

        assert diag.get("scene_clarity_level") == "prepared"
        assert diag.get("player_hint_clarity_level") == "prepared"
        assert diag.get("clarity_level") == "prepared"
        assert diag.get("selection_mode") == "none"
        assert diag.get("active_storylets_count") == 0
        assert diag.get("eligible_storylets_count") == 0
        assert diag.get("fallback_reason") == "none"
        assert top_level_diag == diag
        assert hint.get("clarity") == "prepared"
        assert isinstance(hint.get("hint"), str)
        assert "storylet_id" not in hint
        assert all("projection_tree" not in str(key) for key in hint.keys())

    def test_next_persists_vars_across_calls(self, seeded_client):
        sid = "t3-persist"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {"gold": 50}})
        assert seeded_client.post("/api/next", json={"session_id": sid, "vars": {}}).json()["vars"]["gold"] == 50

    def test_next_applies_client_vars(self, seeded_client):
        assert seeded_client.post("/api/next", json={"session_id": "t4", "vars": {"gold": 100}}).json()["vars"]["gold"] == 100

    def test_next_routes_client_vars_through_reducer_policy(self, seeded_client):
        payload = {
            "session_id": "t4-reducer-policy",
            "vars": {
                "gold": 17,
                "session_id": "hacked",
                "_intrusive": True,
                "danger": 6,
            },
        }
        response = seeded_client.post("/api/next", json=payload)
        assert response.status_code == 200
        vars_payload = response.json()["vars"]
        assert vars_payload["gold"] == 17
        assert vars_payload.get("session_id") is None
        assert vars_payload.get("_intrusive") is None
        assert vars_payload["danger_level"] >= 6

    def test_next_default_vars_applied(self, seeded_client):
        v = seeded_client.post("/api/next", json={"session_id": "t5", "vars": {}}).json()["vars"]
        assert v["name"] == "Adventurer" and v["danger"] == 0
        assert "has_pickaxe" not in v

    def test_next_different_sessions_independent(self, seeded_client):
        seeded_client.post("/api/next", json={"session_id": "t6-a", "vars": {"quest": "dragon"}})
        assert "quest" not in seeded_client.post("/api/next", json={"session_id": "t6-b", "vars": {}}).json()["vars"]

    def test_state_summary_structure(self, seeded_client):
        seeded_client.post("/api/next", json={"session_id": "t7", "vars": {}})
        data = seeded_client.get("/api/state/t7").json()
        for key in (
            "session_id",
            "variables",
            "inventory",
            "relationships",
            "goal",
            "arc_timeline",
            "environment",
            "stats",
        ):
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

    def test_set_goal_state(self, seeded_client):
        sid = "t20-goal"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {}})
        resp = seeded_client.post(
            f"/api/state/{sid}/goal",
            json={
                "primary_goal": "Deliver medicine to ridge village",
                "subgoals": ["Cross the river"],
                "urgency": 0.7,
                "complication": 0.2,
            },
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["goal"]["primary_goal"] == "Deliver medicine to ridge village"
        assert payload["goal"]["subgoals"] == ["Cross the river"]

    def test_next_backfills_primary_goal_after_turn_one_and_is_idempotent(self, seeded_client):
        sid = "t20-goal-backfill"

        first = seeded_client.post(
            "/api/next",
            json={"session_id": sid, "vars": {"player_role": "exiled cartographer"}},
        )
        assert first.status_code == 200
        state_after_first = seeded_client.get(f"/api/state/{sid}").json()
        assert state_after_first["goal"]["primary_goal"] == ""

        second = seeded_client.post("/api/next", json={"session_id": sid, "vars": {}})
        assert second.status_code == 200
        state_after_second = seeded_client.get(f"/api/state/{sid}").json()
        backfilled_goal = state_after_second["goal"]["primary_goal"]
        assert backfilled_goal
        assert "exiled cartographer" in backfilled_goal.lower()

        third = seeded_client.post("/api/next", json={"session_id": sid, "vars": {}})
        assert third.status_code == 200
        state_after_third = seeded_client.get(f"/api/state/{sid}").json()
        assert state_after_third["goal"]["primary_goal"] == backfilled_goal

        backfill_milestones_second = [item for item in state_after_second["arc_timeline"] if item.get("source") == "system_goal_backfill"]
        backfill_milestones_third = [item for item in state_after_third["arc_timeline"] if item.get("source") == "system_goal_backfill"]
        assert len(backfill_milestones_second) == 1
        assert len(backfill_milestones_third) == 1

    def test_next_goal_backfill_does_not_override_explicit_goal(self, seeded_client):
        sid = "t20-goal-backfill-explicit"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {"player_role": "pilot"}})
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {}})

        explicit_goal = "Recover the archive ledger"
        update_resp = seeded_client.post(
            f"/api/state/{sid}/goal",
            json={"primary_goal": explicit_goal},
        )
        assert update_resp.status_code == 200

        next_resp = seeded_client.post("/api/next", json={"session_id": sid, "vars": {}})
        assert next_resp.status_code == 200
        state_payload = seeded_client.get(f"/api/state/{sid}").json()
        assert state_payload["goal"]["primary_goal"] == explicit_goal

    def test_add_goal_milestone_updates_arc_timeline(self, seeded_client):
        sid = "t20-goal-milestone"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {}})
        seeded_client.post(
            f"/api/state/{sid}/goal",
            json={"primary_goal": "Find the courier"},
        )
        resp = seeded_client.post(
            f"/api/state/{sid}/goal/milestone",
            json={
                "title": "The trail went cold at the docks",
                "status": "complicated",
                "complication_delta": 0.3,
            },
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["arc_timeline"]
        assert payload["arc_timeline"][0]["status"] == "complicated"
        assert payload["goal"]["complication"] >= 0.3

    def test_next_applies_storylet_fire_effects_and_records_metadata(self, client, db_session):
        sid = "t20-storylet-effects-fire"
        storylet = Storylet(
            title="storylet-effects-fire",
            text_template="A pressure wave rolls through the hall.",
            requires={},
            choices=[{"label": "Continue", "set": {}}],
            effects=[
                {"op": "set", "when": "on_fire", "key": "focus", "value": "steady"},
                {"op": "increment", "when": "on_fire", "key": "gold", "amount": 2},
                {
                    "op": "append_fact",
                    "when": "on_fire",
                    "subject": "hall",
                    "predicate": "status",
                    "value": "stabilized",
                    "confidence": 0.8,
                },
            ],
            weight=1.0,
        )
        db_session.add(storylet)
        db_session.commit()

        with (
            patch("src.api.game.story.ensure_storylets", return_value=None),
            patch(
                "src.api.game.story.pick_storylet_enhanced",
                return_value=storylet,
            ),
            patch(
                "src.api.game.story.adapt_storylet_to_context",
                return_value={
                    "text": "A pressure wave rolls through the hall.",
                    "choices": [{"label": "Continue", "set": {}}],
                },
            ),
        ):
            response = client.post(
                "/api/next",
                json={"session_id": sid, "vars": {}},
            )

        assert response.status_code == 200
        vars_payload = response.json()["vars"]
        assert vars_payload["focus"] == "steady"
        assert vars_payload["gold"] == 2

        history = client.get(
            "/api/world/history",
            params={"session_id": sid, "event_type": "storylet_fired", "limit": 5},
        )
        assert history.status_code == 200
        events = history.json()["events"]
        assert events
        latest = events[0]
        assert latest["world_state_delta"]["focus"] == "steady"
        assert latest["world_state_delta"]["gold"] == 2
        metadata = latest["world_state_delta"].get("__action_meta__", {})
        assert metadata["storylet_effects_trigger"] == "on_fire"
        assert len(metadata["applied_storylet_effects"]) == 3
        assert "storylet_effects_receipt" in metadata

    def test_next_applies_pending_choice_commit_storylet_effects_once(self, client, db_session):
        sid = "t20-storylet-effects-choice-commit"
        storylet_with_choice_effects = Storylet(
            title="storylet-effects-choice",
            text_template="A binding offer hangs in the air.",
            requires={},
            choices=[{"label": "Take the pact", "set": {"intent": "pact"}}],
            effects=[
                {"op": "set", "when": "on_choice_commit", "key": "focus", "value": "committed"},
                {"op": "increment", "when": "on_choice_commit", "key": "gold", "amount": 3},
            ],
            weight=1.0,
        )
        fallback_storylet = Storylet(
            title="storylet-effects-choice-fallback",
            text_template="The corridor waits.",
            requires={},
            choices=[{"label": "Continue", "set": {}}],
            effects=[],
            weight=1.0,
        )
        db_session.add(storylet_with_choice_effects)
        db_session.add(fallback_storylet)
        db_session.commit()

        picks = [storylet_with_choice_effects, fallback_storylet, fallback_storylet]

        def _pick_storylet(*_args, **_kwargs):
            if picks:
                return picks.pop(0)
            return fallback_storylet

        with (
            patch("src.api.game.story.ensure_storylets", return_value=None),
            patch(
                "src.api.game.story.pick_storylet_enhanced",
                side_effect=_pick_storylet,
            ),
            patch(
                "src.api.game.story.adapt_storylet_to_context",
                return_value={
                    "text": "A deterministic scene.",
                    "choices": [{"label": "Continue", "set": {}}],
                },
            ),
        ):
            first = client.post("/api/next", json={"session_id": sid, "vars": {}})
            assert first.status_code == 200

            second = client.post(
                "/api/next",
                json={
                    "session_id": sid,
                    "vars": {},
                    "choice_taken": {
                        "set": [{"key": "intent", "value": "pact"}],
                        "increment": [],
                        "append_fact": [],
                    },
                },
            )
            assert second.status_code == 200

            third = client.post("/api/next", json={"session_id": sid, "vars": {}})
            assert third.status_code == 200

        state_payload = client.get(f"/api/state/{sid}").json()
        assert state_payload["variables"]["focus"] == "committed"
        assert state_payload["variables"]["gold"] == 3

        history = client.get(
            "/api/world/history",
            params={"session_id": sid, "event_type": "storylet_fired", "limit": 10},
        )
        assert history.status_code == 200
        effect_events = []
        for event in history.json()["events"]:
            metadata = event["world_state_delta"].get("__action_meta__", {})
            choice_commit_metadata = metadata.get("choice_commit_storylet_effects", {})
            if choice_commit_metadata.get("storylet_effects_trigger") == "on_choice_commit":
                effect_events.append(event)
        assert len(effect_events) == 1
        metadata = effect_events[0]["world_state_delta"]["__action_meta__"]["choice_commit_storylet_effects"]
        assert metadata["applied_storylet_effects"]
        assert "storylet_effects_receipt" in metadata

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

    def test_reset_session_clears_world_without_reseeding_by_default(self, seeded_client, seeded_db):
        old_session = "reset-world-old-session"
        seeded_client.post("/api/next", json={"session_id": old_session, "vars": {"marker": "old"}})

        assert seeded_db.query(SessionVars).count() >= 1
        assert seeded_db.query(WorldEvent).count() >= 1

        response = seeded_client.post("/api/reset-session")
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["storylets_seeded"] == 0
        assert payload["legacy_seed_mode"] is False

        old_history = seeded_client.get(f"/api/world/history?session_id={old_session}&limit=20")
        assert old_history.status_code == 200
        assert old_history.json()["count"] == 0

        assert seeded_db.query(SessionVars).count() == 0
        assert seeded_db.query(WorldEvent).count() == 0
        assert seeded_db.query(Storylet).count() == 0

    def test_reset_session_optional_legacy_seed_mode(
        self,
        seeded_client,
        seeded_db,
        monkeypatch,
    ):
        monkeypatch.setattr("src.api.game.state.settings.enable_legacy_test_seeds", True)
        response = seeded_client.post("/api/reset-session?include_legacy_seed=true")
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["legacy_seed_mode"] is True
        assert payload["storylets_seeded"] > 0
        assert seeded_db.query(Storylet).count() == payload["storylets_seeded"]

    def test_dev_hard_reset_disabled_by_default(self, seeded_client, monkeypatch):
        monkeypatch.setattr("src.api.game.state.settings.enable_dev_reset", False)
        response = seeded_client.post("/api/dev/hard-reset")
        assert response.status_code == 404

    def test_dev_hard_reset_wipes_world_when_enabled(self, seeded_client, seeded_db, monkeypatch):
        monkeypatch.setattr("src.api.game.state.settings.enable_dev_reset", True)

        sid = "dev-hard-reset-world"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {"marker": "x"}})
        assert seeded_db.query(Storylet).count() > 0
        assert seeded_db.query(WorldEvent).count() > 0

        response = seeded_client.post("/api/dev/hard-reset")
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["storylets_seeded"] == 0
        assert payload["legacy_seed_mode"] is False
        assert seeded_db.query(Storylet).count() == 0
        assert seeded_db.query(WorldEvent).count() == 0
        assert seeded_db.query(SessionVars).count() == 0

    def test_session_bootstrap_persists_onboarding_vars_and_provenance(self, client):
        session_id = "bootstrap-vars-session"
        response = client.post(
            "/api/session/bootstrap",
            json={
                "session_id": session_id,
                "world_theme": "frontier mystery",
                "player_role": "exiled cartographer",
                "bootstrap_source": "onboarding",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["session_id"] == session_id
        assert payload["storylets_created"] >= 1
        assert payload["bootstrap_state"] == "completed"
        assert payload["theme"] == "frontier mystery"
        assert payload["player_role"] == "exiled cartographer"

        summary = client.get(f"/api/state/{session_id}")
        assert summary.status_code == 200
        variables = summary.json()["variables"]
        assert variables["world_theme"] == "frontier mystery"
        assert variables["player_role"] == "exiled cartographer"
        assert variables["character_profile"] == "exiled cartographer"
        assert variables["_bootstrap_state"] == "completed"
        assert variables["_bootstrap_source"] == "onboarding"
        assert "_bootstrap_completed_at" in variables
        assert "_bootstrap_input_hash" in variables

    def test_session_bootstrap_purges_prior_same_session_state_and_prefetch(self, client, db_session):
        from src.services.prefetch_service import set_prefetched_stubs_for_session

        session_id = "bootstrap-freshness-session"
        first_turn = client.post(
            "/api/next",
            json={"session_id": session_id, "vars": {"marker": "old"}},
        )
        assert first_turn.status_code == 200

        stale_event = db_session.query(WorldEvent).filter(WorldEvent.session_id == session_id).order_by(WorldEvent.id.desc()).first()
        assert stale_event is not None
        assert stale_event.id is not None
        db_session.add(
            WorldProjection(
                path=f"sessions.{session_id}.stale_marker",
                value={"marker": "old"},
                source_event_id=int(stale_event.id),
            )
        )
        db_session.commit()

        set_prefetched_stubs_for_session(
            session_id,
            stubs=[
                {
                    "storylet_id": 99999,
                    "title": "stale-prefetch-stub",
                    "premise": "old stub",
                    "requires": {},
                    "choices": [],
                }
            ],
            context_summary={"source": "test"},
        )
        pre_status = client.get(f"/api/prefetch/status/{session_id}")
        assert pre_status.status_code == 200
        assert pre_status.json()["stubs_cached"] >= 1

        bootstrap = client.post(
            "/api/session/bootstrap",
            json={
                "session_id": session_id,
                "world_theme": "thriller mystery",
                "player_role": "translator of an unwritten language",
                "bootstrap_source": "onboarding",
            },
        )
        assert bootstrap.status_code == 200

        state_payload = client.get(f"/api/state/{session_id}")
        assert state_payload.status_code == 200
        variables = state_payload.json()["variables"]
        assert variables.get("marker") is None
        assert variables["world_theme"] == "thriller mystery"
        assert variables["player_role"] == "translator of an unwritten language"

        history = client.get(f"/api/world/history?session_id={session_id}&limit=20")
        assert history.status_code == 200
        assert history.json()["count"] == 0
        assert db_session.query(WorldEvent).filter(WorldEvent.session_id == session_id).count() == 0
        assert db_session.query(WorldProjection).filter(WorldProjection.path == f"sessions.{session_id}.stale_marker").count() == 0

        post_status = client.get(f"/api/prefetch/status/{session_id}")
        assert post_status.status_code == 200
        assert post_status.json()["stubs_cached"] == 0

    def test_first_scene_after_bootstrap_is_not_legacy_seed_storylet(self, client):
        session_id = "bootstrap-first-scene"
        bootstrap = client.post(
            "/api/session/bootstrap",
            json={
                "session_id": session_id,
                "world_theme": "occult city noir",
                "player_role": "retired ranger",
            },
        )
        assert bootstrap.status_code == 200

        first_scene = client.post("/api/next", json={"session_id": session_id, "vars": {}})
        assert first_scene.status_code == 200
        text = first_scene.json()["text"].lower()
        assert "you move north" not in text
        assert "you move east" not in text

    @patch("src.services.world_bootstrap_service.run_auto_improvements")
    def test_session_bootstrap_skips_auto_improvements(self, mock_auto_improve, client):
        response = client.post(
            "/api/session/bootstrap",
            json={
                "session_id": "bootstrap-no-auto-improve",
                "world_theme": "quiet frontier",
                "player_role": "traveler",
            },
        )
        assert response.status_code == 200
        mock_auto_improve.assert_not_called()

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
        assert response.json()["choices"] == [{"label": "Advance", "set": {"gold": 9}, "intent": None}]

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

        with (
            patch("src.api.game.story.ensure_storylets", return_value=None),
            patch(
                "src.services.world_memory.get_world_history",
                return_value=[],
            ),
            patch(
                "src.services.world_memory.get_recent_graph_fact_summaries",
                return_value=["The old beacon is unstable."],
            ),
            patch(
                "src.services.semantic_selector.compute_player_context_vector",
                return_value=[1.0, 0.0, 0.0],
            ),
            patch(
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
            ),
            patch(
                "src.services.embedding_service.embed_storylet_payload",
                return_value=[1.0, 0.0, 0.0],
            ),
        ):
            response = client.post(
                "/api/next",
                json={"session_id": "runtime-sparse-api", "vars": {}},
            )

        assert response.status_code == 200
        assert response.json()["text"] != "The tunnel is quiet. Nothing compelling meets the eye."
        runtime_count = db_session.query(Storylet).filter(Storylet.source == "runtime_synthesis").count()
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
        payload = response.json()
        assert payload["text"] == "The tunnel is quiet. Nothing compelling meets the eye."
        diag = payload.get("diagnostics", {})
        assert isinstance(diag, dict)
        assert str(diag.get("selection_mode", "")).strip() in {"none", "fallback_weighted"}
        assert diag.get("fallback_reason") in {"no_eligible_storylets", "no_storylet_selected"}
        assert diag.get("clarity_level") == "unknown"

    def test_next_blocks_projection_only_vars_and_prevents_world_history_leak(self, seeded_client):
        session_id = "projection-guard-next"
        response = seeded_client.post(
            "/api/next",
            json={
                "session_id": session_id,
                "vars": {
                    "projection_depth": 9,
                    "non_canon": False,
                    "selected_projection_id": 77,
                },
            },
        )
        assert response.status_code == 200
        vars_payload = response.json()["vars"]
        assert vars_payload.get("projection_depth") is None
        assert vars_payload.get("non_canon") is None
        assert vars_payload.get("selected_projection_id") is None

        history = seeded_client.get("/api/world/history", params={"session_id": session_id, "limit": 25})
        assert history.status_code == 200
        events = history.json().get("events", [])
        assert events
        for event in events:
            delta = event.get("world_state_delta", {})
            assert "projection_depth" not in delta
            assert "non_canon" not in delta
            assert "selected_projection_id" not in delta

    def test_next_commit_invalidates_prefetch_projection_and_surfaces_diag(self, seeded_client):
        from src.services.prefetch_service import set_prefetched_stubs_for_session

        session_id = "projection-invalidate-next"
        set_prefetched_stubs_for_session(
            session_id,
            stubs=[
                {
                    "storylet_id": 9001,
                    "title": "stale-branch",
                    "premise": "stale",
                    "requires": {},
                    "choices": [],
                }
            ],
            context_summary={"source": "test"},
        )

        with patch("src.api.game.story.schedule_prefetch_async_best_effort", new=AsyncMock()):
            response = seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})
        assert response.status_code == 200
        vars_payload = response.json()["vars"]
        diag = vars_payload.get("_ww_diag", {})
        top_level_diag = response.json().get("diagnostics", {})
        assert diag.get("commit_status") == "committed"
        assert int(diag.get("invalidated_projection_count", 0)) >= 1
        assert "selected_projection_id" in diag
        assert top_level_diag == diag

        post_status = seeded_client.get(f"/api/prefetch/status/{session_id}")
        assert post_status.status_code == 200
        assert post_status.json()["stubs_cached"] == 0

    def test_action_commit_invalidates_prefetch_projection_and_surfaces_diag(self, seeded_client):
        from src.services.prefetch_service import set_prefetched_stubs_for_session

        session_id = "projection-invalidate-action"
        seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})
        set_prefetched_stubs_for_session(
            session_id,
            stubs=[
                {
                    "storylet_id": 9010,
                    "title": "stale-action-branch",
                    "premise": "stale",
                    "requires": {},
                    "choices": [],
                }
            ],
            context_summary={"source": "test"},
        )

        with patch("src.api.game.action.schedule_prefetch_async_best_effort", new=AsyncMock()):
            response = seeded_client.post(
                "/api/action",
                json={"session_id": session_id, "action": "I check the room carefully."},
            )
        assert response.status_code == 200
        vars_payload = response.json()["vars"]
        diag = vars_payload.get("_ww_diag", {})
        top_level_diag = response.json().get("diagnostics", {})
        assert diag.get("commit_status") == "committed"
        assert int(diag.get("invalidated_projection_count", 0)) >= 1
        assert diag.get("selected_projection_id") is None
        assert top_level_diag == diag

        post_status = seeded_client.get(f"/api/prefetch/status/{session_id}")
        assert post_status.status_code == 200
        assert post_status.json()["stubs_cached"] == 0

    def test_action_failed_commit_rolls_back_state_snapshot(self, seeded_client):
        session_id = "action-rollback-snapshot"
        seeded_client.post(
            "/api/next",
            json={"session_id": session_id, "vars": {"gold": 11, "location": "start"}},
        )
        before_state = seeded_client.get(f"/api/state/{session_id}").json()["variables"]

        with patch("src.services.turn_service.reduce_event", side_effect=RuntimeError("forced reducer failure")):
            failed = seeded_client.post(
                "/api/action",
                json={"session_id": session_id, "action": "I inspect the floorboards."},
            )

        assert failed.status_code == 500
        after_state = seeded_client.get(f"/api/state/{session_id}").json()["variables"]
        assert after_state.get("gold") == before_state.get("gold")
        assert after_state.get("location") == before_state.get("location")

    # ── Major 109: turn_source / pipeline_mode diagnostics ──────────────────

    def test_next_turn_diagnostics_include_turn_source_and_pipeline_mode(self, seeded_client):
        session_id = "diag-turn-source-next"
        resp = seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})
        assert resp.status_code == 200
        diag = resp.json()["vars"].get("_ww_diag", {})
        assert diag.get("turn_source") == "initial_scene"
        assert diag.get("pipeline_mode") in {"jit_beat", "engine_idle_fallback", "storylet_selection"}

    def test_next_choice_turn_diagnostics_turn_source_is_choice_button(self, seeded_client):
        session_id = "diag-turn-source-choice"
        seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})
        resp = seeded_client.post(
            "/api/next",
            json={"session_id": session_id, "vars": {"location": "start", "_marker": "choice"}},
        )
        assert resp.status_code == 200
        diag = resp.json()["vars"].get("_ww_diag", {})
        assert diag.get("turn_source") == "choice_button"

    def test_action_turn_diagnostics_include_turn_source_and_pipeline_mode(self, seeded_client):
        session_id = "diag-turn-source-action"
        seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})
        resp = seeded_client.post(
            "/api/action",
            json={"session_id": session_id, "action": "I examine the surroundings carefully."},
        )
        assert resp.status_code == 200
        diag = resp.json()["vars"].get("_ww_diag", {})
        assert diag.get("turn_source") == "freeform_action"
        assert diag.get("pipeline_mode") in {"staged_action", "direct_action"}

    # ── Major 108: /session/start unified startup ────────────────────────────

    def test_session_start_returns_bootstrap_and_first_turn(self, client):
        session_id = "session-start-basic"
        resp = client.post(
            "/api/session/start",
            json={
                "session_id": session_id,
                "world_theme": "gothic mystery",
                "player_role": "disgraced archivist",
                "bootstrap_source": "onboarding",
            },
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["success"] is True
        assert payload["bootstrap_state"] == "completed"
        assert payload["storylets_created"] >= 1
        assert payload["startup_source"] == "unified"
        # First turn payload is present and valid
        first_turn = payload.get("first_turn")
        assert isinstance(first_turn, dict), "first_turn must be a dict"
        assert "text" in first_turn
        assert "choices" in first_turn
        assert "vars" in first_turn
        assert payload.get("first_turn_error") is None

    def test_session_start_first_turn_has_initial_scene_turn_source(self, client):
        session_id = "session-start-turn-source"
        resp = client.post(
            "/api/session/start",
            json={
                "session_id": session_id,
                "world_theme": "solarpunk frontier",
                "player_role": "grid architect",
            },
        )
        assert resp.status_code == 200
        payload = resp.json()
        first_turn = payload.get("first_turn") or {}
        diag = (first_turn.get("vars") or {}).get("_ww_diag", {})
        assert diag.get("turn_source") == "initial_scene"

    def test_session_start_persists_bootstrap_vars(self, client):
        session_id = "session-start-vars"
        client.post(
            "/api/session/start",
            json={
                "session_id": session_id,
                "world_theme": "deep space salvage",
                "player_role": "hull technician",
                "bootstrap_source": "onboarding",
            },
        )
        summary = client.get(f"/api/state/{session_id}")
        assert summary.status_code == 200
        variables = summary.json()["variables"]
        assert variables["world_theme"] == "deep space salvage"
        assert variables["player_role"] == "hull technician"
        assert variables["_bootstrap_state"] == "completed"

    def test_session_start_existing_routes_unaffected(self, client):
        """Verify /session/bootstrap + /next still work after /session/start is added."""
        session_id = "session-start-compat"
        bootstrap = client.post(
            "/api/session/bootstrap",
            json={
                "session_id": session_id,
                "world_theme": "mythic noir",
                "player_role": "street oracle",
            },
        )
        assert bootstrap.status_code == 200
        next_resp = client.post("/api/next", json={"session_id": session_id, "vars": {}})
        assert next_resp.status_code == 200
        assert "text" in next_resp.json()

    # ── Minor 111 — bootstrap diagnostics surface ─────────────────────────────

    def test_session_bootstrap_includes_bootstrap_diagnostics(self, client):
        """Bootstrap response includes bootstrap_diagnostics with seeding path info (Minor 111)."""
        resp = client.post(
            "/api/session/bootstrap",
            json={
                "session_id": "bootstrap-diag-test",
                "world_theme": "haunted forest",
                "player_role": "wanderer",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        diag = data.get("bootstrap_diagnostics")
        assert diag is not None, "bootstrap_diagnostics must be present in bootstrap response"
        assert "bootstrap_mode" in diag
        assert "seeding_path" in diag
        assert "world_bible_generated" in diag
        assert "world_bible_fallback" in diag
        assert "storylets_created" in diag
        assert "fallback_active" in diag
        assert "bootstrap_source" in diag
        assert isinstance(diag["world_bible_generated"], bool)
        assert isinstance(diag["storylets_created"], int)

    def test_session_start_includes_bootstrap_diagnostics(self, client):
        """Unified /session/start response also includes bootstrap_diagnostics (Minor 111)."""
        resp = client.post(
            "/api/session/start",
            json={
                "session_id": "start-diag-test",
                "world_theme": "iron frontier",
                "player_role": "surveyor",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        diag = data.get("bootstrap_diagnostics")
        assert diag is not None, "bootstrap_diagnostics must be present in session/start response"
        assert "bootstrap_mode" in diag
        assert "seeding_path" in diag
        assert isinstance(diag["world_bible_generated"], bool)
