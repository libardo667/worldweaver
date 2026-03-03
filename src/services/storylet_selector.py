"""Storylet selection service with semantic and weighted fallback paths."""

import logging
import random
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, cast

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Storylet
from .cache import TTLCacheMap
from .prefetch_service import select_prefetched_storylet
from .state_manager import AdvancedStateManager
from .storylet_utils import find_storylet_by_location, storylet_location

logger = logging.getLogger(__name__)

_runtime_synthesis_counts: TTLCacheMap = TTLCacheMap(
    settings.state_manager_cache_max_size,
    settings.runtime_synthesis_rate_window_seconds,
)


def _active_storylets(db: Session) -> List[Storylet]:
    now = datetime.now(UTC).replace(tzinfo=None)
    return (
        db.query(Storylet)
        .filter(or_(Storylet.expires_at.is_(None), Storylet.expires_at > now))
        .all()
    )


def _recent_repetition_ratio(storylet_ids: List[int]) -> float:
    """Return ratio of most repeated storylet in recent history."""
    if len(storylet_ids) < 3:
        return 0.0
    counts = Counter(storylet_ids)
    return max(counts.values()) / max(1, len(storylet_ids))


def _runtime_synthesis_allowed(session_id: str) -> bool:
    if not settings.enable_runtime_storylet_synthesis:
        return False
    if settings.runtime_synthesis_max_per_session <= 0:
        return False
    used = int(_runtime_synthesis_counts.get(session_id, 0) or 0)
    return used < int(settings.runtime_synthesis_max_per_session)


def _mark_runtime_synthesis(session_id: str) -> None:
    used = int(_runtime_synthesis_counts.get(session_id, 0) or 0)
    _runtime_synthesis_counts[session_id] = used + 1


def _resolve_active_goal(state_manager: AdvancedStateManager) -> str | None:
    vars_snapshot = state_manager.get_contextual_variables()
    for key in ("active_goal", "goal", "quest", "objective", "mission"):
        value = vars_snapshot.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _title_with_runtime_suffix(base_title: str, index: int) -> str:
    """Ensure runtime storylets are uniquely titled to avoid insert collisions."""
    cleaned = str(base_title or "Runtime Storylet").strip() or "Runtime Storylet"
    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    titled = f"{cleaned} [runtime-{suffix}-{index + 1}]"
    return titled[:200]


def _is_sparse_context(
    *,
    eligible_count: int,
    top_score: float,
    repetition_ratio: float,
) -> bool:
    if eligible_count <= int(settings.runtime_synthesis_min_eligible_storylets):
        return True
    if top_score < float(settings.runtime_synthesis_min_top_score):
        return True
    if repetition_ratio >= float(settings.runtime_synthesis_repetition_threshold):
        return True
    return False


def _synthesize_runtime_storylets(
    db: Session,
    state_manager: AdvancedStateManager,
) -> List[Storylet]:
    """Generate and persist runtime storylets for sparse contexts."""
    from . import world_memory
    from .embedding_service import embed_storylet_payload
    from .llm_service import generate_runtime_storylet_candidates

    session_id = state_manager.session_id
    if not _runtime_synthesis_allowed(session_id):
        return []

    recent_window = max(1, int(settings.runtime_synthesis_recent_window))
    recent_events = world_memory.get_world_history(
        db,
        session_id=session_id,
        limit=recent_window,
    )
    seed_event_ids = [
        int(event.id)
        for event in recent_events
        if getattr(event, "id", None) is not None
    ][:recent_window]

    world_facts = world_memory.get_recent_graph_fact_summaries(
        db,
        session_id=session_id,
        limit=recent_window,
    )
    active_goal = _resolve_active_goal(state_manager)
    contextual_vars = state_manager.get_contextual_variables()
    limit = max(1, min(3, int(settings.runtime_synthesis_max_candidates)))
    candidates = generate_runtime_storylet_candidates(
        contextual_vars,
        world_facts,
        active_goal,
        n=limit,
    )

    if not candidates:
        return []

    expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(
        minutes=max(5, int(settings.runtime_synthesis_ttl_minutes))
    )
    persisted: List[Storylet] = []

    for idx, candidate in enumerate(candidates):
        try:
            with db.begin_nested():
                storylet = Storylet(
                    title=_title_with_runtime_suffix(str(candidate.get("title", "")), idx),
                    text_template=str(candidate.get("text_template", "Something happens.")),
                    requires=cast(Dict[str, Any], candidate.get("requires", {})),
                    choices=cast(List[Dict[str, Any]], candidate.get("choices", [])),
                    weight=float(candidate.get("weight", 1.0)),
                    source="runtime_synthesis",
                    seed_event_ids=seed_event_ids,
                    expires_at=expires_at,
                    embedding=embed_storylet_payload(candidate),
                )
                db.add(storylet)
                db.flush()
                persisted.append(storylet)
        except Exception as exc:
            logger.warning("Failed to persist runtime storylet candidate: %s", exc)

    if persisted:
        _mark_runtime_synthesis(session_id)
    return persisted


