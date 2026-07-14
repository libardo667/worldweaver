"""Contract tests for canonical world-event submission."""

import pytest

from src.models import WorldEvent
from src.models.schemas import ActionDeltaContract, ActionDeltaSetOperation
from src.services.event_submission import (
    EventSubmissionError,
    WorldEventCommand,
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
    assert receipt.event.world_state_delta[ACTION_METADATA_KEY]["reducer_receipt"]["applied_changes"] == {"trust": 17}


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
