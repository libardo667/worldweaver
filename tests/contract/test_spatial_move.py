"""Contract test for POST /api/spatial/move/{session_id}."""

from src.models import Storylet


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


def test_post_spatial_move_blocked_move_semantics(client, db_session):
    db_session.add_all(
        [
            Storylet(
                title="Gatehouse",
                text_template="You stand at the gatehouse.",
                requires={"location": "start"},
                choices=[{"label": "Continue", "set": {}}],
                weight=1.0,
                position={"x": 0, "y": 0},
            ),
            Storylet(
                title="Locked Tower",
                text_template="A locked tower looms here.",
                requires={"location": "tower", "tower_key": True},
                choices=[{"label": "Continue", "set": {}}],
                weight=1.0,
                position={"x": 0, "y": -1},
            ),
        ]
    )
    db_session.commit()

    session_id = "test-blocked-move"
    client.post(
        "/api/next",
        json={"session_id": session_id, "vars": {"location": "start", "tower_key": False}},
    )
    response = client.post(
        f"/api/spatial/move/{session_id}",
        json={"direction": "north"},
    )

    assert response.status_code == 403
    assert response.json().get("detail") == "Cannot move in that direction"
