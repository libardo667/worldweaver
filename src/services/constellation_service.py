"""Semantic constellation payload builder for debug inspection."""

from datetime import UTC, datetime
from math import sqrt
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import Storylet
from .embedding_service import cosine_similarity
from .semantic_selector import compute_player_context_vector, score_storylets
from .storylet_utils import find_storylet_by_location, normalize_requires, storylet_location
from types import SimpleNamespace as _NS

# Compass deltas (inlined from removed SpatialNavigator)
_DIRECTIONS = {
    "north": _NS(dx=0, dy=-1), "south": _NS(dx=0, dy=1),
    "east": _NS(dx=1, dy=0),  "west": _NS(dx=-1, dy=0),
    "northeast": _NS(dx=1, dy=-1), "northwest": _NS(dx=-1, dy=-1),
    "southeast": _NS(dx=1, dy=1),  "southwest": _NS(dx=-1, dy=1),
}


def _active_storylets(db: Session) -> List[Storylet]:
    now = datetime.now(UTC).replace(tzinfo=None)
    return db.query(Storylet).filter(or_(Storylet.expires_at.is_(None), Storylet.expires_at > now)).all()


def _safe_position(storylet: Storylet) -> Optional[Dict[str, int]]:
    position = storylet.position if isinstance(storylet.position, dict) else None
    if not isinstance(position, dict):
        return None
    if "x" not in position or "y" not in position:
        return None
    try:
        return {"x": int(position["x"]), "y": int(position["y"])}
    except (TypeError, ValueError):
        return None


def _player_position(
    state_manager: Any,
    db: Session,
    storylet_positions: Dict[int, Dict[str, int]],
    active_storylets: List[Storylet],
) -> Optional[Dict[str, int]]:
    current_location = str(state_manager.get_variable("location", ""))
    if not current_location:
        return None

    current_storylet = find_storylet_by_location(db, current_location)
    if current_storylet and current_storylet.id in storylet_positions:
        return storylet_positions[int(current_storylet.id)]

    for storylet in active_storylets:
        if storylet_location(storylet) == current_location and storylet.id in storylet_positions:
            return storylet_positions[int(storylet.id)]

    return None


def _summarize_context_vars(vars_snapshot: Dict[str, Any], limit: int = 6) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for key in sorted(vars_snapshot.keys()):
        if key == "location" or key.startswith("_"):
            continue
        summary[key] = vars_snapshot[key]
        if len(summary) >= limit:
            break
    return summary


def _distance(
    origin: Optional[Dict[str, int]],
    target: Optional[Dict[str, int]],
) -> Optional[float]:
    if origin is None or target is None:
        return None
    dx = float(target["x"]) - float(origin["x"])
    dy = float(target["y"]) - float(origin["y"])
    return round(sqrt((dx * dx) + (dy * dy)), 3)


def _recent_storylet_ids(db: Session, session_id: str, limit: int = 12) -> List[int]:
    from . import world_memory

    recent = world_memory.get_world_history(
        db,
        session_id=session_id,
        limit=limit,
    )
    return [int(event.storylet_id) for event in recent if event.storylet_id is not None]


def _spatial_edges(storylet_positions: Dict[int, Dict[str, int]]) -> Dict[int, Dict[str, int]]:
    by_position = {(position["x"], position["y"]): storylet_id for storylet_id, position in storylet_positions.items()}
    edges: Dict[int, Dict[str, int]] = {}
    for storylet_id, position in storylet_positions.items():
        neighbor_map: Dict[str, int] = {}
        for direction_name, direction in _DIRECTIONS.items():
            neighbor_id = by_position.get((position["x"] + int(direction.dx), position["y"] + int(direction.dy)))
            if neighbor_id is not None:
                neighbor_map[direction_name] = int(neighbor_id)
        edges[int(storylet_id)] = neighbor_map
    return edges


