"""Shared action sanitization helpers for the turn pipeline."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

from ...models.schemas import ActionDeltaContract, ActionReasoningMetadata
from .types import ActionResult

_MAX_VARIABLE_CHANGES = 20
_MAX_DELTA_DEPTH = 3
_MAX_APPEND_FACTS = 5
_MAX_FACTS_IN_CONTEXT = 8
_MAX_SUGGESTED_BEATS = 3
_KEY_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-]{0,63}$")
_BLOCKED_VAR_KEYS = {
    "session_id",
    "session",
    "db",
    "database",
    "__proto__",
    "prototype",
    "constructor",
    "set",
    "increment",
    "append_fact",
    "variables",
}
_ENV_INT_FIELDS = {"temperature", "danger_level", "noise_level"}
_ENV_STR_FIELDS = {"time_of_day", "weather", "season", "lighting", "air_quality"}
_ALLOWED_BEAT_NAMES = {
    "increasingtension": "IncreasingTension",
    "thematicresonance": "ThematicResonance",
    "catharsis": "Catharsis",
}
_DROP = object()


def _truncate_text(value: Any, max_len: int = 1000) -> str:
    text = str(value or "").strip()
    if len(text) > max_len:
        return text[:max_len]
    return text


def safe_variable_key(raw_key: Any) -> Optional[str]:
    key = str(raw_key or "").strip()
    if not key:
        return None
    if key.startswith("__"):
        return None
    if key.lower() in _BLOCKED_VAR_KEYS:
        return None
    if not _KEY_PATTERN.match(key):
        return None
    return key


def coerce_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def sanitize_value(value: Any, depth: int = 0) -> Any:
    if depth > _MAX_DELTA_DEPTH:
        return _DROP

    if value is None:
        return None

    if isinstance(value, (bool, int, float)):
        return value

    if isinstance(value, str):
        return _truncate_text(value, max_len=400)

    if isinstance(value, list):
        out: List[Any] = []
        for item in value[:10]:
            sanitized = sanitize_value(item, depth + 1)
            if sanitized is not _DROP:
                out.append(sanitized)
        return out

    if isinstance(value, dict):
        out_dict: Dict[str, Any] = {}
        for key, item in list(value.items())[:10]:
            key_text = _truncate_text(key, max_len=64)
            if key_text.startswith("__"):
                continue
            sanitized = sanitize_value(item, depth + 1)
            if sanitized is not _DROP:
                out_dict[key_text] = sanitized
        return out_dict

    return _DROP


def _add_variable_change(
    variable_changes: Dict[str, Any],
    key: Any,
    value: Any,
    rejected_keys: List[str],
    warnings: List[str],
) -> None:
    safe_key = safe_variable_key(key)
    if not safe_key:
        rejected_keys.append(str(key))
        return

    sanitized_value = sanitize_value(value)
    if sanitized_value is _DROP:
        rejected_keys.append(safe_key)
        return

    if len(variable_changes) >= _MAX_VARIABLE_CHANGES and safe_key not in variable_changes:
        warnings.append("max_variable_delta_limit_reached")
        return

    variable_changes[safe_key] = sanitized_value


def sanitize_environment_changes(raw_environment: Any, warnings: List[str]) -> Dict[str, Any]:
    if not isinstance(raw_environment, dict):
        return {}

    out: Dict[str, Any] = {}
    for key, value in raw_environment.items():
        key_text = str(key or "").strip()
        if key_text in _ENV_INT_FIELDS:
            numeric = coerce_number(value)
            if numeric is None:
                warnings.append(f"dropped_environment_{key_text}")
                continue
            coerced = int(round(numeric))
            if key_text in {"danger_level", "noise_level"}:
                coerced = max(0, min(10, coerced))
            out[key_text] = coerced
        elif key_text in _ENV_STR_FIELDS:
            out[key_text] = _truncate_text(value, max_len=64)
    return out


def sanitize_spatial_nodes(raw_nodes: Any, warnings: List[str]) -> Dict[str, Any]:
    if not isinstance(raw_nodes, dict):
        return {}

    out: Dict[str, Any] = {}
    for location_key, payload in list(raw_nodes.items())[:10]:
        loc = _truncate_text(location_key, max_len=64)
        if not loc:
            continue

        if isinstance(payload, dict):
            sanitized_payload: Dict[str, Any] = {}
            for attr, value in list(payload.items())[:10]:
                attr_key = _truncate_text(attr, max_len=64)
                sanitized = sanitize_value(value)
                if sanitized is _DROP:
                    warnings.append(f"dropped_spatial_value_{loc}.{attr_key}")
                    continue
                sanitized_payload[attr_key] = sanitized
            if sanitized_payload:
                out[loc] = sanitized_payload
        else:
            sanitized = sanitize_value(payload)
            if sanitized is not _DROP:
                out[loc] = {"state": sanitized}
    return out


def _coerce_contract_payload(raw_contract: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw_contract, dict):
        return None

    payload: Dict[str, Any] = {}

    set_ops = raw_contract.get("set")
    if isinstance(set_ops, dict):
        payload["set"] = [{"key": key, "value": value} for key, value in set_ops.items()]
    elif isinstance(set_ops, list):
        payload["set"] = set_ops

    inc_ops = raw_contract.get("increment")
    if isinstance(inc_ops, dict):
        payload["increment"] = [{"key": key, "amount": value} for key, value in inc_ops.items()]
    elif isinstance(inc_ops, list):
        payload["increment"] = inc_ops

    append_ops = raw_contract.get("append_fact")
    if isinstance(append_ops, dict):
        payload["append_fact"] = [append_ops]
    elif isinstance(append_ops, list):
        payload["append_fact"] = append_ops

    if not payload:
        return None
    return payload


def _apply_contract_operations(
    raw_contract: Any,
    state_summary: Dict[str, Any],
    variable_changes: Dict[str, Any],
    appended_facts: List[Dict[str, Any]],
    rejected_keys: List[str],
    warnings: List[str],
) -> None:
    payload = _coerce_contract_payload(raw_contract)
    if payload is None:
        return

    try:
        contract = ActionDeltaContract.model_validate(payload)
    except Exception:
        warnings.append("invalid_delta_contract_dropped")
        return

    for op in contract.set:
        _add_variable_change(
            variable_changes,
            op.key,
            op.value,
            rejected_keys,
            warnings,
        )

    variables = state_summary.get("variables", {})
    if not isinstance(variables, dict):
        variables = {}

    for op in contract.increment:
        safe_key = safe_variable_key(op.key)
        if not safe_key:
            rejected_keys.append(str(op.key))
            continue

        current_value = variables.get(safe_key, 0)
        current_number = coerce_number(current_value)
        if current_number is None:
            warnings.append(f"increment_dropped_non_numeric_{safe_key}")
            continue

        next_value = current_number + float(op.amount)
        if isinstance(current_value, int) and float(op.amount).is_integer():
            variable_changes[safe_key] = int(round(next_value))
        else:
            variable_changes[safe_key] = float(next_value)

    for op in contract.append_fact[:_MAX_APPEND_FACTS]:
        appended_facts.append(op.model_dump())


def sanitize_state_changes(
    raw_state_changes: Any,
    raw_delta_contract: Any,
    state_summary: Dict[str, Any],
    rejected_keys: List[str],
    warnings: List[str],
    appended_facts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    variable_changes: Dict[str, Any] = {}
    sanitized_delta: Dict[str, Any] = {}

    _apply_contract_operations(
        raw_delta_contract,
        state_summary,
        variable_changes,
        appended_facts,
        rejected_keys,
        warnings,
    )

    if not isinstance(raw_state_changes, dict):
        if raw_state_changes not in (None, {}):
            warnings.append("state_changes_not_dict_dropped")
    else:
        _apply_contract_operations(
            {
                "set": raw_state_changes.get("set"),
                "increment": raw_state_changes.get("increment"),
                "append_fact": raw_state_changes.get("append_fact"),
            },
            state_summary,
            variable_changes,
            appended_facts,
            rejected_keys,
            warnings,
        )

        raw_environment = raw_state_changes.get("environment")
        environment = sanitize_environment_changes(raw_environment, warnings)
        if environment:
            sanitized_delta["environment"] = environment

        raw_spatial = raw_state_changes.get("spatial_nodes")
        spatial_nodes = sanitize_spatial_nodes(raw_spatial, warnings)
        if spatial_nodes:
            sanitized_delta["spatial_nodes"] = spatial_nodes

        raw_variables = raw_state_changes.get("variables")
        if isinstance(raw_variables, dict):
            for key, value in raw_variables.items():
                _add_variable_change(variable_changes, key, value, rejected_keys, warnings)

        for key, value in raw_state_changes.items():
            if key in {
                "variables",
                "environment",
                "spatial_nodes",
                "set",
                "increment",
                "append_fact",
            }:
                continue
            if key in {"permanent", "_permanent"}:
                sanitized_delta["_permanent"] = bool(value)
                continue
            _add_variable_change(variable_changes, key, value, rejected_keys, warnings)

    for key, value in variable_changes.items():
        sanitized_delta[key] = value

    return sanitized_delta


def sanitize_choice_set(raw_set: Any, rejected_keys: List[str]) -> Dict[str, Any]:
    if not isinstance(raw_set, dict):
        return {}

    out: Dict[str, Any] = {}
    for key, value in list(raw_set.items())[:5]:
        safe_key = safe_variable_key(key)
        if not safe_key:
            rejected_keys.append(str(key))
            continue
        sanitized = sanitize_value(value)
        if sanitized is _DROP:
            rejected_keys.append(safe_key)
            continue
        out[safe_key] = sanitized
    return out


def _canonicalize_beat_name(name: Any) -> Optional[str]:
    key = "".join(ch for ch in str(name or "").lower() if ch.isalnum())
    if key in _ALLOWED_BEAT_NAMES:
        return _ALLOWED_BEAT_NAMES[key]
    return None


def _sanitize_suggested_beat(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None

    normalized_name = _canonicalize_beat_name(raw.get("name"))
    if not normalized_name:
        return None

    intensity = coerce_number(raw.get("intensity"))
    if intensity is None:
        intensity = 0.35
    turns = coerce_number(raw.get("turns", raw.get("turns_remaining")))
    if turns is None:
        turns = 3
    decay = coerce_number(raw.get("decay"))
    if decay is None:
        decay = 0.65

    intensity = max(0.05, min(1.5, float(intensity)))
    turns_int = max(1, min(8, int(round(turns))))
    decay = max(0.1, min(1.0, float(decay)))

    return {
        "name": normalized_name,
        "intensity": intensity,
        "turns_remaining": turns_int,
        "decay": decay,
        "source": "llm",
    }


def normalize_following_beats(
    raw: Any,
    action: str,
    *,
    heuristic_following_beats_fn: Callable[[str], List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    candidates: List[Any] = []
    if isinstance(raw, list):
        candidates = raw[:_MAX_SUGGESTED_BEATS]
    elif isinstance(raw, dict):
        candidates = [raw]

    for candidate in candidates:
        beat = _sanitize_suggested_beat(candidate)
        if beat:
            normalized.append(beat)

    if normalized:
        return normalized[:_MAX_SUGGESTED_BEATS]

    return heuristic_following_beats_fn(action)


def sanitize_goal_update(
    raw_goal_update: Any,
    *,
    action: str,
    state_summary: Dict[str, Any],
    heuristic_goal_update_fn: Callable[[str, Dict[str, Any]], Optional[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    statuses = {"progressed", "complicated", "derailed", "branched", "completed"}
    if not isinstance(raw_goal_update, dict):
        return heuristic_goal_update_fn(action, state_summary)

    status = str(raw_goal_update.get("status", "progressed")).strip().lower()
    if status not in statuses:
        status = "progressed"

    milestone = _truncate_text(raw_goal_update.get("milestone", ""), max_len=220)
    note = _truncate_text(raw_goal_update.get("note", ""), max_len=220)
    subgoal = _truncate_text(raw_goal_update.get("subgoal", ""), max_len=140)

    urgency_delta = coerce_number(raw_goal_update.get("urgency_delta"))
    complication_delta = coerce_number(raw_goal_update.get("complication_delta"))
    urgency_delta = 0.0 if urgency_delta is None else max(-1.0, min(1.0, urgency_delta))
    complication_delta = 0.0 if complication_delta is None else max(-1.0, min(1.0, complication_delta))

    if not milestone and not subgoal and urgency_delta == 0.0 and complication_delta == 0.0:
        return heuristic_goal_update_fn(action, state_summary)

    return {
        "status": status,
        "milestone": milestone or "Goal state adjusted",
        "note": note,
        "subgoal": subgoal,
        "urgency_delta": urgency_delta,
        "complication_delta": complication_delta,
    }


def sanitize_action_payload(
    action: str,
    data: Dict[str, Any],
    state_summary: Dict[str, Any],
    world_facts: List[str],
    *,
    heuristic_following_beats_fn: Callable[[str], List[Dict[str, Any]]],
    heuristic_goal_update_fn: Callable[[str, Dict[str, Any]], Optional[Dict[str, Any]]],
    sanitize_follow_up_choices_fn: Callable[[Any, List[str]], List[Dict[str, Any]]],
) -> ActionResult:
    rejected_keys: List[str] = []
    warnings: List[str] = []
    appended_facts: List[Dict[str, Any]] = []

    state_deltas = sanitize_state_changes(
        raw_state_changes=data.get("state_changes", {}),
        raw_delta_contract=data.get("delta"),
        state_summary=state_summary,
        rejected_keys=rejected_keys,
        warnings=warnings,
        appended_facts=appended_facts,
    )

    narrative = _truncate_text(data.get("narrative") or f"You attempt to {action}.", max_len=1200)
    plausible = bool(data.get("plausible", True))
    should_trigger_storylet = bool(data.get("should_trigger_storylet", False))
    choices = sanitize_follow_up_choices_fn(data.get("choices", []), rejected_keys)
    suggested_beats = normalize_following_beats(
        data.get("following_beats", data.get("following_beat")),
        action=action,
        heuristic_following_beats_fn=heuristic_following_beats_fn,
    )

    goal_update = sanitize_goal_update(
        data.get("goal_update"),
        action=action,
        state_summary=state_summary,
        heuristic_goal_update_fn=heuristic_goal_update_fn,
    )

    confidence_raw = data.get("confidence")
    confidence = coerce_number(confidence_raw)
    if confidence is not None:
        confidence = max(0.0, min(1.0, confidence))

    rationale = _truncate_text(data.get("rationale", ""), max_len=400) or None

    reasoning_metadata = ActionReasoningMetadata(
        facts_considered=world_facts[:_MAX_FACTS_IN_CONTEXT],
        rejected_keys=rejected_keys[:30],
        validation_warnings=warnings[:30],
        confidence=confidence,
        rationale=rationale,
        goal_update=goal_update,
        appended_facts=appended_facts[:_MAX_APPEND_FACTS],
        suggested_beats=suggested_beats,
    ).model_dump(exclude_none=True)

    return ActionResult(
        narrative_text=narrative,
        state_deltas=state_deltas,
        should_trigger_storylet=should_trigger_storylet,
        follow_up_choices=choices,
        suggested_beats=suggested_beats,
        plausible=plausible,
        reasoning_metadata=reasoning_metadata,
    )
