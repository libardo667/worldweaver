"""Natural language command interpreter for freeform player actions."""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .llm_client import get_llm_client, get_model, is_ai_disabled

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    """Result of interpreting a freeform player action."""

    narrative_text: str
    state_deltas: Dict[str, Any] = field(default_factory=dict)
    should_trigger_storylet: bool = False
    follow_up_choices: List[Dict[str, Any]] = field(default_factory=list)
    plausible: bool = True


def _is_ai_disabled() -> bool:
    return is_ai_disabled()


def _build_action_prompt(
    action: str,
    state_summary: Dict[str, Any],
    current_storylet_text: Optional[str],
    recent_events: List[str],
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

PLAYER ACTION: "{action}"

Respond ONLY with valid JSON:
{{
    "plausible": true,
    "narrative": "Your narrative response...",
    "state_changes": {{}},
    "should_trigger_storylet": false,
    "choices": [
        {{"label": "Choice text", "set": {{}}}}
    ]
}}

RULES:
- If the action is implausible, set plausible=false and explain why in the narrative (in-world, not meta)
- state_changes should only modify variables that logically change
- Keep narrative consistent with established world facts
- Never break the fourth wall"""


def _fallback_result(action: str) -> ActionResult:
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
    )


def interpret_action(
    action: str,
    state_manager: Any,
    world_memory_module: Any,
    current_storylet: Optional[Any],
    db: Session,
) -> ActionResult:
    """Interpret a freeform player action using LLM.

    Falls back to a generic response when LLM is unavailable.
    """
    if _is_ai_disabled():
        return _fallback_result(action)

    client = get_llm_client()
    if not client:
        return _fallback_result(action)

    state_summary = state_manager.get_state_summary()

    current_text = None
    if current_storylet:
        current_text = str(getattr(current_storylet, "text_template", ""))

    recent_events: List[str] = []
    try:
        events = world_memory_module.get_world_history(
            db, session_id=state_manager.session_id, limit=5
        )
        recent_events = [e.summary for e in events]
    except Exception:
        pass

    prompt = _build_action_prompt(action, state_summary, current_text, recent_events)

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

        data = json.loads(response.choices[0].message.content or "{}")

        return ActionResult(
            narrative_text=data.get("narrative", f"You attempt to {action}."),
            state_deltas=data.get("state_changes", {}),
            should_trigger_storylet=data.get("should_trigger_storylet", False),
            follow_up_choices=data.get("choices", []),
            plausible=data.get("plausible", True),
        )

    except Exception as e:
        logger.error("LLM interpretation failed: %s", e)
        return _fallback_result(action)
