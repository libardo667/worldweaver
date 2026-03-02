"""Semantic storylet selection using embedding proximity."""

import logging
import random
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..models import Storylet
from .embedding_service import cosine_similarity, embed_text

logger = logging.getLogger(__name__)

FLOOR_PROBABILITY = 0.05
RECENCY_PENALTY = 0.3


def compute_player_context_vector(
    state_manager: Any,
    world_memory_module: Any,
    db: Session,
) -> List[float]:
    """Build and embed a composite text of the player's current state.

    Combines location, key variables, inventory, relationships, and recent
    world history into a single embedding vector.
    """
    parts = []

    variables = state_manager.get_contextual_variables()
    location = variables.get("location", "unknown")
    parts.append(f"Player is at {location}.")

    state_parts = [
        f"{k}={v}"
        for k, v in variables.items()
        if not k.startswith("_") and k != "location"
    ]
    if state_parts:
        parts.append("State: " + ", ".join(state_parts[:10]))

    if state_manager.inventory:
        item_names = [item.name for item in state_manager.inventory.values()]
        parts.append("Carrying: " + ", ".join(item_names[:5]))

    for rel in list(state_manager.relationships.values())[:3]:
        parts.append(
            f"Relationship with {rel.entity_b}: {rel.get_overall_disposition()}"
        )

    try:
        recent = world_memory_module.get_world_history(
            db, session_id=state_manager.session_id, limit=5
        )
        for event in recent:
            parts.append(event.summary)
    except Exception as e:
        logger.debug("Could not fetch world history for context: %s", e)

    composite = " ".join(parts)
    return embed_text(composite)


def score_storylets(
    context_vector: List[float],
    storylets: List[Storylet],
    recent_storylet_ids: Optional[List[int]] = None,
) -> List[Tuple[Storylet, float]]:
    """Score storylets by semantic similarity to the player context.

    Returns (storylet, score) tuples where score >= FLOOR_PROBABILITY.
    """
    recent_ids = set(recent_storylet_ids or [])
    scored = []

    for storylet in storylets:
        if not storylet.embedding:
            continue

        sim = cosine_similarity(context_vector, storylet.embedding)
        score = max(sim, FLOOR_PROBABILITY)

        weight = max(0.01, float(storylet.weight or 1.0))
        score *= weight

        if storylet.id in recent_ids:
            score *= 1.0 - RECENCY_PENALTY

        scored.append((storylet, score))

    return scored


def select_storylet(
    scored_candidates: List[Tuple[Storylet, float]],
) -> Optional[Storylet]:
    """Weighted random selection from scored candidates."""
    if not scored_candidates:
        return None

    storylets = [s for s, _ in scored_candidates]
    weights = [max(0.001, w) for _, w in scored_candidates]

    return random.choices(storylets, weights=weights, k=1)[0]
