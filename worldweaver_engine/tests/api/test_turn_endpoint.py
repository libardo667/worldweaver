"""Tests for optional POST /api/turn unified endpoint."""


class TestTurnEndpoint:

    def test_turn_endpoint_disabled_by_default(self, seeded_client):
        response = seeded_client.post(
            "/api/turn",
            json={"session_id": "turn-disabled", "turn_type": "next", "vars": {}},
        )
        assert response.status_code == 404

    def test_turn_next_path_returns_next_payload_when_enabled(
        self,
        seeded_client,
        monkeypatch,
    ):
        monkeypatch.setattr("src.api.game.turn.settings.enable_turn_endpoint", True)

        response = seeded_client.post(
            "/api/turn",
            json={"session_id": "turn-next", "turn_type": "next", "vars": {}},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["turn_type"] == "next"
        assert payload["next"] is not None
        assert payload["action"] is None
        assert "text" in payload["next"]
        assert "choices" in payload["next"]
        assert "vars" in payload["next"]

    def test_turn_action_path_returns_action_payload_when_enabled(
        self,
        seeded_client,
        monkeypatch,
    ):
        monkeypatch.setattr("src.api.game.turn.settings.enable_turn_endpoint", True)
        seeded_client.post("/api/next", json={"session_id": "turn-action", "vars": {}})

        response = seeded_client.post(
            "/api/turn",
            json={
                "session_id": "turn-action",
                "turn_type": "action",
                "action": "inspect the scene",
                "idempotency_key": "turn-action-001",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["turn_type"] == "action"
        assert payload["next"] is None
        assert payload["action"] is not None
        assert "narrative" in payload["action"]
        assert "choices" in payload["action"]
        assert "vars" in payload["action"]

    def test_turn_action_requires_action_text(self, client, monkeypatch):
        monkeypatch.setattr("src.api.game.turn.settings.enable_turn_endpoint", True)
        response = client.post(
            "/api/turn",
            json={"session_id": "turn-missing-action", "turn_type": "action"},
        )
        assert response.status_code == 422
