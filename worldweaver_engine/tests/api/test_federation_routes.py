from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.api.federation.routes import (
    PulseRequest,
    PulseResidentItem,
    StartTravelRequest,
    TravelTransitionRequest,
    get_traveler_history,
    mark_travel_arrived,
    mark_travel_departed,
    receive_pulse,
    start_travel,
)
from src.models import FederationActor, FederationResident, FederationShard, FederationTraveler


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
        departure_hub="Union Station",
        arrival_hub="Transbay Terminal",
        reason="visit a friend",
    )

    started = start_travel(request, db_session, None)
    repeated_start = start_travel(request, db_session, None)

    assert started["travel"]["status"] == "departing"
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
