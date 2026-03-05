#!/usr/bin/env python
"""Two-phase LLM parameter sweep harness for comparative playtest tuning."""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Sequence

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playtest_harness.long_run_harness import (
    DEFAULT_BASE_URL,
    DEFAULT_DIVERSITY_ACTIONS,
    DEFAULT_PREFETCH_WAIT_TIMEOUT_SECONDS,
    DEFAULT_STORYLET_COUNT,
    PREFETCH_WAIT_POLICIES,
    SCENARIOS,
    RunConfig,
    WorldConfig,
    build_parameter_env_overrides_from_values,
    persist_run_payload,
    run_long_playtest,
)

DEFAULT_OUT_DIR = Path("playtests") / "sweeps"
PHASE_A_DEFAULT_CONFIGS = 16
PHASE_A_DEFAULT_TURNS = 20
PHASE_B_DEFAULT_TURNS = 30
PHASE_B_DEFAULT_RUNS_PER_CONFIG = 3
PHASE_B_DEFAULT_TOP_K = 4

TEMPERATURE_RANGE = (0.1, 1.0)
MAX_TOKENS_RANGE = (900, 2800)
RECENCY_PENALTY_RANGE = (0.05, 0.85)
SEMANTIC_FLOOR_RANGE = (0.0, 0.25)


