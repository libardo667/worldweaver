"""Natural language command interpreter for freeform player actions."""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models.schemas import ActionDeltaContract, ActionReasoningMetadata
from .llm_client import get_llm_client, get_model, is_ai_disabled

logger = logging.getLogger(__name__)

_MAX_VARIABLE_CHANGES = 20
_MAX_DELTA_DEPTH = 3
_MAX_CHOICES = 3
_MAX_APPEND_FACTS = 5
_MAX_FACTS_IN_CONTEXT = 8
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
_DESTRUCTIVE_VERBS = (
    "burn",
    "destroy",
    "blow up",
    "collapse",
    "ruin",
    "smash",
    "break",
    "flood",
    "seal",
)
_TERMINAL_STATUS_MARKERS = (
    "destroy",
    "destroyed",
    "burn",
    "burned",
    "collapse",
    "collapsed",
    "ruin",
    "ruined",
    "break",
    "broken",
    "seal",
    "sealed",
    "flood",
    "flooded",
    "block",
    "blocked",
)
_STATUS_NORMALIZATION = {
    "destroy": "destroyed",
    "burn": "burned",
    "collapse": "collapsed",
    "ruin": "ruined",
    "break": "broken",
    "seal": "sealed",
    "flood": "flooded",
    "block": "blocked",
}
_ENV_INT_FIELDS = {"temperature", "danger_level", "noise_level"}
_ENV_STR_FIELDS = {"time_of_day", "weather", "season", "lighting", "air_quality"}
_DROP = object()


@dataclass
class ActionResult:
    """Result of interpreting a freeform player action."""

    narrative_text: str
    state_deltas: Dict[str, Any] = field(default_factory=dict)
    should_trigger_storylet: bool = False
    follow_up_choices: List[Dict[str, Any]] = field(default_factory=list)
    plausible: bool = True
    reasoning_metadata: Dict[str, Any] = field(default_factory=dict)


def _is_ai_disabled() -> bool:
    return is_ai_disabled()


def _build_action_prompt(
    action: str,
    state_summary: Dict[str, Any],
    current_storylet_text: Optional[str],
    recent_events: List[str],
    world_facts: Optional[List[str]] = None,
) -> str:
    """Build the LLM prompt for action interpretation."""
    variables = state_summary.get("variables", {})
    location = variables.get("location", "unknown")
    var_str = json.dumps(
        {k: v for k, v in variables.items() if not k.startswith("_")},
        default=str,
    )[:500]
    inventory_str = json.dumps(
        state_summary.get("inventory", {}).get("items", {}), default=str
    )[:300]
    events_str = "; ".join(recent_events[:5]) if recent_events else "None"
    facts_str = "; ".join((world_facts or [])[:5]) if world_facts else "None"

    return f"""You are the narrator of an interactive fiction world. The player has typed a freeform action. You must:

1. Determine if the action is PLAUSIBLE given the current state
2. Generate a narrative response (2-4 sentences)
3. Determine what state changes result from the action
4. Suggest 1-3 follow-up choices

CURRENT CONTEXT:
- Location: {location}
- Player state: {var_str}
- Inventory: {inventory_str}
- Current scene: {current_storylet_text or 'No active scene'}
- Recent events: {events_str}
- Known world facts: {facts_str}

PLAYER ACTION: "{action}"

Respond ONLY with valid JSON:
{{
    "plausible": true,
    "narrative": "Your narrative response...",
    "state_changes": {{}},
    "delta": {{
        "set": [{{"key": "bridge_broken", "value": true}}],
        "increment": [{{"key": "danger", "amount": 1}}],
        "append_fact": [{{"subject": "bridge", "predicate": "status", "value": "damaged"}}]
    }},
    "should_trigger_storylet": false,
    "choices": [
        {{"label": "Choice text", "set": {{}}}}
    ],
    "confidence": 0.7,
    "rationale": "Why this interpretation fits"
}}

RULES:
- If the action is implausible, set plausible=false and explain why in the narrative (in-world, not meta)
- state_changes and delta.set can only use safe variable keys (letters, digits, _, ., -)
- Keep narrative consistent with established world facts
- Never break the fourth wall"""


