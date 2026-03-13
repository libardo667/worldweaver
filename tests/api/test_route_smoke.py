"""Route smoke tests for core API surface stability."""


def test_health_route_smoke(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_next_route_smoke(seeded_client):
    response = seeded_client.post("/api/next", json={"session_id": "smoke-next", "vars": {}})
    assert response.status_code == 200


def test_action_route_smoke(client):
    response = client.post("/api/action", json={"session_id": "smoke-action"})
    assert response.status_code == 422


def test_action_stream_route_smoke(client):
    response = client.post("/api/action/stream", json={"session_id": "smoke-action"})
    assert response.status_code == 422


def test_world_history_route_smoke(client):
    response = client.get("/api/world/history")
    assert response.status_code == 200


def test_world_facts_route_smoke(client):
    response = client.get("/api/world/facts?query=bridge")
    assert response.status_code == 200
