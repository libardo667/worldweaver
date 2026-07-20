"""Contract tests for canonical world-event submission."""

import pytest

from src.models import WorldEvent
from src.models.schemas import ActionDeltaContract, ActionDeltaSetOperation
from src.services.event_submission import (
    EventSubmissionError,
    WorldEventCommand,
    cancel_prepared_world_event,
    prepare_world_event,
    submit_prepared_world_event,
    submit_world_event,
)
from src.services.rules.schema import FreeformActionCommittedIntent
from src.services.state_manager import AdvancedStateManager
from src.services.world_memory import (
    ACTION_METADATA_KEY,
    EVENT_TYPE_FREEFORM_ACTION,
    PERMANENT_EVENT_TYPE,
)


def test_submits_observational_event_and_reports_projection(db_session):
    receipt = submit_world_event(
        db_session,
        WorldEventCommand(
            session_id="event-spine-observation",
            event_type=EVENT_TYPE_FREEFORM_ACTION,
            summary="The north gate closes.",
            delta={"environment": {"north_gate": "closed"}},
        ),
    )

    assert receipt.event_id > 0
    # Existing taxonomy promotes durable environment changes automatically.
    assert receipt.event_type == PERMANENT_EVENT_TYPE
    assert receipt.reducer_receipt is None
    assert receipt.projection_paths == ("environment.north_gate",)


def test_reduces_intent_and_persists_reducer_receipt(db_session):
    state_manager = AdvancedStateManager("event-spine-action")
    intent = FreeformActionCommittedIntent(
        action_text="Offer a careful truce.",
        delta=ActionDeltaContract(
            set=[ActionDeltaSetOperation(key="trust", value=17)],
        ),
    )

    receipt = submit_world_event(
        db_session,
        WorldEventCommand(
            session_id="event-spine-action",
            event_type=EVENT_TYPE_FREEFORM_ACTION,
            summary="A careful truce is offered.",
            intent=intent,
            state_manager=state_manager,
        ),
    )

    assert state_manager.get_variable("trust") == 17
    assert receipt.reducer_receipt is not None
    assert receipt.reducer_receipt.applied_changes == {"trust": 17}
    assert receipt.event.world_state_delta["trust"] == 17
    assert receipt.event.world_state_delta[ACTION_METADATA_KEY]["reducer_receipt"][
        "applied_changes"
    ] == {"trust": 17}


@pytest.mark.parametrize(
    "command, message",
    [
        (WorldEventCommand(event_type="", summary="Something happened."), "event_type"),
        (WorldEventCommand(event_type="system", summary="  "), "summary"),
        (
            WorldEventCommand(
                event_type="system",
                summary="Mutation without an intent.",
                state_manager=AdvancedStateManager("invalid-mutation"),
            ),
            "reducer intent",
        ),
    ],
)
def test_rejects_invalid_commands_without_writing(db_session, command, message):
    with pytest.raises(EventSubmissionError, match=message):
        submit_world_event(db_session, command)

    assert db_session.query(WorldEvent).count() == 0


def test_restores_reducer_state_when_persistence_fails(db_session, monkeypatch):
    state_manager = AdvancedStateManager("event-spine-rollback")
    state_manager.set_variable("trust", 4)
    intent = FreeformActionCommittedIntent(
        action_text="Risk trust.",
        delta=ActionDeltaContract(
            set=[ActionDeltaSetOperation(key="trust", value=88)],
        ),
    )

    def fail_record_event(**_kwargs):
        raise RuntimeError("persistence failed")

    monkeypatch.setattr("src.services.event_submission.record_event", fail_record_event)

    with pytest.raises(RuntimeError, match="persistence failed"):
        submit_world_event(
            db_session,
            WorldEventCommand(
                session_id="event-spine-rollback",
                event_type=EVENT_TYPE_FREEFORM_ACTION,
                summary="Trust is risked.",
                intent=intent,
                state_manager=state_manager,
            ),
        )

    assert state_manager.get_variable("trust") == 4
    assert db_session.query(WorldEvent).count() == 0


def test_prepared_reduction_can_be_recorded_after_response_work(db_session):
    state_manager = AdvancedStateManager("event-spine-prepared")
    prepared = prepare_world_event(
        db_session,
        state_manager,
        FreeformActionCommittedIntent(
            action_text="Hold the line.",
            delta=ActionDeltaContract(
                set=[ActionDeltaSetOperation(key="focus", value="observing")],
            ),
        ),
    )

    assert state_manager.get_variable("focus") == "observing"
    receipt = submit_prepared_world_event(
        db_session,
        WorldEventCommand(
            session_id="event-spine-prepared",
            event_type=EVENT_TYPE_FREEFORM_ACTION,
            summary="The line is held.",
        ),
        prepared,
    )

    assert receipt.reducer_receipt is prepared.reducer_receipt
    assert receipt.event.world_state_delta["focus"] == "observing"


def test_prepared_reduction_can_be_cancelled_exactly(db_session):
    state_manager = AdvancedStateManager("event-spine-cancel")
    state_manager.set_variable("trust", 9)
    prepared = prepare_world_event(
        db_session,
        state_manager,
        FreeformActionCommittedIntent(
            action_text="Risk the bond.",
            delta=ActionDeltaContract(
                set=[ActionDeltaSetOperation(key="trust", value=72)],
            ),
        ),
    )

    cancel_prepared_world_event(db_session, prepared)

    assert state_manager.get_variable("trust") == 9
    assert db_session.query(WorldEvent).count() == 0


def test_invalid_prepared_submission_restores_state(db_session):
    state_manager = AdvancedStateManager("event-spine-invalid-prepared")
    state_manager.set_variable("trust", 6)
    prepared = prepare_world_event(
        db_session,
        state_manager,
        FreeformActionCommittedIntent(
            action_text="Overreach.",
            delta=ActionDeltaContract(
                set=[ActionDeltaSetOperation(key="trust", value=91)],
            ),
        ),
    )

    with pytest.raises(EventSubmissionError, match="summary"):
        submit_prepared_world_event(
            db_session,
            WorldEventCommand(
                session_id="event-spine-invalid-prepared",
                event_type=EVENT_TYPE_FREEFORM_ACTION,
                summary="",
            ),
            prepared,
        )

    assert state_manager.get_variable("trust") == 6
    assert db_session.query(WorldEvent).count() == 0


def test_structural_event_can_share_an_outer_transaction(db_session):
    receipt = submit_world_event(
        db_session,
        WorldEventCommand(
            session_id="event-spine-transaction",
            event_type="object_placed",
            summary="A durable object is placed.",
            delta={"consequence": {"object_id": "object-1"}},
            skip_graph_extraction=True,
            skip_projection=True,
            preserve_event_type=True,
            defer_commit=True,
        ),
    )

    assert receipt.event_id > 0
    assert db_session.query(WorldEvent).count() == 1

    db_session.rollback()

    assert db_session.query(WorldEvent).count() == 0


def test_deferred_event_rejects_independent_projection_or_graph_work(db_session):
    with pytest.raises(EventSubmissionError, match="deferred commit"):
        submit_world_event(
            db_session,
            WorldEventCommand(
                session_id="event-spine-unsafe-transaction",
                event_type="object_placed",
                summary="A structurally unsafe event is attempted.",
                defer_commit=True,
            ),
        )

    assert db_session.query(WorldEvent).count() == 0
