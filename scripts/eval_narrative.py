#!/usr/bin/env python
"""Narrative evaluation harness for deterministic regression checks."""

from __future__ import annotations

import argparse
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
    stall_scores = [float(item.get("stall_score", 0.0)) for item in scenario_results]
    repetition = [float(item.get("repetition_frequency", 0.0)) for item in scenario_results]
    success = _success_rate(scenario_results)

    metrics = {
        "memory_carryover_score": round(memory, 6),
        "divergence_score": round(divergence, 6),
        "freeform_coherence_score": round(coherence, 6),
        "stall_repetition_score": round(_average(stall_scores), 6),
        "repetition_frequency": round(_average(repetition), 6),
        "narrative_command_success_rate": round(success, 6),
    }

    success_criteria_map = {
        "vision_success_1_world_bootstrap": ["narrative_command_success_rate", "memory_carryover_score"],
        "vision_success_2_goal_complication_arc": ["stall_repetition_score", "narrative_command_success_rate"],
        "vision_success_3_divergent_playthroughs": ["divergence_score"],
        "vision_success_4_world_memory_influences_future": ["memory_carryover_score"],
        "vision_success_5_unexpected_action_coherence": ["freeform_coherence_score"],
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
