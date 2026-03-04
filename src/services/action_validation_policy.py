"""Strict policy validation for proposed player actions."""

import logging
from typing import Any

from sqlalchemy.orm import Session

from ..config import settings
from .command_interpreter import StagedActionIntent

logger = logging.getLogger(__name__)


def validate_action_intent(
    intent: StagedActionIntent,
    action_text: str,
    state_manager: Any,
    world_memory_module: Any,
    db: Session,
) -> StagedActionIntent:
    """Validate Stage-A proposed deltas against projected affordances and constraints.
    
    If strict validation is disabled, this acts as a no-op passthrough.
    """
    if not settings.enable_strict_action_validation:
        return intent

    deltas = intent.result.state_deltas
    if not isinstance(deltas, dict):
        deltas = {}

    metadata = dict(intent.result.reasoning_metadata)
    warnings = list(metadata.get("validation_warnings", []))
    rejected_keys: list[str] = list(metadata.get("rejected_keys", []))
    
    state_summary = state_manager.get_state_summary()
    inventory = state_summary.get("inventory", {}).get("items", {})
    variables = state_summary.get("variables", {})
    
    action_lower = str(action_text or "").lower()

    if not deltas:
        return intent

    validated_deltas = {}

    location = variables.get("location")

    # Pre-fetch location facts once for efficiency
    location_facts = []
    if location:
        try:
            location_facts = world_memory_module.get_node_facts(db, location, session_id=state_manager.session_id)
        except Exception:
            pass
    fact_strings = [str(f.predicate).lower() + ":" + str(f.value).lower() for f in location_facts]

    # Semantic signals (for grounding checks only — NOT for moral policing)
    ACQUISITION_VERBS = {"grab", "take", "steal", "pick up", "pocket", "swipe", "snag", "loot", "pilfer", "lift"}
    action_implies_gain = any(v in action_lower for v in ACQUISITION_VERBS)

    # 1. Enforce inventory removal constraints
    for key, value in deltas.items():
        # Block removing items that aren't in inventory
        if key in inventory and (value is False or value == 0 or value == "dropped"):
            if inventory.get(key) not in [True, 1, "equipped"]: 
                logger.info(f"Blocked invalid intent delta on missing inventory: {key}")
                rejected_keys.append(str(key))
                warnings.append(f"policy_blocked_inventory_removal:{key}")
                continue

        # 2. Grounding check: block claiming items that don't exist in the scene.
        # Only applies when the action implies gaining something AND the key looks like a novel item.
        # Morally questionable gains (theft, pickup) ARE allowed if the item exists in the scene.
        is_new_gain = (value is True) or (isinstance(value, (int, float)) and value > 0 and key not in inventory)
        looks_like_item = any(word in str(key).lower() for word in (
            "cash", "money", "bill", "coin", "gold", "key", "item", "weapon", "ammo",
            "drug", "loot", "stolen", "gun", "knife", "sword", "shield",
        ))

        if is_new_gain and looks_like_item and action_implies_gain:
            # Check if this item is mentioned in location facts (it physically exists here)
            key_lower = str(key).lower()
            grounded = any(key_lower in f for f in fact_strings) or key in inventory

            if not grounded:
                logger.info(f"Blocked ungrounded item gain (item not in scene): {key}={value}")
                rejected_keys.append(str(key))
                warnings.append(f"grounding_check_failed:{key}")
                continue

        validated_deltas[key] = value

    if len(validated_deltas) < len(deltas):
        metadata["validation_warnings"] = warnings[:30]
        metadata["rejected_keys"] = rejected_keys[:30]
        metadata["staged_pipeline"] = "validate"
        intent.result.state_deltas = validated_deltas
        intent.result.reasoning_metadata = metadata
        
    # If ALL deltas were rejected, mark the action implausible
    if not validated_deltas and deltas:
        intent.result.plausible = False
        intent.ack_line = "That action conflicts with the current state of things."
        intent.result.narrative_text = "The world doesn't support that outcome right now."
        intent.result.state_deltas = {}
            
    return intent


