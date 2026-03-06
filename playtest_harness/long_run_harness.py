#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence, Tuple

import requests

DEFAULT_BASE_URL = os.getenv("WW_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/")
DEFAULT_OUTPUT_DIR = Path("playtests") / "long_runs"
DEFAULT_TURNS = 100
DEFAULT_SEED = 20260304
DEFAULT_STORYLET_COUNT = 15
DEFAULT_REQUEST_TIMEOUT_SECONDS = float(os.getenv("WW_REQUEST_TIMEOUT_SECONDS", "240"))
DEFAULT_PREFETCH_WAIT_TIMEOUT_SECONDS = float(os.getenv("WW_PREFETCH_WAIT_TIMEOUT_SECONDS", "3.0"))
DEFAULT_PREFETCH_WAIT_STRICT_TIMEOUT_SECONDS = float(os.getenv("WW_PREFETCH_WAIT_STRICT_TIMEOUT_SECONDS", "15.0"))
PREFETCH_WAIT_POLICIES = ("off", "bounded", "strict")
PREFIX_SOFT_MATCH_THRESHOLD = 0.6
MOTIF_MIN_TOKEN_LENGTH = 4
MOTIF_MAX_TOKENS_PER_TURN = 24
CLARITY_LEVEL_ORDER = ("unknown", "rumor", "lead", "prepared", "committed")
MOTIF_STOPWORDS = {
    "about",
    "across",
    "after",
    "again",
    "against",
    "around",
    "because",
    "before",
    "begins",
    "below",
    "between",
    "beyond",
    "bring",
    "called",
    "carry",
    "choice",
    "choices",
    "could",
    "current",
    "detail",
    "during",
    "every",
    "explore",
    "find",
    "first",
    "from",
    "gather",
    "given",
    "here",
    "however",
    "initial",
    "into",
    "journey",
    "just",
    "keep",
    "later",
    "likely",
    "look",
    "main",
    "might",
    "more",
    "most",
    "move",
    "next",
    "narrative",
    "nothing",
    "other",
    "over",
    "placeholder",
    "player",
    "press",
    "presses",
    "response",
    "returns",
    "scene",
    "should",
    "some",
    "story",
    "storylet",
    "storylets",
    "there",
    "these",
    "this",
    "through",
    "under",
    "until",
    "upon",
    "using",
    "very",
    "when",
    "where",
    "which",
    "while",
    "with",
    "within",
    "without",
    "world",
    "your",
}
_MOTIF_TOKEN_PATTERN = re.compile(r"[a-z][a-z0-9'-]*")

SCENARIOS: Dict[str, Dict[str, Any]] = {
    "cyberpunk": {
        "title": "Neon Pursuit",
        "theme": "cyberpunk noir",
        "roles": [
            "rogue AI hunter",
            "memory broker",
            "street medic with a black-market license",
            "drone courier running encrypted drops",
        ],
        "description": "A rain-soaked megacity of enforcers, fixers, and unstable AI traces.",
        "key_elements": [
            "neon reflections in rain",
            "memory core extraction",
            "terminal intrusion traces",
            "patrol drones overhead",
            "industrial filtration plants",
        ],
        "tone": "gritty, suspenseful, desperate",
    },
    "space_opera": {
        "title": "Shatter-Belt Run",
        "theme": "space opera",
        "roles": [
            "smuggler captain",
            "salvage pilot",
            "nav-officer turned deserter",
            "station ghost mechanic",
        ],
        "description": "A contested star frontier with patrol sweeps and fragile alliances.",
        "key_elements": [
            "damaged reactor housing",
            "debris shadow approaches",
            "encrypted cargo manifests",
            "patrol scanner sweeps",
            "cold-dark drift maneuvers",
        ],
        "tone": "high-pressure and cinematic",
    },
    "gothic": {
        "title": "Clockwork Decay",
        "theme": "gothic clockwork alchemy",
        "roles": [
            "outcast alchemist",
            "cathedral archivist",
            "gearwright saboteur",
            "state enforcer with a failing prosthetic",
        ],
        "description": "A gear-driven city where alchemical risk and faction politics dominate.",
        "key_elements": [
            "whirring gears",
            "glowing vials",
            "soot-stained gargoyles",
            "clockwork prosthetics",
            "the Great Gear",
        ],
        "tone": "opulent and decaying",
    },
    "dark_fantasy": {
        "title": "Ashen Oathlands",
        "theme": "dark fantasy",
        "roles": [
            "cursed knight",
            "forbidden scripture seeker",
            "gravebound ranger",
            "soul-forger apprentice",
        ],
        "description": "A land of broken vows, haunted ruins, and costly magic.",
        "key_elements": [
            "blackened shrines",
            "ash storms over ruined keeps",
            "blood sigils in stone",
            "oathbound relics",
            "whispering catacombs",
        ],
        "tone": "grim, mythic, relentless",
    },
    "solarpunk": {
        "title": "Canopy Commons",
        "theme": "solarpunk frontier",
        "roles": [
            "grid architect",
            "water-rights negotiator",
            "seed librarian",
            "repair diver in floating districts",
        ],
        "description": "An eco-city balancing innovation, scarcity, and diplomacy.",
        "key_elements": [
            "solar canopies",
            "community fabrication labs",
            "living seawalls",
            "autonomous pollinator swarms",
            "water quota exchanges",
        ],
        "tone": "hopeful, practical, politically tense",
    },
    "post_apocalypse": {
        "title": "Rustline Expanse",
        "theme": "post-apocalyptic survival drama",
        "roles": [
            "convoy scout",
            "salvage quartermaster",
            "former city planner",
            "medic protecting a settlement",
        ],
        "description": "Settlements survive between dead highways and dust fronts.",
        "key_elements": [
            "collapsed overpasses",
            "water caravans",
            "radio towers",
            "ration ledgers",
            "salvage disputes",
        ],
        "tone": "tense, resourceful, human",
    },
    "mystery": {
        "title": "Tideglass Inquiry",
        "theme": "mythic mystery thriller",
        "roles": [
            "forensic folklorist",
            "harbor detective",
            "court translator",
            "retired smuggler turned informant",
        ],
        "description": "A coastal city of cover-ups and conflicting truths.",
        "key_elements": [
            "salt archives",
            "sealed witness logs",
            "ritual masks",
            "fogbound causeways",
            "interrupted radio broadcasts",
        ],
        "tone": "investigative, eerie, deliberate",
    },
    "everyday": {
        "title": "Neighborhood Knots",
        "theme": "everyday city life",
        "roles": [
            "part-time barista balancing rent and friendships",
            "night-shift nurse commuting across districts",
            "public school counselor",
            "rideshare driver supporting extended family",
        ],
        "description": "Small decisions around bills, schedules, trust, and community.",
        "key_elements": [
            "crowded bus rides",
            "group chat spillover",
            "apartment chores and bills",
            "coffee shop regulars",
            "community center classes",
        ],
        "tone": "grounded, warm, quietly tense",
    },
}

DEFAULT_DIVERSITY_ACTIONS: List[str] = [
    "I stop and ask the nearest witness what changed in this district overnight.",
    "I leave a coded message to draw an ally here and then hide nearby.",
    "I inspect the environment for one concrete hazard no one has mentioned yet.",
    "I deliberately take the least obvious route to test whether I am being followed.",
    "I offer help to an exhausted stranger and ask for one useful detail in return.",
    "I provoke a minor confrontation to flush hidden actors into the open.",
    "I pause to secure supplies and reduce immediate risk before moving again.",
    "I search for a rumor network and trade information instead of force.",
    "I change priorities and pursue a side objective tied to local tensions.",
    "I attempt to repair a damaged system so future choices open up.",
    "I test a risky shortcut that could save time but raise danger.",
    "I gather hard evidence before committing to any faction claim.",
    "I revisit a previous location to check how the world has changed.",
    "I negotiate for safe passage and offer a concrete concession.",
    "I set a decoy trail so adversaries react to false information.",
    "I escalate publicly to force a decision from the strongest opponent.",
    "I de-escalate, hide my intent, and wait for a better opening.",
    "I attempt a stealth extraction of a key asset without direct conflict.",
    "I sabotage a chokepoint to limit enemy options in future turns.",
    "I choose empathy over efficiency and prioritize protecting bystanders.",
]


@dataclass
class WorldConfig:
    scenario_id: str
    scenario_title: str
    theme: str
    role: str
    description: str
    key_elements: List[str]
    tone: str


