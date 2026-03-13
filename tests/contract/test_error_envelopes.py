"""Contract tests for error response format."""

from unittest.mock import patch


def test_next_missing_session_id(client):
    resp = client.post("/api/next", json={"vars": {}})
    assert resp.status_code != 200
    assert "detail" in resp.json()


def test_unhandled_exception_returns_500_safe(client):
    with patch("src.api.game.state.get_state_manager", side_effect=RuntimeError("kaboom")):
        resp = client.get("/api/state/test-crash")
    assert resp.status_code == 500
    body = resp.json()
    assert "detail" in body and "kaboom" not in body["detail"]
    assert body["detail"] == "Internal server error"


def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200 and resp.json()["ok"] is True
