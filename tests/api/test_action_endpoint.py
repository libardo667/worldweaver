"""Tests for the POST /api/action endpoint."""

from unittest.mock import patch

from src.models import SessionVars, Storylet
from src.services.command_interpreter import ActionResult


class TestActionEndpoint:

    def test_basic_response(self, seeded_client):
        # Initialize session first
        seeded_client.post(
            "/api/next", json={"session_id": "action-test", "vars": {}}
        )

        resp = seeded_client.post(
            "/api/action",
            json={"session_id": "action-test", "action": "look around"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "narrative" in data
        assert "state_changes" in data
        assert "choices" in data
        assert "plausible" in data
        assert "vars" in data

    def test_action_includes_trace_id_header(self, seeded_client):
        seeded_client.post(
            "/api/next", json={"session_id": "action-trace-test", "vars": {}}
        )
        resp = seeded_client.post(
            "/api/action",
            json={"session_id": "action-trace-test", "action": "look around"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("X-WW-Trace-Id")

    def test_action_schedules_prefetch_without_breaking_response(self, seeded_client):
        seeded_client.post("/api/next", json={"session_id": "action-prefetch-test", "vars": {}})

        with patch("src.api.game.action.schedule_frontier_prefetch", return_value=True) as mock_schedule:
            resp = seeded_client.post(
                "/api/action",
                json={"session_id": "action-prefetch-test", "action": "look around"},
            )

        assert resp.status_code == 200
        mock_schedule.assert_called_once()
        assert mock_schedule.call_args.args[0] == "action-prefetch-test"

    def test_action_stream_emits_draft_and_final_events(self, seeded_client):
        seeded_client.post(
            "/api/next", json={"session_id": "action-stream-test", "vars": {}}
        )

        resp = seeded_client.post(
            "/api/action/stream",
            json={"session_id": "action-stream-test", "action": "inspect the torch"},
        )
        assert resp.status_code == 200
        body = resp.text
        assert "event: phase:ack" in body
        assert "event: phase:commit" in body
        assert "event: draft_chunk" in body
        assert "event: final" in body
        assert '"plausible"' in body

    def test_action_stream_emits_staged_narrate_phase(self, seeded_client):
        seeded_client.post(
            "/api/next", json={"session_id": "action-stream-staged", "vars": {}}
        )
        staged_result = ActionResult(
            narrative_text="You set your shoulder to the sealed gate.",
            state_deltas={"gate_status": "strained"},
            should_trigger_storylet=False,
            follow_up_choices=[{"label": "Continue", "set": {}}],
            plausible=True,
            reasoning_metadata={"goal_update": None},
        )
        staged_intent = type("StagedIntent", (), {"ack_line": "You force the gate.", "result": staged_result})()
        narrated_result = ActionResult(
            narrative_text="Wood splinters and the gate bows inward.",
            state_deltas={"gate_status": "strained"},
            should_trigger_storylet=False,
            follow_up_choices=[{"label": "Slip through", "set": {}}],
            plausible=True,
            reasoning_metadata={"goal_update": None},
        )

        with (
            patch("src.api.game.action.settings.enable_staged_action_pipeline", True),
            patch("src.services.command_interpreter.interpret_action_intent", return_value=staged_intent),
            patch("src.services.command_interpreter.render_validated_action_narration", return_value=narrated_result),
        ):
            resp = seeded_client.post(
                "/api/action/stream",
                json={"session_id": "action-stream-staged", "action": "I force the gate"},
            )

        assert resp.status_code == 200
        body = resp.text
        assert "event: phase:ack" in body
        assert "event: phase:commit" in body
        assert "event: phase:narrate" in body
        assert "event: final" in body

    def test_action_stream_falls_back_to_single_pass_when_stage_a_unavailable(self, seeded_client):
        session_id = "action-stream-fallback"
        seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})

        legacy_result = ActionResult(
            narrative_text="You circle the perimeter and find weak mortar.",
            state_deltas={"wall_weak_spot": True},
            should_trigger_storylet=False,
            follow_up_choices=[{"label": "Continue", "set": {}}],
            plausible=True,
            reasoning_metadata={},
        )

        with (
            patch("src.api.game.action.settings.enable_staged_action_pipeline", True),
            patch("src.services.command_interpreter.interpret_action_intent", return_value=None),
            patch("src.services.command_interpreter.interpret_action", return_value=legacy_result) as legacy_mock,
        ):
            resp = seeded_client.post(
                "/api/action/stream",
                json={"session_id": session_id, "action": "I inspect the wall"},
            )

        assert resp.status_code == 200
        body = resp.text
        assert "event: phase:ack" in body
        assert "event: phase:commit" in body
        assert "event: phase:narrate" not in body
        assert "event: final" in body
        legacy_mock.assert_called_once()

    def test_action_stream_includes_trace_id_header(self, seeded_client):
        seeded_client.post(
            "/api/next", json={"session_id": "action-stream-trace", "vars": {}}
        )

        resp = seeded_client.post(
            "/api/action/stream",
            json={"session_id": "action-stream-trace", "action": "inspect the torch"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("X-WW-Trace-Id")

    def test_action_stream_schedules_prefetch_without_breaking_response(self, seeded_client):
        seeded_client.post("/api/next", json={"session_id": "action-stream-prefetch", "vars": {}})

        with patch("src.api.game.action.schedule_frontier_prefetch", return_value=True) as mock_schedule:
            resp = seeded_client.post(
                "/api/action/stream",
                json={"session_id": "action-stream-prefetch", "action": "inspect the torch"},
            )

        assert resp.status_code == 200
        assert "event: final" in resp.text
        mock_schedule.assert_called_once()
        assert mock_schedule.call_args.args[0] == "action-stream-prefetch"

    def test_missing_action_returns_422(self, client):
        resp = client.post(
            "/api/action",
            json={"session_id": "test"},
        )
        assert resp.status_code == 422

    def test_empty_action_returns_422(self, client):
        resp = client.post(
            "/api/action",
            json={"session_id": "test", "action": ""},
        )
        assert resp.status_code == 422

    def test_invalid_idempotency_key_returns_422(self, client):
        resp = client.post(
            "/api/action",
            json={
                "session_id": "test",
                "action": "look around",
                "idempotency_key": "bad key with spaces",
            },
        )
        assert resp.status_code == 422

    def test_records_world_event(self, seeded_client):
        seeded_client.post(
            "/api/next", json={"session_id": "action-ev", "vars": {}}
        )
        seeded_client.post(
            "/api/action",
            json={"session_id": "action-ev", "action": "peek under the tarp"},
        )

        resp = seeded_client.get("/api/world/history?session_id=action-ev")
        assert resp.status_code == 200
        events = resp.json()["events"]
        freeform = [e for e in events if e["event_type"] == "freeform_action"]
        assert len(freeform) >= 1
        assert "peek under the tarp" in freeform[0]["summary"]

    def test_high_impact_delta_becomes_permanent_change(self, seeded_client):
        seeded_client.post(
            "/api/next", json={"session_id": "action-impact", "vars": {}}
        )

        mocked_result = ActionResult(
            narrative_text="The bridge collapses behind you.",
            state_deltas={"bridge_broken": True},
            should_trigger_storylet=False,
            follow_up_choices=[],
            plausible=True,
        )
        with patch(
            "src.services.command_interpreter.interpret_action",
            return_value=mocked_result,
        ):
            resp = seeded_client.post(
                "/api/action",
                json={
                    "session_id": "action-impact",
                    "action": "I blow up the bridge",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["vars"]["bridge_broken"] is True

        history_resp = seeded_client.get("/api/world/history?session_id=action-impact")
        assert history_resp.status_code == 200
        events = history_resp.json()["events"]
        permanent = [e for e in events if e["event_type"] == "permanent_change"]
        assert permanent
        assert permanent[0]["world_state_delta"]["bridge_broken"] is True

    def test_contradictory_action_returns_refusal(self, seeded_client):
        seeded_client.post(
            "/api/next", json={"session_id": "action-contradiction", "vars": {}}
        )

        initial_result = ActionResult(
            narrative_text="The bridge collapses into rubble.",
            state_deltas={"bridge_broken": True},
            should_trigger_storylet=False,
            follow_up_choices=[],
            plausible=True,
        )
        with patch(
            "src.services.command_interpreter.interpret_action",
            return_value=initial_result,
        ):
            seeded_client.post(
                "/api/action",
                json={
                    "session_id": "action-contradiction",
                    "action": "I destroy the bridge",
                },
            )

        response = seeded_client.post(
            "/api/action",
            json={
                "session_id": "action-contradiction",
                "action": "I destroy the bridge",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["plausible"] is False
        assert payload["state_changes"] == {}
        assert "already" in payload["narrative"].lower()

    def test_malformed_interpreter_result_still_returns_schema_valid_payload(self, seeded_client):
        seeded_client.post(
            "/api/next", json={"session_id": "action-malformed", "vars": {}}
        )

        malformed = ActionResult(
            narrative_text=123,  # type: ignore[arg-type]
            state_deltas="bad",  # type: ignore[arg-type]
            should_trigger_storylet=False,
            follow_up_choices=["bad-choice"],  # type: ignore[list-item]
            plausible="yes",  # type: ignore[arg-type]
        )
        with patch(
            "src.services.command_interpreter.interpret_action",
            return_value=malformed,
        ):
            response = seeded_client.post(
                "/api/action",
                json={"session_id": "action-malformed", "action": "look around"},
            )

        assert response.status_code == 200
        payload = response.json()
        assert isinstance(payload["narrative"], str)
        assert isinstance(payload["state_changes"], dict)
        assert isinstance(payload["choices"], list)
        assert isinstance(payload["plausible"], bool)

    def test_malformed_delta_payload_does_not_mutate_state(self, seeded_client):
        session_id = "action-malformed-delta"
        seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})
        before_state = seeded_client.get(f"/api/state/{session_id}").json()["variables"]

        malformed = ActionResult(
            narrative_text="No coherent state change resolves.",
            state_deltas="bad",  # type: ignore[arg-type]
            should_trigger_storylet=False,
            follow_up_choices=[{"label": "Continue", "set": {}}],
            plausible=True,
        )
        with patch(
            "src.services.command_interpreter.interpret_action",
            return_value=malformed,
        ):
            response = seeded_client.post(
                "/api/action",
                json={"session_id": session_id, "action": "look around"},
            )

        assert response.status_code == 200
        after_state = seeded_client.get(f"/api/state/{session_id}").json()["variables"]
        before_state.pop("turn", None)
        after_state.pop("turn", None)
        if "_story_arc" in before_state:
            before_state["_story_arc"].pop("turn_count", None)
        if "_story_arc" in after_state:
            after_state["_story_arc"].pop("turn_count", None)
        assert after_state == before_state

    def test_idempotency_key_prevents_duplicate_action_event_rows(self, seeded_client):
        session_id = "action-idempotency-events"
        seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})

        payload = {
            "session_id": session_id,
            "action": "inspect the gate hinges",
            "idempotency_key": "idem-action-001",
        }
        first = seeded_client.post("/api/action", json=payload)
        second = seeded_client.post("/api/action", json=payload)
        assert first.status_code == 200
        assert second.status_code == 200

        history = seeded_client.get(f"/api/world/history?session_id={session_id}").json()["events"]
        matching = [
            event
            for event in history
            if "inspect the gate hinges" in str(event.get("summary", ""))
        ]
        assert len(matching) == 1

    def test_duplicate_idempotent_response_matches_first(self, seeded_client):
        session_id = "action-idempotency-response"
        seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})

        payload = {
            "session_id": session_id,
            "action": "look around carefully",
            "idempotency_key": "idem-action-002",
        }
        first = seeded_client.post("/api/action", json=payload)
        second = seeded_client.post("/api/action", json=payload)

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json() == first.json()

    def test_existing_clients_without_idempotency_key_continue_to_work(self, seeded_client):
        session_id = "action-no-idempotency"
        seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})

        first = seeded_client.post(
            "/api/action",
            json={"session_id": session_id, "action": "listen at the door"},
        )
        second = seeded_client.post(
            "/api/action",
            json={"session_id": session_id, "action": "listen at the door"},
        )
        assert first.status_code == 200
        assert second.status_code == 200

        history = seeded_client.get(f"/api/world/history?session_id={session_id}").json()["events"]
        matching = [
            event
            for event in history
            if "listen at the door" in str(event.get("summary", ""))
        ]
        assert len(matching) >= 2

    def test_suggested_beats_are_persisted(self, seeded_client, seeded_db):
        seeded_client.post(
            "/api/next", json={"session_id": "action-beat-persist", "vars": {}}
        )

        beat_result = ActionResult(
            narrative_text="The mood darkens as the bridge burns.",
            state_deltas={},
            should_trigger_storylet=False,
            follow_up_choices=[],
            suggested_beats=[
                {
                    "name": "IncreasingTension",
                    "intensity": 0.5,
                    "turns_remaining": 3,
                    "decay": 0.65,
                }
            ],
            plausible=True,
        )
        with patch(
            "src.services.command_interpreter.interpret_action",
            return_value=beat_result,
        ):
            response = seeded_client.post(
                "/api/action",
                json={"session_id": "action-beat-persist", "action": "I burn the bridge"},
            )

        assert response.status_code == 200
        row = seeded_db.get(SessionVars, "action-beat-persist")
        assert row is not None
        beats = row.vars.get("narrative_beats", [])
        assert beats and beats[0]["name"] == "IncreasingTension"

    def test_looking_for_goal_appends_directional_hint(self, seeded_client, seeded_db):
        seeded_db.add(
            Storylet(
                title="action-semantic-goal-start",
                text_template="A central plaza.",
                requires={"location": "start"},
                choices=[{"label": "Wait", "set": {}}],
                weight=1.0,
                position={"x": 0, "y": 0},
            )
        )
        seeded_db.commit()
        seeded_client.post(
            "/api/next", json={"session_id": "action-semantic-goal", "vars": {}}
        )

        mocked_result = ActionResult(
            narrative_text="You scan the market square.",
            state_deltas={},
            should_trigger_storylet=False,
            follow_up_choices=[],
            plausible=True,
        )
        mocked_nav = type(
            "MockNavigator",
            (),
            {
                "get_semantic_goal_hint": lambda *args, **kwargs: {
                    "direction": "east",
                    "hint": "The sound of hammers rings from the East.",
                    "lead": {"id": 1},
                }
            },
        )()

        with (
            patch("src.services.command_interpreter.interpret_action", return_value=mocked_result),
            patch("src.api.game.action.get_spatial_navigator", return_value=mocked_nav),
            patch("src.services.semantic_selector.compute_player_context_vector", return_value=[0.1, 0.2, 0.3]),
        ):
            response = seeded_client.post(
                "/api/action",
                json={"session_id": "action-semantic-goal", "action": "I'm looking for the blacksmith"},
            )

        assert response.status_code == 200
        payload = response.json()
        assert "hammers" in payload["narrative"].lower()
        assert "east" in payload["narrative"].lower()

    def test_action_goal_update_applies_progress_and_complication(self, seeded_client):
        sid = "action-goal-update"
        seeded_client.post("/api/next", json={"session_id": sid, "vars": {}})
        seeded_client.post(
            f"/api/state/{sid}/goal",
            json={
                "primary_goal": "Recover the ledger",
                "urgency": 0.4,
                "complication": 0.2,
            },
        )

        mocked_result = ActionResult(
            narrative_text="You uncover a partial lead, but guards are alerted.",
            state_deltas={},
            should_trigger_storylet=False,
            follow_up_choices=[],
            plausible=True,
            reasoning_metadata={
                "goal_update": {
                    "status": "complicated",
                    "milestone": "Guards locked down the archive",
                    "urgency_delta": 0.2,
                    "complication_delta": 0.3,
                }
            },
        )
        with patch(
            "src.services.command_interpreter.interpret_action",
            return_value=mocked_result,
        ):
            response = seeded_client.post(
                "/api/action",
                json={"session_id": sid, "action": "I sneak into the archive"},
            )

        assert response.status_code == 200
        state = seeded_client.get(f"/api/state/{sid}").json()
        assert state["goal"]["urgency"] >= 0.6
        assert state["goal"]["complication"] >= 0.5
        assert state["arc_timeline"][0]["status"] == "complicated"
