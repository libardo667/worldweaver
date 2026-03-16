from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

from src.services.turn.intent import (
    IntentDependencies,
    build_intent_prompt,
    collect_action_context,
    interpret_action_intent,
)


def _make_intent_dependencies(**overrides):
    base = dict(
        is_ai_disabled_fn=lambda: False,
        extract_relevant_world_facts_fn=lambda **kwargs: ["The bridge is brittle."],
        detect_action_contradiction_fn=lambda action, facts: None,
        goal_context_from_state_summary_fn=lambda summary: "Primary goal: Cross the bridge",
        heuristic_following_beats_fn=lambda action: [],
        heuristic_goal_update_fn=lambda action, state_summary: {"status": "progressed"},
        collect_colocation_context_fn=lambda **kwargs: [{"role": "Guard", "last_action": "Watching the rain"}],
        build_scene_card_payload_fn=lambda state_manager: {"location": "bridge", "immediate_stakes": "Rain"},
        build_sensory_palette_fn=lambda scene_card: {"sound": "rain"},
        normalize_world_fact_snippets_fn=lambda world_facts, **kwargs: list(world_facts),
        join_world_fact_snippets_fn=lambda snippets: "; ".join(snippets) if snippets else "None",
        canonical_location_rule_fn=lambda canonical_locations: "MOVE-RULE" if canonical_locations else "",
        extract_canonical_locations_fn=lambda state_manager: ["Bridge", "Market"],
        sanitize_state_changes_fn=lambda **kwargs: {"bridge_state": "fragile"},
        normalize_following_beats_fn=lambda raw, action: [{"name": "IncreasingTension", "turns_remaining": 3}],
        sanitize_goal_update_fn=lambda raw, *, action, state_summary: {"status": "progressed", "milestone": "Tested the bridge"},
        coerce_number_fn=lambda value: float(value) if value is not None else None,
        truncate_text_fn=lambda value, max_len=1000: str(value or "")[:max_len],
        ack_line_for_action_fn=lambda action, proposed=None: str(proposed or f"Ack: {action}"),
        get_llm_client_fn=lambda **kwargs: object(),
        shared_inference_policy_fn=lambda state_manager, owner_id="": object(),
        resolve_lane_model_fn=lambda override: "ref-model",
        call_json_chat_completion_fn=lambda **kwargs: {
            "ack_line": "You test the bridge.",
            "plausible": True,
            "delta": {"set": [{"key": "bridge_state", "value": "fragile"}]},
            "following_beat": {"name": "IncreasingTension", "turns": 3, "decay": 0.65},
            "goal_update": {"status": "progressed", "milestone": "Tested the bridge"},
            "confidence": 0.8,
        },
        llm_json_warning_fn=lambda exc: ["llm_json_error:test"],
    )
    base.update(overrides)
    return IntentDependencies(**base)


def test_build_intent_prompt_includes_world_facts_and_location_rule():
    deps = _make_intent_dependencies()

    prompt = build_intent_prompt(
        action="I look for the market",
        scene_card_now={"location": "bridge"},
        recent_events=["Rain lashes the old span."],
        world_facts=["The bridge is brittle."],
        deps=deps,
        canonical_locations=["Bridge", "Market"],
    )

    assert "Rain lashes the old span." in prompt
    assert "The bridge is brittle." in prompt
    assert "MOVE-RULE" in prompt


def test_collect_action_context_builds_scene_and_colocation_payload():
    deps = _make_intent_dependencies()
    state_manager = MagicMock()
    state_manager.get_state_summary.return_value = {"variables": {"location": "bridge"}, "inventory": {}}
    state_manager.session_id = "turn-intent-context"
    state_manager.get_recent_motifs.return_value = ["rain", "timber"]
    world_memory = MagicMock()
    world_memory.get_world_history.return_value = [SimpleNamespace(summary="Rain lashes the old span.")]

    context = collect_action_context(
        action="I test the bridge",
        state_manager=state_manager,
        world_memory_module=world_memory,
        current_storylet=None,
        db=MagicMock(),
        deps=deps,
    )

    assert context["world_facts"] == ["The bridge is brittle."]
    assert context["present_characters"][0]["role"] == "Guard"
    assert context["scene_card_now"]["location"] == "bridge"
    assert context["motifs_recent"] == ["rain", "timber"]


def test_interpret_action_intent_uses_extracted_stage_a_flow():
    deps = _make_intent_dependencies()
    call_json = Mock(
        return_value={
            "ack_line": "You test the bridge.",
            "plausible": True,
            "delta": {"set": [{"key": "bridge_state", "value": "fragile"}]},
            "following_beat": {"name": "IncreasingTension", "turns": 3, "decay": 0.65},
            "goal_update": {"status": "progressed", "milestone": "Tested the bridge"},
            "confidence": 0.8,
        }
    )
    deps = _make_intent_dependencies(call_json_chat_completion_fn=call_json)
    state_manager = MagicMock()
    state_manager.get_state_summary.return_value = {"variables": {"location": "bridge"}, "inventory": {}}
    state_manager.session_id = "turn-intent-stage-a"
    world_memory = MagicMock()
    world_memory.get_world_history.return_value = [SimpleNamespace(summary="Rain lashes the old span.")]

    staged = interpret_action_intent(
        action="I test the bridge",
        state_manager=state_manager,
        world_memory_module=world_memory,
        current_storylet=None,
        db=MagicMock(),
        deps=deps,
    )

    assert staged is not None
    assert staged.ack_line == "You test the bridge."
    assert staged.result.state_deltas == {"bridge_state": "fragile"}
    assert staged.result.reasoning_metadata["staged_pipeline"] == "intent"
    assert call_json.call_args.kwargs["model"] == "ref-model"