@dataclass
class RunConfig:
    base_url: str
    session_id: str
    turns: int
    seed: int
    storylet_count: int
    switch_model: bool
    model_id: str
    hard_reset: bool
    skip_bootstrap: bool
    diversity_every: int
    diversity_chance: float
    output_dir: Path
    world: WorldConfig | None
    request_timeout_seconds: float
    prefetch_wait_policy: str
    prefetch_wait_timeout_seconds: float
    verify_clean_reset: bool
    llm_temperature: float | None
    llm_max_tokens: int | None
    llm_recency_penalty: float | None
    llm_semantic_floor_probability: float | None


@dataclass
class TurnRecord:
    turn: int
    phase: str
    action_source: str
    action_sent: str
    narrative: str
    ack_line: str
    plausible: bool
    choices: List[Dict[str, Any]]
    state_changes: Dict[str, Any]
    vars: Dict[str, Any]
    diagnostics: Dict[str, Any]
    request_duration_ms: float
    prefetch_wait_duration_ms: float
    turn_duration_ms: float
    request_status: str
    request_error: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_slug(value: str) -> str:
    out = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in value.strip().lower())
    out = "-".join(filter(None, out.split("-")))
    return out or "session"


def _split_csv(value: str) -> List[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _request_json(method: str, url: str, *, payload: Dict[str, Any] | None = None, timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS) -> Dict[str, Any]:
    response = requests.request(method, url, json=payload, timeout=timeout)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(f"{method} {url} failed: {response.status_code} {response.text.strip()}") from exc
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError(f"{method} {url} returned unexpected payload type.")
    return body


def _switch_model(base_url: str, model_id: str, *, timeout: float) -> Dict[str, Any]:
    return _request_json("PUT", f"{base_url}/model", payload={"model_id": model_id}, timeout=timeout)


def _hard_reset(base_url: str, *, timeout: float) -> Dict[str, Any]:
    return _request_json("POST", f"{base_url}/dev/hard-reset", payload={}, timeout=timeout)


def _fetch_reset_clean_snapshot(
    base_url: str,
    session_id: str,
    *,
    timeout: float,
) -> Dict[str, int]:
    history = _request_json(
        "GET",
        f"{base_url}/world/history?limit=1",
        timeout=timeout,
    )
    projection = _request_json(
        "GET",
        f"{base_url}/world/projection?limit=1",
        timeout=timeout,
    )
    spatial_map = _request_json(
        "GET",
        f"{base_url}/spatial/map",
        timeout=timeout,
    )
    prefetch_status = _request_json(
        "GET",
        f"{base_url}/prefetch/status/{session_id}",
        timeout=timeout,
    )
    return {
        "world_history_count": int(history.get("count", 0) or 0),
        "world_projection_count": int(projection.get("count", 0) or 0),
        "storylet_count": int(len(spatial_map.get("storylets", []) or [])),
        "prefetch_stubs_cached": int(prefetch_status.get("stubs_cached", 0) or 0),
    }


def _is_reset_clean(snapshot: Dict[str, int]) -> bool:
    return (
        int(snapshot.get("world_history_count", 0)) == 0
        and int(snapshot.get("world_projection_count", 0)) == 0
        and int(snapshot.get("storylet_count", 0)) == 0
        and int(snapshot.get("prefetch_stubs_cached", 0)) == 0
    )


def _bootstrap_session(
    base_url: str,
    session_id: str,
    world: WorldConfig,
    storylet_count: int,
    *,
    timeout: float,
) -> Dict[str, Any]:
    payload = {
        "session_id": session_id,
        "world_theme": world.theme,
        "player_role": world.role,
        "description": world.description,
        "key_elements": world.key_elements,
        "tone": world.tone,
        "storylet_count": int(storylet_count),
        "bootstrap_source": "long-run-harness",
    }
    return _request_json("POST", f"{base_url}/session/bootstrap", payload=payload, timeout=timeout)


def _get_next(
    base_url: str,
    session_id: str,
    choice_vars: Dict[str, Any] | None = None,
    *,
    timeout: float,
) -> Dict[str, Any]:
    return _request_json(
        "POST",
        f"{base_url}/next",
        payload={"session_id": session_id, "vars": choice_vars or {}},
        timeout=timeout,
    )


def _submit_action(
    base_url: str,
    session_id: str,
    action: str,
    turn: int,
    *,
    timeout: float,
) -> Dict[str, Any]:
    return _request_json(
        "POST",
        f"{base_url}/action",
        payload={"session_id": session_id, "action": action, "idempotency_key": f"longrun-{session_id}-{turn}"},
        timeout=timeout,
    )


def _await_prefetch(
    base_url: str,
    session_id: str,
    *,
    timeout: float = DEFAULT_PREFETCH_WAIT_TIMEOUT_SECONDS,
    request_timeout: float = 5.0,
) -> float:
    """Pause until the background prefetch for this session completes or times out."""
    if timeout <= 0:
        return 0.0
    start = time.perf_counter()
    while time.perf_counter() - start < timeout:
        try:
            status = _request_json(
                "GET",
                f"{base_url}/prefetch/status/{session_id}",
                timeout=max(1.0, float(request_timeout)),
            )
            if _prefetch_status_complete(status):
                return round((time.perf_counter() - start) * 1000.0, 3)
        except Exception:
            pass
        time.sleep(0.5)
    return round((time.perf_counter() - start) * 1000.0, 3)


def _prefetch_status_complete(status: Dict[str, Any]) -> bool:
    """Interpret prefetch status across legacy and current API payload shapes."""
    if "prefetch_complete" in status:
        return bool(status.get("prefetch_complete"))

    try:
        stubs_cached = int(status.get("stubs_cached", 0) or 0)
    except (TypeError, ValueError):
        stubs_cached = 0

    try:
        expires_in_seconds = int(status.get("expires_in_seconds", 0) or 0)
    except (TypeError, ValueError):
        expires_in_seconds = 0

    return (stubs_cached > 0) or (expires_in_seconds > 0)


def _resolve_prefetch_wait_timeout_seconds(*, policy: str, configured: float | None) -> float:
    if configured is not None:
        return max(0.0, float(configured))
    if policy == "strict":
        return float(DEFAULT_PREFETCH_WAIT_STRICT_TIMEOUT_SECONDS)
    if policy == "off":
        return 0.0
    return float(DEFAULT_PREFETCH_WAIT_TIMEOUT_SECONDS)


def _normalize_choices(raw_choices: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(raw_choices, list):
        return out
    for item in raw_choices:
        if isinstance(item, dict) and str(item.get("label", "")).strip():
            set_payload = item.get("set") if isinstance(item.get("set"), dict) else {}
            out.append({"label": str(item.get("label")).strip(), "set": set_payload})
    return out


def _extract_response_diagnostics(payload: Dict[str, Any]) -> Dict[str, Any]:
    raw = payload.get("diagnostics")
    if isinstance(raw, dict):
        return dict(raw)
    vars_payload = payload.get("vars")
    if isinstance(vars_payload, dict):
        embedded = vars_payload.get("_ww_diag")
        if isinstance(embedded, dict):
            return dict(embedded)
    return {}


def _load_actions_file(path: Path) -> List[str]:
    out: List[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def _dedupe_preserve_order(items: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for item in items:
        s = item.strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def build_parameter_env_overrides_from_values(
    *,
    llm_temperature: float | None = None,
    llm_max_tokens: int | None = None,
    llm_recency_penalty: float | None = None,
    llm_semantic_floor_probability: float | None = None,
) -> Dict[str, str]:
    """Map optional run-time tuning knobs to backend environment variables."""
    overrides: Dict[str, str] = {}
    if llm_temperature is not None:
        overrides["LLM_TEMPERATURE"] = f"{float(llm_temperature):.4f}"
    if llm_max_tokens is not None:
        overrides["LLM_MAX_TOKENS"] = str(int(llm_max_tokens))
    if llm_recency_penalty is not None:
        overrides["LLM_RECENCY_PENALTY"] = f"{float(llm_recency_penalty):.4f}"
    if llm_semantic_floor_probability is not None:
        overrides["LLM_SEMANTIC_FLOOR_PROBABILITY"] = f"{float(llm_semantic_floor_probability):.4f}"
    return overrides


def build_parameter_env_overrides(config: RunConfig) -> Dict[str, str]:
    """Map run-level tuning values to backend environment variables."""
    return build_parameter_env_overrides_from_values(
        llm_temperature=config.llm_temperature,
        llm_max_tokens=config.llm_max_tokens,
        llm_recency_penalty=config.llm_recency_penalty,
        llm_semantic_floor_probability=config.llm_semantic_floor_probability,
    )


def _normalize_prefix(text: str, *, prefix_chars: int) -> str:
    collapsed = " ".join(str(text or "").strip().lower().split())
    return collapsed[:prefix_chars]


def _prefix_pair_similarity(lhs_prefix: str, rhs_prefix: str) -> float:
    lhs = str(lhs_prefix or "").strip()
    rhs = str(rhs_prefix or "").strip()
    if not lhs or not rhs:
        return 0.0

    lhs_tokens = set(lhs.split())
    rhs_tokens = set(rhs.split())
    union = lhs_tokens.union(rhs_tokens)
    token_jaccard = (len(lhs_tokens.intersection(rhs_tokens)) / float(len(union))) if union else 0.0

    lcp_chars = 0
    for lhs_char, rhs_char in zip(lhs, rhs):
        if lhs_char != rhs_char:
            break
        lcp_chars += 1
    lcp_ratio = lcp_chars / float(max(len(lhs), len(rhs)))
    return max(token_jaccard, lcp_ratio)


def _exact_prefix_repetition_metrics(
    turns: Sequence[TurnRecord],
    *,
    prefix_chars: int = 80,
    soft_match_threshold: float = PREFIX_SOFT_MATCH_THRESHOLD,
) -> Dict[str, Any]:
    prefixes = [_normalize_prefix(turn.narrative, prefix_chars=prefix_chars) for turn in turns if str(turn.narrative or "").strip()]
    if len(prefixes) < 2:
        return {
            "prefix_chars": float(prefix_chars),
            "prefix_non_empty_turns": float(len(prefixes)),
            "prefix_unique_count": float(len(set(prefixes))),
            "prefix_duplicate_count": float(0),
            "soft_match_threshold": float(soft_match_threshold),
            "comparisons": 0.0,
            "exact_prefix_matches": 0.0,
            "exact_prefix_match_rate": 0.0,
            "prefix_soft_matches": 0.0,
            "prefix_soft_match_rate": 0.0,
            "prefix_similarity_avg": 0.0,
            "prefix_similarity_p95": 0.0,
            "prefix_max_similarity": 0.0,
            "prefix_top_reused": [],
        }

    comparisons = 0
    matches = 0
    soft_matches = 0
    similarities: List[float] = []
    for idx in range(1, len(prefixes)):
        comparisons += 1
        if prefixes[idx] == prefixes[idx - 1]:
            matches += 1
        similarity = _prefix_pair_similarity(prefixes[idx], prefixes[idx - 1])
        similarities.append(similarity)
        if similarity >= float(soft_match_threshold):
            soft_matches += 1

    rate = matches / float(comparisons) if comparisons else 0.0
    soft_rate = soft_matches / float(comparisons) if comparisons else 0.0
    unique_prefix_count = len(set(prefixes))
    duplicate_prefix_count = max(0, len(prefixes) - unique_prefix_count)
    prefix_counter = Counter(prefixes)
    top_reused = [{"prefix": prefix_text, "count": int(count)} for prefix_text, count in prefix_counter.most_common(5) if int(count) > 1]
    return {
        "prefix_chars": float(prefix_chars),
        "prefix_non_empty_turns": float(len(prefixes)),
        "prefix_unique_count": float(unique_prefix_count),
        "prefix_duplicate_count": float(duplicate_prefix_count),
        "soft_match_threshold": float(soft_match_threshold),
        "comparisons": float(comparisons),
        "exact_prefix_matches": float(matches),
        "exact_prefix_match_rate": float(rate),
        "prefix_soft_matches": float(soft_matches),
        "prefix_soft_match_rate": float(soft_rate),
        "prefix_similarity_avg": (sum(similarities) / float(len(similarities))) if similarities else 0.0,
        "prefix_similarity_p95": _percentile(similarities, 0.95) if similarities else 0.0,
        "prefix_max_similarity": max(similarities) if similarities else 0.0,
        "prefix_top_reused": top_reused,
    }


def _extract_motif_tokens_from_text(
    text: str,
    *,
    min_token_length: int = MOTIF_MIN_TOKEN_LENGTH,
    max_tokens_per_turn: int = MOTIF_MAX_TOKENS_PER_TURN,
) -> List[str]:
    collapsed = " ".join(str(text or "").strip().lower().split())
    if not collapsed:
        return []
    output: List[str] = []
    seen: set[str] = set()
    for raw_token in _MOTIF_TOKEN_PATTERN.findall(collapsed):
        token = raw_token.strip("'")
        if not token:
            continue
        if len(token) < int(min_token_length):
            continue
        if token in MOTIF_STOPWORDS:
            continue
        if token.isdigit():
            continue
        if token in seen:
            continue
        seen.add(token)
        output.append(token)
        if len(output) >= int(max_tokens_per_turn):
            break
    return output


def _motif_reuse_metrics(turns: Sequence[TurnRecord]) -> Dict[str, Any]:
    motif_counter: Counter[str] = Counter()
    all_seen: set[str] = set()
    turns_with_tokens = 0
    total_tokens = 0
    reused_tokens = 0
    per_turn_overlap_rates: List[float] = []

    for turn in turns:
        turn_tokens = set(_extract_motif_tokens_from_text(turn.narrative))
        if not turn_tokens:
            continue
        turns_with_tokens += 1
        total_tokens += len(turn_tokens)
        overlap_count = len(turn_tokens.intersection(all_seen))
        reused_tokens += overlap_count
        per_turn_overlap_rates.append(overlap_count / float(len(turn_tokens)))
        motif_counter.update(turn_tokens)
        all_seen.update(turn_tokens)

    if total_tokens <= 0:
        reuse_rate = 0.0
        novelty_rate = 0.0
    else:
        reuse_rate = reused_tokens / float(total_tokens)
        novelty_rate = 1.0 - reuse_rate

    top_reused = [{"motif": motif, "count": int(count)} for motif, count in motif_counter.most_common(10) if int(count) > 1]

    return {
        "motif_turns_with_tokens": float(turns_with_tokens),
        "motif_total_tokens": float(total_tokens),
        "motif_unique_tokens": float(len(all_seen)),
        "motif_overlap_count": float(reused_tokens),
        "motif_reused_tokens": float(reused_tokens),
        "motif_reuse_rate": float(reuse_rate),
        "motif_novelty_rate": float(novelty_rate),
        "motif_turn_overlap_rate_avg": (sum(per_turn_overlap_rates) / float(len(per_turn_overlap_rates))) if per_turn_overlap_rates else 0.0,
        "motif_top_reused": top_reused,
    }


def _normalize_clarity_level(value: Any) -> str:
    candidate = str(value or "").strip().lower()
    if candidate in CLARITY_LEVEL_ORDER:
        return candidate
    return "unknown"


def _projection_and_clarity_metrics(turns: Sequence[TurnRecord]) -> Dict[str, Any]:
    clarity_counter: Counter[str] = Counter()
    projection_stub_count = 0
    projection_opportunities = 0
    projection_hits = 0
    projection_waste = 0
    projection_veto = 0

    for turn in turns:
        diag = turn.diagnostics if isinstance(turn.diagnostics, dict) else {}
        clarity_level = _normalize_clarity_level(diag.get("clarity_level", diag.get("scene_clarity_level", "unknown")))
        clarity_counter[clarity_level] += 1

        if not bool(diag.get("projection_seeded_narration_enabled")):
            continue

        projection_opportunities += 1
        projection_seed_used = bool(diag.get("projection_seed_used"))
        has_projection_stub = projection_seed_used or (diag.get("projection_seed_storylet_id") is not None)

        if has_projection_stub:
            projection_stub_count += 1
        if projection_seed_used:
            projection_hits += 1
        else:
            projection_waste += 1

        fallback_reason = str(diag.get("fallback_reason", "") or "").strip().lower()
        if fallback_reason in {"projection_veto", "projection_vetoed"}:
            projection_veto += 1
        elif projection_seed_used and fallback_reason not in {"", "none"}:
            projection_veto += 1

    hit_rate = (projection_hits / float(projection_opportunities)) if projection_opportunities else 0.0
    waste_rate = (projection_waste / float(projection_opportunities)) if projection_opportunities else 0.0
    veto_rate = (projection_veto / float(projection_opportunities)) if projection_opportunities else 0.0
    clarity_distribution = {level: int(clarity_counter.get(level, 0)) for level in CLARITY_LEVEL_ORDER}
    return {
        "projection_stub_count": float(projection_stub_count),
        "projection_hit_rate": float(hit_rate),
        "projection_waste_rate": float(waste_rate),
        "projection_veto_rate": float(veto_rate),
        "clarity_level_distribution": clarity_distribution,
    }


def _percentile(values: Sequence[float], q: float) -> float:
    samples = sorted(float(v) for v in values)
    if not samples:
        return 0.0
    clamped_q = max(0.0, min(1.0, float(q)))
    if len(samples) == 1:
        return samples[0]
    position = clamped_q * (len(samples) - 1)
    lower = int(position)
    upper = min(lower + 1, len(samples) - 1)
    fraction = position - lower
    return (samples[lower] * (1.0 - fraction)) + (samples[upper] * fraction)


def _prompt_text(label: str, default: str) -> str:
    raw = input(f"{label} [{default}]: ").strip()
    return raw or default


def _prompt_yes_no(label: str, default: bool) -> bool:
    marker = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{label} ({marker}): ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Please enter y or n.")


def _prompt_int(label: str, default: int, minimum: int) -> int:
    while True:
        raw = input(f"{label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("Enter a whole number.")
            continue
        if value < minimum:
            print(f"Enter >= {minimum}.")
            continue
        return value


def _prompt_float(label: str, default: float, minimum: float, maximum: float) -> float:
    while True:
        raw = input(f"{label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = float(raw)
        except ValueError:
            print("Enter a numeric value.")
            continue
        if value < minimum or value > maximum:
            print(f"Enter between {minimum} and {maximum}.")
            continue
        return value


def _prompt_select(label: str, options: Sequence[Tuple[str, str]], default_value: str) -> str:
    option_values = {v for v, _ in options}
    if default_value not in option_values:
        default_value = options[0][0]
    print(label)
    for idx, (value, text) in enumerate(options, start=1):
        marker = " (default)" if value == default_value else ""
        print(f"  {idx}. {text}{marker}")
    while True:
        raw = input(f"Select 1-{len(options)} or value [{default_value}]: ").strip()
        if not raw:
            return default_value
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1][0]
        if raw in option_values:
            return raw
        print("Invalid selection.")


def _interactive_enabled(args: argparse.Namespace) -> bool:
    if args.non_interactive:
        return False
    if args.interactive:
        return True
    return sys.stdin.isatty() and sys.stdout.isatty()


def _resolve_world_config(args: argparse.Namespace, interactive: bool) -> WorldConfig | None:
    if args.skip_bootstrap:
        return None

    scenario_keys = sorted(SCENARIOS.keys())
    scenario_choice = args.scenario
    if scenario_choice is None:
        if interactive:
            options = [(k, f"{k}: {SCENARIOS[k]['title']}") for k in scenario_keys]
            options.append(("custom", "custom: provide your own setup"))
            scenario_choice = _prompt_select("Choose scenario preset:", options, "cyberpunk")
        else:
            scenario_choice = "cyberpunk"

    if scenario_choice == "custom":
        title = "Custom Scenario"
        theme = "custom narrative world"
        roles = ["adventurer"]
        description = "A world with conflicting factions and unresolved tensions."
        key_elements = ["rumors", "resource pressure", "hidden agenda"]
        tone = "dramatic"
    else:
        scenario = SCENARIOS[scenario_choice]
        title = str(scenario["title"])
        theme = str(scenario["theme"])
        roles = [str(item) for item in scenario.get("roles", []) if str(item).strip()]
        description = str(scenario["description"])
        key_elements = [str(item) for item in scenario.get("key_elements", []) if str(item).strip()]
        tone = str(scenario["tone"])

    role_default = roles[0] if roles else "adventurer"
    role = str(args.role).strip() if args.role else role_default
    if interactive and not args.role:
        role_options = [(r, r) for r in roles]
        role_options.append(("custom", "custom role"))
        selected_role = _prompt_select("Choose character role:", role_options, role_default)
        role = _prompt_text("Custom role", role_default) if selected_role == "custom" else selected_role

    if args.theme:
        theme = str(args.theme).strip()
    if args.description:
        description = str(args.description).strip()
    if args.tone:
        tone = str(args.tone).strip()
    if args.key_elements:
        key_elements = _split_csv(args.key_elements)

    if interactive:
        title = _prompt_text("Scenario title", title).strip()
        theme = _prompt_text("World theme", theme).strip()
        role = _prompt_text("Player role", role).strip()
        tone = _prompt_text("World tone", tone).strip()
        description = _prompt_text("World description", description).strip()
        keys_default = ", ".join(key_elements) if key_elements else "risk, pressure, rumor network"
        keys_input = _prompt_text("Key elements (comma-separated)", keys_default)
        parsed = _split_csv(keys_input)
        if parsed:
            key_elements = parsed

    if not key_elements:
        key_elements = ["risk", "tradeoff", "complication"]

    return WorldConfig(
        scenario_id=str(scenario_choice or "custom"),
        scenario_title=title,
        theme=theme or "narrative world",
        role=role or role_default,
        description=description or "A world with unresolved conflict.",
        key_elements=key_elements,
        tone=tone or "dramatic",
    )


def _resolve_run_config(args: argparse.Namespace) -> RunConfig:
    interactive = _interactive_enabled(args)
    if interactive and not (sys.stdin.isatty() and sys.stdout.isatty()):
        interactive = False

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    session_default = f"longrun-{timestamp.lower()}"

    base_url = str(args.base_url or DEFAULT_BASE_URL).rstrip("/")
    session_id = str(args.session_id or "").strip() or session_default
    turns = int(args.turns if args.turns is not None else DEFAULT_TURNS)
    seed = int(args.seed if args.seed is not None else DEFAULT_SEED)
    storylet_count = int(args.storylet_count if args.storylet_count is not None else DEFAULT_STORYLET_COUNT)
    request_timeout_seconds = float(args.request_timeout_seconds) if args.request_timeout_seconds is not None else float(DEFAULT_REQUEST_TIMEOUT_SECONDS)
    prefetch_wait_policy = str(args.prefetch_wait_policy or "bounded").strip().lower()
    prefetch_wait_timeout_seconds = _resolve_prefetch_wait_timeout_seconds(
        policy=prefetch_wait_policy,
        configured=args.prefetch_wait_timeout_seconds,
    )
    verify_clean_reset = bool(args.verify_clean_reset)
    diversity_every = int(args.diversity_every if args.diversity_every is not None else 8)
    diversity_chance = float(args.diversity_chance if args.diversity_chance is not None else 0.15)
    llm_temperature = float(args.llm_temperature) if args.llm_temperature is not None else None
    llm_max_tokens = int(args.llm_max_tokens) if args.llm_max_tokens is not None else None
    llm_recency_penalty = float(args.llm_recency_penalty) if args.llm_recency_penalty is not None else None
    llm_semantic_floor_probability = float(args.llm_semantic_floor_probability) if args.llm_semantic_floor_probability is not None else None
    switch_model = bool(args.switch_model or str(args.model_id or "").strip())
    model_id = str(args.model_id or "").strip()
    hard_reset = bool(args.hard_reset)
    skip_bootstrap = bool(args.skip_bootstrap)

    if interactive:
        print("")
        print("Long-Run Harness Setup")
        print("----------------------")
        base_url = _prompt_text("Base URL", base_url).rstrip("/")
        session_id = _prompt_text("Session ID", session_id)
        turns = _prompt_int("Turns", turns, minimum=1)
        seed = _prompt_int("Seed", seed, minimum=0)
        storylet_count = _prompt_int("Storylet count", storylet_count, minimum=5)
        request_timeout_seconds = _prompt_float(
            "Request timeout seconds",
            request_timeout_seconds,
            5.0,
            900.0,
        )
        prefetch_wait_policy = _prompt_select(
            "Prefetch wait policy:",
            [
                ("bounded", "bounded: short wait to capture best-effort prefetch"),
                ("off", "off: skip prefetch waiting"),
                ("strict", "strict: wait up to full strict timeout"),
            ],
            prefetch_wait_policy,
        )
        prefetch_wait_timeout_seconds = _prompt_float(
            "Prefetch wait timeout seconds",
            prefetch_wait_timeout_seconds,
            0.0,
            900.0,
        )
        diversity_every = _prompt_int("Inject diversity every N turns (0 disables cadence)", diversity_every, minimum=0)
        diversity_chance = _prompt_float("Per-turn diversity chance", diversity_chance, 0.0, 1.0)
        if not hard_reset:
            hard_reset = _prompt_yes_no("Run /api/dev/hard-reset first?", False)
        if not skip_bootstrap:
            skip_bootstrap = _prompt_yes_no("Skip bootstrap and continue existing session?", False)
        if not switch_model:
            switch_model = _prompt_yes_no("Switch model before run?", False)
        if switch_model and not model_id:
            model_id = _prompt_text("Model ID", "openai/gpt-4o-mini")

    if turns < 1:
        raise ValueError("--turns must be >= 1")
    if storylet_count < 5:
        raise ValueError("--storylet-count must be >= 5")
    if request_timeout_seconds < 5.0:
        raise ValueError("--request-timeout-seconds must be >= 5")
    if prefetch_wait_policy not in PREFETCH_WAIT_POLICIES:
        raise ValueError(f"--prefetch-wait-policy must be one of {PREFETCH_WAIT_POLICIES}")
    if prefetch_wait_timeout_seconds < 0.0:
        raise ValueError("--prefetch-wait-timeout-seconds must be >= 0")
    if diversity_every < 0:
        raise ValueError("--diversity-every must be >= 0")
    if not 0.0 <= diversity_chance <= 1.0:
        raise ValueError("--diversity-chance must be in [0, 1]")
    if llm_temperature is not None and not 0.0 <= llm_temperature <= 2.0:
        raise ValueError("--llm-temperature must be in [0, 2]")
    if llm_max_tokens is not None and llm_max_tokens < 1:
        raise ValueError("--llm-max-tokens must be >= 1")
    if llm_recency_penalty is not None and not 0.0 <= llm_recency_penalty <= 1.0:
        raise ValueError("--llm-recency-penalty must be in [0, 1]")
    if llm_semantic_floor_probability is not None and not 0.0 <= llm_semantic_floor_probability <= 1.0:
        raise ValueError("--llm-semantic-floor-probability must be in [0, 1]")
    if switch_model and not model_id:
        raise ValueError("model ID is required when switching model")

    world = _resolve_world_config(args, interactive) if not skip_bootstrap else None

    return RunConfig(
        base_url=base_url,
        session_id=session_id,
        turns=turns,
        seed=seed,
        storylet_count=storylet_count,
        switch_model=switch_model,
        model_id=model_id,
        hard_reset=hard_reset,
        skip_bootstrap=skip_bootstrap,
        diversity_every=diversity_every,
        diversity_chance=diversity_chance,
        output_dir=Path(args.output_dir),
        world=world,
        request_timeout_seconds=request_timeout_seconds,
        prefetch_wait_policy=prefetch_wait_policy,
        prefetch_wait_timeout_seconds=prefetch_wait_timeout_seconds,
        verify_clean_reset=verify_clean_reset,
        llm_temperature=llm_temperature,
        llm_max_tokens=llm_max_tokens,
        llm_recency_penalty=llm_recency_penalty,
        llm_semantic_floor_probability=llm_semantic_floor_probability,
    )


def _pick_action(
    rng: random.Random,
    turn: int,
    choices: List[Dict[str, Any]],
    diversity_actions: List[str],
    diversity_every: int,
    diversity_chance: float,
) -> Tuple[str, str, Dict[str, Any]]:
    inject = False
    if diversity_actions:
        if diversity_every > 0 and turn % diversity_every == 0:
            inject = True
        elif diversity_chance > 0 and rng.random() < diversity_chance:
            inject = True
    if inject:
        return rng.choice(diversity_actions), "diversity_freeform", {}

    valid_choices = [c for c in choices if str(c.get("label", "")).strip()]
    if valid_choices:
        choice = rng.choice(valid_choices)
        return str(choice["label"]).strip(), "choice_button", choice.get("set", {})
    if diversity_actions:
        return rng.choice(diversity_actions), "diversity_fallback", {}
    return "Continue", "continue_fallback", {}


def _render_markdown_report(run_payload: Dict[str, Any], diversity_actions: List[str]) -> str:
    turns = run_payload.get("turns", [])
    summary = run_payload.get("summary", {})
    world = run_payload.get("world", {})

    lines: List[str] = [
        "# Long-Run Random Choice Playtest",
        "",
        f"- Session ID: `{run_payload.get('session_id', '')}`",
        f"- Timestamp UTC: `{run_payload.get('timestamp_utc', '')}`",
        f"- Base URL: `{run_payload.get('base_url', '')}`",
        f"- Scenario ID: `{world.get('scenario_id', 'n/a')}`",
        f"- Scenario Title: `{world.get('scenario_title', 'n/a')}`",
        f"- Theme: `{world.get('theme', 'n/a')}`",
        f"- Role: `{world.get('role', 'n/a')}`",
        f"- Tone: `{world.get('tone', 'n/a')}`",
        f"- Turns Requested: `{run_payload.get('turns_requested', 0)}`",
        f"- Turns Completed: `{summary.get('turns_completed', 0)}`",
        f"- Seed: `{run_payload.get('seed', 0)}`",
        f"- Prefetch Wait Policy: `{run_payload.get('prefetch_wait_policy', 'bounded')}`",
        f"- Prefetch Wait Timeout Seconds: `{run_payload.get('prefetch_wait_timeout_seconds', 0.0)}`",
        f"- Diversity Injections: `{summary.get('diversity_turns', 0)}`",
        f"- Choice Button Presses: `{summary.get('choice_turns', 0)}`",
        f"- Plausible Responses: `{summary.get('plausible_true_count', 0)}`",
        f"- Request Latency Avg (ms): `{summary.get('request_latency_ms_avg', summary.get('latency_ms_avg', 0.0))}`",
        f"- Prefetch Wait Avg (ms): `{summary.get('prefetch_wait_ms_avg', 0.0)}`",
        f"- Setup Total (ms): `{summary.get('setup_total_ms', 0.0)}`",
        f"- Turn Wallclock Avg (ms): `{summary.get('turn_wallclock_ms_avg', 0.0)}`",
        f"- Prefix Exact Match Rate: `{summary.get('exact_prefix_match_rate', 0.0)}`",
        f"- Prefix Soft Match Rate: `{summary.get('prefix_soft_match_rate', summary.get('exact_prefix_match_rate', 0.0))}`",
        f"- Prefix Similarity Avg: `{summary.get('prefix_similarity_avg', 0.0)}`",
        f"- Motif Reuse Rate: `{summary.get('motif_reuse_rate', 0.0)}`",
        f"- Motif Overlap Count: `{summary.get('motif_overlap_count', 0)}`",
        f"- Motif Novelty Rate: `{summary.get('motif_novelty_rate', 0.0)}`",
        f"- Projection Stub Count: `{summary.get('projection_stub_count', 0)}`",
        f"- Projection Hit Rate: `{summary.get('projection_hit_rate', 0.0)}`",
        f"- Projection Waste Rate: `{summary.get('projection_waste_rate', 0.0)}`",
        f"- Projection Veto Rate: `{summary.get('projection_veto_rate', 0.0)}`",
        f"- Clarity Distribution: `{json.dumps(summary.get('clarity_level_distribution', {}), sort_keys=True)}`",
        "",
        "## Diversity Freeform Actions",
        "",
    ]
    for action in diversity_actions:
        lines.append(f"- {action}")
    lines.append("")
    top_reused = summary.get("motif_top_reused", [])
    if isinstance(top_reused, list):
        lines.extend(["## Motif Reuse Snapshot", ""])
        if top_reused:
            for item in top_reused:
                if isinstance(item, dict):
                    motif = str(item.get("motif", "")).strip()
                    count = int(item.get("count", 0) or 0)
                    if motif:
                        lines.append(f"- `{motif}`: {count}")
        else:
            lines.append("- (none)")
        lines.append("")

    for turn in turns:
        turn_no = int(turn.get("turn", 0))
        lines.extend(
            [
                f"## Turn {turn_no}",
                "",
                f"- Phase: `{turn.get('phase', 'unknown')}`",
                f"- Action Source: `{turn.get('action_source', 'n/a')}`",
            ]
        )
        action_sent = str(turn.get("action_sent", "")).strip()
        ack_line = str(turn.get("ack_line", "")).strip()
        if action_sent:
            lines.append(f"- Action: {action_sent}")
        if ack_line:
            lines.append(f"- Ack: {ack_line}")
        lines.extend(
            [
                "",
                "**Narrative**",
                "",
                str(turn.get("narrative", "")).strip(),
                "",
                "**Choices Presented**",
                "",
            ]
        )
        choices = _normalize_choices(turn.get("choices", []))
        if choices:
            for choice in choices:
                lines.append(f"- {choice['label']}")
        else:
            lines.append("- (none)")
        lines.append("")
        lines.append(f"**State Changes:** `{json.dumps(turn.get('state_changes', {}), ensure_ascii=True)}`")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=("Run a long autonomous playtest with random choice presses and periodic " "diversity freeform actions. Defaults to guided interactive setup."))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--turns", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--scenario", default=None, choices=sorted(SCENARIOS.keys()) + ["custom"])
    parser.add_argument("--role", default=None)
    parser.add_argument("--theme", default=None)
    parser.add_argument("--description", default=None)
    parser.add_argument("--tone", default=None)
    parser.add_argument("--key-elements", default=None, help="Comma-separated list")
    parser.add_argument("--storylet-count", type=int, default=None)
    parser.add_argument("--switch-model", action="store_true")
    parser.add_argument("--model-id", default="")
    parser.add_argument("--hard-reset", action="store_true")
    parser.add_argument(
        "--verify-clean-reset",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="After /dev/hard-reset, verify world history/projection/storylets/prefetch are empty.",
    )
    parser.add_argument("--skip-bootstrap", action="store_true")
    parser.add_argument("--request-timeout-seconds", type=float, default=None)
    parser.add_argument(
        "--prefetch-wait-policy",
        choices=PREFETCH_WAIT_POLICIES,
        default="bounded",
        help="Post-turn prefetch wait strategy: off|bounded|strict",
    )
    parser.add_argument("--prefetch-wait-timeout-seconds", type=float, default=None)
    parser.add_argument("--diversity-every", type=int, default=None)
    parser.add_argument("--diversity-chance", type=float, default=None)
    parser.add_argument("--llm-temperature", type=float, default=None)
    parser.add_argument("--llm-max-tokens", type=int, default=None)
    parser.add_argument("--llm-recency-penalty", type=float, default=None)
    parser.add_argument("--llm-semantic-floor-probability", type=float, default=None)
    parser.add_argument("--diversity-actions-file", type=Path, default=None)
    parser.add_argument("--add-diversity-action", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--print-diversity-actions", action="store_true")
    parser.add_argument("--interactive", action="store_true", help="Force interactive prompts")
    parser.add_argument("--non-interactive", action="store_true", help="Disable interactive prompts")
    return parser.parse_args()


def _world_payload(world: WorldConfig | None) -> Dict[str, Any]:
    if world is None:
        return {
            "scenario_id": "existing-session",
            "scenario_title": "Existing Session State",
            "theme": "",
            "role": "",
            "description": "",
            "key_elements": [],
            "tone": "",
        }
    return asdict(world)


def _timed_request(call: Callable[[], Dict[str, Any]]) -> Tuple[Dict[str, Any] | None, float, str]:
    started = time.perf_counter()
    try:
        payload = call()
        return payload, round((time.perf_counter() - started) * 1000.0, 3), ""
    except Exception as exc:
        return None, round((time.perf_counter() - started) * 1000.0, 3), str(exc)


def run_long_playtest(
    config: RunConfig,
    diversity_actions: Sequence[str],
    *,
    continue_on_error: bool = False,
    progress: Callable[[str], None] | None = print,
) -> Dict[str, Any]:
    rng = random.Random(config.seed)
    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ").lower()
    run_started = time.perf_counter()
    setup_started = time.perf_counter()
    turns: List[TurnRecord] = []
    errors: List[str] = []
    prefetch_wait_call_count = 0
    switch_model_ms = 0.0
    hard_reset_ms = 0.0
    bootstrap_ms = 0.0
    clean_reset_verify_ms = 0.0
    clean_reset_snapshot: Dict[str, int] = {}
    clean_reset_verified = False
    bootstrap_result: Dict[str, Any] = {}
    bootstrap_gate_failed = False

    def emit(message: str) -> None:
        if progress is not None:
            progress(message)

    def record_setup_error(label: str, exc: Exception) -> None:
        detail = f"{label}: {exc}"
        errors.append(detail)
        emit(f"Run setup error: {detail}")
        if not continue_on_error:
            raise RuntimeError(detail) from exc

    if config.switch_model:
        step_started = time.perf_counter()
        try:
            model_result = _switch_model(
                config.base_url,
                config.model_id,
                timeout=config.request_timeout_seconds,
            )
            emit(f"Model switched to: {model_result.get('current_model', config.model_id)}")
        except Exception as exc:
            record_setup_error("switch_model", exc)
        finally:
            switch_model_ms = round((time.perf_counter() - step_started) * 1000.0, 3)
    if config.hard_reset:
        step_started = time.perf_counter()
        try:
            reset_result = _hard_reset(
                config.base_url,
                timeout=config.request_timeout_seconds,
            )
            emit(str(reset_result.get("message", "Hard reset complete.")))
            if config.verify_clean_reset:
                clean_started = time.perf_counter()
                clean_reset_snapshot = _fetch_reset_clean_snapshot(
                    config.base_url,
                    config.session_id,
                    timeout=config.request_timeout_seconds,
                )
                clean_reset_verify_ms = round((time.perf_counter() - clean_started) * 1000.0, 3)
                clean_reset_verified = _is_reset_clean(clean_reset_snapshot)
                if clean_reset_verified:
                    emit(
                        "ALL CLEAN: "
                        f"history={clean_reset_snapshot.get('world_history_count', 0)} "
                        f"projection={clean_reset_snapshot.get('world_projection_count', 0)} "
                        f"storylets={clean_reset_snapshot.get('storylet_count', 0)} "
                        f"prefetch={clean_reset_snapshot.get('prefetch_stubs_cached', 0)}"
                    )
                else:
                    raise RuntimeError(
                        "reset verification failed: "
                        f"{json.dumps(clean_reset_snapshot, sort_keys=True)}"
                    )
        except Exception as exc:
            record_setup_error("hard_reset", exc)
        finally:
            hard_reset_ms = round((time.perf_counter() - step_started) * 1000.0, 3)
    if not config.skip_bootstrap and config.world is not None:
        step_started = time.perf_counter()
        try:
            bootstrap_result = _bootstrap_session(
                config.base_url,
                config.session_id,
                config.world,
                config.storylet_count,
                timeout=config.request_timeout_seconds,
            )
            bootstrap_state = str(bootstrap_result.get("bootstrap_state", "completed")).strip().lower()
            try:
                storylets_created = int(bootstrap_result.get("storylets_created", 0) or 0)
            except (TypeError, ValueError):
                storylets_created = 0
            if storylets_created <= 0:
                raise RuntimeError("bootstrap success gate failed: storylets_created=0")
            if bootstrap_state not in {"completed", "ok", "success"}:
                raise RuntimeError(f"bootstrap success gate failed: bootstrap_state={bootstrap_state or 'unknown'}")
            emit("Bootstrap complete: " f"{bootstrap_result.get('storylets_created', 0)} storylets, " f"theme={bootstrap_result.get('theme', 'unknown')}")
        except Exception as exc:
            bootstrap_gate_failed = True
            record_setup_error("bootstrap", exc)
        finally:
            bootstrap_ms = round((time.perf_counter() - step_started) * 1000.0, 3)

    setup_total_ms = round((time.perf_counter() - setup_started) * 1000.0, 3)
    if bootstrap_gate_failed:
        emit("Skipping turns: bootstrap success gate failed.")

    current_choices: List[Dict[str, Any]] = []
    if (not errors or continue_on_error) and not bootstrap_gate_failed:
        first_payload, first_duration_ms, first_error = _timed_request(
            lambda: _get_next(
                config.base_url,
                config.session_id,
                timeout=config.request_timeout_seconds,
            )
        )
        if first_error:
            turns.append(
                TurnRecord(
                    turn=1,
                    phase="next",
                    action_source="initial_scene_error",
                    action_sent="",
                    narrative="",
                    ack_line="",
                    plausible=False,
                    choices=[],
                    state_changes={},
                    vars={},
                    diagnostics={},
                    request_duration_ms=first_duration_ms,
                    prefetch_wait_duration_ms=0.0,
                    turn_duration_ms=first_duration_ms,
                    request_status="error",
                    request_error=first_error,
                )
            )
            errors.append(f"turn 1 next failed: {first_error}")
            if not continue_on_error:
                raise RuntimeError(first_error)
        else:
            assert first_payload is not None
            first_choices = _normalize_choices(first_payload.get("choices", []))
            first_vars = first_payload.get("vars", {}) if isinstance(first_payload.get("vars"), dict) else {}
            first_diag = _extract_response_diagnostics(first_payload)
            turns.append(
                TurnRecord(
                    turn=1,
                    phase="next",
                    action_source="initial_scene",
                    action_sent="",
                    narrative=str(first_payload.get("text", "")),
                    ack_line="",
                    plausible=True,
                    choices=first_choices,
                    state_changes={},
                    vars=first_vars,
                    diagnostics=first_diag,
                    request_duration_ms=first_duration_ms,
                    prefetch_wait_duration_ms=0.0,
                    turn_duration_ms=first_duration_ms,
                    request_status="ok",
                    request_error="",
                )
            )
            current_choices = first_choices
            emit(f"Turn 1 loaded. Choices: {len(first_choices)}")
            now_blurb = str(first_payload.get("text", ""))
            if len(now_blurb) > 100:
                now_blurb = now_blurb[:100] + "..."
            emit(f"Now: {now_blurb}")
            emit("Chosen action: (Initial scene)")

    for turn_no in range(2, int(config.turns) + 1):
        if turns and turns[-1].request_status == "error":
            break
        turn_started = time.perf_counter()

        action_text, action_source, choice_vars = _pick_action(
            rng,
            turn_no,
            current_choices,
            list(diversity_actions),
            config.diversity_every,
            config.diversity_chance,
        )

        if action_source == "choice_button":
            payload, request_duration_ms, request_error = _timed_request(
                lambda: _get_next(
                    config.base_url,
                    config.session_id,
                    choice_vars,
                    timeout=config.request_timeout_seconds,
                )
            )
            phase = "next"
        else:
            payload, request_duration_ms, request_error = _timed_request(
                lambda: _submit_action(
                    config.base_url,
                    config.session_id,
                    action_text,
                    turn_no,
                    timeout=config.request_timeout_seconds,
                )
            )
            phase = "action"

        if request_error:
            turns.append(
                TurnRecord(
                    turn=turn_no,
                    phase=phase,
                    action_source=action_source,
                    action_sent=action_text,
                    narrative="",
                    ack_line="",
                    plausible=False,
                    choices=[],
                    state_changes={},
                    vars={},
                    diagnostics={},
                    request_duration_ms=request_duration_ms,
                    prefetch_wait_duration_ms=0.0,
                    turn_duration_ms=round((time.perf_counter() - turn_started) * 1000.0, 3),
                    request_status="error",
                    request_error=request_error,
                )
            )
            errors.append(f"turn {turn_no} {phase} failed: {request_error}")
            emit(f"Turn {turn_no}/{config.turns}: source={action_source}, request failed")
            if not continue_on_error:
                raise RuntimeError(request_error)
            break

        assert payload is not None
        next_choices = _normalize_choices(payload.get("choices", []))
        next_vars = payload.get("vars", {}) if isinstance(payload.get("vars"), dict) else {}
        state_changes = payload.get("state_changes", {}) if isinstance(payload.get("state_changes"), dict) else {}
        next_diag = _extract_response_diagnostics(payload)
        turns.append(
            TurnRecord(
                turn=turn_no,
                phase=phase,
                action_source=action_source,
                action_sent=action_text,
                narrative=str(payload.get("narrative", payload.get("text", ""))),
                ack_line=str(payload.get("ack_line", "")),
                plausible=bool(payload.get("plausible", True)),
                choices=next_choices,
                state_changes=state_changes,
                vars=next_vars,
                diagnostics=next_diag,
                request_duration_ms=request_duration_ms,
                prefetch_wait_duration_ms=0.0,
                turn_duration_ms=0.0,
                request_status="ok",
                request_error="",
            )
        )
        current_choices = next_choices
        emit(f"Turn {turn_no}/{config.turns}: source={action_source}, choices_returned={len(next_choices)}")
        now_blurb = str(payload.get("narrative", payload.get("text", "")))
        if len(now_blurb) > 100:
            now_blurb = now_blurb[:100] + "..."
        emit(f"Now: {now_blurb}")
        emit(f"Chosen action: {action_text}")

        prefetch_wait_duration_ms = 0.0
        if config.prefetch_wait_policy != "off":
            prefetch_wait_call_count += 1
            prefetch_wait_duration_ms = _await_prefetch(
                config.base_url,
                config.session_id,
                timeout=config.prefetch_wait_timeout_seconds,
                request_timeout=min(5.0, config.request_timeout_seconds),
            )
        turns[-1].prefetch_wait_duration_ms = prefetch_wait_duration_ms
        turns[-1].turn_duration_ms = round((time.perf_counter() - turn_started) * 1000.0, 3)

    request_durations = [float(turn.request_duration_ms) for turn in turns if float(turn.request_duration_ms) > 0.0]
    prefetch_wait_durations = [float(turn.prefetch_wait_duration_ms) for turn in turns if float(turn.prefetch_wait_duration_ms) > 0.0]
    turn_durations = [float(turn.turn_duration_ms) for turn in turns if float(turn.turn_duration_ms) > 0.0]
    failed_request_count = sum(1 for turn in turns if turn.request_status == "error")
    request_count = len(turns)
    prefix_metrics = _exact_prefix_repetition_metrics(turns)
    motif_metrics = _motif_reuse_metrics(turns)
    projection_metrics = _projection_and_clarity_metrics(turns)

    failure_rate = (failed_request_count / float(request_count)) if request_count else (1.0 if errors else 0.0)
    request_latency_ms_avg = round(sum(request_durations) / float(len(request_durations)), 3) if request_durations else 0.0
    request_latency_ms_p95 = round(_percentile(request_durations, 0.95), 3) if request_durations else 0.0
    prefetch_wait_ms_total = round(sum(prefetch_wait_durations), 3) if prefetch_wait_durations else 0.0
    prefetch_wait_ms_avg = round(sum(prefetch_wait_durations) / float(len(prefetch_wait_durations)), 3) if prefetch_wait_durations else 0.0
    prefetch_wait_ms_p95 = round(_percentile(prefetch_wait_durations, 0.95), 3) if prefetch_wait_durations else 0.0
    turn_wallclock_ms_avg = round(sum(turn_durations) / float(len(turn_durations)), 3) if turn_durations else 0.0
    turn_wallclock_ms_p95 = round(_percentile(turn_durations, 0.95), 3) if turn_durations else 0.0
    elapsed_ms = round((time.perf_counter() - run_started) * 1000.0, 3)
    harness_overhead_ms_total = round(max(0.0, elapsed_ms - sum(request_durations)), 3)
    non_setup_non_prefetch_overhead_ms_total = round(max(0.0, harness_overhead_ms_total - setup_total_ms - prefetch_wait_ms_total), 3)
    bootstrap_storylets_created = 0
    bootstrap_sample_titles: List[str] = []
    bootstrap_embeddings_computed: bool | None = None
    if isinstance(bootstrap_result, dict):
        try:
            bootstrap_storylets_created = int(bootstrap_result.get("storylets_created", 0) or 0)
        except (TypeError, ValueError):
            bootstrap_storylets_created = 0
        raw_storylets = bootstrap_result.get("storylets")
        if isinstance(raw_storylets, list):
            for item in raw_storylets[:3]:
                if isinstance(item, dict):
                    title = str(item.get("title", "")).strip()
                    if title:
                        bootstrap_sample_titles.append(title)
        if "embeddings_computed" in bootstrap_result:
            bootstrap_embeddings_computed = bool(bootstrap_result.get("embeddings_computed"))
    summary = {
        "turns_completed": len(turns),
        "diversity_turns": sum(1 for turn in turns if turn.action_source.startswith("diversity")),
        "choice_turns": sum(1 for turn in turns if turn.action_source == "choice_button"),
        "plausible_true_count": sum(1 for turn in turns if turn.plausible),
        "final_var_keys": sorted(turns[-1].vars.keys()) if turns else [],
        "request_count": request_count,
        "failed_request_count": failed_request_count,
        "failure_rate": round(float(failure_rate), 6),
        "latency_ms_avg": request_latency_ms_avg,
        "latency_ms_p95": request_latency_ms_p95,
        "request_latency_ms_avg": request_latency_ms_avg,
        "request_latency_ms_p95": request_latency_ms_p95,
        "prefetch_wait_policy": config.prefetch_wait_policy,
        "prefetch_wait_timeout_seconds": round(float(config.prefetch_wait_timeout_seconds), 3),
        "prefetch_wait_calls": int(prefetch_wait_call_count),
        "prefetch_wait_ms_total": prefetch_wait_ms_total,
        "prefetch_wait_ms_avg": prefetch_wait_ms_avg,
        "prefetch_wait_ms_p95": prefetch_wait_ms_p95,
        "turn_wallclock_ms_avg": turn_wallclock_ms_avg,
        "turn_wallclock_ms_p95": turn_wallclock_ms_p95,
        "harness_overhead_ms_total": harness_overhead_ms_total,
        "harness_overhead_ms_avg_per_request": round(harness_overhead_ms_total / float(request_count), 3) if request_count else 0.0,
        "switch_model_ms": switch_model_ms,
        "hard_reset_ms": hard_reset_ms,
        "clean_reset_verification_enabled": bool(config.verify_clean_reset),
        "clean_reset_verification_passed": bool(clean_reset_verified),
        "clean_reset_verify_ms": clean_reset_verify_ms,
        "clean_reset_snapshot": clean_reset_snapshot,
        "bootstrap_ms": bootstrap_ms,
        "bootstrap_state": str(bootstrap_result.get("bootstrap_state", "") or ""),
        "bootstrap_storylets_created": bootstrap_storylets_created,
        "bootstrap_sample_titles": bootstrap_sample_titles,
        "bootstrap_embeddings_computed": bootstrap_embeddings_computed,
        "bootstrap_gate_failed": bool(bootstrap_gate_failed),
        "setup_total_ms": setup_total_ms,
        "non_setup_non_prefetch_overhead_ms_total": non_setup_non_prefetch_overhead_ms_total,
        "prefix_chars": int(prefix_metrics["prefix_chars"]),
        "prefix_non_empty_turns": int(prefix_metrics["prefix_non_empty_turns"]),
        "prefix_unique_count": int(prefix_metrics["prefix_unique_count"]),
        "prefix_duplicate_count": int(prefix_metrics["prefix_duplicate_count"]),
        "prefix_comparisons": int(prefix_metrics["comparisons"]),
        "exact_prefix_matches": int(prefix_metrics["exact_prefix_matches"]),
        "exact_prefix_match_rate": round(float(prefix_metrics["exact_prefix_match_rate"]), 6),
        "prefix_soft_match_threshold": round(float(prefix_metrics["soft_match_threshold"]), 3),
        "prefix_soft_matches": int(prefix_metrics["prefix_soft_matches"]),
        "prefix_soft_match_rate": round(float(prefix_metrics["prefix_soft_match_rate"]), 6),
        "prefix_similarity_avg": round(float(prefix_metrics["prefix_similarity_avg"]), 6),
        "prefix_similarity_p95": round(float(prefix_metrics["prefix_similarity_p95"]), 6),
        "prefix_max_similarity": round(float(prefix_metrics["prefix_max_similarity"]), 6),
        "prefix_top_reused": list(prefix_metrics.get("prefix_top_reused", [])),
        "motif_turns_with_tokens": int(motif_metrics["motif_turns_with_tokens"]),
        "motif_total_tokens": int(motif_metrics["motif_total_tokens"]),
        "motif_unique_tokens": int(motif_metrics["motif_unique_tokens"]),
        "motif_overlap_count": int(motif_metrics["motif_overlap_count"]),
        "motif_reused_tokens": int(motif_metrics["motif_reused_tokens"]),
        "motif_reuse_rate": round(float(motif_metrics["motif_reuse_rate"]), 6),
        "motif_novelty_rate": round(float(motif_metrics["motif_novelty_rate"]), 6),
        "motif_turn_overlap_rate_avg": round(float(motif_metrics["motif_turn_overlap_rate_avg"]), 6),
        "motif_top_reused": list(motif_metrics.get("motif_top_reused", [])),
        "projection_stub_count": int(projection_metrics["projection_stub_count"]),
        "projection_hit_rate": round(float(projection_metrics["projection_hit_rate"]), 6),
        "projection_waste_rate": round(float(projection_metrics["projection_waste_rate"]), 6),
        "projection_veto_rate": round(float(projection_metrics["projection_veto_rate"]), 6),
        "clarity_level_distribution": dict(projection_metrics.get("clarity_level_distribution", {})),
        "error_count": len(errors),
        "aborted": bool(errors),
        "elapsed_ms": elapsed_ms,
    }

    run_payload: Dict[str, Any] = {
        "run_id": f"{run_timestamp}-{_safe_slug(config.session_id)}",
        "timestamp_utc": _utc_now(),
        "base_url": config.base_url,
        "session_id": config.session_id,
        "turns_requested": int(config.turns),
        "seed": int(config.seed),
        "storylet_count": int(config.storylet_count),
        "request_timeout_seconds": float(config.request_timeout_seconds),
        "prefetch_wait_policy": config.prefetch_wait_policy,
        "prefetch_wait_timeout_seconds": float(config.prefetch_wait_timeout_seconds),
        "diversity_every": int(config.diversity_every),
        "diversity_chance": float(config.diversity_chance),
        "diversity_actions_count": len(diversity_actions),
        "switch_model": bool(config.switch_model),
        "model_id": config.model_id,
        "hard_reset": bool(config.hard_reset),
        "verify_clean_reset": bool(config.verify_clean_reset),
        "skip_bootstrap": bool(config.skip_bootstrap),
        "world": _world_payload(config.world),
        "llm_parameters": {
            "llm_temperature": config.llm_temperature,
            "llm_max_tokens": config.llm_max_tokens,
            "llm_recency_penalty": config.llm_recency_penalty,
            "llm_semantic_floor_probability": config.llm_semantic_floor_probability,
        },
        "env_overrides": build_parameter_env_overrides(config),
        "bootstrap_result": bootstrap_result if isinstance(bootstrap_result, dict) else {},
        "summary": summary,
        "errors": errors,
        "turns": [asdict(item) for item in turns],
    }
    return run_payload


def persist_run_payload(
    run_payload: Dict[str, Any],
    *,
    output_dir: Path,
    diversity_actions: Sequence[str],
) -> Tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_slug = str(run_payload.get("run_id", "")).strip() or f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ').lower()}-session"
    json_path = output_dir / f"{run_slug}.json"
    md_path = output_dir / f"{run_slug}.md"
    json_path.write_text(json.dumps(run_payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_render_markdown_report(run_payload, list(diversity_actions)), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    args = parse_args()
    if args.interactive and args.non_interactive:
        print("Error: --interactive and --non-interactive are mutually exclusive.", file=sys.stderr)
        return 2

    diversity_actions = list(DEFAULT_DIVERSITY_ACTIONS)
    if args.diversity_actions_file is not None:
        if not args.diversity_actions_file.exists():
            print(f"Error: diversity actions file not found: {args.diversity_actions_file}", file=sys.stderr)
            return 2
        diversity_actions.extend(_load_actions_file(args.diversity_actions_file))
    diversity_actions.extend([str(item).strip() for item in args.add_diversity_action])
    diversity_actions = _dedupe_preserve_order(diversity_actions)

    if args.print_diversity_actions:
        for action in diversity_actions:
            print(action)
        return 0

    try:
        config = _resolve_run_config(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(f"Session: {config.session_id}")
    print(f"Base URL: {config.base_url}")
    print(f"Turns requested: {config.turns}")
    print(f"Seed: {config.seed}")
    print(f"Request timeout seconds: {config.request_timeout_seconds}")
    print(f"Prefetch wait policy: {config.prefetch_wait_policy}")
    print(f"Prefetch wait timeout seconds: {config.prefetch_wait_timeout_seconds}")
    print(f"Verify clean reset: {config.verify_clean_reset}")
    print(f"Diversity actions pool: {len(diversity_actions)}")
    if config.world is not None:
        print(f"Scenario: {config.world.scenario_id} ({config.world.scenario_title})")
        print(f"Role: {config.world.role}")
        print(f"Theme: {config.world.theme}")
    if config.skip_bootstrap:
        print("Bootstrap: skipped")
    parameter_overrides = build_parameter_env_overrides(config)
    if parameter_overrides:
        print(f"LLM parameter overrides requested: {parameter_overrides}")

    try:
        run_payload = run_long_playtest(
            config,
            diversity_actions,
            continue_on_error=False,
            progress=print,
        )
    except Exception as exc:
        print(f"Run failed: {exc}", file=sys.stderr)
        return 1

    json_path, md_path = persist_run_payload(
        run_payload,
        output_dir=config.output_dir,
        diversity_actions=diversity_actions,
    )

    print(f"Run complete. Turns: {run_payload.get('summary', {}).get('turns_completed', 0)}")
    print(f"JSON report: {json_path}")
    print(f"Markdown transcript: {md_path}")
    if bool(run_payload.get("errors")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
