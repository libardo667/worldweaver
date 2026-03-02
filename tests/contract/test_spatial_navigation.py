"""Contract test for GET /api/spatial/navigation/{session_id}."""

from src.models import Storylet


def test_get_spatial_navigation_contract(seeded_client, seeded_db):
    # Add a location-based storylet so navigation has something to find
    seeded_db.add(Storylet(
        title="Start Location",
        text_template="You are at the start.",
        requires={"location": "start"},
        choices=[{"label": "Look around", "set": {}}],
        weight=1.0,
        position={"x": 0, "y": 0},
    ))
    seeded_db.commit()

    session_id = "test-nav"
    seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})
    response = seeded_client.get(f"/api/spatial/navigation/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert "position" in data and isinstance(data["position"], dict)
    assert "x" in data["position"] and "y" in data["position"]
    assert "directions" in data and isinstance(data["directions"], list)
    valid_directions = {"north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"}
    for d in data["directions"]:
        assert d in valid_directions