def _truncate_text(value: Any, max_len: int = 1000) -> str:
    text = str(value or "").strip()
    if len(text) > max_len:
        return text[:max_len]
    return text


def _safe_variable_key(raw_key: Any) -> Optional[str]:
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


def _coerce_number(value: Any) -> Optional[float]:
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


def _sanitize_value(value: Any, depth: int = 0) -> Any:
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
            sanitized = _sanitize_value(item, depth + 1)
            if sanitized is not _DROP:
                out.append(sanitized)
        return out

    if isinstance(value, dict):
        out_dict: Dict[str, Any] = {}
        for key, item in list(value.items())[:10]:
            key_text = _truncate_text(key, max_len=64)
            if key_text.startswith("__"):
                continue
            sanitized = _sanitize_value(item, depth + 1)
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
    safe_key = _safe_variable_key(key)
    if not safe_key:
        rejected_keys.append(str(key))
        return

    sanitized_value = _sanitize_value(value)
    if sanitized_value is _DROP:
        rejected_keys.append(safe_key)
        return

    if len(variable_changes) >= _MAX_VARIABLE_CHANGES and safe_key not in variable_changes:
        warnings.append("max_variable_delta_limit_reached")
        return

    variable_changes[safe_key] = sanitized_value


def _sanitize_environment_changes(raw_environment: Any, warnings: List[str]) -> Dict[str, Any]:
    if not isinstance(raw_environment, dict):
        return {}

    out: Dict[str, Any] = {}
    for key, value in raw_environment.items():
        key_text = str(key or "").strip()
        if key_text in _ENV_INT_FIELDS:
            numeric = _coerce_number(value)
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


def _sanitize_spatial_nodes(raw_nodes: Any, warnings: List[str]) -> Dict[str, Any]:
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
                sanitized = _sanitize_value(value)
                if sanitized is _DROP:
                    warnings.append(f"dropped_spatial_value_{loc}.{attr_key}")
                    continue
                sanitized_payload[attr_key] = sanitized
            if sanitized_payload:
                out[loc] = sanitized_payload
        else:
            sanitized = _sanitize_value(payload)
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
        safe_key = _safe_variable_key(op.key)
        if not safe_key:
            rejected_keys.append(str(op.key))
            continue

        current_value = variables.get(safe_key, 0)
        current_number = _coerce_number(current_value)
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


