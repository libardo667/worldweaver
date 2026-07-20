"""Contract tests for error response format."""


def test_next_missing_session_id(client):
    resp = client.post("/api/next", json={"vars": {}})
    assert resp.status_code != 200
    assert "detail" in resp.json()


def test_raw_state_route_is_not_public(client):
    resp = client.get("/api/state/test-crash")
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200 and resp.json()["ok"] is True
