"""Contract test for GET /api/spatial/navigation/{session_id}."""

from src.models import Storylet


def test_get_spatial_navigation_contract(seeded_client, seeded_db):
    # Add a location-based storylet so navigation has something to find
    seeded_db.add(
        Storylet(
            title="Start Location",
            text_template="You are at the start.",
            requires={"location": "start"},
            choices=[{"label": "Look around", "set": {}}],
            weight=1.0,
            position={"x": 0, "y": 0},
        )
    )
    seeded_db.commit()

    session_id = "test-nav"
    seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})
    response = seeded_client.get(f"/api/spatial/navigation/{session_id}")
    assert response.status_code == 200
    data = response.json()
    required_keys = {
        "position",
        "directions",
        "available_directions",
        "location_storylet",
        "leads",
        "semantic_goal",
        "goal_hint",
    }
    assert required_keys.issubset(set(data.keys()))
    assert "position" in data and isinstance(data["position"], dict)
    assert "x" in data["position"] and "y" in data["position"]
    assert "directions" in data and isinstance(data["directions"], list)
    assert "available_directions" in data and isinstance(data["available_directions"], dict)
    assert "leads" in data and isinstance(data["leads"], list)
    assert data["location_storylet"] is None or {
        "id",
        "title",
        "position",
    }.issubset(set(data["location_storylet"].keys()))
    valid_directions = {"north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"}
    for d in data["directions"]:
        assert d in valid_directions
    for direction, target in data["available_directions"].items():
        assert direction in valid_directions
        if target is not None:
            assert "accessible" in target
    for lead in data["leads"]:
        assert {"direction", "title", "score"}.issubset(set(lead.keys()))
