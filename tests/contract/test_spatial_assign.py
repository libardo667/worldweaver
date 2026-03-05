"""Contract test for POST /api/spatial/assign-positions."""


def test_post_spatial_assign_positions_contract(seeded_client, seeded_db):
    from src.models import Storylet

    first = seeded_db.query(Storylet).first()
    assert first is not None
    payload = {"positions": [{"storylet_id": first.id, "x": 0, "y": 0}]}
    response = seeded_client.post("/api/spatial/assign-positions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "assigned" in data and isinstance(data["assigned"], list)
    for a in data["assigned"]:
        assert "storylet_id" in a and "x" in a and "y" in a

    # Edge case: invalid storylet_id
    bad_payload = {"positions": [{"storylet_id": 9999, "x": 0, "y": 0}]}
    bad_response = seeded_client.post("/api/spatial/assign-positions", json=bad_payload)
    assert bad_response.status_code in (400, 404)
