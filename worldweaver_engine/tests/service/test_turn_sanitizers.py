from src.services.turn.sanitizers import (
    normalize_following_beats,
    sanitize_action_payload,
    sanitize_state_changes,
)


def test_sanitize_state_changes_drops_invalid_keys_and_coerces_environment():
    rejected = []
    warnings = []
    appended_facts = []

    result = sanitize_state_changes(
        raw_state_changes={
            "variables": {"good_key": 3, "bad key": 7},
            "environment": {"danger_level": "12", "weather": "storm"},
        },
        raw_delta_contract={
            "set": {"bridge_state": "fragile"},
            "append_fact": [{"subject": "bridge", "predicate": "status", "value": "fragile"}],
        },
        state_summary={"variables": {"good_key": 1}},
        rejected_keys=rejected,
        warnings=warnings,
        appended_facts=appended_facts,
    )

    assert result["bridge_state"] == "fragile"
    assert result["good_key"] == 3
    assert result["environment"] == {"danger_level": 10, "weather": "storm"}
    assert "bad key" in rejected
    assert appended_facts[0]["subject"] == "bridge"


def test_sanitize_action_payload_uses_heuristic_fallbacks():
    result = sanitize_action_payload(
        "inspect the bridge",
        {
            "narrative": "You inspect the bridge carefully.",
            "plausible": True,
            "state_changes": {"variables": {"bridge_state": "fragile"}},
            "choices": [{"label": "Retreat", "set": {"stance": "cautious"}}],
            "goal_update": None,
            "following_beat": None,
        },
        {"variables": {"location": "bridge"}},
        ["The bridge is brittle."],
        heuristic_following_beats_fn=lambda action: [{"name": "IncreasingTension", "turns_remaining": 3}],
        heuristic_goal_update_fn=lambda action, state_summary: {"status": "progressed", "milestone": "Bridge inspected"},
        sanitize_follow_up_choices_fn=lambda raw_choices, rejected_keys: raw_choices,
    )

    assert result.state_deltas["bridge_state"] == "fragile"
    assert result.follow_up_choices[0]["label"] == "Retreat"
    assert result.suggested_beats[0]["name"] == "IncreasingTension"
    assert result.reasoning_metadata["goal_update"]["milestone"] == "Bridge inspected"
