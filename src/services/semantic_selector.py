"""Semantic storylet selection using embedding proximity."""

import logging
import math
import random
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..models import NarrativeBeat, Storylet
from ..config import settings
from .embedding_service import cosine_similarity, embed_text

logger = logging.getLogger(__name__)

FLOOR_PROBABILITY = 0.05
RECENCY_PENALTY = 0.3
PHYSICAL_DISTANCE_WEIGHT = 0.35
STANDARD_NARRATIVE_BEAT_PROMPTS: Dict[str, str] = {
    "increasingtension": "danger conflict threat instability violence risk urgency",
    "thematicresonance": "current world themes motifs symbolism social pressure cosmic meaning",
    "catharsis": "resolution relief trust community healing reconciliation aftermath",
}
_beat_embedding_cache: Dict[str, List[float]] = {}


def _clamp_unit_interval(value: float) -> float:
    """Clamp numeric values into [0.0, 1.0]."""
    return max(0.0, min(1.0, float(value)))


def get_floor_probability() -> float:
    """Configured semantic floor probability."""
    return _clamp_unit_interval(settings.llm_semantic_floor_probability)


def get_recency_penalty() -> float:
    """Configured recency penalty applied to recently fired storylets."""
    return _clamp_unit_interval(settings.llm_recency_penalty)


def _canonicalize_beat_name(name: str) -> str:
    return "".join(ch for ch in str(name or "").lower() if ch.isalnum())


def _resolve_beat_vector(beat: NarrativeBeat) -> Optional[List[float]]:
    if beat.vector:
        try:
            return [float(x) for x in beat.vector]
        except Exception:
            return None

    key = _canonicalize_beat_name(beat.name)
    prompt = STANDARD_NARRATIVE_BEAT_PROMPTS.get(key, beat.name)
    if not prompt:
        return None

    if prompt in _beat_embedding_cache:
        return _beat_embedding_cache[prompt]

    try:
        vector = embed_text(prompt)
        _beat_embedding_cache[prompt] = vector
        return vector
    except Exception as exc:
        logger.debug("Failed to embed narrative beat '%s': %s", beat.name, exc)
        return None


def apply_narrative_beats(
    context_vector: List[float],
    active_beats: Optional[List[NarrativeBeat]] = None,
) -> List[float]:
    """Blend active beat vectors into the player context vector."""
    final_vector = list(context_vector)
    beats = active_beats or []
    if not beats:
        return final_vector

    for beat in beats:
        if not beat.is_active():
            continue
        beat_vector = _resolve_beat_vector(beat)
        if not beat_vector or len(beat_vector) != len(final_vector):
            continue
        intensity = max(0.0, float(beat.intensity))
        for idx, value in enumerate(beat_vector):
            final_vector[idx] += value * intensity

    return final_vector


