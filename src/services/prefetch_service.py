"""Background frontier prefetch for low-latency storylet selection."""

import copy
import logging
import threading
import time
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, cast

from sqlalchemy import or_
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings
from ..database import SessionLocal
from ..models import Storylet
from .storylet_utils import find_storylet_by_location, normalize_choice, storylet_location

logger = logging.getLogger(__name__)

_session_frontier_cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_last_schedule_at: Dict[str, float] = {}
_inflight_sessions: set[str] = set()
_cache_lock = threading.Lock()


def _cache_capacity() -> int:
    return max(1, int(settings.state_manager_cache_max_size))


def _ttl_seconds() -> int:
    projection_ttl = int(settings.v3_projection_ttl_seconds or settings.prefetch_ttl_seconds)
    prefetch_ttl = int(settings.prefetch_ttl_seconds)
    return max(1, min(projection_ttl, prefetch_ttl))


def _stub_cap_per_session() -> int:
    return max(0, int(settings.prefetch_max_per_session))


def _schedule_window_seconds() -> int:
    return max(1, int(settings.prefetch_idle_trigger_seconds))


def _projection_expansion_enabled() -> bool:
    return bool(settings.enable_frontier_prefetch and settings.enable_v3_projection_expansion)


def _projection_max_depth() -> int:
    return max(0, int(settings.v3_projection_max_depth))


def _projection_max_nodes() -> int:
    return max(0, int(settings.v3_projection_max_nodes))


def _projection_time_budget_ms() -> int:
    return max(0, int(settings.v3_projection_time_budget_ms))


def _projection_time_budget_seconds() -> float:
    return float(_projection_time_budget_ms()) / 1000.0


def _effective_stub_cap() -> int:
    return max(0, min(_stub_cap_per_session(), _projection_max_nodes()))


def _now_mono() -> float:
    return time.monotonic()


def _safe_session_id(session_id: Any) -> str:
    return str(session_id or "").strip()


def _purge_expired_locked(now: float) -> None:
    expired = [session_id for session_id, payload in _session_frontier_cache.items() if float(payload.get("expires_at_mono", 0.0)) <= now]
    for session_id in expired:
        _session_frontier_cache.pop(session_id, None)


def _store_frontier_locked(
    session_id: str,
    stubs: List[Dict[str, Any]],
    directional_leads: List[Dict[str, Any]],
    context_summary: Dict[str, Any],
    now: float,
) -> Dict[str, Any]:
    expires_at = now + _ttl_seconds()
    stub_cap = _stub_cap_per_session()
    trimmed_stubs = stubs[:stub_cap] if stub_cap > 0 else []
    payload = {
        "session_id": session_id,
        "stubs": trimmed_stubs,
        "directional_leads": directional_leads[:stub_cap] if stub_cap > 0 else [],
        "context_summary": dict(context_summary),
        "created_at_mono": now,
        "expires_at_mono": expires_at,
    }

    if session_id in _session_frontier_cache:
        _session_frontier_cache.pop(session_id, None)
    _session_frontier_cache[session_id] = payload
    while len(_session_frontier_cache) > _cache_capacity():
        _session_frontier_cache.popitem(last=False)
    return payload


def _copy_frontier(payload: Optional[Dict[str, Any]], now: float) -> Optional[Dict[str, Any]]:
    if not payload:
        return None
    ttl_remaining = max(0, int(round(float(payload.get("expires_at_mono", now)) - now)))
    result: Dict[str, Any] = {
        "session_id": str(payload.get("session_id", "")),
        "stubs": [dict(item) for item in cast(List[Dict[str, Any]], payload.get("stubs", []))],
        "directional_leads": [dict(item) for item in cast(List[Dict[str, Any]], payload.get("directional_leads", []))],
        "context_summary": dict(cast(Dict[str, Any], payload.get("context_summary", {}))),
        "expires_in_seconds": ttl_remaining,
    }
    projection_tree = payload.get("projection_tree")
    if isinstance(projection_tree, dict):
        result["projection_tree"] = copy.deepcopy(projection_tree)
    return result


def clear_prefetch_cache() -> None:
    """Reset all in-memory prefetch cache and scheduling metadata."""
    with _cache_lock:
        _session_frontier_cache.clear()
        _last_schedule_at.clear()
        _inflight_sessions.clear()


