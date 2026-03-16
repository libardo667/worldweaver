"""Natural language command interpreter for freeform player actions."""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..config import settings
from ..models.schemas import ActionDeltaContract, ActionReasoningMetadata
from . import runtime_metrics
from .llm_client import (
    InferencePolicy,
    get_llm_client,
    get_model,
    get_trace_id,
    is_ai_disabled,
    platform_shared_policy,
    run_inference_thread,
)
from .turn.choices import sanitize_follow_up_choices as _sanitize_follow_up_choices_impl
from .turn.intent import (
    IntentDependencies,
    build_intent_prompt as _build_intent_prompt_impl,
    collect_action_context as _collect_action_context_impl,
    interpret_action_intent as _interpret_action_intent_impl,
)
from .turn.narration import (
    NarrationDependencies,
    build_narration_prompt as _build_narration_prompt_impl,
    render_validated_action_narration as _render_validated_action_narration_impl,
)
from .llm_json import LLMJsonError, extract_json_object
from . import prompt_library

logger = logging.getLogger(__name__)

_MAX_VARIABLE_CHANGES = 20
_MAX_DELTA_DEPTH = 3
_MAX_CHOICES = 3
_MAX_APPEND_FACTS = 5
_MAX_FACTS_IN_CONTEXT = 8
_MAX_FACTS_IN_PROMPT = 5
_MAX_FACT_SNIPPET_CHARS = 180
_MAX_FACT_PROMPT_CHARS = 900
_MAX_SUGGESTED_BEATS = 3
_MAX_ACK_LINE_CHARS = 160
_NARRATION_MAX_TOKENS = 720
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
_HELPFUL_VERBS = (
    "help",
    "save",
    "rescue",
    "comfort",
    "heal",
    "repair",
    "rebuild",
)
_GOAL_PROGRESS_VERBS = (
    "advance",
    "progress",
    "deliver",
    "complete",
    "finish",
    "secure",
    "recover",
    "find",
)
_GOAL_COMPLICATION_VERBS = (
    "fail",
    "lose",
    "miss",
    "delay",
    "derail",
    "stuck",
    "blocked",
    "complicate",
)
_GOAL_BRANCH_VERBS = (
    "instead",
    "detour",
    "side quest",
    "also",
    "while",
    "new plan",
    "alternate",
)
_ALLOWED_BEAT_NAMES = {
    "increasingtension": "IncreasingTension",
    "thematicresonance": "ThematicResonance",
    "catharsis": "Catharsis",
}
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

# Movement intent detection — Phase 2 spatial navigation
_MOVEMENT_VERBS_RE = re.compile(
    r"""
    (?:^|\b)
    (?:
        (?:i\s+)?(?:go|head|walk|run|move|travel|ride|slip|sneak|make\s+my\s+way|make\s+your\s+way)\s+(?:to(?:ward)?|back\s+to|over\s+to)
        |(?:i\s+)?return\s+to
        |(?:i\s+)?leave\s+(?:for|toward|towards)
        |(?:i\s+)?set\s+(?:off|out)\s+(?:for|toward|towards|to)
        |(?:i\s+)?head\s+(?:for)
    )
    \s+(?:the\s+)?
    """,
    re.IGNORECASE | re.VERBOSE,
)


_VAGUE_DESTINATIONS = frozenset(
    {
        # Directional / relational — not place names
        "here",
        "there",
        "home",
        "away",
        "elsewhere",
        "somewhere",
        "anywhere",
        "outside",
        "inside",
        "upstairs",
        "downstairs",
        "out",
        "back",
        # Positional words that describe a spot, not a named place
        "side",
        "left",
        "right",
        "front",
        "center",
        "centre",
        "middle",
        "corner",
        "edge",
        "end",
        "top",
        "bottom",
        "far",
        "near",
        "entrance",
        "exit",
        "doorway",
        "window",
        "street",
        "road",
    }
)


