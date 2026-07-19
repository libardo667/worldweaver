from __future__ import annotations

import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from src.api.federation.routes import (
    PulseRequest,
    PulseResidentItem,
    RegisterShardRequest,
    StartTravelRequest,
    TravelTransitionRequest,
    _require_node,
    get_traveler_history,
    mark_travel_arrived,
    mark_travel_departed,
    receive_pulse,
    register_shard,
    list_shards,
    start_travel,
)
from src.models import FederationActor, FederationResident, FederationShard, FederationTraveler
from src.database import get_db
from src.services.federation_node_auth import (
    NODE_ID_HEADER,
    NODE_NONCE_HEADER,
    NODE_PUBLIC_KEY_HEADER,
    NODE_SIGNATURE_HEADER,
    NODE_TIMESTAMP_HEADER,
    AuthenticatedNode,
    generate_node_identity,
    signed_request_headers,
)


def _request(method: str, path: str, body: bytes) -> Request:
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "headers": [],
            "scheme": "https",
            "server": ("directory.example", 443),
            "client": ("127.0.0.1", 1234),
        },
        receive,
    )


async def _authenticate_signed_request(db_session, *, method, path, body, headers):
    return await _require_node(
        _request(method, path, body),
        db_session,
        None,
        headers.get(NODE_ID_HEADER),
        headers.get(NODE_TIMESTAMP_HEADER),
        headers.get(NODE_NONCE_HEADER),
        headers.get(NODE_SIGNATURE_HEADER),
        headers.get(NODE_PUBLIC_KEY_HEADER),
    )


def _seed_travel_nodes_and_actor(db_session):
    db_session.add_all(
        [
            FederationShard(
                shard_id="rose-city-coop-1",
                shard_url="https://portland.example",
                shard_type="city",
                city_id="portland",
            ),
            FederationShard(
                shard_id="bay-commons-1",
                shard_url="https://san-francisco.example",
                shard_type="city",
                city_id="san_francisco",
            ),
            FederationActor(
                actor_id="actor-traveler",
                actor_type="agent",
                display_name="Test Traveler",
                home_shard="rose-city-coop-1",
                current_shard="rose-city-coop-1",
                status="active",
                origin="doula",
            ),
            FederationResident(
                resident_id="actor-traveler",
                name="Test Traveler",
                home_shard="rose-city-coop-1",
                current_shard="rose-city-coop-1",
                resident_type="agent",
                status="active",
            ),
        ]
    )
    db_session.commit()


