"""Shared turn orchestration for /api/next and /api/action."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
import logging
import re
import time
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple, cast

from pydantic import TypeAdapter
from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import DetachedInstanceError

from ..config import settings
from ..models import Storylet
from ..models.schemas import (
    ActionDeltaContract,
    ActionDeltaIncrementOperation,
    ActionDeltaSetOperation,
    ActionFactAppendOperation,
    ActionRequest,
    ChoiceOut,
    NextReq,
    NextResp,
    StoryletEffectAppendFactOperation,
    StoryletEffectIncrementOperation,
    StoryletEffectOperation,
    StoryletEffectSetOperation,
)
from .game_logic import ensure_storylets, render
from .llm_service import adapt_storylet_to_context, generate_next_beat
from .prefetch_service import get_cached_frontier, invalidate_projection_for_session
from . import prompt_library
from .rules.reducer import reduce_event
from .rules.schema import (
    ChoiceSelectedIntent,
    FreeformActionCommittedIntent,
    SimulationTickIntent,
    SystemTickIntent,
)
from .session_service import get_spatial_navigator, get_state_manager, save_state
from .simulation.tick import tick_world_simulation
from .storylet_selector import pick_storylet_enhanced
from .storylet_utils import find_storylet_by_location, normalize_choice
from .llm_client import get_trace_id

logger = logging.getLogger(__name__)

_SEMANTIC_GOAL_PATTERN = re.compile(
    r"\b(?:looking for|look for|find|search for|seeking|where(?:'s| is))\s+(?:the\s+)?([a-z][a-z0-9 _-]{1,60})",
    re.IGNORECASE,
)
_STORYLET_EFFECT_ADAPTER = TypeAdapter(StoryletEffectOperation)
_STORYLET_EFFECTS_ON_FIRE = "on_fire"
_STORYLET_EFFECTS_ON_CHOICE_COMMIT = "on_choice_commit"
_PENDING_STORYLET_CHOICE_EFFECTS_KEY = "state.pending_storylet_choice_effects"


def _log_structured_turn_event(event: str, **fields: Any) -> None:
    trace_id = get_trace_id()
    payload: Dict[str, Any] = {
        "event": event,
        "trace_id": trace_id,
        "correlation_id": trace_id,
    }
    payload.update(fields)
    logger.info(json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str))


def _extract_semantic_goal(action: str) -> str | None:
    match = _SEMANTIC_GOAL_PATTERN.search(str(action or ""))
    if not match:
        return None
    goal = match.group(1).strip(" .,!?:;-")
    return goal or None


def _quick_ack_line(action: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(action or "").strip())
    if len(cleaned) > 110:
        cleaned = f"{cleaned[:107]}..."
    return f'You commit to: "{cleaned}".'


def _record_timing(
    timings_ms: Dict[str, float] | None,
    key: str,
    started: float,
) -> None:
    if timings_ms is None:
        return
    timings_ms[key] = round((time.perf_counter() - started) * 1000.0, 3)


def _safe_storylet_identity(story: Storylet | None) -> tuple[int | None, str | None]:
    """Extract storylet id/title without triggering detached-instance refreshes."""
    if story is None:
        return None, None

    story_id: int | None = None
    story_title: str | None = None

    raw_state = getattr(story, "__dict__", {})
    raw_id = raw_state.get("id")
    if raw_id is not None:
        try:
            story_id = int(raw_id)
        except Exception:
            story_id = None

    if story_id is None:
        try:
            identity = sqlalchemy_inspect(story).identity
            if identity and identity[0] is not None:
                story_id = int(identity[0])
        except Exception:
            story_id = None

    if story_id is None:
        try:
            candidate_id = getattr(story, "id")
            if candidate_id is not None:
                story_id = int(candidate_id)
        except (DetachedInstanceError, Exception):
            story_id = None

    raw_title = raw_state.get("title")
    if raw_title is not None:
        story_title = str(raw_title)
    else:
        try:
            candidate_title = getattr(story, "title")
            if candidate_title is not None:
                story_title = str(candidate_title)
        except (DetachedInstanceError, Exception):
            story_title = None

    return story_id, story_title


def _safe_storylet_field(story: Storylet, field: str, default: Any) -> Any:
    """Read one storylet field without triggering detached-instance failures."""
    raw_state = getattr(story, "__dict__", {})
    if isinstance(raw_state, dict) and field in raw_state:
        value = raw_state.get(field)
    else:
        try:
            value = getattr(story, field)
        except (DetachedInstanceError, Exception):
            return default
    return default if value is None else value


def _snapshot_storylet_payload(story: Storylet) -> Dict[str, Any]:
    """Capture a plain-JSON-safe snapshot so downstream logic never depends on ORM liveness."""
    story_id, story_title = _safe_storylet_identity(story)
    try:
        story_weight = float(_safe_storylet_field(story, "weight", 1.0))
    except (TypeError, ValueError):
        story_weight = 1.0
    requires = _safe_storylet_field(story, "requires", {})
    choices = _safe_storylet_field(story, "choices", [])
    effects = _safe_storylet_field(story, "effects", [])
    return {
        "id": story_id,
        "title": str(story_title or ""),
        "text_template": str(_safe_storylet_field(story, "text_template", "")),
        "requires": (cast(Dict[str, Any], requires) if isinstance(requires, dict) else {}),
        "choices": (cast(List[Dict[str, Any]], choices) if isinstance(choices, list) else []),
        "effects": (cast(List[Dict[str, Any]], effects) if isinstance(effects, list) else []),
        "weight": story_weight,
        "source": str(_safe_storylet_field(story, "source", "authored") or "authored"),
    }


def _inject_next_diagnostics(vars_payload: Dict[str, Any], diagnostics: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(vars_payload)
    out["_ww_diag"] = dict(diagnostics)
    return out


def _inject_player_hint(
    vars_payload: Dict[str, Any],
    hint_payload: Dict[str, Any] | None,
) -> Dict[str, Any]:
    out = dict(vars_payload)
    if isinstance(hint_payload, dict) and hint_payload:
        out["_ww_hint"] = dict(hint_payload)
    return out


def _normalize_clarity_level(value: Any) -> str:
    candidate = str(value or "").strip().lower()
    if candidate in {"unknown", "rumor", "lead", "prepared", "committed"}:
        return candidate
    return "unknown"


def _coerce_non_negative_int(value: Any, *, default: int = 0) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError):
        return int(default)
    return out if out >= 0 else int(default)


def _resolve_next_turn_source(payload: NextReq) -> str:
    """Classify a /next turn by its input mode for diagnostics and harness stratification."""
    inbound_vars = payload.vars if isinstance(payload.vars, dict) else {}
    if not inbound_vars and payload.choice_taken is None:
        return "initial_scene"
    return "choice_button"


def _scene_clarity_level_from_projection(selected_projection_stub: Dict[str, Any] | None) -> str:
    if isinstance(selected_projection_stub, dict) and selected_projection_stub:
        return "prepared"
    return "unknown"


def _unknown_player_hint_payload(*, source: str = "hint_channel") -> Dict[str, Any]:
    return {
        "source": str(source or "hint_channel"),
        "clarity": "unknown",
        "hint": "No reliable lead is clear yet.",
    }


def _build_jit_beat_player_hint_payload(beat: Dict[str, Any]) -> Dict[str, Any]:
    """Derive a player hint from a generated JIT beat.

    Promotes clarity from 'unknown' to at least 'rumor' when the beat
    contains tension or unresolved threads, and to 'lead' when a concrete
    location target is visible in the beat's choice set-blocks.
    """
    tension = str(beat.get("tension", "") or "").strip()
    threads: List[str] = [str(t).strip() for t in (beat.get("unresolved_threads") or []) if str(t).strip()]

    # Look for a location target in the beat's state_changes (freeform) or legacy choice set-blocks.
    target_location: str = ""
    state_changes_block = beat.get("state_changes", {})
    if isinstance(state_changes_block, dict) and state_changes_block.get("location"):
        target_location = str(state_changes_block["location"]).strip()
    if not target_location:
        for choice in beat.get("choices", []):
            if not isinstance(choice, dict):
                continue
            set_block = choice.get("set", {})
            if isinstance(set_block, dict) and set_block.get("location"):
                target_location = str(set_block["location"]).strip()
                break

    if target_location:
        hint_text = tension or (threads[0] if threads else "A path leads onward.")
        payload: Dict[str, Any] = {
            "source": "jit_beat",
            "clarity": "lead",
            "hint": hint_text[:200],
            "location": target_location,
        }
        if threads:
            payload["unresolved_threads"] = threads[:2]
        return payload

    if tension or threads:
        hint_text = tension or threads[0]
        payload = {
            "source": "jit_beat",
            "clarity": "rumor",
            "hint": hint_text[:200],
        }
        if threads:
            payload["unresolved_threads"] = threads[:2]
        return payload

    return _unknown_player_hint_payload(source="jit_beat")


def _build_projection_player_hint_payload(
    selected_projection_stub: Dict[str, Any] | None,
    contrast_projection_stub: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    if not isinstance(selected_projection_stub, dict) or not selected_projection_stub:
        return _unknown_player_hint_payload(source="projection_seed")

    premise = str(selected_projection_stub.get("premise", "") or "").strip()
    location = str(selected_projection_stub.get("location", "") or "").strip()
    if premise:
        hint_text = premise
    elif location:
        hint_text = f"A promising lead appears near {location}."
    else:
        hint_text = "A likely next thread begins to take shape."

    payload: Dict[str, Any] = {
        "source": "projection_seed",
        "clarity": "prepared",
        "hint": hint_text[:220],
    }
    if location:
        payload["direction"] = location[:80]

    if isinstance(contrast_projection_stub, dict):
        contrast_premise = str(contrast_projection_stub.get("premise", "") or "").strip()
        if contrast_premise:
            payload["contrast_hint"] = contrast_premise[:180]
    return payload


def _build_semantic_goal_player_hint_payload(raw_hint: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not isinstance(raw_hint, dict):
        return None
    hint_text = str(raw_hint.get("hint", "") or "").strip()
    if not hint_text:
        return None
    payload: Dict[str, Any] = {
        "source": "semantic_goal",
        "clarity": "lead",
        "hint": hint_text[:220],
    }
    direction = str(raw_hint.get("direction", "") or "").strip()
    if direction:
        payload["direction"] = direction[:80]
    return payload


def _projection_stub_for_context(raw_stub: Dict[str, Any], *, expires_in_seconds: int) -> Dict[str, Any]:
    try:
        normalized_storylet_id = int(raw_stub.get("storylet_id")) if raw_stub.get("storylet_id") is not None else None
    except (TypeError, ValueError):
        normalized_storylet_id = None

    try:
        semantic_score = float(raw_stub.get("semantic_score") or 0.0)
    except (TypeError, ValueError):
        semantic_score = 0.0

    try:
        projection_depth = int(raw_stub.get("projection_depth") or 1)
    except (TypeError, ValueError):
        projection_depth = 1

    return {
        "storylet_id": normalized_storylet_id,
        "title": str(raw_stub.get("title", "") or ""),
        "premise": str(raw_stub.get("premise", "") or ""),
        "location": str(raw_stub.get("location", "") or ""),
        "semantic_score": semantic_score,
        "projection_depth": max(1, projection_depth),
        "non_canon": bool(raw_stub.get("non_canon", True)),
        "source": str(raw_stub.get("source", "prefetch_projection") or "prefetch_projection"),
        "expires_in_seconds": max(0, int(expires_in_seconds or 0)),
    }


def _projection_seed_bundle_for_storylet(
    session_id: str,
    story_payload: Dict[str, Any],
) -> tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
    """Resolve one selected projection seed and one optional contrast stub."""
    safe_session_id = str(session_id or "").strip()
    if not safe_session_id:
        return None, None

    frontier = get_cached_frontier(safe_session_id)
    if not isinstance(frontier, dict):
        return None, None

    stubs = frontier.get("stubs", [])
    if not isinstance(stubs, list):
        return None, None

    target_storylet_id = story_payload.get("id")
    target_title = str(story_payload.get("title", "") or "").strip().lower()
    expires_in_seconds = max(0, int(frontier.get("expires_in_seconds", 0) or 0))

    selected_stub: Dict[str, Any] | None = None
    selected_index: int | None = None
    for idx, raw_stub in enumerate(stubs):
        if not isinstance(raw_stub, dict):
            continue
        stub_storylet_id = raw_stub.get("storylet_id")
        id_match = False
        if target_storylet_id is not None and stub_storylet_id is not None:
            try:
                id_match = int(stub_storylet_id) == int(target_storylet_id)
            except (TypeError, ValueError):
                id_match = False
        title_match = (not id_match) and bool(target_title) and str(raw_stub.get("title", "") or "").strip().lower() == target_title
        if not id_match and not title_match:
            continue
        selected_stub = _projection_stub_for_context(raw_stub, expires_in_seconds=expires_in_seconds)
        selected_index = idx
        projection_tree = frontier.get("projection_tree")
        if isinstance(projection_tree, dict):
            selected_stub["projection_tree_depth"] = int(projection_tree.get("max_depth_reached", 0))
            selected_stub["projection_tree_node_count"] = int(projection_tree.get("total_nodes", 0))
            selected_stub["projection_tree_referee_scored"] = bool(projection_tree.get("referee_scored", False))
        break

    if selected_stub is None:
        return None, None

    contrast_stub: Dict[str, Any] | None = None
    for idx, raw_stub in enumerate(stubs):
        if idx == selected_index:
            continue
        if not isinstance(raw_stub, dict):
            continue
        contrast_stub = _projection_stub_for_context(raw_stub, expires_in_seconds=expires_in_seconds)
        break
    return selected_stub, contrast_stub


def _projection_seed_for_storylet(
    session_id: str,
    story_payload: Dict[str, Any],
) -> Dict[str, Any] | None:
    """Resolve one cached non-canon projection stub for narration context."""
    selected_stub, _contrast_stub = _projection_seed_bundle_for_storylet(session_id, story_payload)
    return selected_stub


def _storylet_effects_to_delta_contract(
    raw_effects: Any,
    *,
    trigger: str,
) -> tuple[ActionDeltaContract, List[Dict[str, Any]]]:
    contract = ActionDeltaContract()
    normalized: List[Dict[str, Any]] = []
    if not isinstance(raw_effects, list):
        return contract, normalized

    for raw in raw_effects[:20]:
        if not isinstance(raw, dict):
            continue
        try:
            parsed = _STORYLET_EFFECT_ADAPTER.validate_python(raw)
        except Exception:
            continue
        if str(getattr(parsed, "when", _STORYLET_EFFECTS_ON_FIRE)) != trigger:
            continue

        if isinstance(parsed, StoryletEffectSetOperation):
            contract.set.append(
                ActionDeltaSetOperation(
                    key=parsed.key,
                    value=parsed.value,
                )
            )
        elif isinstance(parsed, StoryletEffectIncrementOperation):
            contract.increment.append(
                ActionDeltaIncrementOperation(
                    key=parsed.key,
                    amount=float(parsed.amount),
                )
            )
        elif isinstance(parsed, StoryletEffectAppendFactOperation):
            contract.append_fact.append(
                ActionFactAppendOperation(
                    subject=parsed.subject,
                    predicate=parsed.predicate,
                    value=parsed.value,
                    location=parsed.location,
                    confidence=float(parsed.confidence),
                )
            )
        else:
            continue

        normalized.append(parsed.model_dump())

    return contract, normalized


def _public_contextual_vars(state_manager: Any) -> Dict[str, Any]:
    payload = state_manager.get_contextual_variables()
    if not isinstance(payload, dict):
        return {}
    out = dict(payload)
    out.pop("_scene_card_now", None)
    out.pop("_scene_card_history", None)
    return out


def _build_scene_card_payload(
    *,
    db: Session,
    state_manager: Any,
    get_spatial_navigator_fn=get_spatial_navigator,
) -> Dict[str, Any]:
    from ..core.scene_card import build_scene_card

    spatial_nav = get_spatial_navigator_fn(db)
    if not hasattr(spatial_nav, "storylet_positions"):
        spatial_nav = SimpleNamespace(storylet_positions={})
    scene_card = build_scene_card(state_manager, spatial_nav).model_dump()
    state_manager.persist_scene_card(scene_card, source="turn")
    return scene_card


def _update_motif_ledger_from_narrative(
    *,
    state_manager: Any,
    narrative_text: str,
) -> List[str]:
    """Extract motifs from committed narration and append to bounded ledger."""
    if not hasattr(state_manager, "extract_motifs_from_text"):
        return []
    if not hasattr(state_manager, "append_recent_motifs"):
        return []
    extracted = state_manager.extract_motifs_from_text(
        narrative_text,
        max_items=max(1, int(settings.motif_extract_max_per_turn)),
    )
    if not extracted:
        return []
    return list(
        state_manager.append_recent_motifs(
            extracted,
            max_items=max(8, int(settings.motif_ledger_max_items)),
        )
    )


def _action_result_to_delta_contract(
    result: Any,
) -> ActionDeltaContract:
    from ..models.schemas import ActionFactAppendOperation

    contract = ActionDeltaContract()
    state_deltas = result.state_deltas if isinstance(result.state_deltas, dict) else {}
    for key, value in state_deltas.items():
        contract.set.append(ActionDeltaSetOperation(key=key, value=value))

    metadata = result.reasoning_metadata if isinstance(result.reasoning_metadata, dict) else {}
    appended_facts = metadata.get("appended_facts")
    if isinstance(appended_facts, list):
        for item in appended_facts[:5]:
            if not isinstance(item, dict):
                continue
            try:
                contract.append_fact.append(ActionFactAppendOperation.model_validate(item))
            except Exception:
                continue
    return contract


def _persist_jit_beat_as_storylet(
    db: Session,
    beat: Dict[str, Any],
    state_manager: Any,
) -> None:
    """Save a JIT-generated beat as a persistent Storylet in the DB.

    This lets the storylet pool grow organically as the player explores,
    turning one-off JIT narration into reusable world content.
    """
    from datetime import datetime, timedelta, UTC
    from .embedding_service import embed_storylet_payload

    title_base = str(beat.get("title") or "JIT Scene").strip() or "JIT Scene"
    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    title = f"{title_base} [jit-{suffix}]"[:200]

    current_location = state_manager.get_contextual_variables().get("location", "")
    requires: Dict[str, Any] = {"location": current_location} if current_location else {}

    choices_raw = beat.get("choices", [])
    choices = [{"label": str(c.get("label", "Continue")), "set": c.get("set", {})} for c in choices_raw if isinstance(c, dict)]

    ttl_minutes = max(10, int(settings.jit_persist_ttl_minutes))
    expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=ttl_minutes)

    payload_for_embedding = {
        "title": title_base,
        "text_template": str(beat.get("text", "")),
        "choices": choices,
        "requires": requires,
    }

    storylet = Storylet(
        title=title,
        text_template=str(beat.get("text", "")),
        requires=requires,
        choices=choices,
        weight=1.0,
        source="jit_beat",
        expires_at=expires_at,
        embedding=embed_storylet_payload(payload_for_embedding),
    )
    db.add(storylet)
    db.commit()
    logger.info(
        "Persisted JIT beat as storylet '%s' (location=%s, expires=%s)",
        title_base,
        current_location or "<any>",
        expires_at.isoformat(),
    )


@dataclass
class UnifiedTurnInput:
    """Normalized turn input for the unified pipeline.

    Constructed from either ActionRequest (via from_action_request) or
    NextReq (via from_next_request).  Once built, process_turn can treat
    all turn types uniformly regardless of origin route.
    """

    session_id: str
    is_freeform: bool
    """True when the player typed free text; False for choice buttons and /next turns."""

    # Freeform text OR choice_intent text (used as contextual label for JIT)
    action: str
    # Idempotency (action turns only; empty string means no key)
    idempotency_key: str
    # Choice button fields
    choice_label: str
    choice_vars: Dict[str, Any] = field(default_factory=dict)  # from ActionRequest.choice_vars
    # /next-style fields
    inbound_vars: Dict[str, Any] = field(default_factory=dict)  # from NextReq.vars
    choice_taken: Any = None  # ActionDeltaContract | None from NextReq.choice_taken

    @classmethod
    def from_action_request(cls, payload: "ActionRequest") -> "UnifiedTurnInput":
        is_choice_button = bool(str(payload.choice_label or "").strip())
        choice_intent_text = str(payload.choice_intent or "").strip() if is_choice_button else ""
        effective_action = choice_intent_text if choice_intent_text else str(payload.action or "")
        return cls(
            session_id=str(payload.session_id),
            is_freeform=not is_choice_button,
            action=effective_action,
            idempotency_key=str(payload.idempotency_key or "").strip(),
            choice_label=str(payload.choice_label or "").strip(),
            choice_vars=dict(payload.choice_vars) if isinstance(payload.choice_vars, dict) else {},
            inbound_vars={},
            choice_taken=None,
        )

    @classmethod
    def from_next_request(cls, payload: "NextReq") -> "UnifiedTurnInput":
        choice_label = str(getattr(payload, "choice_label", None) or "").strip()
        return cls(
            session_id=str(payload.session_id),
            is_freeform=False,
            action="",
            idempotency_key="",
            choice_label=choice_label,
            choice_vars={},
            inbound_vars=dict(payload.vars) if isinstance(payload.vars, dict) else {},
            choice_taken=payload.choice_taken,
        )


class TurnOrchestrator:
    """One authoritative turn pipeline for next/action compatibility routes."""

    @staticmethod
    def process_action_turn(
        *,
        db: Session,
        payload: ActionRequest,
        timings_ms: Dict[str, float] | None = None,
        phase_events: List[Tuple[str, Dict[str, Any]]] | None = None,
        ack_line_hint: str | None = None,
        get_spatial_navigator_fn=get_spatial_navigator,
        render_fn=render,
    ) -> Dict[str, Any]:
        """Interpret and commit one freeform action turn."""
        if settings.enable_unified_turn_pipeline:
            from .game_logic import ensure_storylets
            from .llm_service import adapt_storylet_to_context, generate_next_beat
            from .storylet_selector import pick_storylet_enhanced
            from .storylet_utils import find_storylet_by_location, normalize_choice

            turn_input = UnifiedTurnInput.from_action_request(payload)
            result = TurnOrchestrator.process_turn(
                db=db,
                turn_input=turn_input,
                timings_ms=timings_ms,
                phase_events=phase_events,
                ack_line_hint=ack_line_hint,
                get_spatial_navigator_fn=get_spatial_navigator_fn,
                pick_storylet_fn=pick_storylet_enhanced,
                render_fn=render_fn,
                find_storylet_by_location_fn=find_storylet_by_location,
                ensure_storylets_fn=ensure_storylets,
                adapt_storylet_fn=adapt_storylet_to_context,
                generate_next_beat_fn=generate_next_beat,
                normalize_choice_fn=normalize_choice,
            )
            return TurnOrchestrator._as_action_response(result)

        from . import action_validation_policy
        from . import command_interpreter
        from . import world_memory

        idempotency_key = str(payload.idempotency_key or "").strip()
        idempotency_started = time.perf_counter()
        if idempotency_key:
            replay = world_memory.get_action_idempotent_response(
                db=db,
                session_id=payload.session_id,
                idempotency_key=idempotency_key,
            )
            if replay is not None:
                _record_timing(timings_ms, "idempotency_lookup", idempotency_started)
                return replay
        _record_timing(timings_ms, "idempotency_lookup", idempotency_started)

        is_choice_button = bool(str(payload.choice_label or "").strip())
        # When a choice carries an intent field (Minor 119), use it as the semantic
        # action text for the staged pipeline. This gives the LLM narrator richer
        # prose than the terse button label. Falls back to payload.action otherwise.
        choice_intent_text = str(payload.choice_intent or "").strip() if is_choice_button else ""
        used_choice_intent = bool(choice_intent_text)
        effective_action = choice_intent_text if used_choice_intent else payload.action

        state_started = time.perf_counter()
        state_manager = get_state_manager(payload.session_id, db)
        _record_timing(timings_ms, "load_state_manager", state_started)

        if is_choice_button and isinstance(payload.choice_vars, dict) and payload.choice_vars:
            var_delta = ActionDeltaContract()
            for key, value in payload.choice_vars.items():
                var_delta.set.append(ActionDeltaSetOperation(key=key, value=value))
            reduce_event(
                db,
                state_manager,
                ChoiceSelectedIntent(label=str(payload.choice_label), delta=var_delta),
            )

        location_started = time.perf_counter()
        current_location = str(state_manager.get_variable("location", "start"))
        current_storylet = find_storylet_by_location(db, current_location)
        current_storylet_id, _ = _safe_storylet_identity(current_storylet)
        _record_timing(timings_ms, "resolve_current_storylet", location_started)
        scene_card_started = time.perf_counter()
        scene_card_now = _build_scene_card_payload(
            db=db,
            state_manager=state_manager,
            get_spatial_navigator_fn=get_spatial_navigator_fn,
        )
        _record_timing(timings_ms, "build_scene_card_now", scene_card_started)

        staged_ack_line = ack_line_hint or _quick_ack_line(effective_action)
        strict_three_layer = bool(settings.enable_strict_three_layer_architecture)
        used_staged_pipeline = False
        result = None

        # Phase 2 spatial navigation: detect movement before Stage A
        _pre_movement_target: Optional[str] = None
        _loc_names_set: set = set()
        try:
            _loc_graph = world_memory.get_location_graph(db)
            _loc_names = [n["name"] for n in _loc_graph.get("nodes", []) if n.get("name")]
            _loc_names_set = set(_loc_names)
            _pre_movement_target = command_interpreter._detect_movement_intent(effective_action, _loc_names)
        except Exception:
            pass

        if settings.enable_staged_action_pipeline:
            intent_started = time.perf_counter()
            staged_intent = command_interpreter.interpret_action_intent(
                action=effective_action,
                state_manager=state_manager,
                world_memory_module=world_memory,
                current_storylet=current_storylet,
                db=db,
                scene_card_now=scene_card_now,
            )
            _record_timing(timings_ms, "interpret_action_intent", intent_started)
            if staged_intent is not None:
                staged_intent = action_validation_policy.validate_action_intent(
                    intent=staged_intent,
                    action_text=effective_action,
                    state_manager=state_manager,
                    world_memory_module=world_memory,
                    db=db,
                )
                used_staged_pipeline = True
                staged_ack_line = staged_intent.ack_line or staged_ack_line
                result = staged_intent.result
            else:
                if strict_three_layer:
                    metadata = {
                        "validation_warnings": ["stage_a_unavailable_using_deterministic_planner_fallback"],
                        "staged_pipeline": "intent",
                    }
                    result = command_interpreter.ActionResult(
                        narrative_text=staged_ack_line,
                        state_deltas={},
                        should_trigger_storylet=False,
                        follow_up_choices=[{"label": "Continue", "set": {}}],
                        plausible=True,
                        reasoning_metadata=metadata,
                    )
                    used_staged_pipeline = True
                else:
                    fallback_started = time.perf_counter()
                    result = command_interpreter.interpret_action(
                        action=effective_action,
                        state_manager=state_manager,
                        world_memory_module=world_memory,
                        current_storylet=current_storylet,
                        db=db,
                        scene_card_now=scene_card_now,
                    )
                    _record_timing(
                        timings_ms,
                        "interpret_action_fallback",
                        fallback_started,
                    )
        else:
            interpret_started = time.perf_counter()
            if strict_three_layer:
                staged_intent = command_interpreter.interpret_action_intent(
                    action=effective_action,
                    state_manager=state_manager,
                    world_memory_module=world_memory,
                    current_storylet=current_storylet,
                    db=db,
                    scene_card_now=scene_card_now,
                )
                if staged_intent is not None:
                    staged_intent = action_validation_policy.validate_action_intent(
                        intent=staged_intent,
                        action_text=effective_action,
                        state_manager=state_manager,
                        world_memory_module=world_memory,
                        db=db,
                    )
                    staged_ack_line = staged_intent.ack_line or staged_ack_line
                    result = staged_intent.result
                    used_staged_pipeline = True
                else:
                    metadata = {
                        "validation_warnings": ["stage_a_unavailable_using_deterministic_planner_fallback"],
                        "staged_pipeline": "intent",
                    }
                    result = command_interpreter.ActionResult(
                        narrative_text=staged_ack_line,
                        state_deltas={},
                        should_trigger_storylet=False,
                        follow_up_choices=[{"label": "Continue", "set": {}}],
                        plausible=True,
                        reasoning_metadata=metadata,
                    )
                    used_staged_pipeline = True
            else:
                result = command_interpreter.interpret_action(
                    action=effective_action,
                    state_manager=state_manager,
                    world_memory_module=world_memory,
                    current_storylet=current_storylet,
                    db=db,
                    scene_card_now=scene_card_now,
                )
            _record_timing(timings_ms, "interpret_action", interpret_started)

        if result is None:
            raise RuntimeError("Action interpretation returned no result")

        semantic_goal = _extract_semantic_goal(effective_action)

        beats_started = time.perf_counter()
        for beat in result.suggested_beats:
            if isinstance(beat, dict):
                state_manager.add_narrative_beat(beat)
        _record_timing(timings_ms, "apply_suggested_beats", beats_started)

        goal_started = time.perf_counter()
        goal_update = None
        if isinstance(result.reasoning_metadata, dict):
            raw_goal_update = result.reasoning_metadata.get("goal_update")
            if isinstance(raw_goal_update, dict):
                goal_update = raw_goal_update
        if goal_update:
            state_manager.apply_goal_update(goal_update, source="action_interpreter")
        _record_timing(timings_ms, "apply_goal_update", goal_started)

        applied_deltas: Dict[str, Any] = {}
        committed_deltas: Dict[str, Any] = {}
        reducer_receipt_payload: Dict[str, Any] = {}
        tick_receipt_payload: Dict[str, Any] = {}
        event_type = world_memory.EVENT_TYPE_FREEFORM_ACTION
        action_event_id: int | None = None
        simulation_tick_delta: Dict[str, Any] = {}
        record_event_started = time.perf_counter()
        try:
            delta_contract = _action_result_to_delta_contract(result)
            intent = FreeformActionCommittedIntent(
                action_text=payload.action,
                delta=delta_contract,
            )
            receipt = reduce_event(db, state_manager, intent)
            tick_receipt = reduce_event(db, state_manager, SystemTickIntent())
            committed_deltas = dict(receipt.applied_changes)
            applied_deltas = {**committed_deltas, **tick_receipt.applied_changes}
            # Phase 2: if movement was pre-detected, force location into deltas
            # regardless of what Stage A decided. This is deterministic movement.
            if _pre_movement_target:
                # Ensure the destination exists as a location node (creates it if new).
                try:
                    world_memory.ensure_location_node(db, _pre_movement_target)
                except Exception:
                    pass
                # Stamp the departure event at the ORIGIN so players there can see it.
                # Use "destination" to carry the new location for session tracking.
                applied_deltas = {
                    **applied_deltas,
                    "location": current_location,  # origin — for departure visibility
                    "destination": _pre_movement_target,  # where they went
                }
                # Commit directly to session state so subsequent narration context
                # sees the new location (e.g. co-location queries, scene card).
                try:
                    state_manager.set_variable("location", _pre_movement_target)
                except Exception:
                    pass
            # Guard: the reducer may write a narrative sublocation (e.g. "The Bakery
            # Stall") into applied_deltas["location"] instead of a real graph node.
            # Demote any non-node location to "sublocation" so session tracking always
            # sees a canonical graph node, and heal the state manager so future turns
            # don't start from a corrupted location.
            if not _pre_movement_target and _loc_names_set:
                _raw_loc = applied_deltas.get("location")
                if _raw_loc and _raw_loc not in _loc_names_set:
                    _d = dict(applied_deltas)
                    del _d["location"]
                    _d["sublocation"] = _raw_loc
                    # Restore canonical node — use current_location if it's still valid;
                    # if it was already corrupted, clear it (movement will heal on next wander).
                    _canonical = current_location if current_location in _loc_names_set else None
                    if _canonical:
                        _d["location"] = _canonical
                        try:
                            state_manager.set_variable("location", _canonical)
                        except Exception:
                            pass
                    else:
                        # State manager holds a stale sublocation — clear it so the wander
                        # loop can re-anchor on the next validated movement.
                        try:
                            state_manager.set_variable("location", "")
                        except Exception:
                            pass
                    applied_deltas = _d

            # Always carry the session's current location forward so every event
            # is location-stamped, even when the action doesn't change location.
            if "location" not in applied_deltas:
                current_loc = state_manager.get_variable("location")
                if current_loc:
                    applied_deltas = {**applied_deltas, "location": current_loc}
            reducer_receipt_payload = receipt.model_dump()
            tick_receipt_payload = tick_receipt.model_dump()
            event_type = world_memory.infer_event_type(
                world_memory.EVENT_TYPE_FREEFORM_ACTION,
                applied_deltas,
            )
            if _pre_movement_target:
                event_type = world_memory.EVENT_TYPE_MOVEMENT

            metadata = result.reasoning_metadata if isinstance(result.reasoning_metadata, dict) else {}
            metadata = dict(metadata)
            metadata["reducer_receipt"] = reducer_receipt_payload
            metadata["system_tick_receipt"] = tick_receipt_payload
            metadata["scene_card_now"] = scene_card_now
            _log_structured_turn_event(
                "state_committed",
                session_id=payload.session_id,
                turn_type="action",
                event_type=event_type,
                applied_change_count=len(applied_deltas),
                state_keys=sorted(list(applied_deltas.keys()))[:20],
            )

            sim_delta = tick_world_simulation(state_manager)
            if sim_delta.increment or sim_delta.set or sim_delta.append_fact:
                sim_receipt = reduce_event(
                    db,
                    state_manager,
                    SimulationTickIntent(delta=sim_delta),
                )
                simulation_tick_delta = dict(sim_receipt.applied_changes)
        except Exception as exc:
            logger.exception("Action reducer commit failed; rolling back turn: %s", exc)
            raise

        narrative_excerpt = str(result.narrative_text or "")[:200]
        try:
            event = world_memory.record_event(
                db=db,
                session_id=state_manager.effective_world_session_id(),
                storylet_id=current_storylet_id,
                event_type=event_type,
                summary=f"Player action: {payload.action.rstrip()}{'.' if not payload.action.rstrip().endswith(('.', '!', '?')) else ''} Result: {narrative_excerpt}",
                delta=applied_deltas,
                state_manager=None,
                metadata=metadata,
                idempotency_key=idempotency_key or None,
            )
            action_event_id = int(event.id) if event.id is not None else None

            if simulation_tick_delta:
                world_memory.record_event(
                    db=db,
                    session_id=state_manager.effective_world_session_id(),
                    storylet_id=current_storylet_id,
                    event_type=world_memory.EVENT_TYPE_SIMULATION_TICK,
                    summary="Deterministic world simulation tick",
                    delta=simulation_tick_delta,
                    state_manager=None,
                )
        except Exception as exc:
            logger.warning(
                "Failed to record action world event metadata for session=%s: %s",
                payload.session_id,
                exc,
            )
        _record_timing(timings_ms, "record_action_event", record_event_started)

        validated_result = result
        if applied_deltas:
            validated_result = replace(validated_result, state_deltas=applied_deltas)
        if reducer_receipt_payload or tick_receipt_payload:
            metadata = validated_result.reasoning_metadata if isinstance(validated_result.reasoning_metadata, dict) else {}
            metadata = dict(metadata)
            if reducer_receipt_payload:
                metadata["reducer_receipt"] = reducer_receipt_payload
            if tick_receipt_payload:
                metadata["system_tick_receipt"] = tick_receipt_payload
            metadata["scene_card_now"] = scene_card_now
            validated_result = replace(validated_result, reasoning_metadata=metadata)
        if phase_events is not None:
            phase_events.append(
                (
                    "commit",
                    {
                        "plausible": bool(validated_result.plausible),
                        "state_changes": (validated_result.state_deltas if isinstance(validated_result.state_deltas, dict) else {}),
                    },
                )
            )

        final_result = validated_result
        if used_staged_pipeline and bool(validated_result.plausible):
            if phase_events is not None:
                phase_events.append(("narrate", {"status": "started"}))
            narrate_started = time.perf_counter()
            final_result = command_interpreter.render_validated_action_narration(
                action=effective_action,
                ack_line=staged_ack_line,
                validated_result=validated_result,
                state_manager=state_manager,
                world_memory_module=world_memory,
                current_storylet=current_storylet,
                db=db,
                scene_card_now=scene_card_now,
                resolved_movement_target=_pre_movement_target,
            )
            _record_timing(timings_ms, "render_action_narration", narrate_started)

        choices_started = time.perf_counter()
        raw_choices = final_result.follow_up_choices if isinstance(final_result.follow_up_choices, list) else []
        choices = []
        for choice in raw_choices[:3]:
            if not isinstance(choice, dict):
                continue
            choice_set = choice.get("set", {})
            if not isinstance(choice_set, dict):
                choice_set = {}
            normalized = {
                "label": str(choice.get("label", "Continue")),
                "set": choice_set,
            }
            intent_text = choice.get("intent")
            if intent_text and isinstance(intent_text, str):
                normalized["intent"] = intent_text.strip()
            choices.append(normalized)
        # Freeform mode: no prescribed choices
        choices = []
        _record_timing(timings_ms, "normalize_choices", choices_started)

        arc_started = time.perf_counter()
        state_manager.advance_story_arc(choices_made=choices)
        _record_timing(timings_ms, "advance_story_arc", arc_started)

        state_changes = dict(applied_deltas)
        narrative_text = str(final_result.narrative_text or "")

        # Post-narration: scan narrative for location mentions and grow the graph.
        # Fire-and-forget — errors are swallowed inside extract_location_mentions.
        _current_loc = state_manager.get_variable("location") or ""
        if narrative_text and _current_loc:
            world_memory.extract_location_mentions(db, narrative_text, _current_loc)

        player_hint_channel_enabled = bool(settings.enable_v3_player_hint_channel)
        player_hint_payload: Dict[str, Any] | None = None
        hint_started = time.perf_counter()
        if semantic_goal and player_hint_channel_enabled:
            try:
                from .semantic_selector import compute_player_context_vector

                spatial_nav = get_spatial_navigator_fn(db)
                effective_storylet = current_storylet
                if effective_storylet is None:
                    positioned_ids = list(spatial_nav.storylet_positions.keys())
                    if positioned_ids:
                        effective_storylet = db.query(Storylet).filter(Storylet.id.in_(positioned_ids)).first()
                if effective_storylet is None:
                    raise ValueError("No positioned storylet available for semantic hint")
                effective_storylet_id, _ = _safe_storylet_identity(effective_storylet)
                if effective_storylet_id is None:
                    raise ValueError("No stable storylet id available for semantic hint")

                context_vector = compute_player_context_vector(
                    state_manager,
                    world_memory,
                    db,
                )
                goal_hint = spatial_nav.get_semantic_goal_hint(
                    current_storylet_id=effective_storylet_id,
                    player_vars=_public_contextual_vars(state_manager),
                    semantic_goal=semantic_goal,
                    context_vector=context_vector,
                )
                if goal_hint and goal_hint.get("hint"):
                    player_hint_payload = _build_semantic_goal_player_hint_payload(goal_hint)
                    narrative_text = f"{narrative_text} {goal_hint['hint']}".strip()
            except Exception as exc:
                logger.debug("Could not resolve semantic goal hint: %s", exc)
        _record_timing(timings_ms, "semantic_goal_hint", hint_started)
        if player_hint_channel_enabled and player_hint_payload is None:
            player_hint_payload = _unknown_player_hint_payload(source="semantic_goal")

        motif_started = time.perf_counter()
        _update_motif_ledger_from_narrative(
            state_manager=state_manager,
            narrative_text=narrative_text,
        )
        _record_timing(timings_ms, "update_motif_ledger", motif_started)

        # Projection hint fallback: when no semantic-goal hint resolved and the
        # hint channel is enabled, surface a projection stub from the cache if one
        # exists. The action just committed so clarity is "committed", but the next
        # frontier stubs from the pre-action prefetch may still be useful context.
        if player_hint_channel_enabled and player_hint_payload is None:
            action_story_payload = {"id": current_storylet_id, "title": ""}
            proj_stub, _ = _projection_seed_bundle_for_storylet(payload.session_id, action_story_payload)
            if proj_stub is not None:
                player_hint_payload = _build_projection_player_hint_payload(proj_stub)

        vars_started = time.perf_counter()
        action_plausible = bool(final_result.plausible)
        response = {
            "narrative": narrative_text,
            "state_changes": state_changes,
            "choices": choices,
            "plausible": action_plausible,
            "vars": _public_contextual_vars(state_manager),
        }
        if used_staged_pipeline or is_choice_button:
            response["ack_line"] = staged_ack_line
        _record_timing(timings_ms, "build_response", vars_started)

        response_vars = response.get("vars")
        if not isinstance(response_vars, dict):
            response_vars = {}
        diag = response_vars.get("_ww_diag", {})
        if not isinstance(diag, dict):
            diag = {}
        if used_choice_intent and used_staged_pipeline:
            action_pipeline_mode = "unified_intent"
        elif used_staged_pipeline:
            action_pipeline_mode = "staged_action"
        else:
            action_pipeline_mode = "direct_action"
        diag.update(
            {
                "turn_source": "choice_button" if is_choice_button else "freeform_action",
                "choice_label": str(payload.choice_label or "").strip() if is_choice_button else None,
                "pipeline_mode": action_pipeline_mode,
                "selection_mode": str(diag.get("selection_mode") or "action_commit"),
                "active_storylets_count": _coerce_non_negative_int(diag.get("active_storylets_count"), default=0),
                "eligible_storylets_count": _coerce_non_negative_int(diag.get("eligible_storylets_count"), default=0),
                "fallback_reason": str(diag.get("fallback_reason") or ("none" if action_plausible else "action_interpreter_rejected")),
                "clarity_level": "committed",
                "scene_clarity_level": "committed",
                "player_hint_channel_enabled": player_hint_channel_enabled,
                "player_hint_clarity_level": _normalize_clarity_level(player_hint_payload.get("clarity") if isinstance(player_hint_payload, dict) else "unknown"),
            }
        )
        if player_hint_channel_enabled and isinstance(player_hint_payload, dict):
            response_vars["_ww_hint"] = dict(player_hint_payload)

        invalidation = invalidate_projection_for_session(
            payload.session_id,
            selected_projection_id=None,
            commit_status="committed",
        )
        diag.update(invalidation)
        response_vars["_ww_diag"] = diag
        prioritized_response_vars: Dict[str, Any] = {}
        if "_ww_diag" in response_vars:
            prioritized_response_vars["_ww_diag"] = response_vars["_ww_diag"]
        if "_ww_hint" in response_vars:
            prioritized_response_vars["_ww_hint"] = response_vars["_ww_hint"]
        for key, value in response_vars.items():
            if key in {"_ww_diag", "_ww_hint"}:
                continue
            prioritized_response_vars[key] = value
        response_vars = prioritized_response_vars
        response["vars"] = response_vars
        response["diagnostics"] = dict(diag)

        save_started = time.perf_counter()
        save_state(state_manager, db)
        _record_timing(timings_ms, "save_state", save_started)

        persist_idempotent_started = time.perf_counter()
        if idempotency_key and action_event_id is not None:
            try:
                world_memory.persist_action_idempotent_response(
                    db=db,
                    event_id=action_event_id,
                    response_payload=response,
                )
            except Exception as exc:
                logger.warning("Failed to persist idempotent action response: %s", exc)
        _record_timing(
            timings_ms,
            "persist_idempotent_response",
            persist_idempotent_started,
        )
        return response

    @staticmethod
    def process_next_turn(
        *,
        db: Session,
        payload: NextReq,
        timings_ms: Dict[str, float] | None = None,
        debug_scores: bool = False,
        ensure_storylets_fn=ensure_storylets,
        pick_storylet_fn=pick_storylet_enhanced,
        adapt_storylet_fn=adapt_storylet_to_context,
        generate_next_beat_fn=generate_next_beat,
        normalize_choice_fn=normalize_choice,
        render_fn=render,
    ) -> Dict[str, Any]:
        """Resolve one /next turn through the shared phase pipeline.

        When WW_ENABLE_UNIFIED_TURN_PIPELINE is true (default), delegates to
        process_turn so that /next and /action share the same spine.
        """
        if settings.enable_unified_turn_pipeline:
            turn_input = UnifiedTurnInput.from_next_request(payload)
            result = TurnOrchestrator.process_turn(
                db=db,
                turn_input=turn_input,
                timings_ms=timings_ms,
                debug_scores=debug_scores,
                ensure_storylets_fn=ensure_storylets_fn,
                pick_storylet_fn=pick_storylet_fn,
                adapt_storylet_fn=adapt_storylet_fn,
                generate_next_beat_fn=generate_next_beat_fn,
                normalize_choice_fn=normalize_choice_fn,
                render_fn=render_fn,
            )
            return TurnOrchestrator._as_next_response(result)

        from . import world_memory

        turn_source = _resolve_next_turn_source(payload)
        choice_label = str(payload.choice_label or "").strip() if hasattr(payload, "choice_label") else ""
        state_manager = get_state_manager(payload.session_id, db)
        pre_storylet_applied: Dict[str, Any] = {}
        choice_effect_receipt_payload: Dict[str, Any] = {}
        choice_effect_ops_applied: List[Dict[str, Any]] = []

        set_vars_started = time.perf_counter()
        inbound_vars = payload.vars if isinstance(payload.vars, dict) else {}
        if inbound_vars:
            var_delta = ActionDeltaContract()
            for key, value in inbound_vars.items():
                var_delta.set.append(ActionDeltaSetOperation(key=key, value=value))
            var_receipt = reduce_event(
                db,
                state_manager,
                ChoiceSelectedIntent(
                    label="Client Vars Sync",
                    delta=var_delta,
                ),
            )
            pre_storylet_applied.update(var_receipt.applied_changes)

        if payload.choice_taken:
            intent = ChoiceSelectedIntent(
                label="Player Choice",
                delta=payload.choice_taken,
            )
            choice_receipt = reduce_event(db, state_manager, intent)
            pre_storylet_applied.update(choice_receipt.applied_changes)

            choice_effects_started = time.perf_counter()
            pending_choice_effects = state_manager.get_variable(
                _PENDING_STORYLET_CHOICE_EFFECTS_KEY,
                None,
            )
            pending_effects_payload: Any = None
            if isinstance(pending_choice_effects, dict):
                pending_effects_payload = pending_choice_effects.get("effects", [])

            pending_delta, choice_effect_ops_applied = _storylet_effects_to_delta_contract(
                pending_effects_payload,
                trigger=_STORYLET_EFFECTS_ON_CHOICE_COMMIT,
            )
            if choice_effect_ops_applied:
                pending_receipt = reduce_event(
                    db,
                    state_manager,
                    ChoiceSelectedIntent(
                        label="Storylet Choice Commit Effects",
                        delta=pending_delta,
                    ),
                )
                pre_storylet_applied.update(pending_receipt.applied_changes)
                choice_effect_receipt_payload = pending_receipt.model_dump()
            state_manager.delete_variable(_PENDING_STORYLET_CHOICE_EFFECTS_KEY)
            _record_timing(
                timings_ms,
                "apply_storylet_choice_effects",
                choice_effects_started,
            )

            tick = SystemTickIntent()
            tick_receipt = reduce_event(db, state_manager, tick)
            pre_storylet_applied.update(tick_receipt.applied_changes)
        if pre_storylet_applied:
            _log_structured_turn_event(
                "state_committed",
                session_id=payload.session_id,
                turn_type="next",
                event_type="choice_or_vars",
                applied_change_count=len(pre_storylet_applied),
                state_keys=sorted(list(pre_storylet_applied.keys()))[:20],
            )
        _record_timing(timings_ms, "set_vars", set_vars_started)
        goal_backfill_started = time.perf_counter()
        goal_backfill = state_manager.backfill_primary_goal_if_empty_after_initial_turn(
            minimum_turn_count=1,
        )
        if bool(goal_backfill.get("applied")):
            _log_structured_turn_event(
                "goal_backfilled",
                session_id=payload.session_id,
                turn_type="next",
                primary_goal=goal_backfill.get("primary_goal", ""),
                source=goal_backfill.get("source", ""),
                turn_count=goal_backfill.get("turn_count", 0),
            )
        _record_timing(timings_ms, "backfill_primary_goal", goal_backfill_started)

        context_started = time.perf_counter()
        contextual_vars = _public_contextual_vars(state_manager)
        _record_timing(timings_ms, "get_contextual_vars", context_started)
        scene_card_started = time.perf_counter()
        scene_card_now = _build_scene_card_payload(
            db=db,
            state_manager=state_manager,
            get_spatial_navigator_fn=get_spatial_navigator,
        )
        motifs_recent = list(state_manager.get_recent_motifs(limit=max(8, int(settings.motif_ledger_max_items))))
        sensory_palette = prompt_library.build_scene_card_sensory_palette(scene_card_now)
        _record_timing(timings_ms, "build_scene_card_now", scene_card_started)

        world_bible = state_manager.get_world_bible()
        projection_seeded_narration_enabled = bool(settings.enable_v3_projection_seeded_narration)
        player_hint_channel_enabled = bool(settings.enable_v3_player_hint_channel)
        default_player_hint_payload = _unknown_player_hint_payload(source="projection_seed") if player_hint_channel_enabled else None
        # JIT beat generation fires when the eligible storylet pool is thin
        # (below jit_expansion_eligible_threshold).  This lets the world
        # expand generatively as players explore, rather than only falling
        # back when the pool is completely empty.
        _jit_eligible_count = 0
        if settings.enable_jit_beat_generation and world_bible:
            try:
                from .storylet_selector import count_eligible_storylets

                _jit_eligible_count = count_eligible_storylets(db, state_manager)
            except Exception as _elig_exc:
                logger.debug("Eligible storylet pre-check failed: %s", _elig_exc)
        _jit_threshold = max(0, int(settings.jit_expansion_eligible_threshold))
        if settings.enable_jit_beat_generation and world_bible and _jit_eligible_count < _jit_threshold:
            jit_started = time.perf_counter()
            try:
                recent_event_summaries_jit: List[str] = []
                try:
                    recent_events_jit = world_memory.get_world_history(
                        db,
                        session_id=state_manager.effective_world_session_id(),
                        limit=5,
                    )
                    recent_event_summaries_jit = [str(event.summary).strip() for event in recent_events_jit if str(event.summary).strip()]
                except Exception:
                    pass

                # Pull frontier stubs from BFS prefetch to ground JIT narration.
                # The top stubs (by semantic score) are passed as narrative_hooks
                # so the LLM narrator foreshadows reachable storylet threads
                # rather than improvising in isolation.
                jit_frontier_hooks: List[Dict[str, Any]] = []
                try:
                    cached_frontier = get_cached_frontier(payload.session_id)
                    if isinstance(cached_frontier, dict):
                        raw_stubs = cached_frontier.get("stubs") or []
                        scored = sorted(
                            [s for s in raw_stubs if isinstance(s, dict) and (s.get("premise") or s.get("title"))],
                            key=lambda s: float(s.get("semantic_score") or 0.0),
                            reverse=True,
                        )
                        jit_frontier_hooks = scored[: max(0, int(settings.jit_frontier_hook_count))]
                except Exception:
                    pass

                beat = generate_next_beat_fn(
                    world_bible=world_bible,
                    recent_events=recent_event_summaries_jit,
                    current_vars=state_manager.variables,
                    scene_card=scene_card_now,
                    motifs_recent=motifs_recent,
                    sensory_palette=sensory_palette,
                    frontier_hooks=jit_frontier_hooks,
                )
                state_manager.advance_story_arc(choices_made=[])
                text = beat["text"]
                _update_motif_ledger_from_narrative(
                    state_manager=state_manager,
                    narrative_text=text,
                )
                # Apply any state_changes the beat declares directly to session vars
                beat_state_changes = beat.get("state_changes", {})
                if isinstance(beat_state_changes, dict) and beat_state_changes:
                    for k, v in beat_state_changes.items():
                        state_manager.variables[str(k)] = v
                    state_manager._invalidate_cache()
                choices: List[ChoiceOut] = []
                scene_clarity_level = "unknown"
                _beat_is_fallback = bool(beat.get("beat_fallback"))
                # Derive a live hint from beat content rather than leaving the
                # hint channel frozen at 'unknown' for the entire JIT path.
                jit_hint_payload = _build_jit_beat_player_hint_payload(beat) if player_hint_channel_enabled and not _beat_is_fallback else default_player_hint_payload
                player_hint_clarity_level = _normalize_clarity_level(jit_hint_payload.get("clarity") if isinstance(jit_hint_payload, dict) else "unknown")
                vars_payload = _inject_next_diagnostics(
                    contextual_vars,
                    {
                        "turn_source": turn_source,
                        "pipeline_mode": "jit_beat",
                        "selection_mode": "jit_beat_generation",
                        "active_storylets_count": _jit_eligible_count,
                        "eligible_storylets_count": _jit_eligible_count,
                        "fallback_reason": "jit_beat_fallback" if _beat_is_fallback else "none",
                        "clarity_level": scene_clarity_level,
                        "narrative_source": "jit_beat_fallback" if _beat_is_fallback else "jit_beat",
                        "projection_seeded_narration_enabled": projection_seeded_narration_enabled,
                        "projection_seed_used": False,
                        "player_hint_channel_enabled": player_hint_channel_enabled,
                        "scene_clarity_level": scene_clarity_level,
                        "player_hint_clarity_level": player_hint_clarity_level,
                    },
                )
                vars_payload = _inject_player_hint(vars_payload, jit_hint_payload)
                out = NextResp(
                    text=text,
                    choices=choices,
                    vars=vars_payload,
                    diagnostics=dict(vars_payload.get("_ww_diag", {})) if isinstance(vars_payload.get("_ww_diag"), dict) else {},
                )
                _record_timing(timings_ms, "jit_beat_generation", jit_started)
                # Persist the JIT beat as a real storylet so the pool grows
                # over time, enabling the world to expand generatively.
                if settings.jit_persist_beats:
                    try:
                        _persist_jit_beat_as_storylet(db, beat, state_manager)
                    except Exception as _persist_exc:
                        logger.debug("JIT beat persistence failed (non-fatal): %s", _persist_exc)
                save_state(state_manager, db)
                return {"response": out, "debug": None}
            except Exception as exc:
                logger.warning(
                    "JIT beat generation failed (%s) - falling back to storylet path: %s",
                    type(exc).__name__,
                    exc,
                )
                _record_timing(timings_ms, "jit_beat_generation", jit_started)

        ensure_started = time.perf_counter()
        ensure_storylets_fn(db, contextual_vars)
        _record_timing(timings_ms, "ensure_storylets", ensure_started)

        debug_requested = bool(debug_scores and settings.enable_dev_reset)
        selection_debug: Dict[str, Any] = {}
        select_started = time.perf_counter()
        story = pick_storylet_fn(
            db,
            state_manager,
            debug_selection=selection_debug,
        )
        story_id, story_title = _safe_storylet_identity(story)
        selection_mode = None
        selection_mode = selection_debug.get("selection_mode")
        _log_structured_turn_event(
            "storylet_selected",
            session_id=payload.session_id,
            turn_type="next",
            storylet_id=story_id,
            storylet_title=story_title,
            selection_mode=str(selection_mode or "none"),
        )
        _record_timing(timings_ms, "pick_storylet", select_started)

        fallback_reason = "none"
        narrative_source = "storylet_selection"

        if story is None:
            eligible_count = int(selection_debug.get("eligible_count", 0) or 0)
            fallback_reason = "no_eligible_storylets" if eligible_count <= 0 else "no_storylet_selected"
            narrative_source = "engine_idle_fallback"
            text = "The tunnel is quiet. Nothing compelling meets the eye."
            choices = []

            if state_manager.environment.danger_level > 3:
                text = "The air feels heavy with danger. Perhaps it is wise to wait and listen."
            elif state_manager.environment.time_of_day == "night":
                text = "The darkness is deep. Something stirs in the shadows, but nothing approaches."
            _update_motif_ledger_from_narrative(
                state_manager=state_manager,
                narrative_text=text,
            )
            scene_clarity_level = "unknown"
            player_hint_clarity_level = _normalize_clarity_level(default_player_hint_payload.get("clarity") if isinstance(default_player_hint_payload, dict) else "unknown")
            vars_payload = _inject_next_diagnostics(
                contextual_vars,
                {
                    "turn_source": turn_source,
                    "pipeline_mode": "engine_idle_fallback",
                    "selection_mode": str(selection_mode or "none"),
                    "active_storylets_count": int(selection_debug.get("active_storylets_count", 0) or 0),
                    "eligible_storylets_count": int(selection_debug.get("eligible_count", 0) or 0),
                    "fallback_reason": fallback_reason,
                    "clarity_level": scene_clarity_level,
                    "narrative_source": narrative_source,
                    "projection_seeded_narration_enabled": projection_seeded_narration_enabled,
                    "projection_seed_used": False,
                    "player_hint_channel_enabled": player_hint_channel_enabled,
                    "scene_clarity_level": scene_clarity_level,
                    "player_hint_clarity_level": player_hint_clarity_level,
                },
            )
            vars_payload = _inject_player_hint(vars_payload, default_player_hint_payload)
            out = NextResp(
                text=text,
                choices=choices,
                vars=vars_payload,
                diagnostics=dict(vars_payload.get("_ww_diag", {})) if isinstance(vars_payload.get("_ww_diag"), dict) else {},
            )
        else:
            story_payload = _snapshot_storylet_payload(story)
            story_id = cast(int | None, story_payload.get("id"))
            story_title = str(story_payload.get("title") or "")
            recent_event_summaries: List[str] = []
            history_started = time.perf_counter()
            try:
                recent_events = world_memory.get_world_history(
                    db,
                    session_id=state_manager.effective_world_session_id(),
                    limit=3,
                )
                recent_event_summaries = [str(event.summary).strip() for event in recent_events if str(event.summary).strip()]
            except Exception as exc:
                logging.debug(
                    "Could not load recent world history for adaptation: %s",
                    exc,
                )
            finally:
                _record_timing(timings_ms, "load_recent_history", history_started)

            if story_id is None:
                persist_started = time.perf_counter()
                try:
                    db.add(story)
                    db.commit()
                    db.refresh(story)
                    story_payload = _snapshot_storylet_payload(story)
                    story_id = cast(int | None, story_payload.get("id"))
                    story_title = str(story_payload.get("title") or "")
                except Exception as exc:
                    db.rollback()
                    logger.warning("Failed to persist selected transient stub: %s", exc)
                finally:
                    _record_timing(timings_ms, "persist_stub", persist_started)

            state_manager.advance_story_arc(
                choices_made=payload.vars.get("choices") if payload.vars else [],
            )

            selected_projection_stub: Dict[str, Any] | None = None
            contrast_projection_stub: Dict[str, Any] | None = None
            if projection_seeded_narration_enabled:
                selected_projection_stub, contrast_projection_stub = _projection_seed_bundle_for_storylet(
                    payload.session_id,
                    story_payload,
                )

            adaptation_context = {
                "variables": contextual_vars,
                "environment": state_manager.environment.__dict__.copy(),
                "recent_events": recent_event_summaries,
                "state_summary": state_manager.get_state_summary(),
                "scene_card_now": scene_card_now,
                "goal_lens": state_manager.get_goal_lens_payload(),
                "motifs_recent": motifs_recent,
                "sensory_palette": sensory_palette,
                **({"chosen_action": choice_label} if choice_label else {}),
            }
            if selected_projection_stub is not None:
                adaptation_context["selected_projection_stub"] = selected_projection_stub
            if contrast_projection_stub is not None:
                adaptation_context["contrast_projection_stub"] = contrast_projection_stub
            adapt_started = time.perf_counter()
            adapted = adapt_storylet_fn(SimpleNamespace(**story_payload), adaptation_context)
            _record_timing(timings_ms, "adapt_storylet", adapt_started)
            _adapted_governance = adapted.get("motif_governance", {}) if isinstance(adapted.get("motif_governance"), dict) else {}
            text = str(adapted.get("text") or render_fn(str(story_payload.get("text_template", "")), contextual_vars))
            _update_motif_ledger_from_narrative(
                state_manager=state_manager,
                narrative_text=text,
            )
            adapted_choices = adapted.get("choices")
            if not isinstance(adapted_choices, list):
                adapted_choices = cast(List[Dict[str, Any]], story_payload.get("choices", []))
            if not str(adapted.get("text") or "").strip():
                fallback_reason = "template_fallback_after_adaptation"
                narrative_source = "template_fallback"
            else:
                narrative_source = f"storylet_{str(story_payload.get('source', 'authored') or 'authored')}"
            choices = [ChoiceOut(**normalize_choice_fn(choice)) for choice in cast(List[Dict[str, Any]], adapted_choices)]

            fire_effects_started = time.perf_counter()
            storylet_effect_delta, fire_effect_ops_applied = _storylet_effects_to_delta_contract(
                story_payload.get("effects", []),
                trigger=_STORYLET_EFFECTS_ON_FIRE,
            )
            storylet_effect_applied_changes: Dict[str, Any] = {}
            storylet_effect_receipt_payload: Dict[str, Any] = {}
            if fire_effect_ops_applied:
                fire_receipt = reduce_event(
                    db,
                    state_manager,
                    ChoiceSelectedIntent(
                        label="Storylet Fire Effects",
                        delta=storylet_effect_delta,
                    ),
                )
                storylet_effect_applied_changes.update(fire_receipt.applied_changes)
                storylet_effect_receipt_payload = fire_receipt.model_dump()

            _, pending_choice_effect_ops = _storylet_effects_to_delta_contract(
                story_payload.get("effects", []),
                trigger=_STORYLET_EFFECTS_ON_CHOICE_COMMIT,
            )
            if pending_choice_effect_ops:
                state_manager.set_variable(
                    _PENDING_STORYLET_CHOICE_EFFECTS_KEY,
                    {
                        "storylet_id": story_id,
                        "storylet_title": (story_title or "unknown"),
                        "effects": pending_choice_effect_ops,
                    },
                )
            else:
                state_manager.delete_variable(_PENDING_STORYLET_CHOICE_EFFECTS_KEY)
            _record_timing(timings_ms, "apply_storylet_fire_effects", fire_effects_started)

            final_contextual_vars = _public_contextual_vars(state_manager)
            player_hint_payload = (
                _build_projection_player_hint_payload(
                    selected_projection_stub,
                    contrast_projection_stub,
                )
                if player_hint_channel_enabled
                else None
            )
            scene_clarity_level = _scene_clarity_level_from_projection(selected_projection_stub)
            player_hint_clarity_level = _normalize_clarity_level(player_hint_payload.get("clarity") if isinstance(player_hint_payload, dict) else "unknown")
            choice_ack_line = f'You choose: "{choice_label}".' if choice_label else None
            vars_payload = _inject_next_diagnostics(
                final_contextual_vars,
                {
                    "turn_source": turn_source,
                    "pipeline_mode": "storylet_selection",
                    "selection_mode": str(selection_mode or "none"),
                    "active_storylets_count": int(selection_debug.get("active_storylets_count", 0) or 0),
                    "eligible_storylets_count": int(selection_debug.get("eligible_count", 0) or 0),
                    "fallback_reason": fallback_reason,
                    "clarity_level": scene_clarity_level,
                    "narrative_source": narrative_source,
                    "projection_seeded_narration_enabled": projection_seeded_narration_enabled,
                    "projection_seed_used": bool(selected_projection_stub),
                    "projection_seed_storylet_id": (selected_projection_stub.get("storylet_id") if selected_projection_stub is not None else None),
                    "player_hint_channel_enabled": player_hint_channel_enabled,
                    "scene_clarity_level": scene_clarity_level,
                    "player_hint_clarity_level": player_hint_clarity_level,
                    "narrator_parse_success": bool(adapted.get("narrator_parse_success", True)),
                    "referee_decision_valid": bool(_adapted_governance.get("referee_decision_was_valid", True)),
                    "referee_decision": str(_adapted_governance.get("motif_referee_decision", "skipped")),
                    **({"ack_line": choice_ack_line} if choice_ack_line else {}),
                },
            )
            vars_payload = _inject_player_hint(vars_payload, player_hint_payload)
            out = NextResp(
                text=text,
                choices=choices,
                vars=vars_payload,
                diagnostics=dict(vars_payload.get("_ww_diag", {})) if isinstance(vars_payload.get("_ww_diag"), dict) else {},
            )

            record_started = time.perf_counter()
            try:
                event_metadata: Dict[str, Any] = {}
                if fire_effect_ops_applied:
                    event_metadata = {
                        world_memory.STORYLET_EFFECTS_TRIGGER_KEY: _STORYLET_EFFECTS_ON_FIRE,
                        world_memory.STORYLET_EFFECTS_METADATA_KEY: fire_effect_ops_applied,
                        world_memory.STORYLET_EFFECTS_RECEIPT_KEY: storylet_effect_receipt_payload,
                    }
                if choice_effect_ops_applied:
                    event_metadata[world_memory.STORYLET_CHOICE_COMMIT_EFFECTS_KEY] = {
                        world_memory.STORYLET_EFFECTS_TRIGGER_KEY: _STORYLET_EFFECTS_ON_CHOICE_COMMIT,
                        world_memory.STORYLET_EFFECTS_METADATA_KEY: choice_effect_ops_applied,
                        world_memory.STORYLET_EFFECTS_RECEIPT_KEY: choice_effect_receipt_payload,
                    }
                world_memory.record_event(
                    db=db,
                    session_id=state_manager.effective_world_session_id(),
                    storylet_id=story_id,
                    event_type=world_memory.EVENT_TYPE_STORYLET_FIRED,
                    summary=f"Storylet '{story_title or 'unknown'}' fired",
                    delta=storylet_effect_applied_changes,
                    metadata=event_metadata or None,
                )
            except Exception as exc:
                logging.warning("Failed to record storylet event: %s", exc)
            finally:
                _record_timing(timings_ms, "record_storylet_event", record_started)

            sim_delta = tick_world_simulation(state_manager)
            if sim_delta.increment or sim_delta.set or sim_delta.append_fact:
                sim_receipt = reduce_event(
                    db,
                    state_manager,
                    SimulationTickIntent(delta=sim_delta),
                )
                try:
                    world_memory.record_event(
                        db=db,
                        session_id=state_manager.effective_world_session_id(),
                        storylet_id=story_id,
                        event_type=world_memory.EVENT_TYPE_SIMULATION_TICK,
                        summary="Deterministic world simulation tick",
                        delta=sim_receipt.applied_changes,
                    )
                except Exception as exc:
                    logging.warning("Failed to record simulation tick: %s", exc)

        save_started = time.perf_counter()
        save_state(state_manager, db)
        _record_timing(timings_ms, "save_state", save_started)
        return {
            "response": out,
            "debug": selection_debug if debug_requested else None,
        }

    @staticmethod
    def process_turn(
        *,
        db: Session,
        turn_input: "UnifiedTurnInput",
        timings_ms: Dict[str, float] | None = None,
        phase_events: List[Tuple[str, Dict[str, Any]]] | None = None,
        ack_line_hint: str | None = None,
        debug_scores: bool = False,
        get_spatial_navigator_fn=get_spatial_navigator,
        pick_storylet_fn=pick_storylet_enhanced,
        render_fn=render,
        find_storylet_by_location_fn=find_storylet_by_location,
        ensure_storylets_fn=ensure_storylets,
        adapt_storylet_fn=adapt_storylet_to_context,
        generate_next_beat_fn=generate_next_beat,
        normalize_choice_fn=normalize_choice,
    ) -> Dict[str, Any]:
        """Unified turn pipeline for freeform actions, choice buttons, and /next turns.

        Returns a unified dict:
          narrative, choices (List[ChoiceOut]), vars, diagnostics, plausible,
          state_changes, ack_line, triggered_storylet, _debug.

        Wrapper helpers _as_action_response / _as_next_response project this
        into the legacy shapes expected by the existing routes.

        Routing:
          is_freeform=True  → Stage A intent extraction → Stage C narration (freeform prose)
          is_freeform=False → ChoiceSelectedIntent commit → JIT or storylet narration
        """
        from . import action_validation_policy, command_interpreter, world_memory

        # ── 1. IDEMPOTENCY CHECK (action turns with key only) ─────────────────
        idempotency_key = turn_input.idempotency_key
        action_event_id: int | None = None
        idempotency_started = time.perf_counter()
        if idempotency_key:
            replay = world_memory.get_action_idempotent_response(
                db=db,
                session_id=turn_input.session_id,
                idempotency_key=idempotency_key,
            )
            if replay is not None:
                _record_timing(timings_ms, "idempotency_lookup", idempotency_started)
                return replay
        _record_timing(timings_ms, "idempotency_lookup", idempotency_started)

        # ── 2. LOAD STATE + commit inbound vars / choice ───────────────────────
        state_started = time.perf_counter()
        state_manager = get_state_manager(turn_input.session_id, db)
        _record_timing(timings_ms, "load_state_manager", state_started)

        pre_commit_applied: Dict[str, Any] = {}
        choice_effect_ops_applied: List[Dict[str, Any]] = []
        choice_effect_receipt_payload: Dict[str, Any] = {}

        set_vars_started = time.perf_counter()

        # Action-style choice button: commit choice_vars immediately
        if not turn_input.is_freeform and turn_input.choice_vars:
            var_delta = ActionDeltaContract()
            for key, value in turn_input.choice_vars.items():
                var_delta.set.append(ActionDeltaSetOperation(key=key, value=value))
            reduce_event(
                db,
                state_manager,
                ChoiceSelectedIntent(
                    label=str(turn_input.choice_label or "Choice"),
                    delta=var_delta,
                ),
            )

        # Next-style inbound vars sync
        if turn_input.inbound_vars:
            var_delta = ActionDeltaContract()
            for key, value in turn_input.inbound_vars.items():
                var_delta.set.append(ActionDeltaSetOperation(key=key, value=value))
            var_receipt = reduce_event(
                db,
                state_manager,
                ChoiceSelectedIntent(label="Client Vars Sync", delta=var_delta),
            )
            pre_commit_applied.update(var_receipt.applied_changes)

        # Next-style choice_taken + pending storylet choice effects
        if turn_input.choice_taken:
            choice_receipt = reduce_event(
                db,
                state_manager,
                ChoiceSelectedIntent(label="Player Choice", delta=turn_input.choice_taken),
            )
            pre_commit_applied.update(choice_receipt.applied_changes)

            choice_effects_started = time.perf_counter()
            pending_choice_effects = state_manager.get_variable(_PENDING_STORYLET_CHOICE_EFFECTS_KEY, None)
            pending_effects_payload: Any = None
            if isinstance(pending_choice_effects, dict):
                pending_effects_payload = pending_choice_effects.get("effects", [])
            pending_delta, choice_effect_ops_applied = _storylet_effects_to_delta_contract(pending_effects_payload, trigger=_STORYLET_EFFECTS_ON_CHOICE_COMMIT)
            if choice_effect_ops_applied:
                pending_receipt = reduce_event(
                    db,
                    state_manager,
                    ChoiceSelectedIntent(label="Storylet Choice Commit Effects", delta=pending_delta),
                )
                pre_commit_applied.update(pending_receipt.applied_changes)
                choice_effect_receipt_payload = pending_receipt.model_dump()
            state_manager.delete_variable(_PENDING_STORYLET_CHOICE_EFFECTS_KEY)
            _record_timing(timings_ms, "apply_storylet_choice_effects", choice_effects_started)

            tick_receipt = reduce_event(db, state_manager, SystemTickIntent())
            pre_commit_applied.update(tick_receipt.applied_changes)

        if pre_commit_applied:
            _log_structured_turn_event(
                "state_committed",
                session_id=turn_input.session_id,
                turn_type="next" if not turn_input.is_freeform else "action",
                event_type="choice_or_vars",
                applied_change_count=len(pre_commit_applied),
                state_keys=sorted(list(pre_commit_applied.keys()))[:20],
            )
        _record_timing(timings_ms, "set_vars", set_vars_started)

        # Goal backfill for non-freeform turns
        if not turn_input.is_freeform:
            goal_backfill_started = time.perf_counter()
            goal_backfill = state_manager.backfill_primary_goal_if_empty_after_initial_turn(
                minimum_turn_count=1,
            )
            if bool(goal_backfill.get("applied")):
                _log_structured_turn_event(
                    "goal_backfilled",
                    session_id=turn_input.session_id,
                    turn_type="next",
                    primary_goal=goal_backfill.get("primary_goal", ""),
                    source=goal_backfill.get("source", ""),
                    turn_count=goal_backfill.get("turn_count", 0),
                )
            _record_timing(timings_ms, "backfill_primary_goal", goal_backfill_started)

        # ── 3. SCENE CARD + SHARED CONTEXT ────────────────────────────────────
        location_started = time.perf_counter()
        current_location = str(state_manager.get_variable("location", "start"))
        current_storylet = find_storylet_by_location(db, current_location)
        current_storylet_id, _ = _safe_storylet_identity(current_storylet)
        _record_timing(timings_ms, "resolve_current_storylet", location_started)

        scene_card_started = time.perf_counter()
        scene_card_now = _build_scene_card_payload(
            db=db,
            state_manager=state_manager,
            get_spatial_navigator_fn=get_spatial_navigator_fn,
        )
        _record_timing(timings_ms, "build_scene_card_now", scene_card_started)

        contextual_vars = _public_contextual_vars(state_manager)
        motifs_recent = list(state_manager.get_recent_motifs(limit=max(8, int(settings.motif_ledger_max_items))))
        sensory_palette = prompt_library.build_scene_card_sensory_palette(scene_card_now)
        world_bible = state_manager.get_world_bible()
        projection_seeded_narration_enabled = bool(settings.enable_v3_projection_seeded_narration)
        player_hint_channel_enabled = bool(settings.enable_v3_player_hint_channel)
        default_player_hint_payload = _unknown_player_hint_payload(source="projection_seed") if player_hint_channel_enabled else None

        # ── 4. INTENT EXTRACTION (freeform turns only) ────────────────────────
        result = None
        staged_ack_line = ack_line_hint or (_quick_ack_line(turn_input.action) if turn_input.action else "")
        used_staged_pipeline = False
        semantic_goal: str | None = None

        # Phase 2 spatial navigation: detect movement before Stage A
        _pre_movement_target2: Optional[str] = None
        _loc_names2_set: set = set()
        if turn_input.is_freeform and turn_input.action:
            try:
                _loc_graph2 = world_memory.get_location_graph(db)
                _loc_names2 = [n["name"] for n in _loc_graph2.get("nodes", []) if n.get("name")]
                _loc_names2_set = set(_loc_names2)
                _detected = command_interpreter._detect_movement_intent(turn_input.action, _loc_names2)
                # Only accept the destination if it already exists in the location graph.
                # _detect_movement_intent can invent names when fuzzy-match fails — those
                # destinations have no path edges and strand the player.
                if _detected and _detected in _loc_names2_set:
                    _pre_movement_target2 = _detected
            except Exception:
                pass

        if turn_input.is_freeform and turn_input.action:
            semantic_goal = _extract_semantic_goal(turn_input.action)
            strict_three_layer = bool(settings.enable_strict_three_layer_architecture)

            if settings.enable_staged_action_pipeline:
                intent_started = time.perf_counter()
                staged_intent = command_interpreter.interpret_action_intent(
                    action=turn_input.action,
                    state_manager=state_manager,
                    world_memory_module=world_memory,
                    current_storylet=current_storylet,
                    db=db,
                    scene_card_now=scene_card_now,
                )
                _record_timing(timings_ms, "interpret_action_intent", intent_started)
                if staged_intent is not None:
                    staged_intent = action_validation_policy.validate_action_intent(
                        intent=staged_intent,
                        action_text=turn_input.action,
                        state_manager=state_manager,
                        world_memory_module=world_memory,
                        db=db,
                    )
                    used_staged_pipeline = True
                    staged_ack_line = staged_intent.ack_line or staged_ack_line
                    result = staged_intent.result
                else:
                    if strict_three_layer:
                        metadata = {
                            "validation_warnings": ["stage_a_unavailable_using_deterministic_planner_fallback"],
                            "staged_pipeline": "intent",
                        }
                        result = command_interpreter.ActionResult(
                            narrative_text=staged_ack_line,
                            state_deltas={},
                            should_trigger_storylet=False,
                            follow_up_choices=[{"label": "Continue", "set": {}}],
                            plausible=True,
                            reasoning_metadata=metadata,
                        )
                        used_staged_pipeline = True
                    else:
                        fallback_started = time.perf_counter()
                        result = command_interpreter.interpret_action(
                            action=turn_input.action,
                            state_manager=state_manager,
                            world_memory_module=world_memory,
                            current_storylet=current_storylet,
                            db=db,
                            scene_card_now=scene_card_now,
                        )
                        _record_timing(timings_ms, "interpret_action_fallback", fallback_started)
            else:
                if strict_three_layer:
                    intent_started = time.perf_counter()
                    staged_intent = command_interpreter.interpret_action_intent(
                        action=turn_input.action,
                        state_manager=state_manager,
                        world_memory_module=world_memory,
                        current_storylet=current_storylet,
                        db=db,
                        scene_card_now=scene_card_now,
                    )
                    if staged_intent is not None:
                        staged_intent = action_validation_policy.validate_action_intent(
                            intent=staged_intent,
                            action_text=turn_input.action,
                            state_manager=state_manager,
                            world_memory_module=world_memory,
                            db=db,
                        )
                        staged_ack_line = staged_intent.ack_line or staged_ack_line
                        result = staged_intent.result
                        used_staged_pipeline = True
                    else:
                        metadata = {
                            "validation_warnings": ["stage_a_unavailable_using_deterministic_planner_fallback"],
                            "staged_pipeline": "intent",
                        }
                        result = command_interpreter.ActionResult(
                            narrative_text=staged_ack_line,
                            state_deltas={},
                            should_trigger_storylet=False,
                            follow_up_choices=[{"label": "Continue", "set": {}}],
                            plausible=True,
                            reasoning_metadata=metadata,
                        )
                        used_staged_pipeline = True
                    _record_timing(timings_ms, "interpret_action_intent", intent_started)
                else:
                    interpret_started = time.perf_counter()
                    result = command_interpreter.interpret_action(
                        action=turn_input.action,
                        state_manager=state_manager,
                        world_memory_module=world_memory,
                        current_storylet=current_storylet,
                        db=db,
                        scene_card_now=scene_card_now,
                    )
                    _record_timing(timings_ms, "interpret_action", interpret_started)

            if result is None:
                raise RuntimeError("Action interpretation returned no result")

            beats_started = time.perf_counter()
            for beat in result.suggested_beats:
                if isinstance(beat, dict):
                    state_manager.add_narrative_beat(beat)
            _record_timing(timings_ms, "apply_suggested_beats", beats_started)

            goal_started = time.perf_counter()
            if isinstance(result.reasoning_metadata, dict):
                raw_goal_update = result.reasoning_metadata.get("goal_update")
                if isinstance(raw_goal_update, dict):
                    state_manager.apply_goal_update(raw_goal_update, source="action_interpreter")
            _record_timing(timings_ms, "apply_goal_update", goal_started)

        # ── 5. STATE COMMIT (freeform action turns) ────────────────────────────
        applied_deltas: Dict[str, Any] = {}
        simulation_tick_delta: Dict[str, Any] = {}
        reducer_receipt_payload: Dict[str, Any] = {}
        tick_receipt_payload: Dict[str, Any] = {}
        action_plausible = True
        event_type = world_memory.EVENT_TYPE_FREEFORM_ACTION

        if result is not None:
            record_event_started = time.perf_counter()
            try:
                delta_contract = _action_result_to_delta_contract(result)
                intent = FreeformActionCommittedIntent(action_text=turn_input.action, delta=delta_contract)
                receipt = reduce_event(db, state_manager, intent)
                sys_tick = reduce_event(db, state_manager, SystemTickIntent())
                committed_deltas = dict(receipt.applied_changes)
                applied_deltas = {**committed_deltas, **sys_tick.applied_changes}
                # Phase 2: if movement was pre-detected, force location into deltas
                if _pre_movement_target2:
                    # _pre_movement_target2 is already validated to be in _loc_names2_set,
                    # meaning the node already exists (city-pack location or landmark).
                    # Do NOT call ensure_location_node — it would create a duplicate
                    # player_travel node that shadows the real one and has no path edges.
                    # Stamp departure at origin; carry destination for session tracking.
                    applied_deltas = {
                        **applied_deltas,
                        "location": current_location,  # origin — departure visibility
                        "destination": _pre_movement_target2,  # where they went
                    }
                    try:
                        state_manager.set_variable("location", _pre_movement_target2)
                    except Exception:
                        pass
                # Guard: the reducer may write a narrative sublocation (e.g. "The Bakery
                # Stall") into applied_deltas["location"] instead of a real graph node.
                # Demote any non-node location to "sublocation" so session tracking always
                # sees a canonical graph node, and heal the state manager so future turns
                # don't start from a corrupted location.
                if not _pre_movement_target2 and _loc_names2_set:
                    _raw_loc2 = applied_deltas.get("location")
                    if _raw_loc2 and _raw_loc2 not in _loc_names2_set:
                        _d2 = dict(applied_deltas)
                        del _d2["location"]
                        _d2["sublocation"] = _raw_loc2
                        _canonical2 = current_location if current_location in _loc_names2_set else None
                        if _canonical2:
                            _d2["location"] = _canonical2
                            try:
                                state_manager.set_variable("location", _canonical2)
                            except Exception:
                                pass
                        else:
                            try:
                                state_manager.set_variable("location", "")
                            except Exception:
                                pass
                        applied_deltas = _d2

                # Always carry the session's current location forward so every event
                # is location-stamped, even when the action doesn't change location.
                if "location" not in applied_deltas:
                    current_loc = state_manager.get_variable("location")
                    if current_loc:
                        applied_deltas = {**applied_deltas, "location": current_loc}
                reducer_receipt_payload = receipt.model_dump()
                tick_receipt_payload = sys_tick.model_dump()
                action_plausible = bool(result.plausible)
                event_type = world_memory.infer_event_type(world_memory.EVENT_TYPE_FREEFORM_ACTION, applied_deltas)
                if _pre_movement_target2:
                    event_type = world_memory.EVENT_TYPE_MOVEMENT
                metadata = result.reasoning_metadata if isinstance(result.reasoning_metadata, dict) else {}
                metadata = dict(metadata)
                metadata["reducer_receipt"] = reducer_receipt_payload
                metadata["system_tick_receipt"] = tick_receipt_payload
                metadata["scene_card_now"] = scene_card_now
                _log_structured_turn_event(
                    "state_committed",
                    session_id=turn_input.session_id,
                    turn_type="action",
                    event_type=event_type,
                    applied_change_count=len(applied_deltas),
                    state_keys=sorted(list(applied_deltas.keys()))[:20],
                )
                narrative_excerpt = str(result.narrative_text or "")[:200]
                event = world_memory.record_event(
                    db=db,
                    session_id=state_manager.effective_world_session_id(),
                    storylet_id=current_storylet_id,
                    event_type=event_type,
                    summary=f"Player action: {turn_input.action.rstrip()}{'.' if not turn_input.action.rstrip().endswith(('.', '!', '?')) else ''} Result: {narrative_excerpt}",
                    delta=applied_deltas,
                    state_manager=None,
                    metadata=metadata,
                    idempotency_key=idempotency_key or None,
                )
                action_event_id = int(event.id) if event.id is not None else None
            except Exception as exc:
                logger.exception("Action reducer commit failed; rolling back turn: %s", exc)
                raise
            _record_timing(timings_ms, "record_action_event", record_event_started)

            if phase_events is not None:
                phase_events.append(
                    (
                        "commit",
                        {
                            "plausible": bool(result.plausible),
                            "state_changes": (result.state_deltas if isinstance(result.state_deltas, dict) else {}),
                        },
                    )
                )

        # Refresh contextual_vars after all pre-narration state commits
        contextual_vars = _public_contextual_vars(state_manager)

        # ── 6. NARRATION SOURCE SELECTION ──────────────────────────────────────
        narrative_text: str = ""
        choices: List[ChoiceOut] = []
        pipeline_mode: str = "staged_action"
        story_id: int | None = None
        story_title: str | None = None
        story_source: str = "authored"
        selection_debug: Dict[str, Any] = {}
        fire_effect_ops_applied: List[Dict[str, Any]] = []
        storylet_effect_receipt_payload: Dict[str, Any] = {}
        storylet_effect_applied_changes: Dict[str, Any] = {}
        _adapted_governance: Dict[str, Any] = {}
        narrator_parse_success: bool = True
        referee_decision_valid: bool = True
        referee_decision: str = "skipped"
        fallback_reason: str = "none"
        narrative_source: str = ""
        selection_mode: Any = None
        scene_clarity_level: str = "unknown"
        selected_projection_stub: Dict[str, Any] | None = None
        contrast_projection_stub: Dict[str, Any] | None = None
        player_hint_payload: Dict[str, Any] | None = default_player_hint_payload
        triggered_storylet_text: str | None = None
        ack_line: str | None = None

        if turn_input.is_freeform and result is not None and bool(result.plausible):
            # ── Branch A: Freeform action narration ────────────────────────────
            validated_result = result
            if applied_deltas:
                validated_result = replace(validated_result, state_deltas=applied_deltas)
            if reducer_receipt_payload or tick_receipt_payload:
                meta = validated_result.reasoning_metadata if isinstance(validated_result.reasoning_metadata, dict) else {}
                meta = dict(meta)
                if reducer_receipt_payload:
                    meta["reducer_receipt"] = reducer_receipt_payload
                if tick_receipt_payload:
                    meta["system_tick_receipt"] = tick_receipt_payload
                meta["scene_card_now"] = scene_card_now
                validated_result = replace(validated_result, reasoning_metadata=meta)

            final_result = validated_result
            if used_staged_pipeline:
                # Stage C: LLM narrator renders prose from the committed intent
                if phase_events is not None:
                    phase_events.append(("narrate", {"status": "started"}))
                narrate_started = time.perf_counter()
                final_result = command_interpreter.render_validated_action_narration(
                    action=turn_input.action,
                    ack_line=staged_ack_line,
                    validated_result=validated_result,
                    state_manager=state_manager,
                    world_memory_module=world_memory,
                    current_storylet=current_storylet,
                    db=db,
                    scene_card_now=scene_card_now,
                    resolved_movement_target=_pre_movement_target2,
                )
                _record_timing(timings_ms, "render_action_narration", narrate_started)

            narrative_text = str(final_result.narrative_text or "")

            # Post-narration: scan narrative for location mentions and grow the graph.
            _current_loc = state_manager.get_variable("location") or ""
            if narrative_text and _current_loc:
                world_memory.extract_location_mentions(db, narrative_text, _current_loc)

            choices_started = time.perf_counter()
            raw_choices = final_result.follow_up_choices if isinstance(final_result.follow_up_choices, list) else []
            for choice in raw_choices[:3]:
                if not isinstance(choice, dict):
                    continue
                choice_set = choice.get("set", {})
                if not isinstance(choice_set, dict):
                    choice_set = {}
                normalized: Dict[str, Any] = {
                    "label": str(choice.get("label", "Continue")),
                    "set": choice_set,
                }
                intent_text = choice.get("intent")
                if intent_text and isinstance(intent_text, str):
                    normalized["intent"] = intent_text.strip()
                choices.append(ChoiceOut(**normalized))
            if not choices:
                choices = [ChoiceOut(label="Continue", set={})]
            _record_timing(timings_ms, "normalize_choices", choices_started)

            pipeline_mode = "staged_action"
            ack_line = staged_ack_line
            scene_clarity_level = "committed"
            narrative_source = "staged_action"

            # Simulation tick for freeform turns (after narration, so all mutations visible)
            sim_delta = tick_world_simulation(state_manager)
            if sim_delta.increment or sim_delta.set or sim_delta.append_fact:
                sim_receipt = reduce_event(db, state_manager, SimulationTickIntent(delta=sim_delta))
                simulation_tick_delta = dict(sim_receipt.applied_changes)
                try:
                    world_memory.record_event(
                        db=db,
                        session_id=state_manager.effective_world_session_id(),
                        storylet_id=current_storylet_id,
                        event_type=world_memory.EVENT_TYPE_SIMULATION_TICK,
                        summary="Deterministic world simulation tick",
                        delta=simulation_tick_delta,
                        state_manager=None,
                    )
                except Exception as _exc:
                    logger.warning("Failed to record simulation tick (action): %s", _exc)

            # Semantic goal hint (freeform only)
            if semantic_goal and player_hint_channel_enabled:
                hint_started = time.perf_counter()
                try:
                    from .semantic_selector import compute_player_context_vector

                    spatial_nav = get_spatial_navigator_fn(db)
                    effective_storylet = current_storylet
                    if effective_storylet is None:
                        positioned_ids = list(spatial_nav.storylet_positions.keys())
                        if positioned_ids:
                            effective_storylet = db.query(Storylet).filter(Storylet.id.in_(positioned_ids)).first()
                    if effective_storylet is None:
                        raise ValueError("No positioned storylet for semantic hint")
                    effective_storylet_id, _ = _safe_storylet_identity(effective_storylet)
                    if effective_storylet_id is None:
                        raise ValueError("No stable storylet id for semantic hint")
                    context_vector = compute_player_context_vector(state_manager, world_memory, db)
                    goal_hint = spatial_nav.get_semantic_goal_hint(
                        current_storylet_id=effective_storylet_id,
                        player_vars=_public_contextual_vars(state_manager),
                        semantic_goal=semantic_goal,
                        context_vector=context_vector,
                    )
                    if goal_hint and goal_hint.get("hint"):
                        player_hint_payload = _build_semantic_goal_player_hint_payload(goal_hint)
                        narrative_text = f"{narrative_text} {goal_hint['hint']}".strip()
                except Exception as _exc:
                    logger.debug("Could not resolve semantic goal hint: %s", _exc)
                _record_timing(timings_ms, "semantic_goal_hint", hint_started)

            if player_hint_channel_enabled and player_hint_payload is None:
                player_hint_payload = _unknown_player_hint_payload(source="semantic_goal")

            # Projection hint fallback for freeform turns
            if player_hint_channel_enabled and player_hint_payload is None:
                action_story_payload: Dict[str, Any] = {
                    "id": current_storylet_id,
                    "title": "",
                }
                proj_stub, _ = _projection_seed_bundle_for_storylet(turn_input.session_id, action_story_payload)
                if proj_stub is not None:
                    player_hint_payload = _build_projection_player_hint_payload(proj_stub)

        else:
            # ── Branch B: Choice button / next turn → JIT or storylet ──────────
            if turn_input.choice_label:
                ack_line = f'You choose: "{turn_input.choice_label}".'

            # JIT eligibility check
            _jit_eligible_count = 0
            if settings.enable_jit_beat_generation and world_bible:
                try:
                    from .storylet_selector import count_eligible_storylets

                    _jit_eligible_count = count_eligible_storylets(db, state_manager)
                except Exception as _elig_exc:
                    logger.debug("Eligible storylet pre-check failed: %s", _elig_exc)

            _jit_threshold = max(0, int(settings.jit_expansion_eligible_threshold))
            _used_jit = False

            if settings.enable_jit_beat_generation and world_bible and _jit_eligible_count < _jit_threshold:
                jit_started = time.perf_counter()
                try:
                    recent_event_summaries_jit: List[str] = []
                    try:
                        recent_events_jit = world_memory.get_world_history(db, session_id=state_manager.effective_world_session_id(), limit=5)
                        recent_event_summaries_jit = [str(e.summary).strip() for e in recent_events_jit if str(e.summary).strip()]
                    except Exception:
                        pass

                    jit_frontier_hooks: List[Dict[str, Any]] = []
                    try:
                        cached_frontier = get_cached_frontier(turn_input.session_id)
                        if isinstance(cached_frontier, dict):
                            raw_stubs = cached_frontier.get("stubs") or []
                            scored = sorted(
                                [s for s in raw_stubs if isinstance(s, dict) and (s.get("premise") or s.get("title"))],
                                key=lambda s: float(s.get("semantic_score") or 0.0),
                                reverse=True,
                            )
                            jit_frontier_hooks = scored[: max(0, int(settings.jit_frontier_hook_count))]
                    except Exception:
                        pass

                    beat = generate_next_beat_fn(
                        world_bible=world_bible,
                        recent_events=recent_event_summaries_jit,
                        current_vars=state_manager.variables,
                        scene_card=scene_card_now,
                        motifs_recent=motifs_recent,
                        sensory_palette=sensory_palette,
                        frontier_hooks=jit_frontier_hooks,
                    )
                    narrative_text = beat["text"]
                    raw_beat_choices = beat.get("choices", [])
                    choices = [ChoiceOut(**normalize_choice_fn(c)) for c in cast(List[Dict[str, Any]], raw_beat_choices)]
                    _beat_is_fallback = bool(beat.get("beat_fallback"))
                    jit_hint_payload = _build_jit_beat_player_hint_payload(beat) if player_hint_channel_enabled and not _beat_is_fallback else default_player_hint_payload
                    player_hint_payload = jit_hint_payload
                    pipeline_mode = "jit_beat"
                    narrative_source = "jit_beat_fallback" if _beat_is_fallback else "jit_beat"
                    fallback_reason = "jit_beat_fallback" if _beat_is_fallback else "none"
                    scene_clarity_level = "unknown"

                    state_manager.advance_story_arc(choices_made=beat.get("choices", []))
                    _update_motif_ledger_from_narrative(state_manager=state_manager, narrative_text=narrative_text)

                    _record_timing(timings_ms, "jit_beat_generation", jit_started)
                    _used_jit = True

                    if settings.jit_persist_beats:
                        try:
                            _persist_jit_beat_as_storylet(db, beat, state_manager)
                        except Exception as _persist_exc:
                            logger.debug("JIT beat persistence failed (non-fatal): %s", _persist_exc)

                    # Record JIT world event
                    try:
                        world_memory.record_event(
                            db=db,
                            session_id=state_manager.effective_world_session_id(),
                            storylet_id=current_storylet_id,
                            event_type=world_memory.EVENT_TYPE_STORYLET_FIRED,
                            summary=f"JIT beat generated (eligible={_jit_eligible_count})",
                            delta={},
                            state_manager=None,
                        )
                    except Exception:
                        pass

                except Exception as exc:
                    logger.warning(
                        "JIT beat generation failed (%s) — falling back to storylet path: %s",
                        type(exc).__name__,
                        exc,
                    )
                    _record_timing(timings_ms, "jit_beat_generation", jit_started)
                    _used_jit = False

            if not _used_jit:
                # Storylet path
                ensure_started = time.perf_counter()
                ensure_storylets_fn(db, contextual_vars)
                _record_timing(timings_ms, "ensure_storylets", ensure_started)

                select_started = time.perf_counter()
                story = pick_storylet_fn(db, state_manager, debug_selection=selection_debug)
                story_id, story_title = _safe_storylet_identity(story)
                selection_mode = selection_debug.get("selection_mode")
                _log_structured_turn_event(
                    "storylet_selected",
                    session_id=turn_input.session_id,
                    turn_type="next",
                    storylet_id=story_id,
                    storylet_title=story_title,
                    selection_mode=str(selection_mode or "none"),
                )
                _record_timing(timings_ms, "pick_storylet", select_started)

                if story is None:
                    eligible_count = int(selection_debug.get("eligible_count", 0) or 0)
                    fallback_reason = "no_eligible_storylets" if eligible_count <= 0 else "no_storylet_selected"
                    narrative_source = "engine_idle_fallback"
                    narrative_text = "The tunnel is quiet. Nothing compelling meets the eye."
                    choices = [ChoiceOut(label="Wait", set={})]
                    if state_manager.environment.danger_level > 3:
                        narrative_text = "The air feels heavy with danger. " "Perhaps it is wise to wait and listen."
                    elif state_manager.environment.time_of_day == "night":
                        narrative_text = "The darkness is deep. Something stirs in the shadows, " "but nothing approaches."
                    pipeline_mode = "engine_idle_fallback"
                    _update_motif_ledger_from_narrative(state_manager=state_manager, narrative_text=narrative_text)
                else:
                    story_payload = _snapshot_storylet_payload(story)
                    story_id = cast(int | None, story_payload.get("id"))
                    story_title = str(story_payload.get("title") or "")
                    story_source = str(story_payload.get("source", "authored") or "authored")

                    # Persist transient stub if needed
                    if story_id is None:
                        persist_started = time.perf_counter()
                        try:
                            db.add(story)
                            db.commit()
                            db.refresh(story)
                            story_payload = _snapshot_storylet_payload(story)
                            story_id = cast(int | None, story_payload.get("id"))
                            story_title = str(story_payload.get("title") or "")
                        except Exception as exc:
                            db.rollback()
                            logger.warning("Failed to persist selected transient stub: %s", exc)
                        finally:
                            _record_timing(timings_ms, "persist_stub", persist_started)

                    state_manager.advance_story_arc(
                        choices_made=(turn_input.inbound_vars.get("choices") if turn_input.inbound_vars else []),
                    )

                    if projection_seeded_narration_enabled:
                        selected_projection_stub, contrast_projection_stub = _projection_seed_bundle_for_storylet(turn_input.session_id, story_payload)

                    recent_event_summaries: List[str] = []
                    history_started = time.perf_counter()
                    try:
                        recent_events = world_memory.get_world_history(db, session_id=state_manager.effective_world_session_id(), limit=3)
                        recent_event_summaries = [str(e.summary).strip() for e in recent_events if str(e.summary).strip()]
                    except Exception as exc:
                        logger.debug("Could not load recent world history for adaptation: %s", exc)
                    finally:
                        _record_timing(timings_ms, "load_recent_history", history_started)

                    adaptation_context: Dict[str, Any] = {
                        "variables": contextual_vars,
                        "environment": state_manager.environment.__dict__.copy(),
                        "recent_events": recent_event_summaries,
                        "state_summary": state_manager.get_state_summary(),
                        "scene_card_now": scene_card_now,
                        "goal_lens": state_manager.get_goal_lens_payload(),
                        "motifs_recent": motifs_recent,
                        "sensory_palette": sensory_palette,
                        **({"chosen_action": turn_input.choice_label} if turn_input.choice_label else {}),
                    }
                    if selected_projection_stub is not None:
                        adaptation_context["selected_projection_stub"] = selected_projection_stub
                    if contrast_projection_stub is not None:
                        adaptation_context["contrast_projection_stub"] = contrast_projection_stub

                    adapt_started = time.perf_counter()
                    adapted = adapt_storylet_fn(SimpleNamespace(**story_payload), adaptation_context)
                    _record_timing(timings_ms, "adapt_storylet", adapt_started)
                    _adapted_governance = adapted.get("motif_governance", {}) if isinstance(adapted.get("motif_governance"), dict) else {}
                    narrator_parse_success = bool(adapted.get("narrator_parse_success", True))
                    referee_decision_valid = bool(_adapted_governance.get("referee_decision_was_valid", True))
                    referee_decision = str(_adapted_governance.get("motif_referee_decision", "skipped"))

                    narrative_text = str(adapted.get("text") or render_fn(str(story_payload.get("text_template", "")), contextual_vars))
                    adapted_choices = adapted.get("choices")
                    if not isinstance(adapted_choices, list):
                        adapted_choices = cast(List[Dict[str, Any]], story_payload.get("choices", []))

                    if not str(adapted.get("text") or "").strip():
                        fallback_reason = "template_fallback_after_adaptation"
                        narrative_source = "template_fallback"
                    else:
                        narrative_source = f"storylet_{story_source}"

                    choices = [ChoiceOut(**normalize_choice_fn(c)) for c in cast(List[Dict[str, Any]], adapted_choices)]

                    # Storylet fire effects
                    fire_effects_started = time.perf_counter()
                    storylet_effect_delta, fire_effect_ops_applied = _storylet_effects_to_delta_contract(
                        story_payload.get("effects", []),
                        trigger=_STORYLET_EFFECTS_ON_FIRE,
                    )
                    if fire_effect_ops_applied:
                        fire_receipt = reduce_event(
                            db,
                            state_manager,
                            ChoiceSelectedIntent(
                                label="Storylet Fire Effects",
                                delta=storylet_effect_delta,
                            ),
                        )
                        storylet_effect_applied_changes.update(fire_receipt.applied_changes)
                        storylet_effect_receipt_payload = fire_receipt.model_dump()

                    _, pending_choice_effect_ops = _storylet_effects_to_delta_contract(
                        story_payload.get("effects", []),
                        trigger=_STORYLET_EFFECTS_ON_CHOICE_COMMIT,
                    )
                    if pending_choice_effect_ops:
                        state_manager.set_variable(
                            _PENDING_STORYLET_CHOICE_EFFECTS_KEY,
                            {
                                "storylet_id": story_id,
                                "storylet_title": (story_title or "unknown"),
                                "effects": pending_choice_effect_ops,
                            },
                        )
                    else:
                        state_manager.delete_variable(_PENDING_STORYLET_CHOICE_EFFECTS_KEY)
                    _record_timing(timings_ms, "apply_storylet_fire_effects", fire_effects_started)

                    scene_clarity_level = _scene_clarity_level_from_projection(selected_projection_stub)
                    player_hint_payload = _build_projection_player_hint_payload(selected_projection_stub, contrast_projection_stub) if player_hint_channel_enabled else None
                    pipeline_mode = "storylet_selection"
                    narrative_source = f"storylet_{story_source}"

                    # Record storylet world event
                    record_started = time.perf_counter()
                    try:
                        event_metadata: Dict[str, Any] = {}
                        if fire_effect_ops_applied:
                            event_metadata = {
                                world_memory.STORYLET_EFFECTS_TRIGGER_KEY: _STORYLET_EFFECTS_ON_FIRE,
                                world_memory.STORYLET_EFFECTS_METADATA_KEY: fire_effect_ops_applied,
                                world_memory.STORYLET_EFFECTS_RECEIPT_KEY: storylet_effect_receipt_payload,
                            }
                        if choice_effect_ops_applied:
                            event_metadata[world_memory.STORYLET_CHOICE_COMMIT_EFFECTS_KEY] = {
                                world_memory.STORYLET_EFFECTS_TRIGGER_KEY: _STORYLET_EFFECTS_ON_CHOICE_COMMIT,
                                world_memory.STORYLET_EFFECTS_METADATA_KEY: choice_effect_ops_applied,
                                world_memory.STORYLET_EFFECTS_RECEIPT_KEY: choice_effect_receipt_payload,
                            }
                        world_memory.record_event(
                            db=db,
                            session_id=state_manager.effective_world_session_id(),
                            storylet_id=story_id,
                            event_type=world_memory.EVENT_TYPE_STORYLET_FIRED,
                            summary=f"Storylet '{story_title or 'unknown'}' fired",
                            delta=storylet_effect_applied_changes,
                            metadata=event_metadata or None,
                        )
                    except Exception as exc:
                        logger.warning("Failed to record storylet event: %s", exc)
                    finally:
                        _record_timing(timings_ms, "record_storylet_event", record_started)

                    _update_motif_ledger_from_narrative(state_manager=state_manager, narrative_text=narrative_text)

            # Simulation tick for non-freeform turns (after narration)
            sim_delta = tick_world_simulation(state_manager)
            if sim_delta.increment or sim_delta.set or sim_delta.append_fact:
                sim_receipt = reduce_event(db, state_manager, SimulationTickIntent(delta=sim_delta))
                simulation_tick_delta = dict(sim_receipt.applied_changes)
                try:
                    world_memory.record_event(
                        db=db,
                        session_id=state_manager.effective_world_session_id(),
                        storylet_id=story_id,
                        event_type=world_memory.EVENT_TYPE_SIMULATION_TICK,
                        summary="Deterministic world simulation tick",
                        delta=simulation_tick_delta,
                    )
                except Exception as exc:
                    logger.warning("Failed to record simulation tick: %s", exc)

        # ── 7. CHOICE NORMALIZATION (motif ledger update for freeform done above) ──
        if turn_input.is_freeform:
            # Motif ledger update for freeform turns
            motif_started = time.perf_counter()
            _update_motif_ledger_from_narrative(state_manager=state_manager, narrative_text=narrative_text)
            _record_timing(timings_ms, "update_motif_ledger", motif_started)

            # Story arc for freeform turns
            arc_started = time.perf_counter()
            state_manager.advance_story_arc(choices_made=[c.model_dump() for c in choices])
            _record_timing(timings_ms, "advance_story_arc", arc_started)

        # ── 8. RESPONSE ASSEMBLY ───────────────────────────────────────────────
        final_contextual_vars = _public_contextual_vars(state_manager)

        if turn_input.is_freeform:
            turn_source_str = "freeform_action"
        elif turn_input.choice_label or turn_input.choice_vars or turn_input.choice_taken:
            turn_source_str = "choice_button"
        elif turn_input.inbound_vars:
            turn_source_str = "choice_button"
        else:
            turn_source_str = "initial_scene"

        player_hint_clarity_level = _normalize_clarity_level(player_hint_payload.get("clarity") if isinstance(player_hint_payload, dict) else "unknown")

        diag: Dict[str, Any] = {
            "turn_source": turn_source_str,
            "choice_label": (str(turn_input.choice_label or "").strip() if not turn_input.is_freeform else None),
            "pipeline_mode": pipeline_mode,
            "selection_mode": str(selection_mode or (pipeline_mode if pipeline_mode in ("jit_beat", "engine_idle_fallback") else ("action_commit" if turn_input.is_freeform else "none"))),
            "active_storylets_count": _coerce_non_negative_int(selection_debug.get("active_storylets_count"), default=0),
            "eligible_storylets_count": _coerce_non_negative_int(selection_debug.get("eligible_count"), default=0),
            "fallback_reason": fallback_reason,
            "clarity_level": scene_clarity_level,
            "scene_clarity_level": scene_clarity_level,
            "player_hint_channel_enabled": player_hint_channel_enabled,
            "player_hint_clarity_level": player_hint_clarity_level,
            "projection_seeded_narration_enabled": projection_seeded_narration_enabled,
            "projection_seed_used": bool(selected_projection_stub),
        }
        if not turn_input.is_freeform:
            diag["narrative_source"] = narrative_source
            diag["narrator_parse_success"] = narrator_parse_success
            diag["referee_decision_valid"] = referee_decision_valid
            diag["referee_decision"] = referee_decision
            if selected_projection_stub is not None:
                diag["projection_seed_storylet_id"] = selected_projection_stub.get("storylet_id")
            if ack_line:
                diag["ack_line"] = ack_line
        else:
            diag["clarity_level"] = "committed"
            diag["scene_clarity_level"] = "committed"

        if player_hint_channel_enabled and isinstance(player_hint_payload, dict):
            final_contextual_vars["_ww_hint"] = dict(player_hint_payload)

        # Freeform action turns handle projection invalidation here;
        # non-freeform turns rely on run_next_turn_orchestration to call
        # invalidate_projection_for_session after the response is assembled,
        # since the adapter reads projection_seed_storylet_id from the diag.
        if turn_input.is_freeform:
            invalidation = invalidate_projection_for_session(
                turn_input.session_id,
                selected_projection_id=None,
                commit_status="committed",
            )
            diag.update(invalidation)

        # Priority-ordered vars (_ww_diag and _ww_hint first)
        prioritized_vars: Dict[str, Any] = {"_ww_diag": diag}
        if "_ww_hint" in final_contextual_vars:
            prioritized_vars["_ww_hint"] = final_contextual_vars.pop("_ww_hint")
        for key, value in final_contextual_vars.items():
            if key not in ("_ww_diag", "_ww_hint"):
                prioritized_vars[key] = value

        state_changes = dict(applied_deltas)

        # ── 9. PERSIST ─────────────────────────────────────────────────────────
        save_started = time.perf_counter()
        save_state(state_manager, db)
        _record_timing(timings_ms, "save_state", save_started)

        if idempotency_key and action_event_id is not None:
            persist_idem_started = time.perf_counter()
            try:
                _idem_response: Dict[str, Any] = {
                    "narrative": narrative_text,
                    "state_changes": state_changes,
                    "choices": [c.model_dump() for c in choices],
                    "plausible": action_plausible,
                    "vars": prioritized_vars,
                    "diagnostics": dict(diag),
                    "ack_line": ack_line,
                    "triggered_storylet": triggered_storylet_text,
                }
                world_memory.persist_action_idempotent_response(
                    db=db,
                    event_id=action_event_id,
                    response_payload=_idem_response,
                )
            except Exception as exc:
                logger.warning("Failed to persist idempotent action response: %s", exc)
            _record_timing(timings_ms, "persist_idempotent_response", persist_idem_started)

        return {
            "narrative": narrative_text,
            "choices": choices,  # List[ChoiceOut]
            "vars": prioritized_vars,
            "diagnostics": dict(diag),
            "plausible": action_plausible,
            "state_changes": state_changes,
            "ack_line": ack_line,
            "triggered_storylet": triggered_storylet_text,
            "_debug": selection_debug if (debug_scores and settings.enable_dev_reset) else None,
        }

    @staticmethod
    def _as_action_response(result: Dict[str, Any]) -> Dict[str, Any]:
        """Project process_turn result into the flat dict expected by /action."""
        out = {
            "narrative": result["narrative"],
            "state_changes": result["state_changes"],
            "choices": [c.model_dump() if hasattr(c, "model_dump") else dict(c) for c in result["choices"]],
            "plausible": result["plausible"],
            "vars": result["vars"],
            "diagnostics": result["diagnostics"],
        }
        if result.get("ack_line") is not None:
            out["ack_line"] = result["ack_line"]
        if result.get("triggered_storylet") is not None:
            out["triggered_storylet"] = result["triggered_storylet"]
        return out

    @staticmethod
    def _as_next_response(result: Dict[str, Any]) -> Dict[str, Any]:
        """Project process_turn result into the {response: NextResp, debug: ...} shape."""
        out = NextResp(
            text=result["narrative"],
            choices=result["choices"],
            vars=result["vars"],
            diagnostics=result["diagnostics"],
        )
        return {"response": out, "debug": result.get("_debug")}