def _detect_movement_intent(action_text: str, location_names: List[str]) -> Optional[str]:
    """Return the destination name if the action is a clear movement command.

    Uses regex to detect movement verbs, then fuzzy-matches the remainder
    against known location names. Returns the canonical name on a confident
    match, or a title-cased new destination name if movement is clearly intended
    toward an unknown place. Returns None only if no movement intent is detected.
    """
    action_lower = action_text.strip().lower()
    m = _MOVEMENT_VERBS_RE.search(action_lower)
    if not m:
        return None
    # Remainder after the verb phrase — this is the raw destination string
    remainder = action_lower[m.end() :].strip()
    if not remainder:
        return None
    # Strip trailing punctuation / extra words after the destination
    remainder = re.split(r"[.,;!?\n]", remainder)[0].strip()
    remainder = re.sub(r"\s+(and|then|to|so|but)\b.*$", "", remainder, flags=re.IGNORECASE).strip()
    # Strip trailing adverbs and filler words that creep in after a place name
    remainder = re.sub(
        r"\s+(?:immediately|quickly|slowly|quietly|carefully|suddenly|soon|now|first|next|again|already|just|still|also|together|instead|anyway|perhaps|maybe|eventually|finally)\s*$",
        "",
        remainder,
        flags=re.IGNORECASE,
    ).strip()
    if len(remainder) < 2:
        return None
    # Reject vague non-place destinations
    if remainder in _VAGUE_DESTINATIONS:
        return None
    # Reject if the remainder starts with a verb/gerund — it's an action, not a place.
    # e.g. "gesture at the empty taco baskets", "grab a coffee"
    if re.match(r"^[a-z]+(?:ing|s|ed)?\s+\b(?:at|the|a|an|my|your|his|her|their|its|some|this|that|those|these)\b", remainder):
        return None

    from difflib import SequenceMatcher

    # Tokenize remainder into meaningful words (3+ chars, no possessives)
    _STOP = {"the", "and", "for", "its", "via", "near"}
    remainder_tokens = {w.strip("'s") for w in re.findall(r"[a-z]+", remainder) if len(w) >= 3 and w not in _STOP}

    best_name: Optional[str] = None
    best_score = 0.0
    for name in location_names:
        name_lower = name.lower()
        # Sequence similarity
        score = SequenceMatcher(None, remainder, name_lower).ratio()
        # Substring check
        if remainder in name_lower or name_lower in remainder:
            score = max(score, 0.75)
        # Token overlap: boost if 2+ meaningful words from remainder appear in the node name
        if remainder_tokens:
            name_tokens = set(re.findall(r"[a-z]+", name_lower))
            overlap = remainder_tokens & name_tokens
            if len(overlap) >= 2:
                token_score = len(overlap) / len(remainder_tokens)
                score = max(score, 0.5 + token_score * 0.3)
        if score > best_score:
            best_score = score
            best_name = name
    # Threshold: 0.6 is permissive enough for "silt flats" vs "the silt flats"
    if best_score >= 0.6 and best_name:
        return best_name
    # No known location matched — player is heading somewhere new.
    words = remainder.split()
    # Reject single short/common words that aren't plausible place names.
    if len(words) == 1 and len(remainder) <= 8:
        return None
    # Reject overly long remainders — place names don't exceed ~5 words.
    if len(words) > 5:
        return None
    # Use word-boundary title-case so apostrophe-s stays lowercase ("District's" not "District'S")
    return re.sub(r"(?:^|(?<=\s))\w", lambda m: m.group().upper(), remainder)


def _coerce_non_negative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(round(value)))
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return 0
        try:
            return max(0, int(round(float(stripped))))
        except ValueError:
            return 0
    return 0


def _extract_token_usage(response: Any) -> Dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    if isinstance(usage, dict):
        prompt_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
        completion_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
        total_tokens = usage.get("total_tokens")
    else:
        prompt_tokens = getattr(usage, "prompt_tokens", getattr(usage, "input_tokens", None))
        completion_tokens = getattr(
            usage,
            "completion_tokens",
            getattr(usage, "output_tokens", None),
        )
        total_tokens = getattr(usage, "total_tokens", None)

    input_tokens = _coerce_non_negative_int(prompt_tokens)
    output_tokens = _coerce_non_negative_int(completion_tokens)
    total = _coerce_non_negative_int(total_tokens) or input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
    }


def _log_llm_call_metrics(
    *,
    operation: str,
    model: str,
    duration_ms: float,
    status: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    error_type: Optional[str] = None,
) -> None:
    payload: Dict[str, Any] = {
        "event": "command_interpreter_llm_metrics",
        "component": "command_interpreter",
        "operation": operation,
        "trace_id": get_trace_id(),
        "model": model,
        "status": status,
        "duration_ms": round(max(0.0, float(duration_ms)), 3),
        "input_tokens": int(max(0, input_tokens)),
        "output_tokens": int(max(0, output_tokens)),
        "total_tokens": int(max(0, total_tokens)),
    }
    if error_type:
        payload["error_type"] = str(error_type)
    logger.info(json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str))

    runtime_metrics.record_llm_call(
        component="command_interpreter",
        operation=operation,
        model=model,
        duration_ms=duration_ms,
        status=status,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        trace_id=get_trace_id(),
    )


