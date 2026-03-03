"""Tests for confirmation guard on world generation endpoint."""


def test_generate_world_requires_confirm_delete(client):
    payload = {
        "description": "A windswept frontier with rival factions and hidden ruins.",
        "theme": "frontier",
        "confirm_delete": False,
    }
    response = client.post("/author/generate-world", json=payload)
    assert response.status_code == 422
    assert "confirm_delete=true" in response.json()["detail"]


def test_generate_world_succeeds_with_confirm_delete(client):
    payload = {
        "description": "A windswept frontier with rival factions and hidden ruins.",
        "theme": "frontier",
        "player_role": "courier",
        "confirm_delete": True,
    }
    response = client.post("/author/generate-world", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["storylets_created"] >= 1