def clear_prefetch_cache_for_session(session_id: str) -> None:
    """Clear cached frontier + scheduling metadata for one session."""
    safe_session_id = _safe_session_id(session_id)
    if not safe_session_id:
        return
    with _cache_lock:
        _session_frontier_cache.pop(safe_session_id, None)
        _last_schedule_at.pop(safe_session_id, None)
        _inflight_sessions.discard(safe_session_id)


def get_frontier_status(session_id: str) -> Dict[str, int]:
    """Return current cached frontier count + TTL for one session."""
    safe_session_id = _safe_session_id(session_id)
    if not safe_session_id:
        return {"stubs_cached": 0, "expires_in_seconds": 0}

    now = _now_mono()
    with _cache_lock:
        _purge_expired_locked(now)
        payload = _session_frontier_cache.get(safe_session_id)
        if payload is None:
            return {"stubs_cached": 0, "expires_in_seconds": 0}
        ttl_remaining = max(0, int(round(float(payload.get("expires_at_mono", now)) - now)))
        return {
            "stubs_cached": len(cast(List[Dict[str, Any]], payload.get("stubs", []))),
            "expires_in_seconds": ttl_remaining,
        }


def get_cached_frontier(session_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a session frontier cache snapshot when present and not expired."""
    safe_session_id = _safe_session_id(session_id)
    if not safe_session_id:
        return None

    now = _now_mono()
    with _cache_lock:
        _purge_expired_locked(now)
        payload = _session_frontier_cache.get(safe_session_id)
        return _copy_frontier(payload, now)


def set_prefetched_stubs_for_session(
    session_id: str,
    stubs: Sequence[Dict[str, Any]],
    context_summary: Optional[Dict[str, Any]] = None,
    directional_leads: Optional[Sequence[Dict[str, Any]]] = None,
) -> None:
    """Directly seed prefetch cache for tests/debug flows."""
    safe_session_id = _safe_session_id(session_id)
    if not safe_session_id:
        return

    now = _now_mono()
    with _cache_lock:
        _purge_expired_locked(now)
        _store_frontier_locked(
            safe_session_id,
            [dict(item) for item in stubs],
            [dict(item) for item in (directional_leads or [])],
            dict(context_summary or {}),
            now,
        )


def _active_storylets(db: Session) -> List[Storylet]:
    now_utc = datetime.now(UTC).replace(tzinfo=None)
    return db.query(Storylet).filter(or_(Storylet.expires_at.is_(None), Storylet.expires_at > now_utc)).all()


def _compact_text(text: Any, max_len: int = 180) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[: max_len - 3].rstrip()}..."


def _normalize_stub_choices(raw_choices: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(raw_choices, list):
        return out
    for raw in raw_choices[:3]:
        if isinstance(raw, dict):
            out.append(normalize_choice(raw))
    return out


def _transient_storylet_from_stub(stub: Dict[str, Any]) -> Optional[Storylet]:
    """Build a transient Storylet from cached stub payload for safe reuse."""
    payload = stub.get("storylet_payload") if isinstance(stub.get("storylet_payload"), dict) else None
    if not isinstance(payload, dict):
        return None
    title = str(payload.get("title", "")).strip() or str(stub.get("title", "")).strip()
    text_template = str(payload.get("text_template", "")).strip() or str(stub.get("premise", "")).strip()
    if not title or not text_template:
        return None
    requires = payload.get("requires") if isinstance(payload.get("requires"), dict) else {}
    choices = payload.get("choices") if isinstance(payload.get("choices"), list) else []
    effects = payload.get("effects") if isinstance(payload.get("effects"), list) else []
    source = str(payload.get("source", "runtime_synthesis") or "runtime_synthesis")
    try:
        weight = float(payload.get("weight", 1.0))
    except (TypeError, ValueError):
        weight = 1.0
    return Storylet(
        title=title,
        text_template=text_template,
        requires=cast(Dict[str, Any], requires),
        choices=cast(List[Dict[str, Any]], choices),
        effects=cast(List[Dict[str, Any]], effects),
        weight=weight,
        source=source,
    )


def _resolve_position(storylet: Storylet) -> Optional[Dict[str, int]]:
    position = storylet.position if isinstance(storylet.position, dict) else None
    if isinstance(position, dict) and "x" in position and "y" in position:
        try:
            return {"x": int(position["x"]), "y": int(position["y"])}
        except (TypeError, ValueError):
            return None
    return None


def _collect_storylet_positions(storylets: Iterable[Storylet]) -> Dict[int, Dict[str, int]]:
    out: Dict[int, Dict[str, int]] = {}
    for storylet in storylets:
        if storylet.id is None:
            continue
        position = _resolve_position(storylet)
        if position is not None:
            out[int(storylet.id)] = position
    return out


def _direction_from_delta(dx: int, dy: int) -> str:
    if dx == 0 and dy == 0:
        return "here"
    vertical = ""
    horizontal = ""
    if dy < 0:
        vertical = "north"
    elif dy > 0:
        vertical = "south"
    if dx > 0:
        horizontal = "east"
    elif dx < 0:
        horizontal = "west"
    if vertical and horizontal:
        return f"{vertical}{horizontal}"
    return vertical or horizontal or "here"


def _build_directional_leads(
    selected_storylets: Sequence[Storylet],
    current_position: Optional[Dict[str, int]],
) -> List[Dict[str, Any]]:
    if current_position is None:
        return []
    leads: List[Dict[str, Any]] = []
    for storylet in selected_storylets:
        if storylet.id is None:
            continue
        position = _resolve_position(storylet)
        if position is None:
            continue
        dx = int(position["x"]) - int(current_position["x"])
        dy = int(position["y"]) - int(current_position["y"])
        leads.append(
            {
                "storylet_id": int(storylet.id),
                "direction": _direction_from_delta(dx, dy),
                "x": int(position["x"]),
                "y": int(position["y"]),
                "title": str(storylet.title),
            }
        )
    return leads


_RISK_TAG_KEYWORDS: Dict[str, str] = {
    "danger": "danger_increase",
    "fear": "fear_increase",
    "trust": "trust_change",
    "location": "location_change",
    "health": "health_change",
    "injury": "injury_change",
}


def _generate_risk_tags(stakes_delta: Dict[str, Any]) -> List[str]:
    """Heuristically derive risk tags from choice set-var keys."""
    tags: List[str] = []
    for key in stakes_delta:
        lowered = str(key).lower()
        for keyword, tag in _RISK_TAG_KEYWORDS.items():
            if keyword in lowered and tag not in tags:
                tags.append(tag)
    return tags


def _extract_seed_anchors(title: str, max_anchors: int = 3) -> List[str]:
    """Extract significant words from a storylet title as seed anchors."""
    stop = {"the", "a", "an", "of", "in", "at", "to", "and", "or", "is", "on", "for"}
    words = [w.lower().strip(",.!?:;-\"'") for w in str(title or "").split()]
    return [w for w in words if w and len(w) > 2 and w not in stop][:max_anchors]


def _choices_summary(raw_choices: Any) -> List[Dict[str, Any]]:
    """Build a compact choices summary with label and set keys only."""
    out: List[Dict[str, Any]] = []
    if not isinstance(raw_choices, list):
        return out
    for raw in raw_choices[:4]:
        if not isinstance(raw, dict):
            continue
        label = str(raw.get("label") or raw.get("text") or "Continue")
        set_dict = raw.get("set") or raw.get("set_vars") or {}
        out.append({"label": label, "set_keys": sorted(set_dict.keys()) if isinstance(set_dict, dict) else []})
    return out


def _projection_key_facts(
    state_manager: Any,
    *,
    max_items: int = 10,
) -> List[Dict[str, Any]]:
    """Extract compact world facts for projection referee scoring prompts."""
    raw_variables = getattr(state_manager, "variables", {})
    if not isinstance(raw_variables, dict):
        return []

    facts: List[Dict[str, Any]] = []
    for raw_key, raw_value in raw_variables.items():
        if len(facts) >= max_items:
            break
        key = str(raw_key or "").strip()
        if not key or key.startswith("_"):
            continue
        if isinstance(raw_value, (str, int, float, bool)) or raw_value is None:
            facts.append({"key": key, "value": raw_value})
            continue
        if isinstance(raw_value, list):
            compact = [item for item in raw_value[:3] if isinstance(item, (str, int, float, bool))]
            if compact:
                facts.append({"key": key, "value": compact})
    return facts


def _expand_projection_bfs(
    state_manager: Any,
    depth_0_storylets: List[Storylet],
    active_storylets: List[Storylet],
    *,
    max_depth: int,
    max_nodes: int,
    time_budget_seconds: float,
    session_id: str = "",
    root_location: str = "",
    semantic_scores: Optional[Dict[int, float]] = None,
) -> Dict[str, Any]:
    """Expand a bounded BFS projection tree from depth-0 eligible storylets.

    Returns a dict matching the ProjectionTree schema shape.  The expansion
    simulates applying each choice's ``set`` dict to a forked state snapshot
    and discovering which storylets become eligible at the next depth.
    """
    from ..models.schemas import ProjectionNode, ProjectionTree

    if semantic_scores is None:
        semantic_scores = {}

    started = time.perf_counter()
    nodes: List[Dict[str, Any]] = []
    seen_paths: set[tuple[int, int, str, int]] = set()
    node_count = 0
    max_depth_reached = 0
    budget_exhausted = False

    def _is_over_budget() -> bool:
        nonlocal budget_exhausted
        if time_budget_seconds <= 0.0:
            budget_exhausted = True
            return True
        if node_count >= max_nodes:
            budget_exhausted = True
            return True
        if (time.perf_counter() - started) >= time_budget_seconds:
            budget_exhausted = True
            return True
        return False

    # Queue items: (storylet, depth, parent_node_id, parent_choice_index, parent_choice_label, stakes_delta, forked_state_manager)
    queue: List[tuple] = []

    # Seed depth-0 nodes
    for storylet in depth_0_storylets:
        if _is_over_budget():
            break
        if storylet.id is None:
            continue
        s_id = int(storylet.id)
        node_id = f"d0-s{s_id}"
        location = storylet_location(storylet)
        position = _resolve_position(storylet)
        choices_raw = storylet.choices if isinstance(storylet.choices, list) else []

        node_count += 1
        nodes.append(
            ProjectionNode(
                node_id=node_id,
                depth=0,
                storylet_id=s_id,
                title=str(storylet.title),
                projected_location=location,
                position=position,
                requires=cast(Dict[str, Any], storylet.requires or {}),
                choices_summary=_choices_summary(choices_raw),
                allowed=True,
                confidence=1.0,
                semantic_score=semantic_scores.get(s_id),
                seed_anchors=_extract_seed_anchors(str(storylet.title)),
            ).model_dump()
        )

        # Enqueue choices for deeper expansion
        if max_depth >= 1:
            for ci, choice in enumerate(choices_raw[:4]):
                if not isinstance(choice, dict):
                    continue
                set_dict = choice.get("set") or choice.get("set_vars") or {}
                if not isinstance(set_dict, dict):
                    continue
                label = str(choice.get("label") or choice.get("text") or "Continue")
                queue.append((storylet, 1, node_id, ci, label, dict(set_dict), state_manager))

    # BFS loop
    while queue and not _is_over_budget():
        _storylet, depth, parent_nid, choice_idx, choice_label, delta, parent_sm = queue.pop(0)
        if depth > max_depth:
            continue

        # Fork state and apply choice delta
        forked = parent_sm.fork_for_projection()
        for k, v in delta.items():
            forked.set_variable(k, v)

        # Find newly eligible storylets
        for candidate in active_storylets:
            if _is_over_budget():
                break
            if candidate.id is None:
                continue
            c_id = int(candidate.id)
            requires = cast(Dict[str, Any], candidate.requires or {})
            if not forked.evaluate_condition(requires):
                continue

            dedupe_key = (depth, c_id, str(parent_nid), int(choice_idx))
            if dedupe_key in seen_paths:
                continue
            seen_paths.add(dedupe_key)

            location = storylet_location(candidate)
            position = _resolve_position(candidate)
            choices_raw = candidate.choices if isinstance(candidate.choices, list) else []
            risk_tags = _generate_risk_tags(delta)

            node_id = f"d{depth}-s{c_id}-n{node_count + 1}"
            node_count += 1
            max_depth_reached = max(max_depth_reached, depth)
            nodes.append(
                ProjectionNode(
                    node_id=node_id,
                    depth=depth,
                    storylet_id=c_id,
                    title=str(candidate.title),
                    projected_location=location,
                    position=position,
                    requires=requires,
                    choices_summary=_choices_summary(choices_raw),
                    parent_node_id=parent_nid,
                    parent_choice_index=choice_idx,
                    parent_choice_label=choice_label,
                    allowed=True,
                    confidence=1.0,
                    semantic_score=semantic_scores.get(c_id),
                    stakes_delta=delta,
                    risk_tags=risk_tags,
                    seed_anchors=_extract_seed_anchors(str(candidate.title)),
                ).model_dump()
            )

            # Enqueue this node's choices for next depth
            if depth + 1 <= max_depth:
                for ci2, ch2 in enumerate(choices_raw[:4]):
                    if not isinstance(ch2, dict):
                        continue
                    set_dict2 = ch2.get("set") or ch2.get("set_vars") or {}
                    if not isinstance(set_dict2, dict):
                        continue
                    label2 = str(ch2.get("label") or ch2.get("text") or "Continue")
                    queue.append((candidate, depth + 1, node_id, ci2, label2, dict(set_dict2), forked))

    referee_scored = False
    if nodes:
        try:
            from .llm_service import score_projection_nodes

            remaining_scoring_budget = max(0.0, time_budget_seconds - (time.perf_counter() - started))
            if remaining_scoring_budget <= 0.0:
                budget_exhausted = True
            else:
                scored_nodes, referee_scored = score_projection_nodes(
                    nodes,
                    {
                        "location": root_location,
                        "key_facts": _projection_key_facts(state_manager),
                    },
                    timeout_seconds=remaining_scoring_budget,
                    return_meta=True,
                )
                nodes = scored_nodes
                if (time.perf_counter() - started) >= time_budget_seconds:
                    budget_exhausted = True
        except Exception as exc:
            logger.debug("Projection referee scoring failed (non-fatal): %s", exc)

    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
    return ProjectionTree(
        session_id=session_id,
        root_location=root_location,
        nodes=[ProjectionNode.model_validate(n) for n in nodes],
        max_depth_reached=max_depth_reached,
        total_nodes=len(nodes),
        budget_exhausted=budget_exhausted,
        elapsed_ms=elapsed_ms,
        referee_scored=referee_scored,
        generated_at=datetime.now(UTC).isoformat(),
    ).model_dump()


def _select_prefetch_storylets(
    db: Session,
    state_manager: Any,
    trigger: str,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any], Optional[Dict[str, Any]]]:
    from . import world_memory
    from .semantic_selector import compute_player_context_vector, score_storylets

    runtime_settings = settings.get_v3_runtime_settings()
    projection_flags = dict(cast(Dict[str, Any], runtime_settings.get("flags", {})))
    projection_budget = dict(cast(Dict[str, Any], runtime_settings.get("budgets", {})))
    max_depth = _projection_max_depth()
    max_nodes = _projection_max_nodes()
    time_budget_ms = _projection_time_budget_ms()
    time_budget_seconds = _projection_time_budget_seconds()
    stub_cap = _effective_stub_cap()
    current_location = str(state_manager.get_variable("location", "start") or "start")
    expansion_started = time.perf_counter()
    budget_exhausted = False
    nodes_examined = 0

    def _is_budget_exhausted() -> bool:
        nonlocal budget_exhausted
        if time_budget_seconds <= 0.0:
            budget_exhausted = True
            return True
        if (time.perf_counter() - expansion_started) >= time_budget_seconds:
            budget_exhausted = True
            return True
        return False

    disabled_reasons: List[str] = []
    if max_depth <= 0:
        disabled_reasons.append("max_depth")
    if max_nodes <= 0:
        disabled_reasons.append("max_nodes")
    if stub_cap <= 0:
        disabled_reasons.append("stub_cap")
    if time_budget_ms <= 0:
        disabled_reasons.append("time_budget_ms")

    if disabled_reasons:
        return (
            [],
            [],
            {
                "trigger": trigger,
                "location": current_location,
                "eligible_count": 0,
                "cached_count": 0,
                "projection_nodes_examined": 0,
                "projection_depth_reached": 0,
                "projection_tree_node_count": 0,
                "projection_budget_exhausted": False,
                "projection_elapsed_ms": round((time.perf_counter() - expansion_started) * 1000.0, 3),
                "projection_disabled_reason": ",".join(disabled_reasons),
                "projection_flags": projection_flags,
                "projection_budget": projection_budget,
                "generated_at": datetime.now(UTC).isoformat(),
            },
            None,
        )

    eligible: List[Storylet] = []
    for storylet in _active_storylets(db):
        if nodes_examined >= max_nodes or _is_budget_exhausted():
            break
        nodes_examined += 1
        requires = cast(Dict[str, Any], storylet.requires or {})
        if state_manager.evaluate_condition(requires):
            eligible.append(storylet)

    if not eligible:
        return (
            [],
            [],
            {
                "trigger": trigger,
                "location": current_location,
                "eligible_count": len(eligible),
                "cached_count": 0,
                "projection_nodes_examined": nodes_examined,
                "projection_depth_reached": 0,
                "projection_tree_node_count": 0,
                "projection_budget_exhausted": bool(budget_exhausted),
                "projection_elapsed_ms": round((time.perf_counter() - expansion_started) * 1000.0, 3),
                "projection_flags": projection_flags,
                "projection_budget": projection_budget,
                "generated_at": datetime.now(UTC).isoformat(),
            },
            None,
        )

    location_target = min(max(1, stub_cap // 2), stub_cap)
    semantic_target = max(0, stub_cap - location_target)
    selected: List[Storylet] = []
    selected_ids: set[int] = set()
    semantic_scores: Dict[int, float] = {}

    for storylet in eligible:
        if _is_budget_exhausted():
            break
        if len(selected) >= location_target:
            break
        if storylet_location(storylet) == current_location and storylet.id is not None:
            selected.append(storylet)
            selected_ids.add(int(storylet.id))

    if semantic_target > 0 and not _is_budget_exhausted():
        semantic_candidates = [storylet for storylet in eligible if storylet.embedding and storylet.id is not None and int(storylet.id) not in selected_ids]
        if semantic_candidates:
            try:
                context_vector = compute_player_context_vector(
                    state_manager=state_manager,
                    world_memory_module=world_memory,
                    db=db,
                )
                scored = score_storylets(
                    context_vector,
                    semantic_candidates,
                    recent_storylet_ids=[],
                    active_beats=state_manager.get_active_narrative_beats(),
                    storylet_positions=_collect_storylet_positions(semantic_candidates),
                )
                scored_sorted = sorted(scored, key=lambda item: float(item[1]), reverse=True)
                for storylet, score in scored_sorted:
                    if _is_budget_exhausted():
                        break
                    if len(selected) >= stub_cap:
                        break
                    if storylet.id is None:
                        continue
                    storylet_id = int(storylet.id)
                    if storylet_id in selected_ids:
                        continue
                    selected.append(storylet)
                    selected_ids.add(storylet_id)
                    semantic_scores[storylet_id] = float(score)
                    if len(semantic_scores) >= semantic_target:
                        break
            except Exception as exc:
                logger.debug("Prefetch semantic lead scoring failed: %s", exc)

    if len(selected) < stub_cap and not _is_budget_exhausted():
        for storylet in eligible:
            if _is_budget_exhausted():
                break
            if len(selected) >= stub_cap:
                break
            if storylet.id is None:
                continue
            storylet_id = int(storylet.id)
            if storylet_id in selected_ids:
                continue
            selected.append(storylet)
            selected_ids.add(storylet_id)

    stubs: List[Dict[str, Any]] = []
    projection_ttl_seconds = _ttl_seconds()
    for storylet in selected[:stub_cap]:
        if storylet.id is None:
            continue
        storylet_id = int(storylet.id)
        stubs.append(
            {
                "storylet_id": storylet_id,
                "non_canon": True,
                "projection_depth": 1,
                "projection_ttl_seconds": projection_ttl_seconds,
                "title": str(storylet.title),
                "premise": _compact_text(storylet.text_template),
                "requires": cast(Dict[str, Any], storylet.requires or {}),
                "choices": _normalize_stub_choices(storylet.choices),
                "location": storylet_location(storylet),
                "position": _resolve_position(storylet),
                "semantic_score": semantic_scores.get(storylet_id),
                "source": str(storylet.source or "authored"),
                "storylet_payload": {
                    "title": str(storylet.title),
                    "text_template": str(storylet.text_template),
                    "requires": cast(Dict[str, Any], storylet.requires or {}),
                    "choices": _normalize_stub_choices(storylet.choices),
                    "effects": cast(List[Dict[str, Any]], storylet.effects or []),
                    "weight": float(storylet.weight or 1.0),
                    "source": str(storylet.source or "authored"),
                },
            }
        )

    current_storylet = find_storylet_by_location(db, current_location)
    current_position = _resolve_position(current_storylet) if current_storylet is not None else None
    directional_leads = _build_directional_leads(selected, current_position)

    # BFS projection expansion (depth >= 2)
    projection_tree: Optional[Dict[str, Any]] = None
    bfs_depth_reached = 1 if stubs else 0
    bfs_node_count = 0
    if max_depth >= 2 and _projection_expansion_enabled() and selected and not budget_exhausted:
        remaining_time = max(0.0, time_budget_seconds - (time.perf_counter() - expansion_started))
        if remaining_time > 0.01:
            try:
                all_active = _active_storylets(db)
                projection_tree = _expand_projection_bfs(
                    state_manager,
                    selected,
                    all_active,
                    max_depth=max_depth,
                    max_nodes=max(0, max_nodes - nodes_examined),
                    time_budget_seconds=remaining_time,
                    session_id=str(getattr(state_manager, "session_id", "")),
                    root_location=current_location,
                    semantic_scores=semantic_scores,
                )
                bfs_depth_reached = max(bfs_depth_reached, int(projection_tree.get("max_depth_reached", 0)))
                bfs_node_count = int(projection_tree.get("total_nodes", 0))
                if projection_tree.get("budget_exhausted"):
                    budget_exhausted = True
            except Exception as exc:
                logger.debug("Projection BFS expansion failed (non-fatal): %s", exc)

    context_summary: Dict[str, Any] = {
        "trigger": trigger,
        "location": current_location,
        "eligible_count": len(eligible),
        "cached_count": len(stubs),
        "projection_nodes_examined": nodes_examined,
        "projection_depth_reached": bfs_depth_reached,
        "projection_tree_node_count": bfs_node_count,
        "projection_budget_exhausted": bool(budget_exhausted),
        "projection_elapsed_ms": round((time.perf_counter() - expansion_started) * 1000.0, 3),
        "projection_flags": projection_flags,
        "projection_budget": projection_budget,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    return stubs, directional_leads, context_summary, projection_tree


def refresh_frontier_for_session(
    session_id: str,
    trigger: str = "manual",
    db: Optional[Session] = None,
    bind: Any = None,
) -> Optional[Dict[str, Any]]:
    """Build and cache prefetch artifacts for one session (read-only)."""
    safe_session_id = _safe_session_id(session_id)
    if not safe_session_id or not _projection_expansion_enabled():
        return None

    from .session_service import get_state_manager

    owns_db = False
    active_db = db
    if active_db is None:
        owns_db = True
        if bind is None:
            active_db = SessionLocal()
        else:
            scoped = sessionmaker(bind=bind, autocommit=False, autoflush=False)
            active_db = scoped()

    started = time.perf_counter()
    try:
        state_manager = get_state_manager(safe_session_id, cast(Session, active_db))
        stubs, directional_leads, context_summary, projection_tree = _select_prefetch_storylets(
            cast(Session, active_db),
            state_manager,
            trigger,
        )
        now = _now_mono()
        with _cache_lock:
            _purge_expired_locked(now)
            payload = _store_frontier_locked(
                safe_session_id,
                stubs,
                directional_leads,
                context_summary,
                now,
            )
            if projection_tree is not None:
                payload["projection_tree"] = projection_tree
            out = _copy_frontier(payload, now)
        logger.info(
            ("Prefetch refreshed for session=%s trigger=%s cached=%d nodes_examined=%s " "budget_exhausted=%s duration_ms=%.3f"),
            safe_session_id,
            trigger,
            len(stubs),
            context_summary.get("projection_nodes_examined", 0),
            context_summary.get("projection_budget_exhausted", False),
            (time.perf_counter() - started) * 1000.0,
        )
        return out
    except Exception as exc:
        logger.debug("Prefetch refresh failed for session=%s: %s", safe_session_id, exc)
        return None
    finally:
        if owns_db and active_db is not None:
            active_db.close()


def _finish_inflight(session_id: str) -> None:
    with _cache_lock:
        _inflight_sessions.discard(session_id)


def _run_prefetch_job(session_id: str, trigger: str, bind: Any = None) -> None:
    try:
        refresh_frontier_for_session(session_id=session_id, trigger=trigger, bind=bind)
    finally:
        _finish_inflight(session_id)


def schedule_frontier_prefetch(
    session_id: str,
    trigger: str = "unknown",
    bind: Any = None,
) -> bool:
    """Schedule a best-effort background prefetch without blocking requests."""
    safe_session_id = _safe_session_id(session_id)
    if not safe_session_id or not _projection_expansion_enabled():
        return False

    now = _now_mono()
    with _cache_lock:
        _purge_expired_locked(now)
        if safe_session_id in _inflight_sessions:
            return False
        min_gap = _schedule_window_seconds()
        last = float(_last_schedule_at.get(safe_session_id, 0.0))
        if now - last < float(min_gap):
            return False
        _last_schedule_at[safe_session_id] = now
        _inflight_sessions.add(safe_session_id)

    worker = threading.Thread(
        target=_run_prefetch_job,
        args=(safe_session_id, trigger, bind),
        daemon=True,
        name=f"ww-prefetch-{safe_session_id[:12]}",
    )
    try:
        worker.start()
        return True
    except Exception:
        _finish_inflight(safe_session_id)
        return False


def select_prefetched_storylet(
    session_id: str,
    eligible_storylets: Sequence[Storylet],
    current_location: str,
    recent_storylet_ids: Optional[Sequence[int]] = None,
) -> Optional[Storylet]:
    """Return one eligible cached storylet, preferring location + non-recent items."""
    safe_session_id = _safe_session_id(session_id)
    if not safe_session_id or not _projection_expansion_enabled():
        return None

    frontier = get_cached_frontier(safe_session_id)
    if not frontier:
        return None

    by_id: Dict[int, Storylet] = {}
    for storylet in eligible_storylets:
        if storylet.id is not None:
            by_id[int(storylet.id)] = storylet

    if not by_id:
        return None

    current_location_text = str(current_location or "").strip()
    recent_ids = {int(item) for item in (recent_storylet_ids or [])}
    ranked: List[tuple[tuple[int, int, float, int], Storylet]] = []
    stubs = cast(List[Dict[str, Any]], frontier.get("stubs", []))
    for idx, stub in enumerate(stubs):
        # Handle transient stubs
        if stub.get("is_stub"):
            storylet = _transient_storylet_from_stub(stub)
            if storylet is None:
                continue
            stub_location = str(stub.get("location") or "").strip()
            location_miss = 0 if stub_location and stub_location == current_location_text else 1
            # Ranking: Not recent (0), location miss, semantic score prioritizes stubs slightly
            rank = (0, location_miss, -1.0, idx)
            ranked.append((rank, storylet))
            continue

        raw_storylet_id = stub.get("storylet_id")
        if raw_storylet_id is None:
            continue
        try:
            storylet_id = int(raw_storylet_id)
        except (TypeError, ValueError):
            continue
        storylet = by_id.get(storylet_id)
        if storylet is None:
            continue
        stub_location = str(stub.get("location") or "").strip()
        location_miss = 0 if stub_location and stub_location == current_location_text else 1
        is_recent = 1 if storylet_id in recent_ids else 0
        semantic_score = float(stub.get("semantic_score") or 0.0)
        rank = (is_recent, location_miss, -semantic_score, idx)
        ranked.append((rank, storylet))

    if not ranked:
        return None

    ranked.sort(key=lambda pair: pair[0])
    return ranked[0][1]
