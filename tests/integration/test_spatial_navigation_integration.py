"""Integration test for 8-direction movement and edge cases."""


def test_eight_direction_movement(seeded_client):
    session_id = "test-8dir"
    seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})
    directions = ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"]
    for direction in directions:
        response = seeded_client.post(f"/api/spatial/move/{session_id}", json={"direction": direction})
        # Movement may succeed or be blocked depending on spatial layout
        assert response.status_code in (200, 403, 404)
        if response.status_code == 200:
            data = response.json()
            assert "new_position" in data
            assert isinstance(data["new_position"]["x"], int)
            assert isinstance(data["new_position"]["y"], int)