@pytest.mark.asyncio
async def test_signed_registration_binds_node_key_and_rejects_replay(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr("src.api.federation.routes.settings.federation_token", "")
    private_key = tmp_path / "identity" / "node.key"
    descriptor = generate_node_identity(
        private_key_path=private_key,
        descriptor_path=tmp_path / "node.json",
        node_id="river-coop-1",
        shard_type="city",
        city_id="portland",
    )
    payload_data = {
        "shard_id": "river-coop-1",
        "shard_url": "https://portland.example",
        "client_url": "https://play.portland.example",
        "shard_type": "city",
        "city_id": "portland",
    }
    body = json.dumps(payload_data).encode("utf-8")
    headers = signed_request_headers(
        node_id="river-coop-1",
        private_key_path=private_key,
        method="POST",
        path="/api/federation/register",
        body=body,
        include_public_key=True,
    )

    principal = await _authenticate_signed_request(
        db_session,
        method="POST",
        path="/api/federation/register",
        body=body,
        headers=headers,
    )
    response = register_shard(RegisterShardRequest(**payload_data), db_session, principal)
    shard = db_session.get(FederationShard, "river-coop-1")

    assert response["registered"] is True
    assert principal == AuthenticatedNode(
        node_id="river-coop-1",
        public_key=descriptor["public_key"],
        method="signature",
    )
    assert shard.public_key == descriptor["public_key"]
    assert shard.identity_bound_at is not None

    with pytest.raises(HTTPException) as replay:
        await _authenticate_signed_request(
            db_session,
            method="POST",
            path="/api/federation/register",
            body=body,
            headers=headers,
        )
    assert replay.value.status_code == 409
    assert "already used" in str(replay.value.detail)


def test_signed_registration_and_replay_guard_work_through_http(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr("src.api.federation.routes.settings.federation_token", "")
    private_key = tmp_path / "identity" / "node.key"
    descriptor = generate_node_identity(
        private_key_path=private_key,
        descriptor_path=tmp_path / "node.json",
        node_id="http-node-1",
        shard_type="city",
        city_id="portland",
    )
    payload_data = {
        "shard_id": "http-node-1",
        "shard_url": "https://http-node.example",
        "client_url": "https://play.http-node.example",
        "shard_type": "city",
        "city_id": "portland",
    }
    body = json.dumps(payload_data).encode("utf-8")
    headers = signed_request_headers(
        node_id="http-node-1",
        private_key_path=private_key,
        method="POST",
        path="/api/federation/register",
        body=body,
        include_public_key=True,
    )
    app = FastAPI()
    from src.api.federation.routes import router

    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    attacker_key = tmp_path / "attacker" / "node.key"
    generate_node_identity(
        private_key_path=attacker_key,
        descriptor_path=tmp_path / "attacker.json",
        node_id="http-node-1",
        shard_type="city",
        city_id="portland",
    )
    attacker_headers = signed_request_headers(
        node_id="http-node-1",
        private_key_path=attacker_key,
        method="POST",
        path="/api/federation/register",
        body=body,
        include_public_key=True,
    )

    with TestClient(app) as client:
        public_directory = client.get("/api/federation/shards")
        private_residents = client.get("/api/federation/residents")
        registered = client.post(
            "/api/federation/register",
            content=body,
            headers={"Content-Type": "application/json", **headers},
        )
        impersonation = client.post(
            "/api/federation/register",
            content=body,
            headers={"Content-Type": "application/json", **attacker_headers},
        )
        replay = client.post(
            "/api/federation/register",
            content=body,
            headers={"Content-Type": "application/json", **headers},
        )

    assert public_directory.status_code == 200
    assert private_residents.status_code == 401
    assert registered.status_code == 200
    assert registered.json()["registered"] is True
    assert db_session.get(FederationShard, "http-node-1").public_key == descriptor["public_key"]
    assert impersonation.status_code == 401
    assert "signature is invalid" in impersonation.json()["detail"]
    assert replay.status_code == 409
    assert "already used" in replay.json()["detail"]


def test_signed_node_cannot_report_for_another_node(db_session):
    db_session.add(
        FederationShard(
            shard_id="victim-node",
            shard_url="https://victim.example",
            shard_type="city",
            city_id="portland",
        )
    )
    db_session.commit()
    payload = PulseRequest(shard_id="victim-node", pulse_seq=1)

    with pytest.raises(HTTPException) as forbidden:
        receive_pulse(
            payload,
            db_session,
            AuthenticatedNode(node_id="another-node", public_key="public", method="signature"),
        )
    assert forbidden.value.status_code == 403


def test_receive_pulse_upserts_existing_resident_without_duplicate(db_session):
    db_session.add(
        FederationShard(
            shard_id="san_francisco",
            shard_url="https://world-weaver.org/ww-sfo",
            shard_type="city",
            city_id="san_francisco",
            last_pulse_seq=0,
        )
    )
    db_session.commit()

    first = PulseRequest(
        shard_id="san_francisco",
        shard_url="https://world-weaver.org/ww-sfo",
        pulse_seq=1,
        residents=[
            PulseResidentItem(
                resident_id="resident-sun-li",
                name="test_resident",
                session_id="test_resident-20260317-120000",
                location="Chinatown",
                status="active",
            )
        ],
    )
    second = PulseRequest(
        shard_id="san_francisco",
        shard_url="https://world-weaver.org/ww-sfo",
        pulse_seq=2,
        residents=[
            PulseResidentItem(
                resident_id="resident-sun-li",
                name="test_resident",
                session_id="test_resident-20260317-120000",
                location="Inner Richmond",
                status="active",
            )
        ],
    )

    first_response = receive_pulse(first, db_session, None)
    second_response = receive_pulse(second, db_session, None)

    assert first_response["accepted"] is True
    assert second_response["accepted"] is True

    residents = db_session.query(FederationResident).all()
    assert len(residents) == 1
    assert residents[0].resident_id == "resident-sun-li"
    assert residents[0].last_location == "Inner Richmond"


def test_registry_keeps_api_and_human_client_urls_separate(db_session):
    registered = register_shard(
        RegisterShardRequest(
            shard_id="alderbank-node",
            shard_url="https://api.alderbank.example",
            client_url="https://alderbank.example",
            shard_type="city",
            city_id="alderbank",
        ),
        db_session,
        None,
    )

    assert registered["registered"] is True
    listed = list_shards(db_session)["shards"]
    assert listed[0]["shard_url"] == "https://api.alderbank.example"
    assert listed[0]["client_url"] == "https://alderbank.example"

    pulse = PulseRequest(
        shard_id="alderbank-node",
        shard_url="https://api-2.alderbank.example",
        client_url="https://play.alderbank.example",
        pulse_seq=1,
    )
    receive_pulse(pulse, db_session, None)
    row = db_session.get(FederationShard, "alderbank-node")
    assert row.shard_url == "https://api-2.alderbank.example"
    assert row.client_url == "https://play.alderbank.example"


def test_receive_pulse_rejects_stale_seq_with_last_seq(db_session):
    db_session.add(
        FederationShard(
            shard_id="san_francisco",
            shard_url="https://world-weaver.org/ww-sfo",
            shard_type="city",
            city_id="san_francisco",
            last_pulse_seq=4242,
        )
    )
    db_session.commit()

    payload = PulseRequest(
        shard_id="san_francisco",
        shard_url="https://world-weaver.org/ww-sfo",
        pulse_seq=4242,
        residents=[],
    )

    response = receive_pulse(payload, db_session, None)

    assert response["accepted"] is False
    assert response["reason"] == "stale_pulse"
    assert response["last_seq"] == 4242


def test_receive_pulse_rejects_oversized_seq_without_500(db_session):
    db_session.add(
        FederationShard(
            shard_id="portland",
            shard_url="https://world-weaver.org/ww-pdx",
            shard_type="city",
            city_id="portland",
            last_pulse_seq=100,
        )
    )
    db_session.commit()

    payload = PulseRequest(
        shard_id="portland",
        shard_url="https://world-weaver.org/ww-pdx",
        pulse_seq=9_999_999_999,
        residents=[],
    )

    response = receive_pulse(payload, db_session, None)

    assert response["accepted"] is False
    assert response["reason"] == "invalid_pulse_seq"
    assert response["last_seq"] == 100


def test_travel_lifecycle_is_idempotent_and_changes_node_only_on_arrival(db_session):
    _seed_travel_nodes_and_actor(db_session)
    request = StartTravelRequest(
        travel_id="trip-test-001",
        actor_id="actor-traveler",
        source_shard="rose-city-coop-1",
        destination_shard="bay-commons-1",
        departure_hub_id="portland-union-station",
        departure_hub="Union Station",
        arrival_hub_id="transbay-bart",
        arrival_hub="Transbay Terminal",
        reason="visit a friend",
    )

    started = start_travel(request, db_session, None)
    repeated_start = start_travel(request, db_session, None)

    assert started["travel"]["status"] == "departing"
    assert started["travel"]["departure_hub_id"] == "portland-union-station"
    assert started["travel"]["arrival_hub_id"] == "transbay-bart"
    assert started["idempotent"] is False
    assert repeated_start["idempotent"] is True
    assert db_session.query(FederationTraveler).count() == 1

    departed = mark_travel_departed(
        "trip-test-001",
        TravelTransitionRequest(shard_id="rose-city-coop-1"),
        db_session,
        None,
    )
    repeated_departure = mark_travel_departed(
        "trip-test-001",
        TravelTransitionRequest(shard_id="rose-city-coop-1"),
        db_session,
        None,
    )

    assert departed["travel"]["status"] == "traveling"
    assert repeated_departure["idempotent"] is True
    actor = db_session.get(FederationActor, "actor-traveler")
    assert actor.status == "traveling"
    assert actor.current_shard == "rose-city-coop-1"

    arrived = mark_travel_arrived(
        "trip-test-001",
        TravelTransitionRequest(shard_id="bay-commons-1"),
        db_session,
        None,
    )
    repeated_arrival = mark_travel_arrived(
        "trip-test-001",
        TravelTransitionRequest(shard_id="bay-commons-1"),
        db_session,
        None,
    )

    assert arrived["travel"]["status"] == "arrived"
    assert repeated_arrival["idempotent"] is True
    assert actor.status == "active"
    assert actor.current_shard == "bay-commons-1"
    resident = db_session.get(FederationResident, "actor-traveler")
    assert resident.status == "active"
    assert resident.current_shard == "bay-commons-1"

    history = get_traveler_history("actor-traveler", db_session)
    assert history["actor_id"] == "actor-traveler"
    assert history["travel_history"][0]["travel_id"] == "trip-test-001"
    assert history["travel_history"][0]["status"] == "arrived"


def test_travel_lifecycle_enforces_source_destination_ownership_and_order(db_session):
    _seed_travel_nodes_and_actor(db_session)
    start_travel(
        StartTravelRequest(
            travel_id="trip-test-002",
            actor_id="actor-traveler",
            source_shard="rose-city-coop-1",
            destination_shard="bay-commons-1",
        ),
        db_session,
        None,
    )

    with pytest.raises(HTTPException) as wrong_departure_node:
        mark_travel_departed(
            "trip-test-002",
            TravelTransitionRequest(shard_id="bay-commons-1"),
            db_session,
            None,
        )
    assert wrong_departure_node.value.status_code == 403

    with pytest.raises(HTTPException) as early_arrival:
        mark_travel_arrived(
            "trip-test-002",
            TravelTransitionRequest(shard_id="bay-commons-1"),
            db_session,
            None,
        )
    assert early_arrival.value.status_code == 409

    with pytest.raises(HTTPException) as conflicting_retry:
        start_travel(
            StartTravelRequest(
                travel_id="trip-test-002",
                actor_id="actor-traveler",
                source_shard="rose-city-coop-1",
                destination_shard="somewhere-else",
            ),
            db_session,
            None,
        )
    assert conflicting_retry.value.status_code == 409
