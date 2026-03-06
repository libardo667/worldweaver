"""Integration test for 8-direction movement and edge cases."""

import pytest

from tests.integration_helpers import assert_ok_response, assert_status_in


DIRECTIONS = (
    "north",
    "northeast",
    "east",
    "southeast",
    "south",
    "southwest",
    "west",
    "northwest",
)


@pytest.mark.parametrize("direction", DIRECTIONS)
def test_eight_direction_movement(seeded_client, direction):
    session_id = f"test-8dir-{direction}"
    seed_response = seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})
    assert_ok_response(seed_response)
    response = seeded_client.post(f"/api/spatial/move/{session_id}", json={"direction": direction})
    # Movement may succeed or be blocked depending on spatial layout.
    assert_status_in(response, (200, 403, 404))
    if response.status_code == 200:
        data = response.json()
        assert "new_position" in data
        assert isinstance(data["new_position"]["x"], int)
        assert isinstance(data["new_position"]["y"], int)
