"""The retired freeform narrator fails honestly and performs no work."""


def test_freeform_action_route_is_an_explicit_tombstone(client):
    response = client.post(
        "/api/action",
        json={"session_id": "old-client", "action": "invent an outcome"},
    )

    assert response.status_code == 410
    assert response.json()["detail"]["error"] == "freeform_action_removed"


def test_streaming_action_route_is_the_same_tombstone(client):
    response = client.post(
        "/api/action/stream",
        json={"session_id": "old-client", "action": "invent an outcome"},
    )

    assert response.status_code == 410
    assert response.json()["detail"]["error"] == "freeform_action_removed"
