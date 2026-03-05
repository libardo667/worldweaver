"""Authoritative event reducer and rulebook for world-state mutations."""

import logging
from typing import Any

from sqlalchemy.orm import Session

from ...models.schemas import ActionDeltaContract
from ..state_manager import AdvancedStateManager
from .schema import (
    EventIntent,
    ChoiceSelectedIntent,
    FreeformActionCommittedIntent,
    SystemTickIntent,
    SimulationTickIntent,
    ReducerReceipt,
    VARIABLE_CLAMP_SCHEMA,
    MAX_UNSTRUCTURED_STATE_ITEMS,
    MULTI_ACTOR_SCENE_KEYS,
    STRUCTURED_STANCE_KEY,
    UNSTRUCTURED_STATE_BAG_KEY,
    canonicalize_structured_key,
    extract_structured_alias_value,
    is_structured_state_key,
    is_unstructured_state_hint_key,
    normalize_structured_value,
)

logger = logging.getLogger(__name__)


def reduce_event(
    db: Session,
    state_manager: AdvancedStateManager,
    intent: EventIntent,
) -> ReducerReceipt:
    """
    Authoritative state mutator.
    Takes a normalized intent, applies validation rules, aliases, clamps,
    and side-effects (like fact decay), then updates the StateManager.
    """
    receipt = ReducerReceipt()

    # 1. Dispatch by intent type to extract the proposed deltas
    delta = ActionDeltaContract()
    if isinstance(intent, ChoiceSelectedIntent):
        delta = intent.delta
    elif isinstance(intent, FreeformActionCommittedIntent):
        delta = intent.delta
    elif isinstance(intent, SystemTickIntent):
        # System ticks don't bring external deltas, they just trigger decay.
        pass
    elif isinstance(intent, SimulationTickIntent):
        delta = intent.delta

    stance_set_this_intent: str | None = None
    multi_actor_scene = _is_multi_actor_scene(state_manager)

    # 2. Canonicalize and apply set operations.
    for set_op in delta.set:
        raw_key = _canonicalize_key(set_op.key)
        key = canonicalize_structured_key(raw_key)
        val = extract_structured_alias_value(raw_key, set_op.value)
        receipt.proposed_changes[key] = val

        if _is_blocked(key):
            receipt.rejected_changes.append(key)
            receipt.rejection_reasons[key] = f"Blocked system key: {key}"
            continue

        if is_structured_state_key(key):
            normalized_val, reason = normalize_structured_value(key, val)
            if reason:
                receipt.rejected_changes.append(key)
                receipt.rejection_reasons[key] = reason
                continue

            if key == STRUCTURED_STANCE_KEY and isinstance(normalized_val, str) and stance_set_this_intent is not None and normalized_val != stance_set_this_intent and not multi_actor_scene:
                receipt.rejected_changes.append(key)
                receipt.rejection_reasons[key] = "Mutually exclusive stance conflict in one reducer event"
                continue

            if key == STRUCTURED_STANCE_KEY and isinstance(normalized_val, str):
                stance_set_this_intent = normalized_val

            state_manager.set_variable(key, normalized_val)
            receipt.applied_changes[key] = normalized_val
            continue

        if is_unstructured_state_hint_key(raw_key):
            before = state_manager.get_unstructured_state_bag()
            state_manager.set_unstructured_state_value(
                key,
                val,
                max_items=MAX_UNSTRUCTURED_STATE_ITEMS,
            )
            after = state_manager.get_unstructured_state_bag()
            pruned = sorted(set(before.keys()) - set(after.keys()))
            for pruned_key in pruned[:10]:
                receipt.facts_decayed.append(f"unstructured_pruned:{pruned_key}")
            receipt.applied_changes[f"{UNSTRUCTURED_STATE_BAG_KEY}.{key}"] = val
            continue

        val = _apply_clamp_policies(key, val, receipt)
        _apply_environment_alias(state_manager, key, val)
        state_manager.set_variable(key, val)
        receipt.applied_changes[key] = val
        _sync_legacy_aliases(state_manager, key, val, receipt)

    # 3. Canonicalize and apply increment/decrement operations.
    for inc_op in delta.increment:
        raw_key = _canonicalize_key(inc_op.key)
        key = canonicalize_structured_key(raw_key)
        amount = float(inc_op.amount)
        receipt.proposed_changes[key] = f"inc/dec by {amount}"

        if _is_blocked(key):
            receipt.rejected_changes.append(key)
            receipt.rejection_reasons[key] = f"Blocked system key: {key}"
            continue

        if is_structured_state_key(key):
            receipt.rejected_changes.append(key)
            receipt.rejection_reasons[key] = "Structured state keys do not support increment operations"
            continue

        if is_unstructured_state_hint_key(raw_key):
            payload = {"increment": amount}
            state_manager.set_unstructured_state_value(
                key,
                payload,
                max_items=MAX_UNSTRUCTURED_STATE_ITEMS,
            )
            receipt.applied_changes[f"{UNSTRUCTURED_STATE_BAG_KEY}.{key}"] = payload
            continue

        current = state_manager.get_variable(key, None)
        if current is None:
            env_alias_current = _get_environment_alias_value(state_manager, key)
            if env_alias_current is not None:
                current = env_alias_current
        if current is None:
            current = 0.0
        try:
            current_float = float(current)
        except (ValueError, TypeError):
            current_float = 0.0

        new_val = current_float + amount
        new_val = _apply_clamp_policies(key, new_val, receipt)

        _apply_environment_alias(state_manager, key, new_val)
        state_manager.set_variable(key, new_val)
        receipt.applied_changes[key] = new_val
        _sync_legacy_aliases(state_manager, key, new_val, receipt)

    # 4. Appended facts are persisted via world_memory in the caller path.
    for _fact_op in delta.append_fact:
        pass

    # 5. Apply lifecycle side-effects.
    _apply_tick_side_effects(
        state_manager,
        receipt,
        decay_tactics=isinstance(intent, (SystemTickIntent, SimulationTickIntent)),
    )

    return receipt


