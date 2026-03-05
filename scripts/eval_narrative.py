#!/usr/bin/env python
"""Narrative evaluation harness for deterministic regression checks."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import random
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import app
from src.api.game import _spatial_navigators, _state_managers
from src.database import Base, create_tables, get_db
from src.services.command_interpreter import interpret_action
from src.services.seed_data import seed_legacy_storylets_if_empty_sync

DEFAULT_SCENARIO_FILE = ROOT / "tests" / "integration" / "narrative_eval_scenarios.json"
DEFAULT_OUT_DIR = ROOT / "reports" / "narrative_eval"
DEFAULT_BASELINE_FILE = ROOT / "reports" / "narrative_eval" / "baseline.json"
DEFAULT_HISTORY_FILE = ROOT / "reports" / "narrative_eval" / "history.jsonl"
WORD_RE = re.compile(r"[a-z0-9]+")
_SUBJECT_FRAGMENT = r"[a-z][a-z0-9_-]*(?:\s+[a-z0-9_-]+){0,4}"
_STATUS_POLARITY: Dict[str, Tuple[str, int]] = {
    "alive": ("existence", 1),
    "dead": ("existence", -1),
    "intact": ("integrity", 1),
    "repaired": ("integrity", 1),
    "stable": ("integrity", 1),
    "broken": ("integrity", -1),
    "destroyed": ("integrity", -1),
    "collapsed": ("integrity", -1),
    "ruined": ("integrity", -1),
    "burned": ("integrity", -1),
    "open": ("access", 1),
    "closed": ("access", -1),
    "sealed": ("access", -1),
    "unsealed": ("access", 1),
    "locked": ("lock", -1),
    "unlocked": ("lock", 1),
    "lit": ("light", 1),
    "unlit": ("light", -1),
    "safe": ("safety", 1),
    "dangerous": ("safety", -1),
}
_STATUS_ALIASES = {
    "burnt": "burned",
    "collapse": "collapsed",
    "destroy": "destroyed",
    "seal": "sealed",
    "lock": "locked",
    "unlock": "unlocked",
    "unsafe": "dangerous",
}
_STATUS_TEXT_PATTERNS = [
    re.compile(
        rf"\b(?P<subject>{_SUBJECT_FRAGMENT})\s+(?:is|was|seems|remains|became|becomes)\s+(?P<status>[a-z-]+)\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?P<subject>{_SUBJECT_FRAGMENT})\s+(?P<status>destroyed|collapsed|burned|sealed|unsealed|locked|unlocked|broken|repaired)\b",
        re.IGNORECASE,
    ),
]
_STATUS_PREDICATE_HINTS = (
    "status",
    "state",
    "condition",
    "integrity",
    "lock",
    "access",
    "safety",
    "alive",
    "dead",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _tokenize(texts: List[str]) -> set[str]:
    joined = " ".join(str(text or "").lower() for text in texts)
    return set(WORD_RE.findall(joined))


def _word_overlap_score(left: str, right: str) -> float:
    left_tokens = _tokenize([left])
    right_tokens = _tokenize([right])
    if not left_tokens or not right_tokens:
        return 0.0
    return 1.0 - _jaccard_distance(left_tokens, right_tokens)


def _jaccard_distance(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return 1.0 - (len(left & right) / float(len(union)))


def _normalize_turn_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _stall_score(turn_texts: List[str]) -> Tuple[float, float]:
    normalized = [_normalize_turn_text(t) for t in turn_texts if str(t or "").strip()]
    if len(normalized) < 2:
        return 1.0, 0.0
    repeated = 0
    for idx in range(1, len(normalized)):
        if normalized[idx] == normalized[idx - 1]:
            repeated += 1
    repetition_frequency = repeated / float(len(normalized) - 1)
    return 1.0 - repetition_frequency, repetition_frequency


def _normalize_subject(subject: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(subject or "").strip().lower())
    cleaned = re.sub(r"^(the|a|an)\s+", "", cleaned)
    return cleaned


def _normalize_status_token(status: str) -> str:
    cleaned = str(status or "").strip().lower()
    return _STATUS_ALIASES.get(cleaned, cleaned)


def _extract_status_claims_from_text(texts: List[str]) -> List[Tuple[str, str, int, str]]:
    claims: List[Tuple[str, str, int, str]] = []
    for text in texts:
        sample = str(text or "").lower()
        if not sample:
            continue
        for pattern in _STATUS_TEXT_PATTERNS:
            for match in pattern.finditer(sample):
                subject = _normalize_subject(match.group("subject"))
                status = _normalize_status_token(match.group("status"))
                if not subject or status not in _STATUS_POLARITY:
                    continue
                group, polarity = _STATUS_POLARITY[status]
                claims.append((subject, group, polarity, status))
    return claims


def _extract_status_claims_from_graph_facts(
    facts: List[Dict[str, Any]],
) -> List[Tuple[str, str, int, str]]:
    claims: List[Tuple[str, str, int, str]] = []
    for item in facts:
        if not isinstance(item, dict):
            continue
        subject_payload = item.get("subject_node")
        subject = ""
        if isinstance(subject_payload, dict):
            subject = str(subject_payload.get("normalized_name") or subject_payload.get("name") or "").strip()
        subject = _normalize_subject(subject)
        predicate = str(item.get("predicate", "")).strip().lower()
        value_tokens = WORD_RE.findall(str(item.get("value", "")).lower())
        should_consider_predicate = any(hint in predicate for hint in _STATUS_PREDICATE_HINTS)
        for raw_token in value_tokens:
            token = _normalize_status_token(raw_token)
            if token not in _STATUS_POLARITY:
                continue
            if not subject and not should_consider_predicate:
                continue
            group, polarity = _STATUS_POLARITY[token]
            claims.append((subject or "unknown", group, polarity, token))
    return claims


def _declared_goal_for_scenario(scenario: Dict[str, Any]) -> str:
    arc_expectations = scenario.get("arc_expectations")
    if isinstance(arc_expectations, dict):
        expected_goal = str(arc_expectations.get("expected_goal", "")).strip()
        if expected_goal:
            return expected_goal
    for step in scenario.get("steps", []):
        if str(step.get("op", "")).strip().lower() != "next":
            continue
        vars_payload = step.get("vars")
        if not isinstance(vars_payload, dict):
            continue
        goal = str(vars_payload.get("goal", "")).strip()
        if goal:
            return goal
    return ""


def _contradiction_metrics(
    scenario_results: List[Dict[str, Any]],
) -> Tuple[float, float, List[Dict[str, Any]]]:
    details: List[Dict[str, Any]] = []
    total_claim_groups = 0
    total_contradictions = 0

    for result in scenario_results:
        text_claims = _extract_status_claims_from_text(list(result.get("turn_texts", [])) + list(result.get("world_event_summaries", [])) + list(result.get("world_fact_summaries", [])))
        fact_claims = _extract_status_claims_from_graph_facts(list(result.get("world_graph_facts", [])))
        seen: Dict[Tuple[str, str], set[int]] = defaultdict(set)
        for subject, group, polarity, _token in [*text_claims, *fact_claims]:
            seen[(subject, group)].add(int(polarity))

        claim_groups = len(seen)
        contradictions = sum(1 for polarities in seen.values() if len(polarities) > 1)
        total_claim_groups += claim_groups
        total_contradictions += contradictions
        details.append(
            {
                "id": result.get("id"),
                "claim_groups": claim_groups,
                "contradictions": contradictions,
            }
        )

    contradiction_frequency = total_contradictions / float(total_claim_groups) if total_claim_groups else 0.0
    contradiction_free_score = 1.0 - min(1.0, contradiction_frequency)
    return (
        round(contradiction_free_score, 6),
        round(contradiction_frequency, 6),
        details,
    )


def _arc_adherence_score(
    scenario_results: List[Dict[str, Any]],
    scenarios: List[Dict[str, Any]],
) -> Tuple[float, List[Dict[str, Any]]]:
    by_id = {str(item["id"]): item for item in scenario_results}
    scenario_scores: List[float] = []
    details: List[Dict[str, Any]] = []

    for scenario in scenarios:
        scenario_id = str(scenario.get("id"))
        result = by_id.get(scenario_id)
        if result is None:
            continue

        arc_expectations = scenario.get("arc_expectations")
        if not isinstance(arc_expectations, dict):
            arc_expectations = {}
        declared_goal = _declared_goal_for_scenario(scenario)

        require_arc_activity = bool(arc_expectations.get("require_arc_activity", bool(declared_goal)))
        min_overlap = float(arc_expectations.get("goal_overlap_min", 0.35))
        min_milestones = int(max(0, int(arc_expectations.get("min_milestones", 0) or 0)))
        allowed_statuses = {str(item).strip().lower() for item in arc_expectations.get("allowed_statuses", []) if str(item).strip()}

        goal_candidates: List[str] = []
        state_goal = result.get("state_goal")
        if isinstance(state_goal, dict):
            goal_candidates.append(str(state_goal.get("primary_goal", "")))
        state_variables = result.get("state_variables")
        if isinstance(state_variables, dict):
            goal_candidates.append(str(state_variables.get("goal", "")))
        final_vars = result.get("final_vars")
        if isinstance(final_vars, dict):
            goal_candidates.append(str(final_vars.get("goal", "")))
        goal_candidates = [text.strip() for text in goal_candidates if text and text.strip()]

        signals: List[float] = []
        best_goal_overlap = 0.0
        if declared_goal:
            for candidate in goal_candidates:
                best_goal_overlap = max(
                    best_goal_overlap,
                    _word_overlap_score(declared_goal, candidate),
                )
            signals.append(1.0 if best_goal_overlap >= min_overlap else 0.0)

        arc_timeline = result.get("arc_timeline", [])
        if not isinstance(arc_timeline, list):
            arc_timeline = []
        story_arc_turn_count = 0
        state_variables_for_arc = result.get("state_variables")
        if isinstance(state_variables_for_arc, dict):
            story_arc_payload = state_variables_for_arc.get("_story_arc")
            if isinstance(story_arc_payload, dict):
                raw_turn_count = story_arc_payload.get("turn_count", 0)
                try:
                    story_arc_turn_count = max(0, int(raw_turn_count))
                except (TypeError, ValueError):
                    story_arc_turn_count = 0
        has_arc_activity = len(arc_timeline) > 0 or story_arc_turn_count > 0
        if require_arc_activity:
            signals.append(1.0 if has_arc_activity else 0.0)
        if min_milestones > 0:
            signals.append(1.0 if (len(arc_timeline) >= min_milestones or story_arc_turn_count >= min_milestones) else 0.0)
        if allowed_statuses:
            statuses = {str(item.get("status", "")).strip().lower() for item in arc_timeline if isinstance(item, dict)}
            if statuses:
                signals.append(1.0 if statuses & allowed_statuses else 0.0)

        if not signals:
            continue

        scenario_score = _average(signals)
        scenario_scores.append(scenario_score)
        details.append(
            {
                "id": scenario_id,
                "declared_goal": declared_goal,
                "best_goal_overlap": round(best_goal_overlap, 6),
                "arc_activity_count": len(arc_timeline),
                "story_arc_turn_count": story_arc_turn_count,
                "score": round(scenario_score, 6),
            }
        )

    if not scenario_scores:
        return 0.0, details
    return round(_average(scenario_scores), 6), details


def _repetition_window_guard_score(
    scenario_results: List[Dict[str, Any]],
    *,
    window: int = 3,
) -> Tuple[float, float, List[Dict[str, Any]]]:
    effective_window = max(1, int(window))
    total_windows = 0
    total_violations = 0
    details: List[Dict[str, Any]] = []

    for result in scenario_results:
        world_events = result.get("world_events", [])
        if not isinstance(world_events, list):
            world_events = []
        ordered_events = sorted(
            [item for item in world_events if isinstance(item, dict)],
            key=lambda item: str(item.get("created_at") or ""),
        )
        sequence: List[str] = [str(item.get("storylet_id")) for item in ordered_events if str(item.get("event_type", "")).strip().lower() == "storylet_fired" and item.get("storylet_id") is not None]
        if len(sequence) < 2:
            sequence = [_normalize_turn_text(text) for text in result.get("turn_texts", []) if str(text or "").strip()]

        scenario_windows = 0
        scenario_violations = 0
        for idx in range(1, len(sequence)):
            scenario_windows += 1
            start = max(0, idx - effective_window)
            if sequence[idx] in sequence[start:idx]:
                scenario_violations += 1

        total_windows += scenario_windows
        total_violations += scenario_violations
        details.append(
            {
                "id": result.get("id"),
                "sequence_length": len(sequence),
                "windows": scenario_windows,
                "violations": scenario_violations,
            }
        )

    violation_rate = total_violations / float(total_windows) if total_windows else 0.0
    repetition_guard_score = 1.0 - min(1.0, violation_rate)
    return (
        round(repetition_guard_score, 6),
        round(violation_rate, 6),
        details,
    )


@contextmanager
def _evaluation_client() -> Iterator[Tuple[TestClient, Session]]:
    # Keep deterministic offline behavior for eval runs.
    import os

    os.environ["DW_DISABLE_AI"] = "1"
    os.environ.setdefault("WW_ENABLE_CONSTELLATION", "0")

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_factory()
    seed_legacy_storylets_if_empty_sync(db)
    db.commit()

    create_tables()

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    _state_managers.clear()
    _spatial_navigators.clear()

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, db

    app.dependency_overrides.clear()
    _state_managers.clear()
    _spatial_navigators.clear()
    db.close()
    engine.dispose()


def _run_scenario(client: TestClient, scenario: Dict[str, Any]) -> Dict[str, Any]:
    session_id = str(scenario["session_id"])
    turn_texts: List[str] = []
    status_codes: List[int] = []
    final_vars: Dict[str, Any] = {}
    state_goal: Dict[str, Any] = {}
    state_variables: Dict[str, Any] = {}
    arc_timeline: List[Dict[str, Any]] = []
    world_events: List[Dict[str, Any]] = []
    world_event_summaries: List[str] = []
    world_graph_facts: List[Dict[str, Any]] = []
    world_fact_summaries: List[str] = []
    steps = scenario.get("steps", [])

    for step in steps:
        operation = str(step.get("op", "")).strip().lower()
        if operation == "next":
            payload = {"session_id": session_id, "vars": step.get("vars", {})}
            response = client.post("/api/next", json=payload)
            status_codes.append(response.status_code)
            if response.status_code == 200:
                body = response.json()
                turn_texts.append(str(body.get("text", "")))
                vars_payload = body.get("vars")
                if isinstance(vars_payload, dict):
                    final_vars = vars_payload
            continue

        if operation == "action":
            payload = {
                "session_id": session_id,
                "action": str(step.get("action", "")),
            }
            response = client.post("/api/action", json=payload)
            status_codes.append(response.status_code)
            if response.status_code == 200:
                body = response.json()
                turn_texts.append(str(body.get("narrative", "")))
                vars_payload = body.get("vars")
                if isinstance(vars_payload, dict):
                    final_vars = vars_payload
            continue

        raise ValueError(f"Unsupported operation '{operation}' in scenario '{scenario.get('id')}'")

    state_response = client.get(f"/api/state/{session_id}")
    if state_response.status_code == 200:
        payload = state_response.json()
        state_goal = payload.get("goal") if isinstance(payload.get("goal"), dict) else {}
        state_variables = payload.get("variables") if isinstance(payload.get("variables"), dict) else {}
        arc_payload = payload.get("arc_timeline")
        if isinstance(arc_payload, list):
            arc_timeline = [item for item in arc_payload if isinstance(item, dict)]

    events_response = client.get(
        "/api/world/history",
        params={"session_id": session_id, "limit": 120},
    )
    if events_response.status_code == 200:
        payload = events_response.json()
        events_payload = payload.get("events")
        if isinstance(events_payload, list):
            world_events = [item for item in events_payload if isinstance(item, dict)]
            world_event_summaries = [str(item.get("summary", "")).strip() for item in world_events if str(item.get("summary", "")).strip()]

    facts_response = client.get(
        "/api/world/graph/facts",
        params={"session_id": session_id, "query": "", "limit": 100},
    )
    if facts_response.status_code == 200:
        payload = facts_response.json()
        facts_payload = payload.get("facts")
        if isinstance(facts_payload, list):
            world_graph_facts = [item for item in facts_payload if isinstance(item, dict)]
            world_fact_summaries = [str(item.get("summary", "")).strip() for item in world_graph_facts if str(item.get("summary", "")).strip()]

    all_ok = all(code == 200 for code in status_codes)
    completed_steps = sum(1 for code in status_codes if code == 200)
    total_steps = len(status_codes)
    stall_score, repetition_frequency = _stall_score(turn_texts)
    return {
        "id": scenario.get("id"),
        "session_id": session_id,
        "all_ok": all_ok,
        "completed_steps": completed_steps,
        "total_steps": total_steps,
        "turn_texts": turn_texts,
        "final_vars": final_vars,
        "status_codes": status_codes,
        "stall_score": round(stall_score, 6),
        "repetition_frequency": round(repetition_frequency, 6),
        "declared_goal": _declared_goal_for_scenario(scenario),
        "state_goal": state_goal,
        "state_variables": state_variables,
        "arc_timeline": arc_timeline,
        "world_events": world_events,
        "world_event_summaries": world_event_summaries,
        "world_graph_facts": world_graph_facts,
        "world_fact_summaries": world_fact_summaries,
    }


def _memory_carryover_score(
    scenario_results: List[Dict[str, Any]],
    scenarios: List[Dict[str, Any]],
) -> float:
    checks_total = 0
    checks_passed = 0
    by_id = {str(item["id"]): item for item in scenario_results}
    for scenario in scenarios:
        expected = scenario.get("memory_expectations", [])
        result = by_id.get(str(scenario.get("id")))
        if result is None:
            continue
        final_vars = result.get("final_vars", {})
        for item in expected:
            checks_total += 1
            key = str(item.get("key", ""))
            expected_value = item.get("value")
            if key in final_vars and final_vars.get(key) == expected_value:
                checks_passed += 1
    if checks_total == 0:
        return 0.0
    return checks_passed / float(checks_total)


def _divergence_score(
    scenario_results: List[Dict[str, Any]],
    divergence_pair: List[str],
) -> float:
    if len(divergence_pair) != 2:
        return 0.0
    by_id = {str(item["id"]): item for item in scenario_results}
    left = by_id.get(divergence_pair[0])
    right = by_id.get(divergence_pair[1])
    if left is None or right is None:
        return 0.0
    left_tokens = _tokenize(left.get("turn_texts", []))
    right_tokens = _tokenize(right.get("turn_texts", []))
    return _jaccard_distance(left_tokens, right_tokens)


def _coherence_score(db: Session, probes: List[Dict[str, Any]]) -> Tuple[float, List[Dict[str, Any]]]:
    from unittest.mock import MagicMock

    outcomes: List[Dict[str, Any]] = []
    passed = 0
    for probe in probes:
        state_manager = MagicMock()
        state_manager.session_id = f"eval-probe-{probe.get('id', 'unknown')}"
        state_manager.get_state_summary.return_value = {
            "variables": {"location": probe.get("location", "bridge")},
            "inventory": {},
        }
        state_manager.environment = MagicMock(danger_level=0, noise_level=0, weather="clear", time_of_day="day")
        state_manager.goal_state = MagicMock(primary_goal="Testing", urgency=0.0, complication=0.0)
        state_manager.relationships = {}
        state_manager.inventory = {}
        state_manager.get_variable.side_effect = lambda k, d=None: state_manager.get_state_summary.return_value["variables"].get(k, d)

        world_memory = MagicMock()
        world_memory.get_world_history.return_value = []
        world_memory.get_relevant_action_facts.return_value = list(probe.get("facts", []))

        action = str(probe.get("action", ""))
        expected_plausible = bool(probe.get("expected_plausible", True))
        result = interpret_action(
            action=action,
            state_manager=state_manager,
            world_memory_module=world_memory,
            current_storylet=None,
            db=db,
        )
        matched = bool(result.plausible) == expected_plausible
        if matched:
            passed += 1
        outcomes.append(
            {
                "id": probe.get("id"),
                "expected_plausible": expected_plausible,
                "actual_plausible": bool(result.plausible),
                "matched": matched,
            }
        )

    if not probes:
        return 0.0, outcomes
    return passed / float(len(probes)), outcomes


def _success_rate(scenario_results: List[Dict[str, Any]]) -> float:
    total = sum(int(item.get("total_steps", 0)) for item in scenario_results)
    ok = sum(int(item.get("completed_steps", 0)) for item in scenario_results)
    if total == 0:
        return 0.0
    return ok / float(total)


def _average(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / float(len(values))


def _apply_smoke_mode(config: Dict[str, Any]) -> Dict[str, Any]:
    scenarios = list(config.get("scenarios", []))[:2]
    for scenario in scenarios:
        scenario["steps"] = list(scenario.get("steps", []))[:3]
    probes = list(config.get("coherence_probes", []))
    divergence_pair = list(config.get("divergence_pair", []))
    smoke_pair = []
    for scenario in scenarios:
        smoke_pair.append(str(scenario.get("id")))
        if len(smoke_pair) >= 2:
            break
    if len(smoke_pair) < 2 and len(divergence_pair) >= 2:
        smoke_pair = divergence_pair[:2]
    return {
        "scenarios": scenarios,
        "coherence_probes": probes,
        "divergence_pair": smoke_pair,
    }


def _evaluate(config: Dict[str, Any], *, smoke: bool, seed: int) -> Dict[str, Any]:
    random.seed(seed)
    run_config = _apply_smoke_mode(config) if smoke else config
    scenarios = list(run_config.get("scenarios", []))
    divergence_pair = list(run_config.get("divergence_pair", []))
    probes = list(run_config.get("coherence_probes", []))

    with _evaluation_client() as (client, db):
        scenario_results = [_run_scenario(client, scenario) for scenario in scenarios]
        coherence, probe_results = _coherence_score(db, probes)

    memory = _memory_carryover_score(scenario_results, scenarios)
    divergence = _divergence_score(scenario_results, divergence_pair)
    contradiction_free, contradiction_frequency, contradiction_details = _contradiction_metrics(scenario_results)
    arc_adherence, arc_adherence_details = _arc_adherence_score(
        scenario_results,
        scenarios,
    )
    repetition_window_guard, repetition_window_violation_rate, repetition_window_details = _repetition_window_guard_score(scenario_results)
    stall_scores = [float(item.get("stall_score", 0.0)) for item in scenario_results]
    repetition = [float(item.get("repetition_frequency", 0.0)) for item in scenario_results]
    success = _success_rate(scenario_results)

    metrics = {
        "memory_carryover_score": round(memory, 6),
        "divergence_score": round(divergence, 6),
        "freeform_coherence_score": round(coherence, 6),
        "contradiction_free_score": contradiction_free,
        "contradiction_frequency": contradiction_frequency,
        "arc_adherence_score": arc_adherence,
        "repetition_window_guard_score": repetition_window_guard,
        "repetition_window_violation_rate": repetition_window_violation_rate,
        "stall_repetition_score": round(_average(stall_scores), 6),
        "repetition_frequency": round(_average(repetition), 6),
        "narrative_command_success_rate": round(success, 6),
    }

    success_criteria_map = {
        "vision_success_1_world_bootstrap": ["narrative_command_success_rate", "memory_carryover_score"],
        "vision_success_2_goal_complication_arc": ["stall_repetition_score", "narrative_command_success_rate"],
        "vision_success_3_divergent_playthroughs": ["divergence_score"],
        "vision_success_4_world_memory_influences_future": ["memory_carryover_score"],
        "vision_success_5_unexpected_action_coherence": ["freeform_coherence_score", "contradiction_free_score"],
        "vision_success_6_world_feels_independent": ["stall_repetition_score", "divergence_score"],
    }

    return {
        "seed": seed,
        "smoke": smoke,
        "scenario_count": len(scenarios),
        "coherence_probe_count": len(probes),
        "metrics": metrics,
        "scenario_results": scenario_results,
        "coherence_probe_results": probe_results,
        "contradiction_details": contradiction_details,
        "arc_adherence_details": arc_adherence_details,
        "repetition_window_details": repetition_window_details,
        "success_criteria_map": success_criteria_map,
    }


def _load_thresholds(path: Path) -> Dict[str, float]:
    payload = _load_json(path)
    thresholds = payload.get("thresholds", {})
    return {str(k): float(v) for k, v in thresholds.items()}


def _evaluate_thresholds(metrics: Dict[str, float], thresholds: Dict[str, float]) -> List[Dict[str, Any]]:
    regressions: List[Dict[str, Any]] = []
    for metric_name, minimum in thresholds.items():
        value = float(metrics.get(metric_name, 0.0))
        if value < minimum:
            regressions.append(
                {
                    "metric": metric_name,
                    "value": round(value, 6),
                    "minimum": round(minimum, 6),
                    "delta": round(value - minimum, 6),
                }
            )
    return regressions


def _write_report(
    report: Dict[str, Any],
    *,
    out_dir: Path,
    history_file: Path,
) -> None:
    def _path_label(path: Path) -> str:
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)

    out_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = out_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    latest_file = out_dir / "latest.json"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_file = runs_dir / f"{timestamp}.json"

    latest_file.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    run_file.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    history_file.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "timestamp_utc": report["timestamp_utc"],
        "commit": report["commit"],
        "smoke": report["smoke"],
        "metrics": report["metrics"],
        "regressions": report["regressions"],
        "latest_report": _path_label(latest_file),
        "run_report": _path_label(run_file),
    }
    with history_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(summary, sort_keys=True) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run narrative evaluation harness.")
    parser.add_argument("--scenario-file", type=Path, default=DEFAULT_SCENARIO_FILE)
    parser.add_argument("--baseline-file", type=Path, default=DEFAULT_BASELINE_FILE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--history-file", type=Path, default=DEFAULT_HISTORY_FILE)
    parser.add_argument("--seed", type=int, default=20260303)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args()


def main() -> int:
    run_started = time.perf_counter()
    args = parse_args()

    def _path_label(path: Path) -> str:
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)

    scenario_file = args.scenario_file
    if not scenario_file.is_absolute():
        scenario_file = ROOT / scenario_file
    baseline_file = args.baseline_file
    if not baseline_file.is_absolute():
        baseline_file = ROOT / baseline_file
    out_dir = args.out_dir
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    history_file = args.history_file
    if not history_file.is_absolute():
        history_file = ROOT / history_file

    config = _load_json(scenario_file)
    evaluation = _evaluate(config, smoke=args.smoke, seed=int(args.seed))
    thresholds = _load_thresholds(baseline_file)
    regressions = _evaluate_thresholds(evaluation["metrics"], thresholds)

    report = {
        "timestamp_utc": _utc_now(),
        "commit": _git_commit(),
        "smoke": bool(args.smoke),
        "seed": int(args.seed),
        "scenario_file": _path_label(scenario_file),
        "baseline_file": _path_label(baseline_file),
        "metrics": evaluation["metrics"],
        "thresholds": thresholds,
        "regressions": regressions,
        "scenario_results": evaluation["scenario_results"],
        "coherence_probe_results": evaluation["coherence_probe_results"],
        "contradiction_details": evaluation["contradiction_details"],
        "arc_adherence_details": evaluation["arc_adherence_details"],
        "repetition_window_details": evaluation["repetition_window_details"],
        "success_criteria_map": evaluation["success_criteria_map"],
        "elapsed_ms": round((time.perf_counter() - run_started) * 1000.0, 3),
    }

    _write_report(report, out_dir=out_dir, history_file=history_file)

    print(json.dumps({"metrics": evaluation["metrics"], "regressions": regressions}, indent=2))
    if args.enforce and regressions:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
