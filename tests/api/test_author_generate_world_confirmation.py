"""Tests for confirmation guard on world generation endpoint."""

from unittest.mock import patch


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


@patch("src.services.world_bootstrap_service.run_auto_improvements")
def test_generate_world_still_runs_auto_improvements_for_author_flow(mock_auto_improve, client):
    mock_auto_improve.return_value = {"success": True, "total_improvements": 0}
    payload = {
        "description": "A windswept frontier with rival factions and hidden ruins.",
        "theme": "frontier",
        "player_role": "courier",
        "confirm_delete": True,
    }
    response = client.post("/author/generate-world", json=payload)
    assert response.status_code == 200
    mock_auto_improve.assert_called_once()
