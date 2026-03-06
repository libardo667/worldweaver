"""Integration test for coordinate assignment and fallbacks."""

from src.models import Storylet
from tests.integration_helpers import assert_ok_response


def test_coordinate_assignment_and_fallbacks(seeded_client, seeded_db):
    first = seeded_db.query(Storylet).first()
    assert first is not None
    payload = {"positions": [{"storylet_id": first.id, "x": 0, "y": 0}]}
    response = seeded_client.post("/api/spatial/assign-positions", json=payload)
    assert_ok_response(response)
    data = response.json()
    assert "assigned" in data and isinstance(data["assigned"], list)
    for a in data["assigned"]:
        assert "storylet_id" in a and "x" in a and "y" in a
