"""Tests for the POST /api/action endpoint."""

from unittest.mock import patch

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
