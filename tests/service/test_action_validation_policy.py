"""Tests for action validation policy."""

from unittest.mock import MagicMock

from src.config import settings
from src.services.action_validation_policy import validate_action_intent
from src.services.command_interpreter import ActionResult, StagedActionIntent


def test_validation_bypassed_if_disabled():
    settings.enable_strict_action_validation = False

    intent = StagedActionIntent(ack_line="Okay.", result=ActionResult(narrative_text="Text", state_deltas={"apple": "dropped"}, reasoning_metadata={}))

    state_manager = MagicMock()
    state_manager.get_state_summary.return_value = {"inventory": {"items": {}}, "variables": {"location": "test"}}

    validated = validate_action_intent(intent, "I drop the apple", state_manager, world_memory_module=MagicMock(), db=MagicMock())

    # Should not block dropping since validation is false
    assert "apple" in validated.result.state_deltas
    assert validated.result.plausible is True


def test_validation_blocks_dropping_item_not_in_inventory():
    settings.enable_strict_action_validation = True

    intent = StagedActionIntent(ack_line="Okay.", result=ActionResult(narrative_text="Text", state_deltas={"apple": "dropped", "gold": 5}, reasoning_metadata={"rejected_keys": [], "validation_warnings": []}))

    state_manager = MagicMock()
    # Player has no apple
    state_manager.get_state_summary.return_value = {"inventory": {"items": {"apple": False, "sword": True}}, "variables": {"location": "test"}}

    validated = validate_action_intent(intent, "I drop the apple", state_manager, world_memory_module=MagicMock(), db=MagicMock())

    # Apple drop blocked
    assert "apple" not in validated.result.state_deltas
    # Gold kept
    assert "gold" in validated.result.state_deltas

    warnings = validated.result.reasoning_metadata["validation_warnings"]
    assert "policy_blocked_inventory_removal:apple" in warnings


def test_validation_implausible_if_all_deltas_blocked():
    settings.enable_strict_action_validation = True

    intent = StagedActionIntent(ack_line="Okay.", result=ActionResult(narrative_text="You drop the missing item.", state_deltas={"apple": "dropped"}, reasoning_metadata={"rejected_keys": [], "validation_warnings": []}))

    state_manager = MagicMock()
    state_manager.get_state_summary.return_value = {"inventory": {"items": {"apple": False}}, "variables": {"location": "test"}}

    validated = validate_action_intent(intent, "I drop the apple", state_manager, world_memory_module=MagicMock(), db=MagicMock())

    assert not validated.result.state_deltas
    assert validated.result.plausible is False
    assert "conflicts with the current state of things" in validated.ack_line