def pick_storylet_enhanced(
    db: Session,
    state_manager: AdvancedStateManager,
    debug_selection: Dict[str, Any] | None = None,
) -> Storylet | None:
    """Pick an eligible storylet, preferring semantic ranking when possible."""
    from . import world_memory
    from .semantic_selector import (
        compute_player_context_vector,
        score_storylets,
        select_storylet,
        top_storylet_score,
    )

    all_storylets = _active_storylets(db)
    eligible: List[Storylet] = []

    for storylet in all_storylets:
        requirements = cast(Dict[str, Any], storylet.requires or {})
        if state_manager.evaluate_condition(requirements):
            eligible.append(storylet)

    active_beats = state_manager.get_active_narrative_beats()
    storylet_positions = {}
    for storylet in eligible:
        position = storylet.position if isinstance(storylet.position, dict) else None
        if (
            isinstance(position, dict)
            and "x" in position
            and "y" in position
            and storylet.id is not None
        ):
            storylet_positions[int(storylet.id)] = {
                "x": int(position["x"]),
                "y": int(position["y"]),
            }

    player_position = None
    current_location = str(state_manager.get_variable("location", ""))
    if current_location:
        current_storylet = find_storylet_by_location(db, current_location)
        if (
            current_storylet is not None
            and isinstance(current_storylet.position, dict)
            and "x" in current_storylet.position
            and "y" in current_storylet.position
        ):
            player_position = {
                "x": int(current_storylet.position["x"]),
                "y": int(current_storylet.position["y"]),
            }
    if player_position is None:
        for storylet in eligible:
            if (
                storylet_location(storylet) == current_location
                and storylet.id in storylet_positions
            ):
                player_position = storylet_positions[int(storylet.id)]
                break

    recent_storylet_ids: List[int] = []
    try:
        recent_events = world_memory.get_world_history(
            db,
            session_id=state_manager.session_id,
            limit=max(5, int(settings.runtime_synthesis_recent_window)),
        )
        recent_storylet_ids = [int(e.storylet_id) for e in recent_events if e.storylet_id]
    except Exception as exc:
        logger.debug("Could not load recent storylet history: %s", exc)

    context_vector: List[float] | None = None
    scored = []
    score_breakdown: List[Dict[str, Any]] = []
    chosen_storylet: Storylet | None = select_prefetched_storylet(
        session_id=state_manager.session_id,
        eligible_storylets=eligible,
        current_location=current_location,
        recent_storylet_ids=recent_storylet_ids,
    )
    selection_mode = "fallback_weighted"
    if chosen_storylet is not None:
        selection_mode = "prefetched_stub"
    embedded = [s for s in eligible if s.embedding]
    if embedded and chosen_storylet is None:
        try:
            context_vector = compute_player_context_vector(
                state_manager,
                world_memory,
                db,
            )
            scored = score_storylets(
                context_vector,
                embedded,
                recent_storylet_ids,
                active_beats=active_beats,
                player_position=player_position,
                storylet_positions=storylet_positions,
                score_breakdown=score_breakdown if debug_selection is not None else None,
            )
            chosen_storylet = select_storylet(scored)
            if chosen_storylet is not None:
                selection_mode = "semantic_weighted"
        except Exception as exc:
            logger.warning("Semantic selection failed, falling back: %s", exc)

    repetition_ratio = _recent_repetition_ratio(recent_storylet_ids)
    sparse = _is_sparse_context(
        eligible_count=len(eligible),
        top_score=top_storylet_score(scored),
        repetition_ratio=repetition_ratio,
    )

    if (
        sparse
        and selection_mode != "prefetched_stub"
        and _runtime_synthesis_allowed(state_manager.session_id)
    ):
        try:
            synthesized = _synthesize_runtime_storylets(db, state_manager)
            if synthesized:
                eligible.extend(synthesized)
                for storylet in synthesized:
                    position = (
                        storylet.position if isinstance(storylet.position, dict) else None
                    )
                    if (
                        isinstance(position, dict)
                        and "x" in position
                        and "y" in position
                        and storylet.id is not None
                    ):
                        storylet_positions[int(storylet.id)] = {
                            "x": int(position["x"]),
                            "y": int(position["y"]),
                        }

                embedded = [s for s in eligible if s.embedding]
                if embedded:
                    if context_vector is None:
                        context_vector = compute_player_context_vector(
                            state_manager,
                            world_memory,
                            db,
                        )
                    scored = score_storylets(
                        context_vector,
                        embedded,
                        recent_storylet_ids,
                        active_beats=active_beats,
                        player_position=player_position,
                        storylet_positions=storylet_positions,
                        score_breakdown=score_breakdown if debug_selection is not None else None,
                    )
                    selected = select_storylet(scored)
                    if selected is not None:
                        chosen_storylet = selected
                        selection_mode = "semantic_weighted"
        except Exception as exc:
            logger.warning("Runtime synthesis failed; continuing with fallback: %s", exc)

    if chosen_storylet is None and eligible:
        # Fallback: weight-based random selection.
        weights = [max(0.0, cast(float, s.weight or 0.0)) for s in eligible]
        chosen_storylet = random.choices(eligible, weights=weights, k=1)[0]
        selection_mode = "fallback_weighted"

    if debug_selection is not None:
        ranked = sorted(
            score_breakdown,
            key=lambda item: float(item.get("final_score", 0.0)),
            reverse=True,
        )
        ranked_with_position: List[Dict[str, Any]] = []
        for idx, item in enumerate(ranked, start=1):
            entry = dict(item)
            entry["rank"] = idx
            ranked_with_position.append(entry)

        debug_selection.clear()
        debug_selection.update(
            {
                "eligible_count": len(eligible),
                "embedded_count": len(embedded),
                "recent_storylet_ids": recent_storylet_ids[:10],
                "selection_mode": selection_mode,
                "top_score": float(top_storylet_score(scored)),
                "selected_storylet_id": (
                    int(chosen_storylet.id) if chosen_storylet and chosen_storylet.id is not None else None
                ),
                "selected_storylet_title": (
                    str(chosen_storylet.title) if chosen_storylet is not None else None
                ),
                "scored_candidates": ranked_with_position,
            }
        )

    if chosen_storylet is not None and active_beats:
        state_manager.decay_narrative_beats()

    return chosen_storylet