@dataclass(frozen=True)
class SweepParameterSet:
    llm_temperature: float
    llm_max_tokens: int
    llm_recency_penalty: float
    llm_semantic_floor_probability: float

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def env_overrides(self) -> Dict[str, str]:
        return build_parameter_env_overrides_from_values(
            llm_temperature=self.llm_temperature,
            llm_max_tokens=self.llm_max_tokens,
            llm_recency_penalty=self.llm_recency_penalty,
            llm_semantic_floor_probability=self.llm_semantic_floor_probability,
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ").lower()


def _path_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except Exception:
        return str(path.resolve())


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        value = result.stdout.strip()
        return value or "unknown"
    except Exception:
        return "unknown"


def _latin_hypercube_column(*, count: int, rng: random.Random, minimum: float, maximum: float) -> List[float]:
    step = 1.0 / float(count)
    values = [((idx + rng.random()) * step) for idx in range(count)]
    rng.shuffle(values)
    return [minimum + (value * (maximum - minimum)) for value in values]


def generate_phase_a_parameter_sets(*, count: int, seed: int) -> List[SweepParameterSet]:
    if count < 1:
        raise ValueError("count must be >= 1")

    rng = random.Random(seed)
    temperatures = _latin_hypercube_column(
        count=count,
        rng=rng,
        minimum=TEMPERATURE_RANGE[0],
        maximum=TEMPERATURE_RANGE[1],
    )
    max_tokens = _latin_hypercube_column(
        count=count,
        rng=rng,
        minimum=float(MAX_TOKENS_RANGE[0]),
        maximum=float(MAX_TOKENS_RANGE[1]),
    )
    recency_penalties = _latin_hypercube_column(
        count=count,
        rng=rng,
        minimum=RECENCY_PENALTY_RANGE[0],
        maximum=RECENCY_PENALTY_RANGE[1],
    )
    semantic_floors = _latin_hypercube_column(
        count=count,
        rng=rng,
        minimum=SEMANTIC_FLOOR_RANGE[0],
        maximum=SEMANTIC_FLOOR_RANGE[1],
    )

    output: List[SweepParameterSet] = []
    for idx in range(count):
        output.append(
            SweepParameterSet(
                llm_temperature=round(float(temperatures[idx]), 4),
                llm_max_tokens=int(round(float(max_tokens[idx]))),
                llm_recency_penalty=round(float(recency_penalties[idx]), 4),
                llm_semantic_floor_probability=round(float(semantic_floors[idx]), 4),
            )
        )
    return output


def score_run_metrics(
    *,
    latency_ms_avg: float,
    exact_prefix_match_rate: float,
    failure_rate: float,
) -> float:
    clean_failure_rate = max(0.0, min(1.0, float(failure_rate)))
    clean_repetition_rate = max(0.0, min(1.0, float(exact_prefix_match_rate)))
    clean_latency = max(0.0, float(latency_ms_avg))

    failure_component = 1.0 - clean_failure_rate
    repetition_component = 1.0 - clean_repetition_rate
    latency_component = 1.0 / (1.0 + (clean_latency / 1200.0))

    return round(
        (failure_component * 0.55) + (repetition_component * 0.30) + (latency_component * 0.15),
        6,
    )


def rank_phase_results(results: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for item in results:
        metrics = item.get("metrics", {})
        latency = float(metrics.get("latency_ms_avg", 0.0))
        repetition = float(metrics.get("exact_prefix_match_rate", 0.0))
        failure = float(metrics.get("failure_rate", 1.0))
        scored = dict(item)
        scored["composite_score"] = score_run_metrics(
            latency_ms_avg=latency,
            exact_prefix_match_rate=repetition,
            failure_rate=failure,
        )
        enriched.append(scored)

    return sorted(
        enriched,
        key=lambda item: (
            -float(item.get("composite_score", 0.0)),
            float(item.get("metrics", {}).get("failure_rate", 1.0)),
            float(item.get("metrics", {}).get("exact_prefix_match_rate", 1.0)),
            float(item.get("metrics", {}).get("latency_ms_avg", float("inf"))),
            str(item.get("config_id", "")),
        ),
    )


def _resolve_world_config(args: argparse.Namespace) -> WorldConfig:
    scenario_id = str(args.scenario).strip()
    if scenario_id not in SCENARIOS:
        raise ValueError(f"unknown scenario '{scenario_id}'")
    scenario = SCENARIOS[scenario_id]
    role_default = str((scenario.get("roles") or ["adventurer"])[0])
    role = str(args.role).strip() if args.role else role_default

    key_elements_raw = args.key_elements
    if key_elements_raw:
        key_elements = [part.strip() for part in str(key_elements_raw).split(",") if part.strip()]
    else:
        key_elements = [str(item) for item in scenario.get("key_elements", []) if str(item).strip()]
    if not key_elements:
        key_elements = ["risk", "tradeoff", "complication"]

    return WorldConfig(
        scenario_id=scenario_id,
        scenario_title=str(scenario.get("title", scenario_id)),
        theme=str(args.theme).strip() if args.theme else str(scenario.get("theme", "")),
        role=role,
        description=(str(args.description).strip() if args.description else str(scenario.get("description", ""))),
        key_elements=key_elements,
        tone=str(args.tone).strip() if args.tone else str(scenario.get("tone", "")),
    )


def _build_run_config(
    *,
    base_url: str,
    output_dir: Path,
    world: WorldConfig,
    session_id: str,
    turns: int,
    seed: int,
    storylet_count: int,
    diversity_every: int,
    diversity_chance: float,
    request_timeout_seconds: float,
    prefetch_wait_policy: str,
    prefetch_wait_timeout_seconds: float,
    switch_model: bool,
    model_id: str,
    hard_reset: bool,
    params: SweepParameterSet,
) -> RunConfig:
    return RunConfig(
        base_url=base_url.rstrip("/"),
        session_id=session_id,
        turns=int(turns),
        seed=int(seed),
        storylet_count=int(storylet_count),
        switch_model=bool(switch_model),
        model_id=str(model_id),
        hard_reset=bool(hard_reset),
        skip_bootstrap=False,
        diversity_every=int(diversity_every),
        diversity_chance=float(diversity_chance),
        output_dir=output_dir,
        world=world,
        request_timeout_seconds=float(request_timeout_seconds),
        prefetch_wait_policy=str(prefetch_wait_policy),
        prefetch_wait_timeout_seconds=float(prefetch_wait_timeout_seconds),
        llm_temperature=float(params.llm_temperature),
        llm_max_tokens=int(params.llm_max_tokens),
        llm_recency_penalty=float(params.llm_recency_penalty),
        llm_semantic_floor_probability=float(params.llm_semantic_floor_probability),
    )


def _run_single_config(
    *,
    config_id: str,
    phase_label: str,
    run_index: int,
    params: SweepParameterSet,
    run_seed: int,
    run_turns: int,
    base_url: str,
    run_output_dir: Path,
    world: WorldConfig,
    storylet_count: int,
    diversity_every: int,
    diversity_chance: float,
    request_timeout_seconds: float,
    prefetch_wait_policy: str,
    prefetch_wait_timeout_seconds: float,
    switch_model: bool,
    model_id: str,
    hard_reset: bool,
    backend_mode: str,
    backend_startup_ms: float,
    quiet: bool,
) -> Dict[str, Any]:
    session_id = f"sweep-{phase_label}-{config_id}-{run_index:02d}-seed-{run_seed}"
    run_config = _build_run_config(
        base_url=base_url,
        output_dir=run_output_dir,
        world=world,
        session_id=session_id,
        turns=run_turns,
        seed=run_seed,
        storylet_count=storylet_count,
        diversity_every=diversity_every,
        diversity_chance=diversity_chance,
        request_timeout_seconds=request_timeout_seconds,
        prefetch_wait_policy=prefetch_wait_policy,
        prefetch_wait_timeout_seconds=prefetch_wait_timeout_seconds,
        switch_model=switch_model,
        model_id=model_id,
        hard_reset=hard_reset,
        params=params,
    )
    progress = None if quiet else print
    run_payload = run_long_playtest(
        run_config,
        DEFAULT_DIVERSITY_ACTIONS,
        continue_on_error=True,
        progress=progress,
    )
    report_json, report_md = persist_run_payload(
        run_payload,
        output_dir=run_output_dir,
        diversity_actions=DEFAULT_DIVERSITY_ACTIONS,
    )
    metrics = {
        "latency_ms_avg": float(run_payload.get("summary", {}).get("latency_ms_avg", 0.0)),
        "latency_ms_p95": float(run_payload.get("summary", {}).get("latency_ms_p95", 0.0)),
        "request_latency_ms_avg": float(run_payload.get("summary", {}).get("request_latency_ms_avg", 0.0)),
        "request_latency_ms_p95": float(run_payload.get("summary", {}).get("request_latency_ms_p95", 0.0)),
        "prefetch_wait_ms_total": float(run_payload.get("summary", {}).get("prefetch_wait_ms_total", 0.0)),
        "prefetch_wait_ms_avg": float(run_payload.get("summary", {}).get("prefetch_wait_ms_avg", 0.0)),
        "prefetch_wait_ms_p95": float(run_payload.get("summary", {}).get("prefetch_wait_ms_p95", 0.0)),
        "turn_wallclock_ms_avg": float(run_payload.get("summary", {}).get("turn_wallclock_ms_avg", 0.0)),
        "turn_wallclock_ms_p95": float(run_payload.get("summary", {}).get("turn_wallclock_ms_p95", 0.0)),
        "harness_overhead_ms_total": float(run_payload.get("summary", {}).get("harness_overhead_ms_total", 0.0)),
        "harness_overhead_ms_avg_per_request": float(run_payload.get("summary", {}).get("harness_overhead_ms_avg_per_request", 0.0)),
        "switch_model_ms": float(run_payload.get("summary", {}).get("switch_model_ms", 0.0)),
        "hard_reset_ms": float(run_payload.get("summary", {}).get("hard_reset_ms", 0.0)),
        "bootstrap_ms": float(run_payload.get("summary", {}).get("bootstrap_ms", 0.0)),
        "setup_total_ms": float(run_payload.get("summary", {}).get("setup_total_ms", 0.0)),
        "non_setup_non_prefetch_overhead_ms_total": float(run_payload.get("summary", {}).get("non_setup_non_prefetch_overhead_ms_total", 0.0)),
        "elapsed_ms": float(run_payload.get("summary", {}).get("elapsed_ms", 0.0)),
        "exact_prefix_match_rate": float(run_payload.get("summary", {}).get("exact_prefix_match_rate", 1.0)),
        "failure_rate": float(run_payload.get("summary", {}).get("failure_rate", 1.0)),
        "request_count": int(run_payload.get("summary", {}).get("request_count", 0)),
        "failed_request_count": int(run_payload.get("summary", {}).get("failed_request_count", 0)),
        "turns_completed": int(run_payload.get("summary", {}).get("turns_completed", 0)),
        "prefetch_wait_policy": str(run_payload.get("summary", {}).get("prefetch_wait_policy", prefetch_wait_policy)),
        "prefetch_wait_timeout_seconds": float(run_payload.get("summary", {}).get("prefetch_wait_timeout_seconds", prefetch_wait_timeout_seconds)),
        "backend_mode": str(backend_mode),
        "backend_startup_ms": float(backend_startup_ms),
    }
    return {
        "config_id": config_id,
        "phase": phase_label,
        "run_index": int(run_index),
        "seed": int(run_seed),
        "turns": int(run_turns),
        "session_id": session_id,
        "parameters": params.as_dict(),
        "metrics": metrics,
        "errors": list(run_payload.get("errors", [])),
        "report_json": _path_label(report_json),
        "report_md": _path_label(report_md),
    }


def _wait_for_backend(base_url: str, process: subprocess.Popen[Any], timeout_seconds: float) -> None:
    deadline = time.time() + float(timeout_seconds)
    readiness_url = f"{base_url.rstrip('/')}/settings/readiness"
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError("spawned backend exited before readiness checks passed")
        try:
            response = requests.get(readiness_url, timeout=1.5)
            if response.status_code < 500:
                return
        except Exception:
            pass
        time.sleep(0.4)
    raise RuntimeError(f"timed out waiting for backend readiness at {readiness_url}")


@contextmanager
def managed_backend(
    *,
    port: int,
    env_overrides: Dict[str, str],
    log_path: Path,
    startup_timeout: float,
) -> Iterator[tuple[str, float]]:
    base_url = f"http://127.0.0.1:{int(port)}/api"
    env = os.environ.copy()
    env.update(env_overrides)
    env["PYTHONUNBUFFERED"] = "1"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--port", str(int(port))],
            cwd=str(ROOT),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
        try:
            readiness_started = time.perf_counter()
            _wait_for_backend(base_url, process, startup_timeout)
            startup_ms = round((time.perf_counter() - readiness_started) * 1000.0, 3)
            yield base_url, startup_ms
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5.0)


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _coerce_parameter_set(raw: Dict[str, Any]) -> SweepParameterSet:
    return SweepParameterSet(
        llm_temperature=float(raw["llm_temperature"]),
        llm_max_tokens=int(raw["llm_max_tokens"]),
        llm_recency_penalty=float(raw["llm_recency_penalty"]),
        llm_semantic_floor_probability=float(raw["llm_semantic_floor_probability"]),
    )


def run_phase_a(args: argparse.Namespace, *, run_dir: Path, world: WorldConfig) -> Dict[str, Any]:
    configs = generate_phase_a_parameter_sets(count=int(args.phase_a_configs), seed=int(args.seed))
    runs_dir = run_dir / "phase_a" / "runs"
    logs_dir = run_dir / "phase_a" / "backend_logs"
    planned: List[Dict[str, Any]] = []
    results: List[Dict[str, Any]] = []

    for idx, params in enumerate(configs, start=1):
        config_id = f"a{idx:02d}"
        planned.append(
            {
                "config_id": config_id,
                "seed": int(args.seed + idx - 1),
                "turns": int(args.phase_a_turns),
                "parameters": params.as_dict(),
                "env_overrides": params.env_overrides(),
                "prefetch_wait_policy": str(args.prefetch_wait_policy),
                "prefetch_wait_timeout_seconds": float(args.prefetch_wait_timeout_seconds),
            }
        )
        if args.dry_run:
            continue

        print(f"[phase-a] running {config_id} ({idx}/{len(configs)})")
        seed_value = int(args.seed + idx - 1)
        if args.reuse_backend:
            base_url = str(args.base_url).rstrip("/")
            result = _run_single_config(
                config_id=config_id,
                phase_label="a",
                run_index=1,
                params=params,
                run_seed=seed_value,
                run_turns=int(args.phase_a_turns),
                base_url=base_url,
                run_output_dir=runs_dir,
                world=world,
                storylet_count=int(args.storylet_count),
                diversity_every=int(args.diversity_every),
                diversity_chance=float(args.diversity_chance),
                request_timeout_seconds=float(args.request_timeout_seconds),
                prefetch_wait_policy=str(args.prefetch_wait_policy),
                prefetch_wait_timeout_seconds=float(args.prefetch_wait_timeout_seconds),
                switch_model=bool(args.switch_model),
                model_id=str(args.model_id or ""),
                hard_reset=True,
                backend_mode="reuse",
                backend_startup_ms=0.0,
                quiet=bool(args.quiet),
            )
        else:
            log_path = logs_dir / f"{config_id}.log"
            with managed_backend(
                port=int(args.spawn_port),
                env_overrides=params.env_overrides(),
                log_path=log_path,
                startup_timeout=float(args.startup_timeout),
            ) as backend_context:
                spawned_base_url, backend_startup_ms = backend_context
                result = _run_single_config(
                    config_id=config_id,
                    phase_label="a",
                    run_index=1,
                    params=params,
                    run_seed=seed_value,
                    run_turns=int(args.phase_a_turns),
                    base_url=spawned_base_url,
                    run_output_dir=runs_dir,
                    world=world,
                    storylet_count=int(args.storylet_count),
                    diversity_every=int(args.diversity_every),
                    diversity_chance=float(args.diversity_chance),
                    request_timeout_seconds=float(args.request_timeout_seconds),
                    prefetch_wait_policy=str(args.prefetch_wait_policy),
                    prefetch_wait_timeout_seconds=float(args.prefetch_wait_timeout_seconds),
                    switch_model=bool(args.switch_model),
                    model_id=str(args.model_id or ""),
                    hard_reset=True,
                    backend_mode="spawn",
                    backend_startup_ms=float(backend_startup_ms),
                    quiet=bool(args.quiet),
                )
        results.append(result)

    ranked = rank_phase_results(results)
    top_count = max(3, min(5, int(args.phase_b_top_k)))
    top_candidates = ranked[:top_count]

    summary = {
        "phase": "a",
        "timestamp_utc": _utc_now(),
        "commit": _git_commit(),
        "dry_run": bool(args.dry_run),
        "scenario": asdict(world),
        "base_url": str(args.base_url).rstrip("/"),
        "reuse_backend": bool(args.reuse_backend),
        "spawn_port": int(args.spawn_port),
        "request_timeout_seconds": float(args.request_timeout_seconds),
        "prefetch_wait_policy": str(args.prefetch_wait_policy),
        "prefetch_wait_timeout_seconds": float(args.prefetch_wait_timeout_seconds),
        "planned": planned,
        "results": ranked,
        "top_candidates": top_candidates,
        "overhead_diagnostics": _phase_overhead_diagnostics(ranked),
    }

    summary_path = run_dir / "phase_a_summary.json"
    _write_json(summary_path, summary)
    print(f"[phase-a] summary: {_path_label(summary_path)}")
    return summary


def _aggregate_phase_b_metrics(runs: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    if not runs:
        return {
            "latency_ms_avg": 0.0,
            "latency_ms_p95": 0.0,
            "request_latency_ms_avg": 0.0,
            "request_latency_ms_p95": 0.0,
            "prefetch_wait_ms_total": 0.0,
            "prefetch_wait_ms_avg": 0.0,
            "prefetch_wait_ms_p95": 0.0,
            "turn_wallclock_ms_avg": 0.0,
            "turn_wallclock_ms_p95": 0.0,
            "harness_overhead_ms_total": 0.0,
            "harness_overhead_ms_avg_per_request": 0.0,
            "switch_model_ms": 0.0,
            "hard_reset_ms": 0.0,
            "bootstrap_ms": 0.0,
            "setup_total_ms": 0.0,
            "non_setup_non_prefetch_overhead_ms_total": 0.0,
            "exact_prefix_match_rate": 1.0,
            "failure_rate": 1.0,
        }

    def average(values: Sequence[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / float(len(values))

    latency_avg = average([float(run["metrics"]["latency_ms_avg"]) for run in runs])
    latency_p95 = average([float(run["metrics"]["latency_ms_p95"]) for run in runs])
    request_latency_avg = average([float(run["metrics"].get("request_latency_ms_avg", 0.0)) for run in runs])
    request_latency_p95 = average([float(run["metrics"].get("request_latency_ms_p95", 0.0)) for run in runs])
    prefetch_wait_total = average([float(run["metrics"].get("prefetch_wait_ms_total", 0.0)) for run in runs])
    prefetch_wait_avg = average([float(run["metrics"].get("prefetch_wait_ms_avg", 0.0)) for run in runs])
    prefetch_wait_p95 = average([float(run["metrics"].get("prefetch_wait_ms_p95", 0.0)) for run in runs])
    turn_wallclock_avg = average([float(run["metrics"].get("turn_wallclock_ms_avg", 0.0)) for run in runs])
    turn_wallclock_p95 = average([float(run["metrics"].get("turn_wallclock_ms_p95", 0.0)) for run in runs])
    harness_overhead_total = average([float(run["metrics"].get("harness_overhead_ms_total", 0.0)) for run in runs])
    harness_overhead_avg_per_request = average([float(run["metrics"].get("harness_overhead_ms_avg_per_request", 0.0)) for run in runs])
    switch_model_ms_avg = average([float(run["metrics"].get("switch_model_ms", 0.0)) for run in runs])
    hard_reset_ms_avg = average([float(run["metrics"].get("hard_reset_ms", 0.0)) for run in runs])
    bootstrap_ms_avg = average([float(run["metrics"].get("bootstrap_ms", 0.0)) for run in runs])
    setup_total_ms_avg = average([float(run["metrics"].get("setup_total_ms", 0.0)) for run in runs])
    non_setup_non_prefetch_overhead_total_avg = average([float(run["metrics"].get("non_setup_non_prefetch_overhead_ms_total", 0.0)) for run in runs])
    repetition = average([float(run["metrics"]["exact_prefix_match_rate"]) for run in runs])
    failure = average([float(run["metrics"]["failure_rate"]) for run in runs])
    return {
        "latency_ms_avg": round(latency_avg, 3),
        "latency_ms_p95": round(latency_p95, 3),
        "request_latency_ms_avg": round(request_latency_avg, 3),
        "request_latency_ms_p95": round(request_latency_p95, 3),
        "prefetch_wait_ms_total": round(prefetch_wait_total, 3),
        "prefetch_wait_ms_avg": round(prefetch_wait_avg, 3),
        "prefetch_wait_ms_p95": round(prefetch_wait_p95, 3),
        "turn_wallclock_ms_avg": round(turn_wallclock_avg, 3),
        "turn_wallclock_ms_p95": round(turn_wallclock_p95, 3),
        "harness_overhead_ms_total": round(harness_overhead_total, 3),
        "harness_overhead_ms_avg_per_request": round(harness_overhead_avg_per_request, 3),
        "switch_model_ms": round(switch_model_ms_avg, 3),
        "hard_reset_ms": round(hard_reset_ms_avg, 3),
        "bootstrap_ms": round(bootstrap_ms_avg, 3),
        "setup_total_ms": round(setup_total_ms_avg, 3),
        "non_setup_non_prefetch_overhead_ms_total": round(non_setup_non_prefetch_overhead_total_avg, 3),
        "exact_prefix_match_rate": round(repetition, 6),
        "failure_rate": round(failure, 6),
    }


def _phase_overhead_diagnostics(results: Sequence[Dict[str, Any]]) -> Dict[str, float | str]:
    if not results:
        return {
            "request_latency_ms_avg": 0.0,
            "prefetch_wait_ms_avg": 0.0,
            "turn_wallclock_ms_avg": 0.0,
            "harness_overhead_ms_total_avg": 0.0,
            "setup_total_ms_avg": 0.0,
            "bootstrap_ms_avg": 0.0,
            "hard_reset_ms_avg": 0.0,
            "switch_model_ms_avg": 0.0,
            "non_setup_non_prefetch_overhead_ms_total_avg": 0.0,
            "backend_startup_ms_avg": 0.0,
            "observed_backend_mode": "unknown",
        }

    metrics = [item.get("metrics", {}) for item in results]

    def average_from(key: str) -> float:
        values = [float(metric.get(key, 0.0)) for metric in metrics]
        if not values:
            return 0.0
        return sum(values) / float(len(values))

    backend_modes = {str(metric.get("backend_mode", "")).strip() for metric in metrics if str(metric.get("backend_mode", "")).strip()}
    return {
        "request_latency_ms_avg": round(average_from("request_latency_ms_avg"), 3),
        "prefetch_wait_ms_avg": round(average_from("prefetch_wait_ms_avg"), 3),
        "turn_wallclock_ms_avg": round(average_from("turn_wallclock_ms_avg"), 3),
        "harness_overhead_ms_total_avg": round(average_from("harness_overhead_ms_total"), 3),
        "setup_total_ms_avg": round(average_from("setup_total_ms"), 3),
        "bootstrap_ms_avg": round(average_from("bootstrap_ms"), 3),
        "hard_reset_ms_avg": round(average_from("hard_reset_ms"), 3),
        "switch_model_ms_avg": round(average_from("switch_model_ms"), 3),
        "non_setup_non_prefetch_overhead_ms_total_avg": round(average_from("non_setup_non_prefetch_overhead_ms_total"), 3),
        "backend_startup_ms_avg": round(average_from("backend_startup_ms"), 3),
        "observed_backend_mode": ",".join(sorted(backend_modes)) if backend_modes else "unknown",
    }


def _phase_b_candidates_from_summary(payload: Dict[str, Any], *, top_k: int) -> List[Dict[str, Any]]:
    candidates = list(payload.get("top_candidates", []))
    if not candidates:
        candidates = list(payload.get("results", []))
    if not candidates:
        for item in payload.get("planned", []):
            raw_params = item.get("parameters")
            if not isinstance(raw_params, dict):
                continue
            candidates.append(
                {
                    "config_id": str(item.get("config_id", "")),
                    "parameters": raw_params,
                    "metrics": {
                        "latency_ms_avg": 0.0,
                        "exact_prefix_match_rate": 1.0,
                        "failure_rate": 1.0,
                    },
                    "composite_score": 0.0,
                }
            )
    return candidates[:top_k]


def run_phase_b(
    args: argparse.Namespace,
    *,
    run_dir: Path,
    world: WorldConfig,
    phase_a_summary_path: Path,
) -> Dict[str, Any]:
    phase_a_payload = _load_json(phase_a_summary_path)
    top_k = max(3, min(5, int(args.phase_b_top_k)))
    candidates = _phase_b_candidates_from_summary(phase_a_payload, top_k=top_k)
    runs_per_config = max(1, int(args.phase_b_runs_per_config))
    phase_b_turns = int(args.phase_b_turns)
    runs_dir = run_dir / "phase_b" / "runs"
    logs_dir = run_dir / "phase_b" / "backend_logs"

    phase_b_results: List[Dict[str, Any]] = []
    for candidate_index, candidate in enumerate(candidates, start=1):
        config_id = str(candidate.get("config_id", f"b{candidate_index:02d}"))
        params = _coerce_parameter_set(candidate.get("parameters", {}))
        seed_base = int(args.seed + (candidate_index * 1000))
        per_seed_runs: List[Dict[str, Any]] = []

        print(f"[phase-b] analyzing {config_id} ({candidate_index}/{len(candidates)})")
        if args.dry_run:
            planned_seeds = [int(seed_base + offset) for offset in range(runs_per_config)]
            phase_b_results.append(
                {
                    "config_id": config_id,
                    "parameters": params.as_dict(),
                    "planned_seeds": planned_seeds,
                    "runs": [],
                    "aggregate_metrics": {
                        "latency_ms_avg": 0.0,
                        "latency_ms_p95": 0.0,
                        "request_latency_ms_avg": 0.0,
                        "request_latency_ms_p95": 0.0,
                        "prefetch_wait_ms_total": 0.0,
                        "prefetch_wait_ms_avg": 0.0,
                        "prefetch_wait_ms_p95": 0.0,
                        "turn_wallclock_ms_avg": 0.0,
                        "turn_wallclock_ms_p95": 0.0,
                        "harness_overhead_ms_total": 0.0,
                        "harness_overhead_ms_avg_per_request": 0.0,
                        "switch_model_ms": 0.0,
                        "hard_reset_ms": 0.0,
                        "bootstrap_ms": 0.0,
                        "setup_total_ms": 0.0,
                        "non_setup_non_prefetch_overhead_ms_total": 0.0,
                        "exact_prefix_match_rate": 1.0,
                        "failure_rate": 1.0,
                    },
                    "composite_score": 0.0,
                }
            )
            continue

        if args.reuse_backend:
            for run_offset in range(runs_per_config):
                run_seed = int(seed_base + run_offset)
                run_entry = _run_single_config(
                    config_id=config_id,
                    phase_label="b",
                    run_index=run_offset + 1,
                    params=params,
                    run_seed=run_seed,
                    run_turns=phase_b_turns,
                    base_url=str(args.base_url).rstrip("/"),
                    run_output_dir=runs_dir,
                    world=world,
                    storylet_count=int(args.storylet_count),
                    diversity_every=int(args.diversity_every),
                    diversity_chance=float(args.diversity_chance),
                    request_timeout_seconds=float(args.request_timeout_seconds),
                    prefetch_wait_policy=str(args.prefetch_wait_policy),
                    prefetch_wait_timeout_seconds=float(args.prefetch_wait_timeout_seconds),
                    switch_model=bool(args.switch_model),
                    model_id=str(args.model_id or ""),
                    hard_reset=True,
                    backend_mode="reuse",
                    backend_startup_ms=0.0,
                    quiet=bool(args.quiet),
                )
                per_seed_runs.append(run_entry)
        else:
            log_path = logs_dir / f"{config_id}.log"
            with managed_backend(
                port=int(args.spawn_port),
                env_overrides=params.env_overrides(),
                log_path=log_path,
                startup_timeout=float(args.startup_timeout),
            ) as backend_context:
                spawned_base_url, backend_startup_ms = backend_context
                for run_offset in range(runs_per_config):
                    run_seed = int(seed_base + run_offset)
                    run_entry = _run_single_config(
                        config_id=config_id,
                        phase_label="b",
                        run_index=run_offset + 1,
                        params=params,
                        run_seed=run_seed,
                        run_turns=phase_b_turns,
                        base_url=spawned_base_url,
                        run_output_dir=runs_dir,
                        world=world,
                        storylet_count=int(args.storylet_count),
                        diversity_every=int(args.diversity_every),
                        diversity_chance=float(args.diversity_chance),
                        request_timeout_seconds=float(args.request_timeout_seconds),
                        prefetch_wait_policy=str(args.prefetch_wait_policy),
                        prefetch_wait_timeout_seconds=float(args.prefetch_wait_timeout_seconds),
                        switch_model=bool(args.switch_model),
                        model_id=str(args.model_id or ""),
                        hard_reset=True,
                        backend_mode="spawn",
                        backend_startup_ms=float(backend_startup_ms),
                        quiet=bool(args.quiet),
                    )
                    per_seed_runs.append(run_entry)

        aggregate_metrics = _aggregate_phase_b_metrics(per_seed_runs)
        composite_score = score_run_metrics(
            latency_ms_avg=float(aggregate_metrics["latency_ms_avg"]),
            exact_prefix_match_rate=float(aggregate_metrics["exact_prefix_match_rate"]),
            failure_rate=float(aggregate_metrics["failure_rate"]),
        )
        phase_b_results.append(
            {
                "config_id": config_id,
                "parameters": params.as_dict(),
                "runs": per_seed_runs,
                "aggregate_metrics": aggregate_metrics,
                "composite_score": composite_score,
            }
        )

    ranked = sorted(
        phase_b_results,
        key=lambda item: (
            -float(item.get("composite_score", 0.0)),
            float(item.get("aggregate_metrics", {}).get("failure_rate", 1.0)),
            float(item.get("aggregate_metrics", {}).get("exact_prefix_match_rate", 1.0)),
            float(item.get("aggregate_metrics", {}).get("latency_ms_avg", float("inf"))),
        ),
    )
    top_count = max(3, min(5, int(args.phase_b_top_k)))
    summary = {
        "phase": "b",
        "timestamp_utc": _utc_now(),
        "commit": _git_commit(),
        "dry_run": bool(args.dry_run),
        "phase_a_summary": _path_label(phase_a_summary_path),
        "scenario": asdict(world),
        "runs_per_config": runs_per_config,
        "turns_per_run": phase_b_turns,
        "request_timeout_seconds": float(args.request_timeout_seconds),
        "prefetch_wait_policy": str(args.prefetch_wait_policy),
        "prefetch_wait_timeout_seconds": float(args.prefetch_wait_timeout_seconds),
        "results": ranked,
        "recommended_configs": ranked[:top_count],
        "overhead_diagnostics": _phase_overhead_diagnostics(ranked),
    }
    summary_path = run_dir / "phase_b_summary.json"
    _write_json(summary_path, summary)
    print(f"[phase-b] summary: {_path_label(summary_path)}")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run two-phase LLM parameter sweep harness.")
    parser.add_argument("--phase", choices=("a", "b", "both"), default="both")
    parser.add_argument("--phase-a-summary", type=Path, default=None)
    parser.add_argument("--phase-a-configs", type=int, default=PHASE_A_DEFAULT_CONFIGS)
    parser.add_argument("--phase-a-turns", type=int, default=PHASE_A_DEFAULT_TURNS)
    parser.add_argument("--phase-b-turns", type=int, default=PHASE_B_DEFAULT_TURNS)
    parser.add_argument("--phase-b-runs-per-config", type=int, default=PHASE_B_DEFAULT_RUNS_PER_CONFIG)
    parser.add_argument("--phase-b-top-k", type=int, default=PHASE_B_DEFAULT_TOP_K)
    parser.add_argument("--seed", type=int, default=20260305)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--reuse-backend", action="store_true")
    parser.add_argument("--spawn-port", type=int, default=8010)
    parser.add_argument("--startup-timeout", type=float, default=45.0)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS.keys()), default="cyberpunk")
    parser.add_argument("--role", default=None)
    parser.add_argument("--theme", default=None)
    parser.add_argument("--description", default=None)
    parser.add_argument("--tone", default=None)
    parser.add_argument("--key-elements", default=None, help="Comma-separated list")
    parser.add_argument("--storylet-count", type=int, default=DEFAULT_STORYLET_COUNT)
    parser.add_argument("--switch-model", action="store_true")
    parser.add_argument("--model-id", default="")
    parser.add_argument("--diversity-every", type=int, default=8)
    parser.add_argument("--diversity-chance", type=float, default=0.15)
    parser.add_argument("--request-timeout-seconds", type=float, default=240.0)
    parser.add_argument(
        "--prefetch-wait-policy",
        choices=PREFETCH_WAIT_POLICIES,
        default="bounded",
        help="Post-turn prefetch wait strategy during sweep runs.",
    )
    parser.add_argument(
        "--prefetch-wait-timeout-seconds",
        type=float,
        default=float(DEFAULT_PREFETCH_WAIT_TIMEOUT_SECONDS),
        help="Max seconds to wait per-turn when prefetch wait is enabled.",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if int(args.phase_a_configs) < 1:
        print("Error: --phase-a-configs must be >= 1", file=sys.stderr)
        return 2
    if int(args.phase_a_turns) < 1 or int(args.phase_b_turns) < 1:
        print("Error: turn counts must be >= 1", file=sys.stderr)
        return 2
    if int(args.storylet_count) < 5:
        print("Error: --storylet-count must be >= 5", file=sys.stderr)
        return 2
    if int(args.diversity_every) < 0:
        print("Error: --diversity-every must be >= 0", file=sys.stderr)
        return 2
    if not 0.0 <= float(args.diversity_chance) <= 1.0:
        print("Error: --diversity-chance must be in [0, 1]", file=sys.stderr)
        return 2
    if float(args.request_timeout_seconds) < 5.0:
        print("Error: --request-timeout-seconds must be >= 5", file=sys.stderr)
        return 2
    if float(args.prefetch_wait_timeout_seconds) < 0.0:
        print("Error: --prefetch-wait-timeout-seconds must be >= 0", file=sys.stderr)
        return 2

    run_dir = (ROOT / args.out_dir).resolve() / _timestamp_slug()
    world = _resolve_world_config(args)
    print(f"[sweep] run dir: {_path_label(run_dir)}")
    print(f"[sweep] phase: {args.phase}")
    print(f"[sweep] scenario: {world.scenario_id} ({world.scenario_title})")
    print(f"[sweep] backend mode: {'reuse' if args.reuse_backend else 'spawn-per-config'}")
    print(f"[sweep] request timeout seconds: {float(args.request_timeout_seconds)}")
    print(f"[sweep] prefetch wait policy: {args.prefetch_wait_policy}")
    print(f"[sweep] prefetch wait timeout seconds: {float(args.prefetch_wait_timeout_seconds)}")

    phase_a_summary_payload: Dict[str, Any] | None = None
    phase_a_summary_path: Path | None = None

    try:
        if args.phase in {"a", "both"}:
            phase_a_summary_payload = run_phase_a(args, run_dir=run_dir, world=world)
            phase_a_summary_path = run_dir / "phase_a_summary.json"

        if args.phase in {"b", "both"}:
            if args.phase == "b":
                if args.phase_a_summary is None:
                    print("Error: --phase-a-summary is required when --phase b is selected", file=sys.stderr)
                    return 2
                phase_a_summary_path = (args.phase_a_summary if args.phase_a_summary.is_absolute() else (ROOT / args.phase_a_summary)).resolve()
                if not phase_a_summary_path.exists():
                    print(f"Error: phase A summary not found: {phase_a_summary_path}", file=sys.stderr)
                    return 2
            assert phase_a_summary_path is not None
            run_phase_b(
                args,
                run_dir=run_dir,
                world=world,
                phase_a_summary_path=phase_a_summary_path,
            )

    except Exception as exc:
        print(f"[sweep] failed: {exc}", file=sys.stderr)
        return 1

    manifest = {
        "timestamp_utc": _utc_now(),
        "commit": _git_commit(),
        "phase": args.phase,
        "run_dir": _path_label(run_dir),
        "phase_a_summary": _path_label(run_dir / "phase_a_summary.json") if (run_dir / "phase_a_summary.json").exists() else None,
        "phase_b_summary": _path_label(run_dir / "phase_b_summary.json") if (run_dir / "phase_b_summary.json").exists() else None,
        "dry_run": bool(args.dry_run),
        "reuse_backend": bool(args.reuse_backend),
        "request_timeout_seconds": float(args.request_timeout_seconds),
        "prefetch_wait_policy": str(args.prefetch_wait_policy),
        "prefetch_wait_timeout_seconds": float(args.prefetch_wait_timeout_seconds),
    }
    manifest_path = run_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    print(f"[sweep] manifest: {_path_label(manifest_path)}")
    if phase_a_summary_payload is not None and args.phase == "a" and args.dry_run:
        print(f"[sweep] planned configs: {len(phase_a_summary_payload.get('planned', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