def _semantic_edges(
    scored_storylets: List[Tuple[Storylet, float]],
    neighbor_k: int,
) -> Dict[int, List[int]]:
    scored_by_id = {int(storylet.id): storylet for storylet, _ in scored_storylets if storylet.id is not None and isinstance(storylet.embedding, list)}
    edges: Dict[int, List[int]] = {}
    for storylet_id, storylet in scored_by_id.items():
        base = storylet.embedding
        if not isinstance(base, list):
            edges[storylet_id] = []
            continue

        similarities: List[Tuple[int, float]] = []
        for neighbor_id, candidate in scored_by_id.items():
            if neighbor_id == storylet_id:
                continue
            candidate_embedding = candidate.embedding
            if not isinstance(candidate_embedding, list):
                continue
            if len(base) != len(candidate_embedding):
                continue
            similarity = cosine_similarity(base, candidate_embedding)
            similarities.append((neighbor_id, float(similarity)))

        similarities.sort(key=lambda item: (-item[1], item[0]))
        edges[storylet_id] = [neighbor_id for neighbor_id, _ in similarities[:neighbor_k]]

    return edges


def get_semantic_constellation(
    *,
    db: Session,
    state_manager: Any,
    session_id: str,
    top_n: int = 20,
    include_edges: bool = True,
    semantic_neighbors_k: int = 3,
) -> Dict[str, Any]:
    """Build semantic constellation data from the current session context."""
    from . import world_memory

    capped_top_n = max(1, min(100, int(top_n)))
    neighbor_k = max(0, min(10, int(semantic_neighbors_k)))

    active_storylets = _active_storylets(db)
    contextual_vars = state_manager.get_contextual_variables()
    active_beats = state_manager.get_active_narrative_beats()

    storylet_positions: Dict[int, Dict[str, int]] = {}
    accessible_map: Dict[int, bool] = {}
    embedded_storylets: List[Storylet] = []

    for storylet in active_storylets:
        if storylet.id is None:
            continue
        storylet_id = int(storylet.id)
        requires = normalize_requires(storylet.requires)
        accessible_map[storylet_id] = bool(state_manager.evaluate_condition(requires))

        position = _safe_position(storylet)
        if position is not None:
            storylet_positions[storylet_id] = position

        if isinstance(storylet.embedding, list):
            embedded_storylets.append(storylet)

    context = {
        "location": str(contextual_vars.get("location", "unknown")),
        "vars": _summarize_context_vars(contextual_vars),
    }

    if not embedded_storylets:
        return {
            "session_id": session_id,
            "context": context,
            "storylets": [],
            "count": 0,
            "top_n": capped_top_n,
        }

    context_vector = compute_player_context_vector(state_manager, world_memory, db)
    recent_storylet_ids = _recent_storylet_ids(db, session_id=session_id)
    player_position = _player_position(
        state_manager,
        db,
        storylet_positions,
        active_storylets,
    )
    scored = score_storylets(
        context_vector,
        embedded_storylets,
        recent_storylet_ids=recent_storylet_ids,
        active_beats=active_beats,
        player_position=player_position,
        storylet_positions=storylet_positions,
    )
    scored.sort(key=lambda pair: (-float(pair[1]), int(pair[0].id or 0)))
    top_scored = scored[:capped_top_n]

    spatial_edges = _spatial_edges(storylet_positions) if include_edges else {}
    semantic_edges = _semantic_edges(top_scored, neighbor_k) if include_edges else {}

    storylet_payload: List[Dict[str, Any]] = []
    for storylet, score in top_scored:
        if storylet.id is None:
            continue
        storylet_id = int(storylet.id)
        position = storylet_positions.get(storylet_id)
        storylet_payload.append(
            {
                "id": storylet_id,
                "title": str(storylet.title),
                "position": position,
                "score": round(float(score), 6),
                "accessible": bool(accessible_map.get(storylet_id, False)),
                "location": storylet_location(storylet),
                "distance": _distance(player_position, position),
                "edges": {
                    "spatial_neighbors": spatial_edges.get(storylet_id, {}),
                    "semantic_neighbors": semantic_edges.get(storylet_id, []),
                },
            }
        )

    return {
        "session_id": session_id,
        "context": context,
        "storylets": storylet_payload,
        "count": len(storylet_payload),
        "top_n": capped_top_n,
    }
