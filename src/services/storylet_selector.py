"""Storylet selection service with semantic and weighted fallback paths."""

import logging
import random
from typing import Any, Dict, cast

from sqlalchemy.orm import Session

from ..models import Storylet
from .state_manager import AdvancedStateManager

logger = logging.getLogger(__name__)


def pick_storylet_enhanced(
    db: Session,
    state_manager: AdvancedStateManager,
) -> Storylet | None:
    """Pick an eligible storylet, preferring semantic ranking when possible."""
    all_storylets = db.query(Storylet).all()
    eligible = []

    for storylet in all_storylets:
        requirements = cast(Dict[str, Any], storylet.requires or {})
        if state_manager.evaluate_condition(requirements):
            eligible.append(storylet)

    if not eligible:
        return None

    active_beats = state_manager.get_active_narrative_beats()

    # Try semantic selection if any eligible storylets have embeddings.
    embedded = [s for s in eligible if s.embedding]
    chosen_storylet: Storylet | None = None
    if embedded:
        try:
            from .semantic_selector import (
                compute_player_context_vector,
                score_storylets,
                select_storylet,
            )
            from . import world_memory

            recent_storylet_ids = []
            try:
                recent_events = world_memory.get_world_history(
                    db,
                    session_id=state_manager.session_id,
                    limit=5,
                )
                recent_storylet_ids = [
                    e.storylet_id
                    for e in recent_events
                    if e.storylet_id
                ]
            except Exception:
                pass

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
            )
            result = select_storylet(scored)
            if result:
                chosen_storylet = result
        except Exception as e:
            logger.warning("Semantic selection failed, falling back: %s", e)

    if chosen_storylet is None:
        # Fallback: weight-based random selection.
        weights = [max(0.0, cast(float, s.weight or 0.0)) for s in eligible]
        chosen_storylet = random.choices(eligible, weights=weights, k=1)[0]

    if active_beats:
        state_manager.decay_narrative_beats()

    return chosen_storylet
