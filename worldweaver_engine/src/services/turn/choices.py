"""Choice normalization helpers for turn orchestration."""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from ...models.schemas import ChoiceOut

_MAX_CHOICES = 3


def sanitize_follow_up_choices(
    raw_choices: Any,
    rejected_keys: List[str],
    *,
    truncate_text_fn: Callable[[Any, int], str],
    sanitize_choice_set_fn: Callable[[Any, List[str]], Dict[str, Any]],
    max_choices: int = _MAX_CHOICES,
) -> List[Dict[str, Any]]:
    if not isinstance(raw_choices, list):
        return [{"label": "Continue", "set": {}}]

    out: List[Dict[str, Any]] = []
    for item in raw_choices[:max_choices]:
        if not isinstance(item, dict):
            continue
        label = truncate_text_fn(
            item.get("label") or item.get("text") or "Continue",
            120,
        )
        out.append(
            {
                "label": label if label else "Continue",
                "set": sanitize_choice_set_fn(
                    item.get("set") or item.get("set_vars") or {},
                    rejected_keys,
                ),
            }
        )

    if not out:
        return [{"label": "Continue", "set": {}}]
    return out


def normalize_action_result_choices(
    raw_choices: Any,
    *,
    default_label: str = "Continue",
    emit_default_when_empty: bool = True,
    max_choices: int = _MAX_CHOICES,
) -> List[ChoiceOut]:
    out: List[ChoiceOut] = []

    if isinstance(raw_choices, list):
        for choice in raw_choices[:max_choices]:
            if not isinstance(choice, dict):
                continue
            choice_set = choice.get("set", {})
            if not isinstance(choice_set, dict):
                choice_set = {}
            payload: Dict[str, Any] = {
                "label": str(choice.get("label", default_label)),
                "set": choice_set,
            }
            intent_text = choice.get("intent")
            if intent_text and isinstance(intent_text, str):
                payload["intent"] = intent_text.strip()
            out.append(ChoiceOut(**payload))

    if out or not emit_default_when_empty:
        return out
    return [ChoiceOut(label=default_label, set={})]
