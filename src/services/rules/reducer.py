"""Authoritative event reducer and rulebook for world-state mutations."""

import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from ...models.schemas import ActionDeltaContract
from ..state_manager import AdvancedStateManager
from .schema import (
    EventIntent,
    ChoiceSelectedIntent,
    FreeformActionCommittedIntent,
    SystemTickIntent,
    ReducerReceipt,
)

logger = logging.getLogger(__name__)

# Constants for fact TTLs and clamping
_MAX_ENVIRONMENT_DANGER = 10
_SCENE_TTL_TURNS = 3


def reduce_event(
    db: Session,
    state_manager: AdvancedStateManager,
    intent: EventIntent,
) -> ReducerReceipt:
    """
    Authoritative state mutator.
    Takes a normalized intent, applies validation rules, aliases, clamps,
    and side-effects (like fact decay), and then updates the StateManager.
    """
    receipt = ReducerReceipt()

    # 1. Dispatch by intent type to extract the proposed deltas
    delta = ActionDeltaContract()
    if isinstance(intent, ChoiceSelectedIntent):
        delta = intent.delta
    elif isinstance(intent, FreeformActionCommittedIntent):
        delta = intent.delta
    elif isinstance(intent, SystemTickIntent):
        # System ticks don't bring external deltas, they just trigger decay
        pass

    # 2. Canonicalize & Apply Sets
    for set_op in delta.set:
        key = _canonicalize_key(set_op.key)
        val = set_op.value
        receipt.proposed_changes[key] = val
        
        # Validation / Blocklist
        if _is_blocked(key):
            receipt.rejected_changes.append(key)
            receipt.rejection_reasons[key] = f"Blocked system key: {key}"
            continue

        state_manager.set_variable(key, val)
        receipt.applied_changes[key] = val

    # 3. Canonicalize & Apply Increments/Decrements
    for inc_op in delta.increment:
        key = _canonicalize_key(inc_op.key)
        amount = float(inc_op.amount)
        receipt.proposed_changes[key] = f"inc/dec by {amount}"
        
        if _is_blocked(key):
            receipt.rejected_changes.append(key)
            receipt.rejection_reasons[key] = f"Blocked system key: {key}"
            continue
            
        current = state_manager.get_variable(key, 0.0)
        try:
            current_float = float(current)
        except (ValueError, TypeError):
            current_float = 0.0

        new_val = current_float + amount
        
        # Clamping
        if key == "environment.danger_level" or key == "danger":
            new_val = max(0.0, min(new_val, _MAX_ENVIRONMENT_DANGER))
            
        state_manager.set_variable(key, new_val)
        receipt.applied_changes[key] = new_val

    # 4. Appended Facts
    for fact_op in delta.append_fact:
        # We record facts to world_memory outside the normal vars,
        # but the reducer can still intercept them or decay them.
        # For now, we rely on the caller or interpreter to write the fact,
        # or we can move fact persistence here in the future.
        pass

    # 5. Apply Global Rulebook Side-Effects
    _apply_tick_side_effects(state_manager, receipt)

    return receipt


def _canonicalize_key(key: str) -> str:
    """Normalize variable aliases to canon."""
    k = str(key).strip().lower()
    if k == "danger":
        return "environment.danger_level"
    return k


def _is_blocked(key: str) -> bool:
    """Prevent overwriting critical system state."""
    k = key.lower()
    if k.startswith("_"):
        return True
    if k in ("session_id", "turn_count"):
        return True
    return False


PROTECTED_INTERNAL_PREFIXES = (
    "_bootstrap_",
    "_mood_",
)

PROTECTED_INTERNAL_KEYS = {
    "_world_bible",
    "_story_arc",
    "_v",
    "_inventory_count",
    "_total_item_quantity",
    "_relationship_count",
    "_time_of_day",
    "_weather",
    "_danger_level",
}

def _apply_tick_side_effects(
    state_manager: AdvancedStateManager,
    receipt: ReducerReceipt,
) -> None:
    """Evaluate constraints and lifecycle on every turn increment."""
    # Decay hyper-specific environment details meant for flavor, not persistence
    vars_to_check = list(state_manager.variables.items())
    for k, v in vars_to_check:
        k_lower = k.lower()
        
        # 1. Decay flavor adjectives
        if "flavor_" in k_lower or "muddy" in k_lower or "descriptive_" in k_lower:
            state_manager.delete_variable(k)
            receipt.facts_decayed.append(k)
            
        # 2. Sweep out any _ prefixed keys that bled in from older un-validated turns
        elif k_lower.startswith("_"):
            is_protected = any(k_lower.startswith(prefix) for prefix in PROTECTED_INTERNAL_PREFIXES)
            if not is_protected and k_lower not in PROTECTED_INTERNAL_KEYS:
                state_manager.delete_variable(k)
                receipt.facts_decayed.append(k)