def _sanitize_state_changes(
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
        environment = _sanitize_environment_changes(raw_environment, warnings)
        if environment:
            sanitized_delta["environment"] = environment

        raw_spatial = raw_state_changes.get("spatial_nodes")
        spatial_nodes = _sanitize_spatial_nodes(raw_spatial, warnings)
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


def _sanitize_choice_set(raw_set: Any, rejected_keys: List[str]) -> Dict[str, Any]:
    if not isinstance(raw_set, dict):
        return {}

    out: Dict[str, Any] = {}
    for key, value in list(raw_set.items())[:5]:
        safe_key = _safe_variable_key(key)
        if not safe_key:
            rejected_keys.append(str(key))
            continue
        sanitized = _sanitize_value(value)
        if sanitized is _DROP:
            rejected_keys.append(safe_key)
            continue
        out[safe_key] = sanitized
    return out


def _sanitize_follow_up_choices(raw_choices: Any, rejected_keys: List[str]) -> List[Dict[str, Any]]:
    if not isinstance(raw_choices, list):
        return [{"label": "Continue", "set": {}}]

    out: List[Dict[str, Any]] = []
    for item in raw_choices[:_MAX_CHOICES]:
        if not isinstance(item, dict):
            continue
        label = _truncate_text(item.get("label") or item.get("text") or "Continue", max_len=120)
        out.append(
            {
                "label": label if label else "Continue",
                "set": _sanitize_choice_set(item.get("set") or item.get("set_vars") or {}, rejected_keys),
            }
        )

    if not out:
        return [{"label": "Continue", "set": {}}]
    return out


def _extract_relevant_world_facts(
    world_memory_module: Any,
    db: Session,
    session_id: str,
    action: str,
    location: Optional[str],
) -> List[str]:
    facts: List[str] = []
    try:
        if hasattr(world_memory_module, "get_relevant_action_facts"):
            facts = world_memory_module.get_relevant_action_facts(
                db=db,
                action=action,
                session_id=session_id,
                location=location,
                limit=_MAX_FACTS_IN_CONTEXT,
            )
            return [fact for fact in facts if isinstance(fact, str) and fact.strip()]
    except Exception:
        pass

    try:
        if hasattr(world_memory_module, "query_graph_facts"):
            graph_facts = world_memory_module.query_graph_facts(
                db,
                query=action,
                session_id=session_id,
                limit=_MAX_FACTS_IN_CONTEXT,
            )
            for fact in graph_facts:
                summary = str(getattr(fact, "summary", "") or "").strip()
                if summary:
                    facts.append(summary)
        elif hasattr(world_memory_module, "query_world_facts"):
            event_facts = world_memory_module.query_world_facts(
                db,
                query=action,
                session_id=session_id,
                limit=_MAX_FACTS_IN_CONTEXT,
            )
            for event in event_facts:
                summary = str(getattr(event, "summary", "") or "").strip()
                if summary:
                    facts.append(summary)
    except Exception:
        pass

    return facts[:_MAX_FACTS_IN_CONTEXT]


def _extract_action_targets(action: str) -> List[str]:
    action_lower = action.lower()
    targets: List[str] = []
    pattern = re.compile(
        r"\b(?:burn|destroy|blow up|collapse|ruin|smash|break|flood|seal)\s+(?:the\s+)?([a-z][a-z0-9 _-]{1,60})"
    )
    for match in pattern.finditer(action_lower):
        target = match.group(1).strip(" .,!?:;-")
        target = re.sub(r"\b(again|already|now)\b", "", target).strip()
        if target and target not in targets:
            targets.append(target)
    return targets


def _detect_action_contradiction(action: str, world_facts: List[str]) -> Optional[str]:
    action_lower = action.lower()
    if not any(verb in action_lower for verb in _DESTRUCTIVE_VERBS):
        return None

    targets = _extract_action_targets(action)
    if not targets:
        return None

    for fact in world_facts:
        fact_lower = fact.lower()
        marker = next((m for m in _TERMINAL_STATUS_MARKERS if m in fact_lower), None)
        if not marker:
            continue
        for target in targets:
            if target in fact_lower:
                normalized_marker = _STATUS_NORMALIZATION.get(marker, marker)
                return f"{target} is already {normalized_marker}"
    return None


def _sanitize_action_payload(
    action: str,
    data: Dict[str, Any],
    state_summary: Dict[str, Any],
    world_facts: List[str],
) -> ActionResult:
    rejected_keys: List[str] = []
    warnings: List[str] = []
    appended_facts: List[Dict[str, Any]] = []

    state_deltas = _sanitize_state_changes(
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
    choices = _sanitize_follow_up_choices(data.get("choices", []), rejected_keys)

    confidence_raw = data.get("confidence")
    confidence = _coerce_number(confidence_raw)
    if confidence is not None:
        confidence = max(0.0, min(1.0, confidence))

    rationale = _truncate_text(data.get("rationale", ""), max_len=400)
    if not rationale:
        rationale = None

    reasoning_metadata = ActionReasoningMetadata(
        facts_considered=world_facts[:_MAX_FACTS_IN_CONTEXT],
        rejected_keys=rejected_keys[:30],
        validation_warnings=warnings[:30],
        confidence=confidence,
        rationale=rationale,
        appended_facts=appended_facts[:_MAX_APPEND_FACTS],
    ).model_dump(exclude_none=True)

    return ActionResult(
        narrative_text=narrative,
        state_deltas=state_deltas,
        should_trigger_storylet=should_trigger_storylet,
        follow_up_choices=choices,
        plausible=plausible,
        reasoning_metadata=reasoning_metadata,
    )


def _fallback_result(action: str, reasoning_metadata: Optional[Dict[str, Any]] = None) -> ActionResult:
    """Generate a fallback result when AI is unavailable."""
    return ActionResult(
        narrative_text=(
            f"You attempt to {action.lower().rstrip('.')}. "
            "The world shifts around you, but the outcome remains uncertain."
        ),
        state_deltas={},
        should_trigger_storylet=False,
        follow_up_choices=[
            {"label": "Continue exploring", "set": {}},
            {"label": "Try something else", "set": {}},
        ],
        plausible=True,
        reasoning_metadata=reasoning_metadata or {},
    )


def interpret_action(
    action: str,
    state_manager: Any,
    world_memory_module: Any,
    current_storylet: Optional[Any],
    db: Session,
) -> ActionResult:
    """Interpret a freeform player action using LLM."""
    state_summary = state_manager.get_state_summary()

    current_text = None
    if current_storylet:
        current_text = str(getattr(current_storylet, "text_template", ""))

    recent_events: List[str] = []
    try:
        events = world_memory_module.get_world_history(
            db,
            session_id=state_manager.session_id,
            limit=5,
        )
        recent_events = [event.summary for event in events]
    except Exception:
        pass

    location = None
    variables = state_summary.get("variables", {})
    if isinstance(variables, dict):
        location = str(variables.get("location", "")) or None

    world_facts = _extract_relevant_world_facts(
        world_memory_module=world_memory_module,
        db=db,
        session_id=state_manager.session_id,
        action=action,
        location=location,
    )

    contradiction = _detect_action_contradiction(action, world_facts)
    if contradiction:
        metadata = ActionReasoningMetadata(
            facts_considered=world_facts[:_MAX_FACTS_IN_CONTEXT],
            rejected_keys=[],
            validation_warnings=[],
            contradiction=contradiction,
            rationale="Action conflicts with existing persistent world facts.",
        ).model_dump(exclude_none=True)
        target = contradiction.split(" is already ")[0]
        status = contradiction.split(" is already ")[-1]
        return ActionResult(
            narrative_text=(
                f"You try to {action.lower().rstrip('.')}, but the {target} is already {status}. "
                "You can only deal with the aftermath now."
            ),
            state_deltas={},
            should_trigger_storylet=False,
            follow_up_choices=[
                {"label": "Inspect the aftermath", "set": {}},
                {"label": "Change your plan", "set": {}},
            ],
            plausible=False,
            reasoning_metadata=metadata,
        )

    if _is_ai_disabled():
        metadata = ActionReasoningMetadata(
            facts_considered=world_facts[:_MAX_FACTS_IN_CONTEXT],
            rejected_keys=[],
            validation_warnings=["ai_disabled_or_unavailable"],
        ).model_dump(exclude_none=True)
        return _fallback_result(action, reasoning_metadata=metadata)

    client = get_llm_client()
    if not client:
        metadata = ActionReasoningMetadata(
            facts_considered=world_facts[:_MAX_FACTS_IN_CONTEXT],
            rejected_keys=[],
            validation_warnings=["llm_client_unavailable"],
        ).model_dump(exclude_none=True)
        return _fallback_result(action, reasoning_metadata=metadata)

    prompt = _build_action_prompt(
        action,
        state_summary,
        current_text,
        recent_events,
        world_facts=world_facts,
    )

    try:
        response = client.chat.completions.create(
            model=get_model(),
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a narrative AI interpreting freeform player actions "
                        "in an interactive fiction world. Respond only with valid JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=800,
        )

        payload = json.loads(response.choices[0].message.content or "{}")
        if not isinstance(payload, dict):
            payload = {}
        return _sanitize_action_payload(action, payload, state_summary, world_facts)

    except Exception as exc:
        logger.error("LLM interpretation failed: %s", exc)
        metadata = ActionReasoningMetadata(
            facts_considered=world_facts[:_MAX_FACTS_IN_CONTEXT],
            rejected_keys=[],
            validation_warnings=["llm_interpretation_exception"],
        ).model_dump(exclude_none=True)
        return _fallback_result(action, reasoning_metadata=metadata)