def _call_json_chat_completion(
    *,
    client: Any,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout: Optional[int],
    response_format: Optional[Dict[str, str]],
    operation: str,
    frequency_penalty: Optional[float] = None,
    presence_penalty: Optional[float] = None,
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if timeout is not None:
        kwargs["timeout"] = timeout
    if response_format:
        kwargs["response_format"] = response_format
    if frequency_penalty is not None:
        kwargs["frequency_penalty"] = float(frequency_penalty)
    if presence_penalty is not None:
        kwargs["presence_penalty"] = float(presence_penalty)

    started = time.perf_counter()
    try:
        response = client.chat.completions.create(**kwargs)
        usage = _extract_token_usage(response)
        _log_llm_call_metrics(
            operation=operation,
            model=model,
            duration_ms=(time.perf_counter() - started) * 1000.0,
            status="ok",
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
            total_tokens=usage["total_tokens"],
        )
        return extract_json_object(response.choices[0].message.content or "{}")
    except Exception as exc:
        error_type = exc.error_category if isinstance(exc, LLMJsonError) else exc.__class__.__name__
        _log_llm_call_metrics(
            operation=operation,
            model=model,
            duration_ms=(time.perf_counter() - started) * 1000.0,
            status="error",
            error_type=error_type,
        )
        raise


def _llm_json_warning(exc: Exception) -> List[str]:
    if isinstance(exc, LLMJsonError):
        return [f"llm_json_error:{exc.error_category}"]
    return []


def _resolve_lane_model(override: Any) -> str:
    cleaned = str(override or "").strip()
    return cleaned or get_model()


def _shared_inference_policy(state_manager: Any, *, owner_id: str = "") -> InferencePolicy:
    session_id = str(getattr(state_manager, "session_id", "") or "").strip()
    return platform_shared_policy(owner_id=owner_id or session_id or "command_interpreter")


@dataclass
class ActionResult:
    """Result of interpreting a freeform player action."""

    narrative_text: str
    state_deltas: Dict[str, Any] = field(default_factory=dict)
    should_trigger_storylet: bool = False
    follow_up_choices: List[Dict[str, Any]] = field(default_factory=list)
    suggested_beats: List[Dict[str, Any]] = field(default_factory=list)
    plausible: bool = True
    reasoning_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StagedActionIntent:
    """Stage-A output: validated deterministic deltas plus immediate ack line."""

    ack_line: str
    result: ActionResult


def _is_ai_disabled() -> bool:
    return is_ai_disabled()


def _canonical_location_rule(canonical_locations: List[str]) -> str:
    """Return a prompt rule line for canonical location enforcement, or empty string."""
    if not canonical_locations:
        return ""
    names = ", ".join(f'"{n}"' for n in canonical_locations)
    return (
        f"- MOVEMENT RULE: If the action involves traveling to, going to, or moving toward a location, "
        f'you MUST include {{"key": "location", "value": <name>}} in delta.set. '
        f"Match the player's stated destination to the nearest entry from this list: {names}. "
        f"Use the exact string from the list. Never invent a location not on this list. "
        f"Movement is always plausible — do not set plausible=false just because travel is involved."
    )


def _extract_canonical_locations(state_manager: Any) -> List[str]:
    """Extract canonical location names from the session world bible."""
    try:
        world_bible = state_manager.get_world_bible()
    except Exception:
        return []
    if not isinstance(world_bible, dict):
        return []
    names: List[str] = []
    for loc in world_bible.get("locations", []):
        if isinstance(loc, dict):
            name = str(loc.get("name", "")).strip()
            if name:
                names.append(name)
    return names


def _build_action_prompt(
    action: str,
    scene_card_now: Dict[str, Any],
    current_storylet_text: Optional[str],
    recent_events: List[str],
    world_facts: Optional[List[str]] = None,
    canonical_locations: Optional[List[str]] = None,
    ) -> str:
    """Build the LLM prompt for action interpretation."""
    events_str = "; ".join(recent_events[:5]) if recent_events else "None"
    prompt_facts = _normalize_world_fact_snippets(
        world_facts,
        limit=_MAX_FACTS_IN_PROMPT,
        per_fact_chars=_MAX_FACT_SNIPPET_CHARS,
    )
    facts_str = _join_world_fact_snippets(prompt_facts)

    narrator_identity = prompt_library.build_action_system_prompt()

    return f"""{narrator_identity}

Your task:
1. Determine if the action is PLAUSIBLE given the current state
2. Generate a narrative response (2-4 sentences)
3. Determine what state changes result from the action
4. Suggest 1-3 follow-up choices

CURRENT CONTEXT:
- Scene Card: {json.dumps(scene_card_now, ensure_ascii=False)}
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
    "following_beat": {{
        "name": "IncreasingTension",
        "intensity": 0.35,
        "turns": 3,
        "decay": 0.65
    }},
    "should_trigger_storylet": false,
    "choices": [
        {{"label": "Choice text", "set": {{}}}}
    ],
    "confidence": 0.7,
    "rationale": "Why this interpretation fits",
    "goal_update": {{
        "status": "progressed|complicated|derailed|branched|completed",
        "milestone": "short arc event text",
        "urgency_delta": 0.0,
        "complication_delta": 0.0,
        "subgoal": "optional new subgoal"
    }}
}}

RULES:
- If the action is implausible, set plausible=false and explain why in the narrative (in-world, not meta)
- state_changes and delta.set can only use safe variable keys (letters, digits, _, ., -)
- Keep narrative consistent with established world facts
- following_beat is optional. If provided, choose one of: IncreasingTension, ThematicResonance, Catharsis
- goal_update is optional; include when action changes goal progress/complication
- Never break the fourth wall{chr(10)}{_canonical_location_rule(canonical_locations or [])}"""


def _build_intent_prompt(
    action: str,
    scene_card_now: Dict[str, Any],
    recent_events: List[str],
    world_facts: List[str],
    canonical_locations: Optional[List[str]] = None,
) -> str:
    return _build_intent_prompt_impl(
        action=action,
        scene_card_now=scene_card_now,
        recent_events=recent_events,
        world_facts=world_facts,
        deps=_intent_dependencies(),
        canonical_locations=canonical_locations,
    )


def _build_narration_prompt(
    *,
    action: str,
    ack_line: str,
    validated_state_changes: Dict[str, Any],
    current_storylet_text: Optional[str],
    recent_events: List[str],
    world_facts: List[str],
    scene_card_now: Dict[str, Any],
    motifs_recent: List[str],
    sensory_palette: Dict[str, Any],
    present_characters: Optional[List[Dict[str, Any]]] = None,
    resolved_movement_target: Optional[str] = None,
) -> str:
    return _build_narration_prompt_impl(
        action=action,
        ack_line=ack_line,
        validated_state_changes=validated_state_changes,
        current_storylet_text=current_storylet_text,
        recent_events=recent_events,
        world_facts=world_facts,
        scene_card_now=scene_card_now,
        motifs_recent=motifs_recent,
        sensory_palette=sensory_palette,
        present_characters=present_characters,
        resolved_movement_target=resolved_movement_target,
    )


def _truncate_text(value: Any, max_len: int = 1000) -> str:
    text = str(value or "").strip()
    if len(text) > max_len:
        return text[:max_len]
    return text


def _ack_line_for_action(action: str, proposed: Any = None) -> str:
    """Return a concise immediate feedback line for streaming ack phase."""
    proposed_text = _truncate_text(proposed, max_len=_MAX_ACK_LINE_CHARS).strip()
    if proposed_text:
        return proposed_text
    cleaned = re.sub(r"\s+", " ", str(action or "").strip())
    if len(cleaned) > 110:
        cleaned = f"{cleaned[:107]}..."
    return f'You commit to: "{cleaned}".'


def _normalize_world_fact_snippets(
    world_facts: Optional[List[str]],
    *,
    limit: int,
    per_fact_chars: int,
) -> List[str]:
    snippets: List[str] = []
    seen: set[str] = set()
    for raw in world_facts or []:
        text = re.sub(r"\s+", " ", str(raw or "").strip())
        if not text:
            continue
        text = _truncate_text(text, max_len=per_fact_chars)
        if text in seen:
            continue
        seen.add(text)
        snippets.append(text)
        if len(snippets) >= limit:
            break
    return snippets


def _join_world_fact_snippets(snippets: List[str]) -> str:
    if not snippets:
        return "None"

    selected: List[str] = []
    used_chars = 0
    for snippet in snippets:
        separator_chars = 2 if selected else 0
        if used_chars + separator_chars + len(snippet) > _MAX_FACT_PROMPT_CHARS:
            break
        selected.append(snippet)
        used_chars += separator_chars + len(snippet)

    return "; ".join(selected) if selected else "None"


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
    return _sanitize_follow_up_choices_impl(
        raw_choices,
        rejected_keys,
        truncate_text_fn=_truncate_text,
        sanitize_choice_set_fn=_sanitize_choice_set,
    )


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
            return _normalize_world_fact_snippets(
                facts if isinstance(facts, list) else [],
                limit=_MAX_FACTS_IN_CONTEXT,
                per_fact_chars=_MAX_FACT_SNIPPET_CHARS,
            )
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

    return _normalize_world_fact_snippets(
        facts,
        limit=_MAX_FACTS_IN_CONTEXT,
        per_fact_chars=_MAX_FACT_SNIPPET_CHARS,
    )


def _extract_action_targets(action: str) -> List[str]:
    action_lower = action.lower()
    targets: List[str] = []
    pattern = re.compile(r"\b(?:burn|destroy|blow up|collapse|ruin|smash|break|flood|seal)\s+(?:the\s+)?([a-z][a-z0-9 _-]{1,60})")
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

    intensity = _coerce_number(raw.get("intensity"))
    if intensity is None:
        intensity = 0.35
    turns = _coerce_number(raw.get("turns", raw.get("turns_remaining")))
    if turns is None:
        turns = 3
    decay = _coerce_number(raw.get("decay"))
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


def _heuristic_following_beats(action: str) -> List[Dict[str, Any]]:
    lowered = str(action or "").lower()
    beats: List[Dict[str, Any]] = []

    if any(verb in lowered for verb in _DESTRUCTIVE_VERBS):
        beats.append(
            {
                "name": "IncreasingTension",
                "intensity": 0.45,
                "turns_remaining": 3,
                "decay": 0.65,
                "source": "heuristic",
            }
        )

    if any(verb in lowered for verb in _HELPFUL_VERBS):
        beats.append(
            {
                "name": "Catharsis",
                "intensity": 0.3,
                "turns_remaining": 3,
                "decay": 0.65,
                "source": "heuristic",
            }
        )

    return beats[:_MAX_SUGGESTED_BEATS]


def _normalize_following_beats(raw: Any, action: str) -> List[Dict[str, Any]]:
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

    return _heuristic_following_beats(action)


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
    suggested_beats = _normalize_following_beats(
        data.get("following_beats", data.get("following_beat")),
        action=action,
    )

    goal_update = _sanitize_goal_update(
        data.get("goal_update"),
        action=action,
        state_summary=state_summary,
    )

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


def _fallback_result(
    action: str,
    reasoning_metadata: Optional[Dict[str, Any]] = None,
    suggested_beats: Optional[List[Dict[str, Any]]] = None,
) -> ActionResult:
    """Generate a fallback result when AI is unavailable."""
    return ActionResult(
        narrative_text=(f"You attempt to {action.lower().rstrip('.')}. " "The world shifts around you, but the outcome remains uncertain."),
        state_deltas={},
        should_trigger_storylet=False,
        follow_up_choices=[
            {"label": "Continue exploring", "set": {}},
            {"label": "Try something else", "set": {}},
        ],
        suggested_beats=list(suggested_beats or []),
        plausible=True,
        reasoning_metadata=reasoning_metadata or {},
    )


def _goal_context_from_state_summary(state_summary: Dict[str, Any]) -> str:
    goal_payload = state_summary.get("goal", {})
    if not isinstance(goal_payload, dict):
        return ""

    primary_goal = str(goal_payload.get("primary_goal", "")).strip()
    if not primary_goal:
        return ""

    parts = [f"Primary goal: {primary_goal}"]
    subgoals = goal_payload.get("subgoals", [])
    if isinstance(subgoals, list):
        cleaned = [str(item).strip() for item in subgoals if str(item).strip()]
        if cleaned:
            parts.append("Subgoals: " + ", ".join(cleaned[:5]))
    urgency = goal_payload.get("urgency")
    complication = goal_payload.get("complication")
    if isinstance(urgency, (int, float)) and isinstance(complication, (int, float)):
        parts.append(f"urgency={max(0.0, min(1.0, float(urgency))):.2f}, " f"complication={max(0.0, min(1.0, float(complication))):.2f}")
    return " | ".join(parts)


def _sanitize_goal_update(
    raw_goal_update: Any,
    *,
    action: str,
    state_summary: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    statuses = {"progressed", "complicated", "derailed", "branched", "completed"}
    if not isinstance(raw_goal_update, dict):
        return _heuristic_goal_update(action, state_summary)

    status = str(raw_goal_update.get("status", "progressed")).strip().lower()
    if status not in statuses:
        status = "progressed"

    milestone = _truncate_text(raw_goal_update.get("milestone", ""), max_len=220)
    note = _truncate_text(raw_goal_update.get("note", ""), max_len=220)
    subgoal = _truncate_text(raw_goal_update.get("subgoal", ""), max_len=140)

    urgency_delta = _coerce_number(raw_goal_update.get("urgency_delta"))
    complication_delta = _coerce_number(raw_goal_update.get("complication_delta"))
    urgency_delta = 0.0 if urgency_delta is None else max(-1.0, min(1.0, urgency_delta))
    complication_delta = 0.0 if complication_delta is None else max(-1.0, min(1.0, complication_delta))

    if not milestone and not subgoal and urgency_delta == 0.0 and complication_delta == 0.0:
        return _heuristic_goal_update(action, state_summary)

    return {
        "status": status,
        "milestone": milestone or "Goal state adjusted",
        "note": note,
        "subgoal": subgoal,
        "urgency_delta": urgency_delta,
        "complication_delta": complication_delta,
    }


def _heuristic_goal_update(action: str, state_summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    goal_context = _goal_context_from_state_summary(state_summary)
    if not goal_context:
        return None

    lowered = str(action or "").lower()
    milestone = str(action or "").strip()
    if not milestone:
        return None

    if any(token in lowered for token in _GOAL_BRANCH_VERBS):
        return {
            "status": "branched",
            "milestone": f"Branched objective via action: {milestone}",
            "note": "",
            "subgoal": milestone[:120],
            "urgency_delta": 0.05,
            "complication_delta": 0.1,
        }

    if any(token in lowered for token in _GOAL_COMPLICATION_VERBS):
        return {
            "status": "complicated",
            "milestone": f"Complication: {milestone}",
            "note": "",
            "subgoal": "",
            "urgency_delta": 0.1,
            "complication_delta": 0.25,
        }

    if any(token in lowered for token in _GOAL_PROGRESS_VERBS):
        completed = "completed" if any(k in lowered for k in ("complete", "finish")) else "progressed"
        return {
            "status": completed,
            "milestone": f"Goal progress: {milestone}",
            "note": "",
            "subgoal": "",
            "urgency_delta": -0.05 if completed == "completed" else 0.0,
            "complication_delta": -0.05,
        }

    return None


def _collect_colocation_context(
    *,
    db: Session,
    world_memory_module: Any,
    current_session_id: str,
    location: str,
    scan_limit: int = 100,
    max_characters: int = 6,
) -> List[Dict[str, Any]]:
    """Return a list of characters currently co-located with the player.

    Scans recent world events to find other sessions whose last known location
    matches the current player's location. For each, pulls their display name
    (from player_role) and their most recent action summary at this location.
    """
    from .session_service import get_state_manager as _gsm

    all_events = world_memory_module.get_world_history(db, limit=scan_limit)

    # Find each other session's most recent location and most recent summary
    session_last_location: Dict[str, str] = {}
    session_last_summary: Dict[str, str] = {}
    for event in reversed(all_events):  # oldest first → later events overwrite
        sid = event.session_id or ""
        if not sid or sid == current_session_id:
            continue
        loc = (event.world_state_delta or {}).get("location")
        if loc:
            session_last_location[sid] = str(loc)
        if event.summary:
            session_last_summary[sid] = str(event.summary)

    # Keep only sessions at our location
    collocated_ids = [sid for sid, loc in session_last_location.items() if loc == location][:max_characters]

    result = []
    for sid in collocated_ids:
        role = ""
        try:
            sm = _gsm(sid, db)
            raw_role = sm.get_variable("player_role") or ""
            # player_role format: "Name — description" or just a description
            role = raw_role.split(" — ")[0].strip() if " — " in raw_role else raw_role.strip()
        except Exception:
            pass
        last_action = session_last_summary.get(sid, "")
        result.append(
            {
                "session_id": sid,
                "role": role or sid,
                "last_action": last_action,
            }
        )

    return result


def _collect_action_context(
    *,
    action: str,
    state_manager: Any,
    world_memory_module: Any,
    current_storylet: Optional[Any],
    db: Session,
    scene_card_now: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _collect_action_context_impl(
        action=action,
        state_manager=state_manager,
        world_memory_module=world_memory_module,
        current_storylet=current_storylet,
        db=db,
        deps=_intent_dependencies(),
        scene_card_now=scene_card_now,
    )


def interpret_action_intent(
    action: str,
    state_manager: Any,
    world_memory_module: Any,
    current_storylet: Optional[Any],
    db: Session,
    scene_card_now: Optional[Dict[str, Any]] = None,
) -> Optional[StagedActionIntent]:
    return _interpret_action_intent_impl(
        action=action,
        state_manager=state_manager,
        world_memory_module=world_memory_module,
        current_storylet=current_storylet,
        db=db,
        deps=_intent_dependencies(),
        scene_card_now=scene_card_now,
    )


def _build_scene_card_payload_for_action_context(state_manager: Any) -> Dict[str, Any]:
    from ..core.scene_card import build_scene_card

    return build_scene_card(state_manager).model_dump()


def _intent_dependencies() -> IntentDependencies:
    return IntentDependencies(
        is_ai_disabled_fn=_is_ai_disabled,
        extract_relevant_world_facts_fn=_extract_relevant_world_facts,
        detect_action_contradiction_fn=_detect_action_contradiction,
        goal_context_from_state_summary_fn=_goal_context_from_state_summary,
        heuristic_following_beats_fn=_heuristic_following_beats,
        heuristic_goal_update_fn=_heuristic_goal_update,
        collect_colocation_context_fn=_collect_colocation_context,
        build_scene_card_payload_fn=_build_scene_card_payload_for_action_context,
        build_sensory_palette_fn=prompt_library.build_scene_card_sensory_palette,
        normalize_world_fact_snippets_fn=_normalize_world_fact_snippets,
        join_world_fact_snippets_fn=_join_world_fact_snippets,
        canonical_location_rule_fn=_canonical_location_rule,
        extract_canonical_locations_fn=_extract_canonical_locations,
        sanitize_state_changes_fn=_sanitize_state_changes,
        normalize_following_beats_fn=_normalize_following_beats,
        sanitize_goal_update_fn=_sanitize_goal_update,
        coerce_number_fn=_coerce_number,
        truncate_text_fn=_truncate_text,
        ack_line_for_action_fn=_ack_line_for_action,
        get_llm_client_fn=get_llm_client,
        shared_inference_policy_fn=_shared_inference_policy,
        resolve_lane_model_fn=_resolve_lane_model,
        call_json_chat_completion_fn=_call_json_chat_completion,
        llm_json_warning_fn=_llm_json_warning,
        action_result_type=ActionResult,
        staged_action_intent_type=StagedActionIntent,
    )


def render_validated_action_narration(
    *,
    action: str,
    ack_line: str,
    validated_result: ActionResult,
    state_manager: Any,
    world_memory_module: Any,
    current_storylet: Optional[Any],
    db: Session,
    scene_card_now: Optional[Dict[str, Any]] = None,
    resolved_movement_target: Optional[str] = None,
    inference_policy: InferencePolicy | None = None,
) -> ActionResult:
    return _render_validated_action_narration_impl(
        action=action,
        ack_line=ack_line,
        validated_result=validated_result,
        state_manager=state_manager,
        world_memory_module=world_memory_module,
        current_storylet=current_storylet,
        db=db,
        deps=NarrationDependencies(
            collect_action_context_fn=_collect_action_context,
            fallback_result_fn=_fallback_result,
            is_ai_disabled_fn=_is_ai_disabled,
            get_llm_client_fn=get_llm_client,
            shared_inference_policy_fn=_shared_inference_policy,
            resolve_lane_model_fn=_resolve_lane_model,
            call_json_chat_completion_fn=_call_json_chat_completion,
            sanitize_follow_up_choices_fn=_sanitize_follow_up_choices,
            llm_json_warning_fn=_llm_json_warning,
            truncate_text_fn=_truncate_text,
        ),
        scene_card_now=scene_card_now,
        resolved_movement_target=resolved_movement_target,
        inference_policy=inference_policy,
    )


def interpret_action(
    action: str,
    state_manager: Any,
    world_memory_module: Any,
    current_storylet: Optional[Any],
    db: Session,
    scene_card_now: Optional[Dict[str, Any]] = None,
) -> ActionResult:
    """Interpret a freeform player action using LLM."""
    context = _collect_action_context(
        action=action,
        state_manager=state_manager,
        world_memory_module=world_memory_module,
        current_storylet=current_storylet,
        db=db,
        scene_card_now=scene_card_now,
    )
    state_summary = context["state_summary"]
    heuristic_beats = context["heuristic_beats"]
    heuristic_goal_update = context["heuristic_goal_update"]
    current_text = context["current_text"]
    recent_events = context["recent_events"]
    world_facts = context["world_facts"]
    contradiction = context["contradiction"]

    if contradiction:
        metadata = ActionReasoningMetadata(
            facts_considered=world_facts[:_MAX_FACTS_IN_CONTEXT],
            rejected_keys=[],
            validation_warnings=[],
            contradiction=contradiction,
            rationale="Action conflicts with existing persistent world facts.",
            goal_update=heuristic_goal_update,
            suggested_beats=[],
        ).model_dump(exclude_none=True)
        target = contradiction.split(" is already ")[0]
        status = contradiction.split(" is already ")[-1]
        return ActionResult(
            narrative_text=(f"You try to {action.lower().rstrip('.')}, but the {target} is already {status}. " "You can only deal with the aftermath now."),
            state_deltas={},
            should_trigger_storylet=False,
            follow_up_choices=[
                {"label": "Inspect the aftermath", "set": {}},
                {"label": "Change your plan", "set": {}},
            ],
            suggested_beats=[],
            plausible=False,
            reasoning_metadata=metadata,
        )

    if _is_ai_disabled():
        metadata = ActionReasoningMetadata(
            facts_considered=world_facts[:_MAX_FACTS_IN_CONTEXT],
            rejected_keys=[],
            validation_warnings=["ai_disabled_or_unavailable"],
            goal_update=heuristic_goal_update,
            suggested_beats=heuristic_beats,
        ).model_dump(exclude_none=True)
        return _fallback_result(
            action,
            reasoning_metadata=metadata,
            suggested_beats=heuristic_beats,
        )

    client = get_llm_client(policy=_shared_inference_policy(state_manager, owner_id="legacy_action"))
    if not client:
        metadata = ActionReasoningMetadata(
            facts_considered=world_facts[:_MAX_FACTS_IN_CONTEXT],
            rejected_keys=[],
            validation_warnings=["llm_client_unavailable"],
            goal_update=heuristic_goal_update,
            suggested_beats=heuristic_beats,
        ).model_dump(exclude_none=True)
        return _fallback_result(
            action,
            reasoning_metadata=metadata,
            suggested_beats=heuristic_beats,
        )

    prompt = _build_action_prompt(
        action,
        scene_card_now=context["scene_card_now"],
        current_storylet_text=current_text,
        recent_events=recent_events,
        world_facts=world_facts,
        canonical_locations=_extract_canonical_locations(state_manager),
    )

    try:
        payload = _call_json_chat_completion(
            client=client,
            model=get_model(),
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": ("You are a narrative AI interpreting freeform player actions " "in an interactive fiction world. Respond only with valid JSON."),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=800,
            timeout=None,
            operation="interpret_action",
        )
        return _sanitize_action_payload(action, payload, state_summary, world_facts)

    except Exception as exc:
        category = _llm_json_warning(exc)
        logger.error(
            "LLM interpretation failed (%s): %s",
            category[0] if category else "llm_error",
            exc,
        )
        metadata = ActionReasoningMetadata(
            facts_considered=world_facts[:_MAX_FACTS_IN_CONTEXT],
            rejected_keys=[],
            validation_warnings=["llm_interpretation_exception", *category],
            goal_update=heuristic_goal_update,
            suggested_beats=heuristic_beats,
        ).model_dump(exclude_none=True)
        return _fallback_result(
            action,
            reasoning_metadata=metadata,
            suggested_beats=heuristic_beats,
        )


async def interpret_action_intent_non_blocking(
    action: str,
    state_manager: Any,
    world_memory_module: Any,
    current_storylet: Optional[Any],
    db: Session,
    scene_card_now: Optional[Dict[str, Any]] = None,
) -> Optional[StagedActionIntent]:
    """Async wrapper that offloads stage-A intent planning from event loop."""

    return await run_inference_thread(
        interpret_action_intent,
        action,
        state_manager,
        world_memory_module,
        current_storylet,
        db,
        scene_card_now,
    )


async def render_validated_action_narration_non_blocking(
    *,
    action: str,
    ack_line: str,
    validated_result: ActionResult,
    state_manager: Any,
    world_memory_module: Any,
    current_storylet: Optional[Any],
    db: Session,
    scene_card_now: Optional[Dict[str, Any]] = None,
    resolved_movement_target: Optional[str] = None,
    inference_policy: InferencePolicy | None = None,
) -> ActionResult:
    """Async wrapper that offloads narration rendering from event loop."""

    return await run_inference_thread(
        render_validated_action_narration,
        action=action,
        ack_line=ack_line,
        validated_result=validated_result,
        state_manager=state_manager,
        world_memory_module=world_memory_module,
        current_storylet=current_storylet,
        db=db,
        scene_card_now=scene_card_now,
        resolved_movement_target=resolved_movement_target,
        inference_policy=inference_policy,
    )


async def interpret_action_non_blocking(
    action: str,
    state_manager: Any,
    world_memory_module: Any,
    current_storylet: Optional[Any],
    db: Session,
    scene_card_now: Optional[Dict[str, Any]] = None,
) -> ActionResult:
    """Async wrapper that offloads legacy single-pass interpretation."""

    return await run_inference_thread(
        interpret_action,
        action,
        state_manager,
        world_memory_module,
        current_storylet,
        db,
        scene_card_now,
    )
