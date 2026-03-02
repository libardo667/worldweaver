"""Semantic storylet selection using embedding proximity."""

import logging
import random
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..models import Storylet
from ..config import settings
from .embedding_service import cosine_similarity, embed_text

logger = logging.getLogger(__name__)

FLOOR_PROBABILITY = 0.05
RECENCY_PENALTY = 0.3


def _clamp_unit_interval(value: float) -> float:
    """Clamp numeric values into [0.0, 1.0]."""
    return max(0.0, min(1.0, float(value)))


def get_floor_probability() -> float:
    """Configured semantic floor probability."""
    return _clamp_unit_interval(settings.llm_semantic_floor_probability)


def get_recency_penalty() -> float:
    """Configured recency penalty applied to recently fired storylets."""
    return _clamp_unit_interval(settings.llm_recency_penalty)


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
    player_vector = embed_text(composite)

    try:
        world_vector = world_memory_module.get_world_context_vector(
            db, session_id=state_manager.session_id, limit=20
        )
    except Exception as e:
        logger.debug("Could not fetch weighted world context vector: %s", e)
        world_vector = None

    if world_vector and len(world_vector) == len(player_vector):
        # Blend immediate player context with persistent world history.
        return [
            (p * 0.7) + (w * 0.3)
            for p, w in zip(player_vector, world_vector)
        ]

    return player_vector


def score_storylets(
    context_vector: List[float],
    storylets: List[Storylet],
    recent_storylet_ids: Optional[List[int]] = None,
) -> List[Tuple[Storylet, float]]:
    """Score storylets by semantic similarity to the player context.

    Returns (storylet, score) tuples where score >= configured floor.
    """
    floor_probability = get_floor_probability()
    recency_penalty = get_recency_penalty()
    recent_ids = set(recent_storylet_ids or [])
    scored = []

    for storylet in storylets:
        if not storylet.embedding:
            continue

        sim = cosine_similarity(context_vector, storylet.embedding)
        score = max(sim, floor_probability)

        weight = max(0.01, float(storylet.weight or 1.0))
        score *= weight

        if storylet.id in recent_ids:
            score *= 1.0 - recency_penalty

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
