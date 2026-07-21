# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

import pytest

from src.models import SessionVars, WorldEvent, WorldFact
from src.services import movement as movement_module
from src.services.movement import move_session
from src.services.session_service import get_state_manager, save_state
from src.services.world_memory import seed_location_graph


def test_move_session_directly_uses_canonical_state_and_event_path(db_session):
    seed_location_graph(
        db_session,
        [{"name": "Tea House"}, {"name": "Market Street"}],
    )
    state = get_state_manager("direct-mover", db_session)
    state.set_variable("location", "Tea House")
    state.set_variable("player_role", "Levi — tester")
    save_state(state, db_session)

    receipt = move_session(
        db_session,
        session_id="direct-mover",
        destination="Market Street",
    )

    assert receipt.moved is True
    assert receipt.from_location == "Tea House"
    assert receipt.to_location == "Market Street"
    assert get_state_manager("direct-mover", db_session).get_variable("location") == (
        "Market Street"
    )
    event = (
        db_session.query(WorldEvent)
        .filter(
            WorldEvent.session_id == "direct-mover",
            WorldEvent.event_type == "movement",
        )
        .one()
    )
    assert event.world_state_delta["destination"] == "Market Street"
    fact = (
        db_session.query(WorldFact)
        .filter(
            WorldFact.session_id == "direct-mover",
            WorldFact.predicate == "location",
            WorldFact.is_active.is_(True),
        )
        .one()
    )
    assert fact.value == "Market Street"


def test_move_session_rolls_back_state_when_event_write_fails(db_session, monkeypatch):
    seed_location_graph(
        db_session,
        [{"name": "Tea House"}, {"name": "Market Street"}],
    )
    state = get_state_manager("rollback-mover", db_session)
    state.set_variable("location", "Tea House")
    save_state(state, db_session)

    def fail_event_write(*_args, **_kwargs):
        raise RuntimeError("event write failed")

    monkeypatch.setattr("src.services.movement.submit_world_event", fail_event_write)

    with pytest.raises(RuntimeError, match="event write failed"):
        move_session(
            db_session,
            session_id="rollback-mover",
            destination="Market Street",
        )

    row = db_session.get(SessionVars, "rollback-mover")
    assert row is not None
    assert row.vars["variables"]["location"] == "Tea House"
    assert state.get_variable("location") == "Tea House"
    assert (
        db_session.query(WorldEvent)
        .filter(WorldEvent.session_id == "rollback-mover")
        .count()
        == 0
    )


def test_skip_move_rolls_back_earlier_hops_when_the_final_event_fails(
    db_session, monkeypatch
):
    seed_location_graph(
        db_session,
        [
            {"name": "Tea House"},
            {"name": "Market Street"},
            {"name": "Hill Gate"},
        ],
    )
    state = get_state_manager("skip-rollback-mover", db_session)
    state.set_variable("location", "Tea House")
    save_state(state, db_session)

    monkeypatch.setattr(
        movement_module,
        "find_route",
        lambda *_args, **_kwargs: ["Tea House", "Market Street", "Hill Gate"],
    )
    real_submit = movement_module.submit_world_event
    submitted = 0

    def fail_final_event(*args, **kwargs):
        nonlocal submitted
        submitted += 1
        if submitted == 2:
            raise RuntimeError("final event write failed")
        return real_submit(*args, **kwargs)

    monkeypatch.setattr(movement_module, "submit_world_event", fail_final_event)

    with pytest.raises(RuntimeError, match="final event write failed"):
        move_session(
            db_session,
            session_id="skip-rollback-mover",
            destination="Hill Gate",
            skip_to_destination=True,
        )

    row = db_session.get(SessionVars, "skip-rollback-mover")
    assert row is not None
    assert row.vars["variables"]["location"] == "Tea House"
    assert state.get_variable("location") == "Tea House"
    assert (
        db_session.query(WorldEvent)
        .filter(WorldEvent.session_id == "skip-rollback-mover")
        .count()
        == 0
    )
