from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.services.command_interpreter import ActionResult
from src.services.turn.orchestration import resolve_freeform_action_interpretation


def test_resolve_freeform_action_interpretation_uses_stage_a_result(db_session):
    state_manager = MagicMock()
    staged_result = ActionResult(
        narrative_text="You orient on the ringing hammer blows.",
        state_deltas={"focus": "blacksmith"},
        should_trigger_storylet=False,
        follow_up_choices=[],
        suggested_beats=[{"name": "RisingSignal"}],
        plausible=True,
        reasoning_metadata={"goal_update": {"primary_goal": "Find the blacksmith"}},
    )
    staged_intent = SimpleNamespace(ack_line="You track the sound of metalwork.", result=staged_result)

    with (
        patch("src.services.turn.orchestration.settings.enable_staged_action_pipeline", True),
        patch("src.services.turn.orchestration.settings.enable_strict_three_layer_architecture", False),
        patch("src.services.command_interpreter.interpret_action_intent", return_value=staged_intent),
        patch("src.services.action_validation_policy.validate_action_intent", return_value=staged_intent),
    ):
        outcome = resolve_freeform_action_interpretation(
            action_text="I'm looking for the blacksmith",
            state_manager=state_manager,
            world_memory_module=MagicMock(),
            current_storylet=None,
            db=db_session,
            scene_card_now={"location": "market"},
            timings_ms={},
        )

    assert outcome.result is staged_result
    assert outcome.staged_ack_line == "You track the sound of metalwork."
    assert outcome.used_staged_pipeline is True
    assert outcome.semantic_goal == "blacksmith"
    state_manager.add_narrative_beat.assert_called_once_with({"name": "RisingSignal"})
    state_manager.apply_goal_update.assert_called_once_with(
        {"primary_goal": "Find the blacksmith"},
        source="action_interpreter",
    )


def test_resolve_freeform_action_interpretation_uses_strict_fallback_without_legacy_interpreter(db_session):
    state_manager = MagicMock()

    with (
        patch("src.services.turn.orchestration.settings.enable_staged_action_pipeline", False),
        patch("src.services.turn.orchestration.settings.enable_strict_three_layer_architecture", True),
        patch("src.services.command_interpreter.interpret_action_intent", return_value=None),
        patch("src.services.command_interpreter.interpret_action") as legacy_interpreter,
    ):
        outcome = resolve_freeform_action_interpretation(
            action_text="inspect the gate",
            state_manager=state_manager,
            world_memory_module=MagicMock(),
            current_storylet=None,
            db=db_session,
            scene_card_now={"location": "gate"},
            timings_ms={},
        )

    assert outcome.used_staged_pipeline is True
    assert outcome.result.plausible is True
    assert outcome.result.reasoning_metadata["staged_pipeline"] == "intent"
    legacy_interpreter.assert_not_called()


def test_resolve_freeform_action_interpretation_uses_legacy_interpreter_when_stage_a_unavailable(db_session):
    state_manager = MagicMock()
    legacy_result = ActionResult(
        narrative_text="You study the lock and find a weak tooth.",
        state_deltas={"lock_state": "inspected"},
        should_trigger_storylet=False,
        follow_up_choices=[],
        plausible=True,
        reasoning_metadata={},
    )

    with (
        patch("src.services.turn.orchestration.settings.enable_staged_action_pipeline", True),
        patch("src.services.turn.orchestration.settings.enable_strict_three_layer_architecture", False),
        patch("src.services.command_interpreter.interpret_action_intent", return_value=None),
        patch("src.services.command_interpreter.interpret_action", return_value=legacy_result) as legacy_interpreter,
    ):
        outcome = resolve_freeform_action_interpretation(
            action_text="inspect the lock",
            state_manager=state_manager,
            world_memory_module=MagicMock(),
            current_storylet=None,
            db=db_session,
            scene_card_now={"location": "vault"},
            timings_ms={},
        )

    assert outcome.result is legacy_result
    assert outcome.used_staged_pipeline is False
    legacy_interpreter.assert_called_once()
