"""Contract test for POST /api/spatial/move/{session_id}."""


def test_post_spatial_move_contract(seeded_client):
    session_id = "test-move"
    seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})
    # Try moving — may succeed or fail depending on spatial layout
    response = seeded_client.post(f"/api/spatial/move/{session_id}", json={"direction": "north"})
    assert response.status_code in (200, 403, 404)
    if response.status_code == 200:
        data = response.json()
        assert "result" in data and "new_position" in data

    # Invalid direction
    bad_response = seeded_client.post(f"/api/spatial/move/{session_id}", json={"direction": "INVALID"})
    assert bad_response.status_code in (400, 422)
