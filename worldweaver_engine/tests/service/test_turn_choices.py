from src.services.turn.choices import (
    normalize_action_result_choices,
    sanitize_follow_up_choices,
)


def test_normalize_action_result_choices_preserves_intent_and_default():
    choices = normalize_action_result_choices(
        [
            {"label": "Open the door", "set": {"door": "open"}, "intent": "I open the door"},
            "bad-entry",
        ]
    )

    assert len(choices) == 1
    assert choices[0].label == "Open the door"
    assert choices[0].set == {"door": "open"}
    assert choices[0].intent == "I open the door"

    defaulted = normalize_action_result_choices(None)
    assert len(defaulted) == 1
    assert defaulted[0].label == "Continue"


def test_sanitize_follow_up_choices_uses_injected_sanitizers():
    rejected = []

    def _truncate(value, max_len):
        return str(value)[:max_len]

    def _sanitize_choice_set(raw_set, rejected_keys):
        if not isinstance(raw_set, dict):
            return {}
        out = {}
        for key, value in raw_set.items():
            if " " in str(key):
                rejected_keys.append(str(key))
                continue
            out[str(key)] = value
        return out

    choices = sanitize_follow_up_choices(
        [
            {"label": "Inspect", "set": {"good_key": True, "bad key": True}},
            {"text": "Continue onward", "set_vars": {"direction": "north"}},
        ],
        rejected,
        truncate_text_fn=_truncate,
        sanitize_choice_set_fn=_sanitize_choice_set,
    )

    assert choices[0] == {"label": "Inspect", "set": {"good_key": True}}
    assert choices[1] == {"label": "Continue onward", "set": {"direction": "north"}}
    assert rejected == ["bad key"]