def _spatial_distance_modifier(
    storylet_id: Optional[int],
    player_position: Optional[Dict[str, int]] = None,
    storylet_positions: Optional[Dict[int, Dict[str, int]]] = None,
) -> float:
    """Convert physical grid distance into a smooth multiplicative modifier."""
    if storylet_id is None or player_position is None or storylet_positions is None or storylet_id not in storylet_positions:
        return 1.0

    candidate = storylet_positions[storylet_id]
    try:
        dx = float(candidate["x"]) - float(player_position["x"])
        dy = float(candidate["y"]) - float(player_position["y"])
    except (KeyError, TypeError, ValueError):
        return 1.0

    distance = math.sqrt((dx * dx) + (dy * dy))
    return 1.0 / (1.0 + (distance * PHYSICAL_DISTANCE_WEIGHT))


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

    goal_context = ""
    try:
        if hasattr(state_manager, "get_goal_lens_payload"):
            lens = state_manager.get_goal_lens_payload()
            primary_goal = lens.get("primary_goal", "")
            urgency = lens.get("urgency", 0.0)
            complication = lens.get("complication", 0.0)
            if primary_goal:
                goal_context = f"Goal: {primary_goal}. Urgency: {urgency:.2f}. Complications: {complication:.2f}."
        elif hasattr(state_manager, "get_goal_embedding_context"):
            goal_context = str(state_manager.get_goal_embedding_context() or "").strip()
    except Exception as exc:
        logger.debug("Failed to extract goal context for semantic embedding: %s", exc)
        goal_context = ""
    if goal_context:
        parts.append(goal_context)

    state_parts = [f"{k}={v}" for k, v in variables.items() if not k.startswith("_") and k != "location"]
    if state_parts:
        parts.append("State: " + ", ".join(state_parts[:10]))

    if state_manager.inventory:
        item_names = [item.name for item in state_manager.inventory.values()]
        parts.append("Carrying: " + ", ".join(item_names[:5]))

    for rel in list(state_manager.relationships.values())[:3]:
        parts.append(f"Relationship with {rel.entity_b}: {rel.get_overall_disposition()}")

    try:
        recent = world_memory_module.get_world_history(db, session_id=state_manager.session_id, limit=5)
        for event in recent:
            parts.append(event.summary)
    except Exception as e:
        logger.debug("Could not fetch world history for context: %s", e)

    try:
        fact_summaries = world_memory_module.get_recent_graph_fact_summaries(
            db,
            session_id=state_manager.session_id,
            limit=5,
        )
        if fact_summaries:
            parts.append("Known world facts: " + "; ".join(fact_summaries))
    except Exception as e:
        logger.debug("Could not fetch graph facts for context: %s", e)

    composite = " ".join(parts)
    player_vector = embed_text(composite)

    try:
        world_vector = world_memory_module.get_world_context_vector(db, session_id=state_manager.session_id, limit=20)
    except Exception as e:
        logger.debug("Could not fetch weighted world context vector: %s", e)
        world_vector = None

    if world_vector and len(world_vector) == len(player_vector):
        # Blend immediate player context with persistent world history.
        return [(p * 0.7) + (w * 0.3) for p, w in zip(player_vector, world_vector)]

    return player_vector


def score_storylets(
    context_vector: List[float],
    storylets: List[Storylet],
    recent_storylet_ids: Optional[List[int]] = None,
    active_beats: Optional[List[NarrativeBeat]] = None,
    player_position: Optional[Dict[str, int]] = None,
    storylet_positions: Optional[Dict[int, Dict[str, int]]] = None,
    score_breakdown: Optional[List[Dict[str, Any]]] = None,
) -> List[Tuple[Storylet, float]]:
    """Score storylets by semantic similarity to the player context.

    Returns (storylet, score) tuples where score >= configured floor.
    """
    floor_probability = get_floor_probability()
    recency_penalty = get_recency_penalty()
    recent_ids = set(recent_storylet_ids or [])
    scored = []
    final_context_vector = apply_narrative_beats(context_vector, active_beats)

    for storylet in storylets:
        if not storylet.embedding:
            continue

        sim = cosine_similarity(final_context_vector, storylet.embedding)
        floored_similarity = max(sim, floor_probability)
        score = floored_similarity

        weight = max(0.01, float(storylet.weight or 1.0))
        spatial_modifier = _spatial_distance_modifier(
            storylet_id=storylet.id,
            player_position=player_position,
            storylet_positions=storylet_positions,
        )
        recency_multiplier = 1.0

        score *= weight
        score *= spatial_modifier

        if storylet.id in recent_ids:
            recency_multiplier = 1.0 - recency_penalty
            score *= recency_multiplier

        if score_breakdown is not None:
            score_breakdown.append(
                {
                    "storylet_id": int(storylet.id) if storylet.id is not None else None,
                    "title": str(storylet.title),
                    "similarity": float(sim),
                    "floor_probability": float(floor_probability),
                    "floored_similarity": float(floored_similarity),
                    "weight": float(weight),
                    "spatial_modifier": float(spatial_modifier),
                    "recency_multiplier": float(recency_multiplier),
                    "is_recent": bool(storylet.id in recent_ids),
                    "final_score": float(score),
                }
            )

        scored.append((storylet, score))

    return scored


def select_storylet(
    scored_candidates: List[Tuple[Storylet, float]],
    rng: Optional[random.Random] = None,
) -> Optional[Storylet]:
    """Weighted random selection from scored candidates."""
    if not scored_candidates:
        return None

    storylets = [s for s, _ in scored_candidates]
    weights = [max(0.001, w) for _, w in scored_candidates]
    chooser = rng if rng is not None else random
    return chooser.choices(storylets, weights=weights, k=1)[0]


def top_storylet_score(scored_candidates: List[Tuple[Storylet, float]]) -> float:
    """Return the best semantic score from candidate tuples."""
    if not scored_candidates:
        return 0.0
    return max(float(score) for _, score in scored_candidates)
