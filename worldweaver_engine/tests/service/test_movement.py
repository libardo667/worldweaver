# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from src.models import WorldEvent, WorldFact
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
