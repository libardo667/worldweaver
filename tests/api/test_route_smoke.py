"""Route smoke tests for core API surface stability."""

from src.models import Storylet


def test_health_route_smoke(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_next_route_smoke(seeded_client):
    response = seeded_client.post("/api/next", json={"session_id": "smoke-next", "vars": {}})
    assert response.status_code == 200


def test_action_route_smoke(client):
    response = client.post("/api/action", json={"session_id": "smoke-action"})
    assert response.status_code == 422


def test_spatial_navigation_route_smoke(seeded_client, seeded_db):
    seeded_db.add(
        Storylet(
            title="smoke-navigation-start",
            text_template="A reliable start marker.",
            requires={"location": "start"},
            choices=[{"label": "Wait", "set": {}}],
            weight=1.0,
            position={"x": 0, "y": 0},
        )
    )
    seeded_db.commit()

    session_id = "smoke-navigation"
    seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})
    response = seeded_client.get(f"/api/spatial/navigation/{session_id}")
    assert response.status_code == 200


def test_spatial_move_route_smoke(seeded_client):
    session_id = "smoke-move"
    seeded_client.post("/api/next", json={"session_id": session_id, "vars": {}})
    response = seeded_client.post(
        f"/api/spatial/move/{session_id}",
        json={"direction": "INVALID"},
    )
    assert response.status_code in (400, 422)


def test_spatial_map_route_smoke(seeded_client):
    response = seeded_client.get("/api/spatial/map")
    assert response.status_code == 200


def test_spatial_assign_positions_route_smoke(seeded_client, seeded_db):
    first_storylet = seeded_db.query(Storylet).first()
    assert first_storylet is not None

    response = seeded_client.post(
        "/api/spatial/assign-positions",
        json={"positions": [{"storylet_id": first_storylet.id, "x": 0, "y": 0}]},
    )
    assert response.status_code == 200


def test_world_history_route_smoke(client):
    response = client.get("/api/world/history")
    assert response.status_code == 200


def test_world_facts_route_smoke(client):
    response = client.get("/api/world/facts?query=bridge")
    assert response.status_code == 200


def test_author_suggest_route_smoke(client):
    response = client.post("/author/suggest", json={"n": 0, "themes": [], "bible": {}})
    assert response.status_code == 422


def test_author_populate_route_smoke(client):
    response = client.post("/author/populate", params={"target_count": 0})
    assert response.status_code == 400


def test_author_generate_world_route_smoke(client):
    response = client.post(
        "/author/generate-world",
        json={
            "description": "A world for smoke route validation.",
            "theme": "smoke",
            "confirm_delete": False,
        },
    )
    assert response.status_code == 422