def _canonicalize_key(key: str) -> str:
    """Normalize variable aliases to canonical keys."""
    k = str(key).strip().lower()
    if k == "danger":
        return "environment.danger_level"
    return k


def _apply_clamp_policies(key: str, value: Any, receipt: ReducerReceipt) -> Any:
    """Clamp numeric values according to global VARIABLE_CLAMP_SCHEMA."""
    if key in VARIABLE_CLAMP_SCHEMA:
        min_val, max_val = VARIABLE_CLAMP_SCHEMA[key]
        try:
            float_val = float(value)
            clamped = max(min_val, min(float_val, max_val))
            if clamped != float_val:
                logger.warning("Clamped '%s' from %s to %s", key, float_val, clamped)
                receipt.rejection_reasons[f"{key}_clamped"] = f"Value {float_val} clamped to [{min_val}, {max_val}]"
            return clamped
        except (ValueError, TypeError):
            logger.warning(
                "Failed to apply numeric clamp to '%s' with value %s",
                key,
                value,
            )
            return value
    return value


def _is_blocked(key: str) -> bool:
    """Prevent overwriting critical system state."""
    k = key.lower()
    if k.startswith("_"):
        return True
    if k in ("session_id", "turn_count"):
        return True
    return False


def _is_multi_actor_scene(state_manager: AdvancedStateManager) -> bool:
    for key in MULTI_ACTOR_SCENE_KEYS:
        value = state_manager.get_variable(key, False)
        if isinstance(value, bool) and value:
            return True
        if str(value).strip().lower() in {"1", "true", "yes"}:
            return True
    return False


def _environment_attr_from_key(key: str) -> str | None:
    lowered = str(key or "").strip().lower()
    if not lowered.startswith("environment."):
        return None
    attr = lowered.split(".", 1)[1].strip()
    return attr or None


def _get_environment_alias_value(
    state_manager: AdvancedStateManager,
    key: str,
) -> Any:
    attr = _environment_attr_from_key(key)
    if not attr:
        return None
    if not hasattr(state_manager.environment, attr):
        return None
    return getattr(state_manager.environment, attr)


def _apply_environment_alias(
    state_manager: AdvancedStateManager,
    key: str,
    value: Any,
) -> None:
    """Mirror environment.* variable aliases onto canonical environment object fields."""
    attr = _environment_attr_from_key(key)
    if not attr:
        return
    if not hasattr(state_manager.environment, attr):
        return

    next_value: Any = value
    if attr in {"temperature", "danger_level", "noise_level"}:
        try:
            next_value = int(round(float(value)))
        except (ValueError, TypeError):
            return
    elif attr in {"time_of_day", "weather", "season", "lighting", "air_quality"}:
        next_value = str(value)

    state_manager.update_environment({attr: next_value})


def _sync_legacy_aliases(
    state_manager: AdvancedStateManager,
    key: str,
    value: Any,
    receipt: ReducerReceipt,
) -> None:
    """Keep known legacy aliases in sync while canonical reducer keys remain authoritative."""
    lowered = str(key or "").strip().lower()
    if lowered == "environment.danger_level":
        state_manager.set_variable("danger", value)
        receipt.applied_changes["danger"] = value


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
    "_scene_card_now",
    "_scene_card_history",
}


def _apply_tick_side_effects(
    state_manager: AdvancedStateManager,
    receipt: ReducerReceipt,
    *,
    decay_tactics: bool = False,
) -> None:
    """Evaluate constraints and lifecycle on turn progression."""
    if decay_tactics:
        expired_tactics = state_manager.decay_tactics()
        for tactic_name in expired_tactics:
            receipt.facts_decayed.append(f"tactic:{tactic_name}")

    # Decay hyper-specific environment details meant for flavor, not persistence.
    vars_to_check = list(state_manager.variables.items())
    for key, _value in vars_to_check:
        key_lower = key.lower()

        # 1) Decay flavor adjectives.
        if "flavor_" in key_lower or "muddy" in key_lower or "descriptive_" in key_lower:
            state_manager.delete_variable(key)
            receipt.facts_decayed.append(key)

        # 2) Sweep out unknown underscore-prefixed keys from older turns.
        elif key_lower.startswith("_"):
            is_protected = any(key_lower.startswith(prefix) for prefix in PROTECTED_INTERNAL_PREFIXES)
            if not is_protected and key_lower not in PROTECTED_INTERNAL_KEYS:
                state_manager.delete_variable(key)
                receipt.facts_decayed.append(key)
