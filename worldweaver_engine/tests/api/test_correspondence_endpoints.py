# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from src.models import DirectMessage, WorldEvent, WorldFact, WorldProjection


def _register(client, *, email: str, name: str) -> dict:
    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "display_name": name,
            "password": "correspondence-password-1",
            "password_confirmation": "correspondence-password-1",
            "terms_accepted": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _join(client, *, auth: dict, session_id: str, world_id: str) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {auth['token']}"}
    response = client.post(
        "/api/session/bootstrap",
        json={
            "session_id": session_id,
            "world_id": world_id,
            "player_role": auth["display_name"],
            "bootstrap_source": "correspondence-test",
            "entry_location": "Willow Court",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return headers


def test_actor_addressed_correspondence_requires_proof_and_explicit_acknowledgement(
    seeded_client, seeded_world_id, db_session, monkeypatch
):
    monkeypatch.setattr(
        "src.api.auth.routes.send_welcome_email", lambda *_args, **_kwargs: None
    )
    mara = _register(
        seeded_client, email="correspondence-mara@example.com", name="Mara"
    )
    ivo = _register(seeded_client, email="correspondence-ivo@example.com", name="Ivo")
    mara_headers = _join(
        seeded_client,
        auth=mara,
        session_id="correspondence-mara",
        world_id=seeded_world_id,
    )
    ivo_headers = _join(
        seeded_client,
        auth=ivo,
        session_id="correspondence-ivo",
        world_id=seeded_world_id,
    )
    public_event_count = db_session.query(WorldEvent).count()
    public_fact_count = db_session.query(WorldFact).count()
    public_projection_count = db_session.query(WorldProjection).count()

    payload = {
        "session_id": "correspondence-mara",
        "recipient_actor_id": ivo["actor_id"],
        "body": "I will check the footbridge tomorrow.",
    }
    anonymous = seeded_client.post("/api/world/correspondence", json=payload)
    assert anonymous.status_code == 401

    sent = seeded_client.post(
        "/api/world/correspondence", json=payload, headers=mara_headers
    )
    assert sent.status_code == 200, sent.text
    message_id = sent.json()["message_id"]

    anonymous_inbox = seeded_client.get(
        "/api/world/session/correspondence-ivo/correspondence"
    )
    assert anonymous_inbox.status_code == 401

    first_offer = seeded_client.get(
        "/api/world/session/correspondence-ivo/correspondence",
        headers=ivo_headers,
    )
    second_offer = seeded_client.get(
        "/api/world/session/correspondence-ivo/correspondence",
        headers=ivo_headers,
    )
    assert first_offer.status_code == second_offer.status_code == 200
    assert first_offer.json() == second_offer.json()
    assert first_offer.json()["messages"][0]["message_id"] == message_id

    wrong_actor = seeded_client.post(
        "/api/world/session/correspondence-mara/correspondence/acknowledge",
        json={"message_ids": [message_id]},
        headers=mara_headers,
    )
    assert wrong_actor.status_code == 403

    acknowledged = seeded_client.post(
        "/api/world/session/correspondence-ivo/correspondence/acknowledge",
        json={"message_ids": [message_id]},
        headers=ivo_headers,
    )
    assert acknowledged.status_code == 200, acknowledged.text
    assert acknowledged.json()["acknowledged_ids"] == [message_id]

    empty = seeded_client.get(
        "/api/world/session/correspondence-ivo/correspondence",
        headers=ivo_headers,
    )
    assert empty.json()["messages"] == []

    thread = seeded_client.get(
        "/api/world/session/correspondence-ivo/correspondence/threads",
        headers=ivo_headers,
    )
    assert thread.status_code == 200
    assert thread.json()["threads"][0]["counterpart_actor_id"] == mara["actor_id"]

    row = db_session.get(DirectMessage, message_id)
    assert row.sender_actor_id == mara["actor_id"]
    assert row.recipient_actor_id == ivo["actor_id"]
    assert row.acknowledged_at is not None
    assert db_session.query(WorldEvent).count() == public_event_count
    assert db_session.query(WorldFact).count() == public_fact_count
    assert db_session.query(WorldProjection).count() == public_projection_count


def test_legacy_name_and_session_addressed_dm_routes_are_retired(client):
    assert client.post("/api/world/dm", json={}).status_code == 410
    assert client.post("/api/world/dm/reply", json={}).status_code == 410
    assert client.get("/api/world/dm/inbox/test_resident").status_code == 410
    assert client.get("/api/world/dm/my-inbox/old-session").status_code == 410
    assert client.get("/api/world/dm/my-threads/old-session").status_code == 410
    assert (
        client.post("/api/world/dm/my-threads/old-session/read/thread").status_code
        == 410
    )
