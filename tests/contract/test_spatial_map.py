"""Contract test for GET /api/spatial/map."""


def test_get_spatial_map_contract(seeded_client):
    response = seeded_client.get("/api/spatial/map")
    assert response.status_code == 200
    data = response.json()
    assert "storylets" in data and isinstance(data["storylets"], list)
