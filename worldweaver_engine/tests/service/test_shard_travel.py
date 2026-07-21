# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from src.models import SessionVars, ShardTravelHandoff, WorldEvent
from src.services import shard_travel as travel_module
from src.services.shard_travel import (
    finish_destination_arrival,
    finish_source_departure,
)


def test_departure_event_failure_stays_recoverable(db_session, monkeypatch):
    handoff = ShardTravelHandoff(
        travel_id="departure-event-retry",
        actor_id="actor-departing",
        session_id="departed-session",
        role="source",
        source_shard="source-city",
        destination_shard="destination-city",
        status="session_retired",
    )
    db_session.add(handoff)
    db_session.commit()
    monkeypatch.setattr(
        travel_module.federation_travel,
        "confirm_federated_departure",
        lambda **_kwargs: {"idempotent": True},
    )
    real_submit = travel_module.submit_world_event
    monkeypatch.setattr(
        travel_module,
        "submit_world_event",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("event failed")),
    )

    failed = finish_source_departure(db_session, handoff)

    assert failed.status_code == 202
    assert db_session.get(ShardTravelHandoff, handoff.travel_id).status == (
        "session_retired"
    )
    assert db_session.query(WorldEvent).count() == 0

    monkeypatch.setattr(travel_module, "submit_world_event", real_submit)
    recovered = finish_source_departure(
        db_session, db_session.get(ShardTravelHandoff, handoff.travel_id)
    )

    assert recovered.status_code == 200
    assert db_session.get(ShardTravelHandoff, handoff.travel_id).status == "traveling"
    assert (
        db_session.query(WorldEvent)
        .filter_by(event_type="cross_shard_departure")
        .count()
        == 1
    )


def test_arrival_event_failure_stays_recoverable(db_session, monkeypatch):
    db_session.add(
        SessionVars(
            session_id="arrived-session",
            actor_id="actor-arriving",
            vars={"location": "Station"},
        )
    )
    handoff = ShardTravelHandoff(
        travel_id="arrival-event-retry",
        actor_id="actor-arriving",
        session_id="arrived-session",
        role="destination",
        source_shard="source-city",
        destination_shard="destination-city",
        status="session_booted",
    )
    db_session.add(handoff)
    db_session.commit()
    monkeypatch.setattr(
        travel_module.federation_travel,
        "confirm_federated_arrival",
        lambda **_kwargs: {"idempotent": True},
    )
    real_submit = travel_module.submit_world_event
    monkeypatch.setattr(
        travel_module,
        "submit_world_event",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("event failed")),
    )

    failed = finish_destination_arrival(
        db_session,
        handoff,
        player=None,
        world_id="test-world",
    )

    assert failed.status_code == 202
    assert db_session.get(ShardTravelHandoff, handoff.travel_id).status == (
        "session_booted"
    )
    assert db_session.query(WorldEvent).count() == 0

    monkeypatch.setattr(travel_module, "submit_world_event", real_submit)
    recovered = finish_destination_arrival(
        db_session,
        db_session.get(ShardTravelHandoff, handoff.travel_id),
        player=None,
        world_id="test-world",
    )

    assert recovered.status_code == 200
    assert db_session.get(ShardTravelHandoff, handoff.travel_id).status == "arrived"
    assert (
        db_session.query(WorldEvent).filter_by(event_type="cross_shard_arrival").count()
        == 1
    )
