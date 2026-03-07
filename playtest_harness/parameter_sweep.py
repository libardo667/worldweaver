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
from itertools import product
from pathlib import Path
from typing import Any, Dict, Iterator, List, Sequence

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playtest_harness.long_run_harness import (
    CLARITY_LEVEL_ORDER,
    CLARITY_HEALTH_THRESHOLD,
    DEFAULT_BASE_URL,
    DEFAULT_DIVERSITY_ACTIONS,
    DEFAULT_PREFETCH_WAIT_TIMEOUT_SECONDS,
    DEFAULT_STORYLET_COUNT,
    PREFETCH_WAIT_POLICIES,
    SCENARIOS,
    RunConfig,
    WorldConfig,
    build_parameter_env_overrides_from_values,
    clarity_distribution_score,
    clarity_health_check,
    persist_run_payload,
    run_long_playtest,
)

DEFAULT_OUT_DIR = Path("playtests") / "sweeps"
PHASE_A_DEFAULT_CONFIGS = 16
PHASE_A_DEFAULT_TURNS = 20
PHASE_B_DEFAULT_TURNS = 30
PHASE_B_DEFAULT_RUNS_PER_CONFIG = 3
PHASE_B_DEFAULT_TOP_K = 4

NARRATOR_TEMPERATURE_RANGE = (0.4, 1.2)
REFEREE_TEMPERATURE_RANGE = (0.0, 0.5)
MAX_TOKENS_RANGE = (900, 2800)
RECENCY_PENALTY_RANGE = (0.05, 0.85)
SEMANTIC_FLOOR_RANGE = (0.0, 0.25)
LANE_MATRIX_PRESET_OFF = "off"
LANE_MATRIX_PRESET_V3_DEFAULT = "v3-default"


@dataclass(frozen=True)
class SweepParameterSet:
    llm_narrator_temperature: float
    llm_referee_temperature: float
    llm_max_tokens: int
    llm_recency_penalty: float
    llm_semantic_floor_probability: float

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def env_overrides(self) -> Dict[str, str]:
        return build_parameter_env_overrides_from_values(
            llm_narrator_temperature=self.llm_narrator_temperature,
            llm_referee_temperature=self.llm_referee_temperature,
            llm_max_tokens=self.llm_max_tokens,
            llm_recency_penalty=self.llm_recency_penalty,
            llm_semantic_floor_probability=self.llm_semantic_floor_probability,
        )


@dataclass(frozen=True)
class LaneBudgetVariant:
    llm_narrator_model: str | None = None
    llm_referee_model: str | None = None
    v3_projection_max_depth: int | None = None
    v3_projection_max_nodes: int | None = None
    v3_projection_time_budget_ms: int | None = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def env_overrides(self) -> Dict[str, str]:
        return build_parameter_env_overrides_from_values(
            llm_narrator_model=self.llm_narrator_model,
            llm_referee_model=self.llm_referee_model,
            v3_projection_max_depth=self.v3_projection_max_depth,
            v3_projection_max_nodes=self.v3_projection_max_nodes,
            v3_projection_time_budget_ms=self.v3_projection_time_budget_ms,
        )


def _split_csv_values(raw: str | None) -> List[str]:
    if raw is None:
        return []
    values = [part.strip() for part in str(raw).split(",")]
    return [value for value in values if value]


def _split_int_csv_values(raw: str | None) -> List[int]:
    out: List[int] = []
    for item in _split_csv_values(raw):
        out.append(int(item))
    return out


def _dedupe_preserve_order(values: Sequence[Any]) -> List[Any]:
    out: List[Any] = []
    seen: set[str] = set()
    for value in values:
        marker = json.dumps(value, sort_keys=True, default=str)
        if marker in seen:
            continue
        seen.add(marker)
        out.append(value)
    return out


def _normalize_model_axis(values: Sequence[str]) -> List[str | None]:
    if not values:
        return [None]
    normalized: List[str | None] = []
    for raw in values:
        cleaned = str(raw or "").strip()
        normalized.append(cleaned or None)
    return [item for item in _dedupe_preserve_order(normalized)]


def _resolve_lane_budget_variants(args: argparse.Namespace) -> List[LaneBudgetVariant]:
    cached_variants = getattr(args, "_resolved_lane_budget_variants", None)
    if isinstance(cached_variants, list) and cached_variants:
        output: List[LaneBudgetVariant] = []
        for item in cached_variants:
            if isinstance(item, LaneBudgetVariant):
                output.append(item)
        if output:
            return output

    narrator_values_raw = _split_csv_values(getattr(args, "lane_narrator_models", None))
    referee_values_raw = _split_csv_values(getattr(args, "lane_referee_models", None))
    depth_values = _split_int_csv_values(getattr(args, "projection_depth_options", None))
    node_values = _split_int_csv_values(getattr(args, "projection_node_options", None))
    time_values = _split_int_csv_values(getattr(args, "projection_time_budget_ms_options", None))
    preset = str(getattr(args, "lane_matrix_preset", LANE_MATRIX_PRESET_OFF) or LANE_MATRIX_PRESET_OFF).strip().lower()

    if preset == LANE_MATRIX_PRESET_V3_DEFAULT:
        if not narrator_values_raw:
            narrator_values_raw = _dedupe_preserve_order(
                [
                    os.environ.get("LLM_NARRATOR_MODEL", "").strip(),
                    os.environ.get("LLM_MODEL", "").strip(),
                    "",
                ]
            )
        if not referee_values_raw:
            referee_values_raw = _dedupe_preserve_order(
                [
                    os.environ.get("LLM_REFEREE_MODEL", "").strip(),
                    os.environ.get("LLM_MODEL", "").strip(),
                    "",
                ]
            )
        if not depth_values:
            depth_values = [2, 3]
        if not node_values:
            node_values = [12, 18]
        if not time_values:
            time_values = [120, 220]

    narrator_values = _normalize_model_axis(narrator_values_raw)
    referee_values = _normalize_model_axis(referee_values_raw)
    projection_depth_values: List[int | None] = [int(value) for value in depth_values] if depth_values else [None]
    projection_node_values: List[int | None] = [int(value) for value in node_values] if node_values else [None]
    projection_time_values: List[int | None] = [int(value) for value in time_values] if time_values else [None]

    variants: List[LaneBudgetVariant] = []
    for narrator_model, referee_model, depth, nodes, time_budget in product(
        narrator_values,
        referee_values,
        projection_depth_values,
        projection_node_values,
        projection_time_values,
    ):
        variants.append(
            LaneBudgetVariant(
                llm_narrator_model=narrator_model,
                llm_referee_model=referee_model,
                v3_projection_max_depth=depth,
                v3_projection_max_nodes=nodes,
                v3_projection_time_budget_ms=time_budget,
            )
        )

    deduped = _dedupe_preserve_order(variants)
    return [item for item in deduped if isinstance(item, LaneBudgetVariant)] or [LaneBudgetVariant()]


def _build_seed_schedule(*, seed_base: int, runs_per_config: int) -> List[int]:
    return [int(seed_base + offset) for offset in range(max(1, int(runs_per_config)))]


def _extract_row_seeds(row: Dict[str, Any]) -> List[int]:
    if isinstance(row.get("runs"), list):
        seeds: List[int] = []
        for run in row.get("runs", []):
            if isinstance(run, dict) and "seed" in run:
                seeds.append(int(run.get("seed")))
        if seeds:
            return seeds
    if isinstance(row.get("planned_seeds"), list):
        return [int(seed) for seed in row.get("planned_seeds", [])]
    if "seed" in row:
        return [int(row.get("seed"))]
    return []


def _validate_shared_seed_schedule(rows: Sequence[Dict[str, Any]], expected: Sequence[int], *, context: str) -> None:
    normalized_expected = [int(seed) for seed in expected]
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_seeds = _extract_row_seeds(row)
        if row_seeds and row_seeds != normalized_expected:
            raise ValueError(f"{context} seed schedule mismatch for config_id={row.get('config_id', 'unknown')}: " f"expected={normalized_expected}, actual={row_seeds}")


def _validate_per_run_seed_sequence(runs: Sequence[Dict[str, Any]], expected: Sequence[int], *, context: str, config_id: str) -> None:
    normalized_expected = [int(seed) for seed in expected]
    actual: List[int] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        if "seed" not in run:
            continue
        actual.append(int(run.get("seed")))
    if actual and actual != normalized_expected:
        raise ValueError(f"{context} seed schedule mismatch for config_id={config_id}: " f"expected={normalized_expected}, actual={actual}")


def _lane_budget_axes_payload(variants: Sequence[LaneBudgetVariant]) -> Dict[str, Any]:
    narrator_models = _dedupe_preserve_order([item.llm_narrator_model for item in variants if item.llm_narrator_model])
    referee_models = _dedupe_preserve_order([item.llm_referee_model for item in variants if item.llm_referee_model])
    projection_depths = _dedupe_preserve_order([item.v3_projection_max_depth for item in variants if item.v3_projection_max_depth is not None])
    projection_nodes = _dedupe_preserve_order([item.v3_projection_max_nodes for item in variants if item.v3_projection_max_nodes is not None])
    projection_time_budgets = _dedupe_preserve_order([item.v3_projection_time_budget_ms for item in variants if item.v3_projection_time_budget_ms is not None])
    return {
        "variant_count": int(len(variants)),
        "llm_narrator_models": narrator_models,
        "llm_referee_models": referee_models,
        "v3_projection_max_depth_options": [int(value) for value in projection_depths],
        "v3_projection_max_nodes_options": [int(value) for value in projection_nodes],
        "v3_projection_time_budget_ms_options": [int(value) for value in projection_time_budgets],
    }


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
    narrator_temperatures = _latin_hypercube_column(
        count=count,
        rng=rng,
        minimum=NARRATOR_TEMPERATURE_RANGE[0],
        maximum=NARRATOR_TEMPERATURE_RANGE[1],
    )
    referee_temperatures = _latin_hypercube_column(
        count=count,
        rng=rng,
        minimum=REFEREE_TEMPERATURE_RANGE[0],
        maximum=REFEREE_TEMPERATURE_RANGE[1],
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
                llm_narrator_temperature=round(float(narrator_temperatures[idx]), 4),
                llm_referee_temperature=round(float(referee_temperatures[idx]), 4),
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
    prefix_soft_match_rate: float | None = None,
    motif_reuse_rate: float | None = None,
    failure_rate: float,
    projection_hit_rate: float | None = None,
    projection_waste_rate: float | None = None,
    clarity_distribution_score: float | None = None,
) -> float:
    """Compute composite quality score in [0, 1] for a sweep run (higher = better).

    Weights:
        failure:    0.50  (was 0.55 pre-major-111)
        repetition: 0.20  (was 0.25)
        motif:      0.05  (unchanged)
        latency:    0.05  (was 0.10 pre-minor-117)
        projection: 0.10  (was 0.15 pre-minor-117)
        clarity:    0.10  (new in minor-117 — direct V3 Pillar 3 signal)

    When projection_hit_rate and projection_waste_rate are both None the
    projection component defaults to 0.5 (neutral) so old callers are unaffected.

    When clarity_distribution_score is None the clarity component defaults to
    0.5 (neutral) so old callers without clarity data are unaffected.
    """
    clean_failure_rate = max(0.0, min(1.0, float(failure_rate)))
    clean_repetition_rate = max(0.0, min(1.0, float(exact_prefix_match_rate)))
    if prefix_soft_match_rate is None:
        clean_soft_repetition_rate = clean_repetition_rate
    else:
        clean_soft_repetition_rate = max(0.0, min(1.0, float(prefix_soft_match_rate)))
    if motif_reuse_rate is None:
        clean_motif_reuse_rate = clean_repetition_rate
    else:
        clean_motif_reuse_rate = max(0.0, min(1.0, float(motif_reuse_rate)))
    clean_latency = max(0.0, float(latency_ms_avg))
    repetition_signal = max(clean_repetition_rate, clean_soft_repetition_rate)

    failure_component = 1.0 - clean_failure_rate
    repetition_component = 1.0 - repetition_signal
    motif_component = 1.0 - clean_motif_reuse_rate
    latency_component = 1.0 / (1.0 + (clean_latency / 1200.0))

    if projection_hit_rate is None and projection_waste_rate is None:
        projection_component = 0.5
    else:
        clean_hit = max(0.0, min(1.0, float(projection_hit_rate if projection_hit_rate is not None else 0.0)))
        clean_waste = max(0.0, min(1.0, float(projection_waste_rate if projection_waste_rate is not None else 1.0)))
        projection_penalty = (clean_waste * 0.60) + ((1.0 - clean_hit) * 0.40)
        projection_component = 1.0 - projection_penalty

    if clarity_distribution_score is None:
        clarity_component = 0.5
    else:
        clarity_component = max(0.0, min(1.0, float(clarity_distribution_score)))

    return round(
        (failure_component * 0.50) + (repetition_component * 0.20) + (motif_component * 0.05) + (latency_component * 0.05) + (projection_component * 0.10) + (clarity_component * 0.10),
        6,
    )


def motif_penalty_score(
    *,
    motif_reuse_rate: float,
    motif_turn_overlap_rate_avg: float,
) -> float:
    clean_reuse_rate = max(0.0, min(1.0, float(motif_reuse_rate)))
    clean_turn_overlap = max(0.0, min(1.0, float(motif_turn_overlap_rate_avg)))
    return round((0.6 * clean_reuse_rate) + (0.4 * clean_turn_overlap), 6)


def _rank_phase_results_by_motif_penalty(results: Sequence[Dict[str, Any]], *, metrics_key: str = "metrics") -> List[Dict[str, Any]]:
    return sorted(
        list(results),
        key=lambda item: (
            float(item.get(metrics_key, {}).get("motif_penalty_score", float("inf"))),
            float(item.get(metrics_key, {}).get("failure_rate", 1.0)),
            float(item.get(metrics_key, {}).get("latency_ms_avg", float("inf"))),
            str(item.get("config_id", "")),
        ),
    )


def _projection_penalty_score(metrics: Dict[str, Any]) -> float:
    hit_rate = max(0.0, min(1.0, float(metrics.get("projection_hit_rate", 0.0))))
    waste_rate = max(0.0, min(1.0, float(metrics.get("projection_waste_rate", 1.0))))
    veto_rate = max(0.0, min(1.0, float(metrics.get("projection_veto_rate", 1.0))))
    return round((waste_rate * 0.45) + (veto_rate * 0.35) + ((1.0 - hit_rate) * 0.20), 6)


def _rank_phase_results_by_projection_efficiency(
    results: Sequence[Dict[str, Any]],
    *,
    metrics_key: str = "metrics",
) -> List[Dict[str, Any]]:
    return sorted(
        list(results),
        key=lambda item: (
            _projection_penalty_score(item.get(metrics_key, {})),
            float(item.get(metrics_key, {}).get("failure_rate", 1.0)),
            float(item.get(metrics_key, {}).get("latency_ms_avg", float("inf"))),
            str(item.get("config_id", "")),
        ),
    )


def _rank_phase_results_by_latency_reliability(
    results: Sequence[Dict[str, Any]],
    *,
    metrics_key: str = "metrics",
) -> List[Dict[str, Any]]:
    return sorted(
        list(results),
        key=lambda item: (
            float(item.get(metrics_key, {}).get("failure_rate", 1.0)),
            float(item.get(metrics_key, {}).get("latency_ms_avg", float("inf"))),
            float(item.get(metrics_key, {}).get("latency_ms_p95", float("inf"))),
            str(item.get("config_id", "")),
        ),
    )


def check_run_projection_health(metrics: Dict[str, Any], turn_count: int = 0) -> List[str]:
    """Return a list of warning strings for degenerate projection behavior in a run.

    Warnings are informational only — they do not disqualify configs from Phase B.
    """
    warnings: List[str] = []
    waste_rate = max(0.0, min(1.0, float(metrics.get("projection_waste_rate", 0.0))))
    hit_rate = max(0.0, min(1.0, float(metrics.get("projection_hit_rate", 0.0))))
    dist = metrics.get("clarity_level_distribution", {})
    if waste_rate > 0.90:
        warnings.append(f"projection_waste_rate={waste_rate:.2f} > 0.90 threshold (prefetch nearly never used)")
    if isinstance(dist, dict):
        prepared = int(dist.get("prepared", 0) or 0)
        committed = int(dist.get("committed", 0) or 0)
        total = sum(int(dist.get(level, 0) or 0) for level in CLARITY_LEVEL_ORDER)
        if total > 0 and prepared == 0 and committed == 0:
            warnings.append("no turns reached prepared or committed clarity level")
    if int(turn_count) > 10 and hit_rate == 0.0:
        warnings.append(f"projection_hit_rate=0.0 for {int(turn_count)} turns")
    return warnings


def _rank_phase_results_by_clarity(
    results: "Sequence[Dict[str, Any]]",
    *,
    metrics_key: str = "metrics",
) -> "List[Dict[str, Any]]":
    return sorted(
        list(results),
        key=lambda item: (
            -clarity_distribution_score(item.get(metrics_key, {}).get("clarity_level_distribution", {})),
            float(item.get(metrics_key, {}).get("failure_rate", 1.0)),
            float(item.get(metrics_key, {}).get("latency_ms_avg", float("inf"))),
            str(item.get("config_id", "")),
        ),
    )


def _repetition_signal(metrics: Dict[str, Any]) -> float:
    exact_repetition = float(metrics.get("exact_prefix_match_rate", 0.0))
    soft_repetition = float(metrics.get("prefix_soft_match_rate", exact_repetition))
    clean_exact = max(0.0, min(1.0, exact_repetition))
    clean_soft = max(0.0, min(1.0, soft_repetition))
    return max(clean_exact, clean_soft)


def rank_phase_results(results: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for item in results:
        metrics = item.get("metrics", {})
        latency = float(metrics.get("latency_ms_avg", 0.0))
        repetition = float(metrics.get("exact_prefix_match_rate", 0.0))
        prefix_soft_repetition = float(metrics.get("prefix_soft_match_rate", repetition))
        motif_reuse = float(metrics.get("motif_reuse_rate", repetition))
        failure = float(metrics.get("failure_rate", 1.0))
        proj_hit = metrics.get("projection_hit_rate")
        proj_waste = metrics.get("projection_waste_rate")
        scored = dict(item)
        raw_clarity = metrics.get("clarity_distribution_score")
        scored["composite_score"] = score_run_metrics(
            latency_ms_avg=latency,
            exact_prefix_match_rate=repetition,
            prefix_soft_match_rate=prefix_soft_repetition,
            motif_reuse_rate=motif_reuse,
            failure_rate=failure,
            projection_hit_rate=float(proj_hit) if proj_hit is not None else None,
            projection_waste_rate=float(proj_waste) if proj_waste is not None else None,
            clarity_distribution_score=float(raw_clarity) if raw_clarity is not None else None,
        )
        enriched.append(scored)

    return sorted(
        enriched,
        key=lambda item: (
            -float(item.get("composite_score", 0.0)),
            float(item.get("metrics", {}).get("failure_rate", 1.0)),
            float(item.get("metrics", {}).get("motif_reuse_rate", item.get("metrics", {}).get("exact_prefix_match_rate", 1.0))),
            _repetition_signal(item.get("metrics", {})),
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
    verify_clean_reset: bool,
    switch_model: bool,
    model_id: str,
    hard_reset: bool,
    params: SweepParameterSet,
    lane_budget: LaneBudgetVariant,
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
        verify_clean_reset=bool(verify_clean_reset),
        llm_temperature=None,
        llm_narrator_temperature=float(params.llm_narrator_temperature),
        llm_referee_temperature=float(params.llm_referee_temperature),
        llm_max_tokens=int(params.llm_max_tokens),
        llm_recency_penalty=float(params.llm_recency_penalty),
        llm_semantic_floor_probability=float(params.llm_semantic_floor_probability),
        llm_narrator_model=lane_budget.llm_narrator_model,
        llm_referee_model=lane_budget.llm_referee_model,
        v3_projection_max_depth=lane_budget.v3_projection_max_depth,
        v3_projection_max_nodes=lane_budget.v3_projection_max_nodes,
        v3_projection_time_budget_ms=lane_budget.v3_projection_time_budget_ms,
    )


def _run_single_config(
    *,
    config_id: str,
    phase_label: str,
    run_index: int,
    params: SweepParameterSet,
    lane_budget: LaneBudgetVariant,
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
    verify_clean_reset: bool,
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
        verify_clean_reset=verify_clean_reset,
        switch_model=switch_model,
        model_id=model_id,
        hard_reset=hard_reset,
        params=params,
        lane_budget=lane_budget,
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
    summary_payload = run_payload.get("summary", {})
    clarity_distribution_raw = summary_payload.get("clarity_level_distribution", {})
    if not isinstance(clarity_distribution_raw, dict):
        clarity_distribution_raw = {}
    clarity_distribution = {level: int(clarity_distribution_raw.get(level, 0) or 0) for level in CLARITY_LEVEL_ORDER}
    metrics = {
        "latency_ms_avg": float(summary_payload.get("latency_ms_avg", 0.0)),
        "latency_ms_p95": float(summary_payload.get("latency_ms_p95", 0.0)),
        "request_latency_ms_avg": float(summary_payload.get("request_latency_ms_avg", 0.0)),
        "request_latency_ms_p95": float(summary_payload.get("request_latency_ms_p95", 0.0)),
        "prefetch_wait_ms_total": float(summary_payload.get("prefetch_wait_ms_total", 0.0)),
        "prefetch_wait_ms_avg": float(summary_payload.get("prefetch_wait_ms_avg", 0.0)),
        "prefetch_wait_ms_p95": float(summary_payload.get("prefetch_wait_ms_p95", 0.0)),
        "turn_wallclock_ms_avg": float(summary_payload.get("turn_wallclock_ms_avg", 0.0)),
        "turn_wallclock_ms_p95": float(summary_payload.get("turn_wallclock_ms_p95", 0.0)),
        "harness_overhead_ms_total": float(summary_payload.get("harness_overhead_ms_total", 0.0)),
        "harness_overhead_ms_avg_per_request": float(summary_payload.get("harness_overhead_ms_avg_per_request", 0.0)),
        "switch_model_ms": float(summary_payload.get("switch_model_ms", 0.0)),
        "hard_reset_ms": float(summary_payload.get("hard_reset_ms", 0.0)),
        "bootstrap_ms": float(summary_payload.get("bootstrap_ms", 0.0)),
        "setup_total_ms": float(summary_payload.get("setup_total_ms", 0.0)),
        "non_setup_non_prefetch_overhead_ms_total": float(summary_payload.get("non_setup_non_prefetch_overhead_ms_total", 0.0)),
        "elapsed_ms": float(summary_payload.get("elapsed_ms", 0.0)),
        "exact_prefix_match_rate": float(summary_payload.get("exact_prefix_match_rate", 1.0)),
        "prefix_soft_match_rate": float(summary_payload.get("prefix_soft_match_rate", summary_payload.get("exact_prefix_match_rate", 1.0))),
        "prefix_similarity_avg": float(summary_payload.get("prefix_similarity_avg", 0.0)),
        "prefix_similarity_p95": float(summary_payload.get("prefix_similarity_p95", 0.0)),
        "motif_turns_with_tokens": int(summary_payload.get("motif_turns_with_tokens", 0)),
        "motif_total_tokens": int(summary_payload.get("motif_total_tokens", 0)),
        "motif_unique_tokens": int(summary_payload.get("motif_unique_tokens", 0)),
        "motif_overlap_count": int(summary_payload.get("motif_overlap_count", 0)),
        "motif_reused_tokens": int(summary_payload.get("motif_reused_tokens", 0)),
        "motif_reuse_rate": float(summary_payload.get("motif_reuse_rate", 0.0)),
        "motif_novelty_rate": float(summary_payload.get("motif_novelty_rate", 0.0)),
        "motif_turn_overlap_rate_avg": float(summary_payload.get("motif_turn_overlap_rate_avg", 0.0)),
        "projection_stub_count": float(summary_payload.get("projection_stub_count", 0.0)),
        "projection_hit_rate": float(summary_payload.get("projection_hit_rate", 0.0)),
        "projection_waste_rate": float(summary_payload.get("projection_waste_rate", 0.0)),
        "projection_veto_rate": float(summary_payload.get("projection_veto_rate", 0.0)),
        "clarity_level_distribution": clarity_distribution,
        "fallback_reason_distribution": dict(summary_payload.get("fallback_reason_distribution", {})) if isinstance(summary_payload.get("fallback_reason_distribution", {}), dict) else {},
        "stratified_metrics": dict(summary_payload.get("stratified_metrics", {})) if isinstance(summary_payload.get("stratified_metrics", {}), dict) else {},
        "clarity_distribution_score": float(summary_payload.get("clarity_distribution_score", 0.0)),
        "clarity_health_warning": str(summary_payload.get("clarity_health_warning", "") or ""),
        "failure_rate": float(summary_payload.get("failure_rate", 1.0)),
        "request_count": int(summary_payload.get("request_count", 0)),
        "failed_request_count": int(summary_payload.get("failed_request_count", 0)),
        "turns_completed": int(summary_payload.get("turns_completed", 0)),
        "prefetch_wait_policy": str(summary_payload.get("prefetch_wait_policy", prefetch_wait_policy)),
        "prefetch_wait_timeout_seconds": float(summary_payload.get("prefetch_wait_timeout_seconds", prefetch_wait_timeout_seconds)),
        "backend_mode": str(backend_mode),
        "backend_startup_ms": float(backend_startup_ms),
    }
    metrics["motif_penalty_score"] = motif_penalty_score(
        motif_reuse_rate=float(metrics.get("motif_reuse_rate", 0.0)),
        motif_turn_overlap_rate_avg=float(metrics.get("motif_turn_overlap_rate_avg", 0.0)),
    )
    return {
        "config_id": config_id,
        "phase": phase_label,
        "run_index": int(run_index),
        "seed": int(run_seed),
        "turns": int(run_turns),
        "session_id": session_id,
        "parameters": params.as_dict(),
        "lane_budget": lane_budget.as_dict(),
        "lane_budget_env_overrides": lane_budget.env_overrides(),
        "metrics": metrics,
        "projection_health_warnings": check_run_projection_health(
            metrics,
            turn_count=int(metrics.get("turns_completed", int(run_turns))),
        ),
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
        llm_narrator_temperature=float(raw["llm_narrator_temperature"]),
        llm_referee_temperature=float(raw["llm_referee_temperature"]),
        llm_max_tokens=int(raw["llm_max_tokens"]),
        llm_recency_penalty=float(raw["llm_recency_penalty"]),
        llm_semantic_floor_probability=float(raw["llm_semantic_floor_probability"]),
    )


def _coerce_lane_budget_variant(raw: Dict[str, Any] | None) -> LaneBudgetVariant:
    payload = raw if isinstance(raw, dict) else {}
    narrator_model = str(payload.get("llm_narrator_model", "") or "").strip() or None
    referee_model = str(payload.get("llm_referee_model", "") or "").strip() or None
    depth = payload.get("v3_projection_max_depth")
    nodes = payload.get("v3_projection_max_nodes")
    time_budget = payload.get("v3_projection_time_budget_ms")
    return LaneBudgetVariant(
        llm_narrator_model=narrator_model,
        llm_referee_model=referee_model,
        v3_projection_max_depth=(int(depth) if depth is not None else None),
        v3_projection_max_nodes=(int(nodes) if nodes is not None else None),
        v3_projection_time_budget_ms=(int(time_budget) if time_budget is not None else None),
    )


def run_phase_a(args: argparse.Namespace, *, run_dir: Path, world: WorldConfig) -> Dict[str, Any]:
    configs = generate_phase_a_parameter_sets(count=int(args.phase_a_configs), seed=int(args.seed))
    lane_budget_variants = _resolve_lane_budget_variants(args)
    lane_budget_axes = _lane_budget_axes_payload(lane_budget_variants)
    seed_schedule = _build_seed_schedule(seed_base=int(args.seed), runs_per_config=1)
    runs_dir = run_dir / "phase_a" / "runs"
    logs_dir = run_dir / "phase_a" / "backend_logs"
    planned: List[Dict[str, Any]] = []
    results: List[Dict[str, Any]] = []

    for idx, params in enumerate(configs, start=1):
        config_id = f"a{idx:02d}"
        lane_budget = lane_budget_variants[(idx - 1) % len(lane_budget_variants)]
        env_overrides = {
            **params.env_overrides(),
            **lane_budget.env_overrides(),
        }
        planned.append(
            {
                "config_id": config_id,
                "seed": int(args.seed),
                "seed_schedule": list(seed_schedule),
                "turns": int(args.phase_a_turns),
                "parameters": params.as_dict(),
                "lane_budget": lane_budget.as_dict(),
                "env_overrides": env_overrides,
                "prefetch_wait_policy": str(args.prefetch_wait_policy),
                "prefetch_wait_timeout_seconds": float(args.prefetch_wait_timeout_seconds),
            }
        )
        if args.dry_run:
            continue

        print(f"[phase-a] running {config_id} ({idx}/{len(configs)})")
        # Head-to-head tuning: keep RNG seed fixed across configs.
        seed_value = int(args.seed)
        if args.reuse_backend:
            base_url = str(args.base_url).rstrip("/")
            result = _run_single_config(
                config_id=config_id,
                phase_label="a",
                run_index=1,
                params=params,
                lane_budget=lane_budget,
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
                verify_clean_reset=bool(getattr(args, "verify_clean_reset", True)),
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
                env_overrides=env_overrides,
                log_path=log_path,
                startup_timeout=float(args.startup_timeout),
            ) as backend_context:
                spawned_base_url, backend_startup_ms = backend_context
                result = _run_single_config(
                    config_id=config_id,
                    phase_label="a",
                    run_index=1,
                    params=params,
                    lane_budget=lane_budget,
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
                    verify_clean_reset=bool(getattr(args, "verify_clean_reset", True)),
                    switch_model=bool(args.switch_model),
                    model_id=str(args.model_id or ""),
                    hard_reset=True,
                    backend_mode="spawn",
                    backend_startup_ms=float(backend_startup_ms),
                    quiet=bool(args.quiet),
                )
        results.append(result)

    _validate_shared_seed_schedule(planned, seed_schedule, context="phase-a-planned")
    _validate_shared_seed_schedule(results, seed_schedule, context="phase-a-results")
    ranked = rank_phase_results(results)
    motif_ranked = _rank_phase_results_by_motif_penalty(ranked, metrics_key="metrics")
    projection_ranked = _rank_phase_results_by_projection_efficiency(ranked, metrics_key="metrics")
    clarity_ranked = _rank_phase_results_by_clarity(ranked, metrics_key="metrics")
    latency_ranked = _rank_phase_results_by_latency_reliability(ranked, metrics_key="metrics")
    top_count = max(3, min(5, int(args.phase_b_top_k)))
    top_candidates = ranked[:top_count]
    top_motif_candidates = motif_ranked[:top_count]
    top_projection_candidates = projection_ranked[:top_count]
    top_clarity_candidates = clarity_ranked[:top_count]
    top_latency_candidates = latency_ranked[:top_count]

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
        "verify_clean_reset": bool(getattr(args, "verify_clean_reset", True)),
        "lane_matrix_preset": str(getattr(args, "lane_matrix_preset", LANE_MATRIX_PRESET_OFF)),
        "lane_budget_axes": lane_budget_axes,
        "seed_schedule": list(seed_schedule),
        "planned": planned,
        "results": ranked,
        "top_candidates": top_candidates,
        "motif_ranked_results": motif_ranked,
        "top_motif_candidates": top_motif_candidates,
        "projection_ranked_results": projection_ranked,
        "top_projection_candidates": top_projection_candidates,
        "clarity_ranked_results": clarity_ranked,
        "top_clarity_candidates": top_clarity_candidates,
        "latency_ranked_results": latency_ranked,
        "top_latency_candidates": top_latency_candidates,
        "projection_health_summary": _build_projection_health_summary(ranked),
        "overhead_diagnostics": _phase_overhead_diagnostics(ranked),
        "quality_gate_outcomes": {
            "shared_seed_schedule_validated": True,
            "projection_quality_metrics_present": True,
            **_clarity_gate_outcomes(ranked, metrics_key="metrics"),
        },
    }

    summary_path = run_dir / "phase_a_summary.json"
    _write_json(summary_path, summary)
    print(f"[phase-a] summary: {_path_label(summary_path)}")
    return summary


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


def _aggregate_phase_b_metrics(runs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
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
            "prefix_soft_match_rate": 1.0,
            "prefix_similarity_avg": 0.0,
            "prefix_similarity_p95": 0.0,
            "motif_turns_with_tokens": 0.0,
            "motif_total_tokens": 0.0,
            "motif_unique_tokens": 0.0,
            "motif_overlap_count": 0.0,
            "motif_reused_tokens": 0.0,
            "motif_reuse_rate": 0.0,
            "motif_novelty_rate": 0.0,
            "motif_turn_overlap_rate_avg": 0.0,
            "motif_penalty_score": 0.0,
            "projection_stub_count": 0.0,
            "projection_stub_count_p95": 0.0,
            "projection_hit_rate": 0.0,
            "projection_hit_rate_p95": 0.0,
            "projection_waste_rate": 0.0,
            "projection_waste_rate_p95": 0.0,
            "projection_veto_rate": 0.0,
            "projection_veto_rate_p95": 0.0,
            "clarity_level_distribution": {level: 0.0 for level in CLARITY_LEVEL_ORDER},
            "fallback_reason_distribution": {"none": 0.0},
            "stratified_metrics": {
                "choice": {"turn_count": 0, "latency_ms_avg": 0.0, "failure_rate": 0.0, "projection_hit_rate": 0.0, "projection_waste_rate": 0.0, "projection_veto_rate": 0.0, "clarity_level_distribution": {level: 0.0 for level in CLARITY_LEVEL_ORDER}},
                "freeform": {"turn_count": 0, "latency_ms_avg": 0.0, "failure_rate": 0.0, "projection_hit_rate": 0.0, "projection_waste_rate": 0.0, "projection_veto_rate": 0.0, "clarity_level_distribution": {level: 0.0 for level in CLARITY_LEVEL_ORDER}},
            },
            "clarity_distribution_score_avg": 0.0,
            "narrator_parse_success_rate": 1.0,
            "referee_decision_valid_rate": 1.0,
            "narrator_revise_decision_rate": 0.0,
            "failure_rate": 1.0,
        }

    def average(values: Sequence[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / float(len(values))

    def p95(values: Sequence[float]) -> float:
        return _percentile(values, 0.95)

    metrics_by_run: List[Dict[str, Any]] = []
    for run in runs:
        raw_metrics = run.get("metrics", {})
        metrics_by_run.append(raw_metrics if isinstance(raw_metrics, dict) else {})

    def collect_values(key: str, *, default: float = 0.0) -> List[float]:
        return [float(metrics.get(key, default)) for metrics in metrics_by_run]

    latency_avg = average(collect_values("latency_ms_avg"))
    latency_p95 = average(collect_values("latency_ms_p95"))
    request_latency_avg = average(collect_values("request_latency_ms_avg"))
    request_latency_p95 = average(collect_values("request_latency_ms_p95"))
    prefetch_wait_total = average(collect_values("prefetch_wait_ms_total"))
    prefetch_wait_avg = average(collect_values("prefetch_wait_ms_avg"))
    prefetch_wait_p95 = average(collect_values("prefetch_wait_ms_p95"))
    turn_wallclock_avg = average(collect_values("turn_wallclock_ms_avg"))
    turn_wallclock_p95 = average(collect_values("turn_wallclock_ms_p95"))
    harness_overhead_total = average(collect_values("harness_overhead_ms_total"))
    harness_overhead_avg_per_request = average(collect_values("harness_overhead_ms_avg_per_request"))
    switch_model_ms_avg = average(collect_values("switch_model_ms"))
    hard_reset_ms_avg = average(collect_values("hard_reset_ms"))
    bootstrap_ms_avg = average(collect_values("bootstrap_ms"))
    setup_total_ms_avg = average(collect_values("setup_total_ms"))
    non_setup_non_prefetch_overhead_total_avg = average(collect_values("non_setup_non_prefetch_overhead_ms_total"))
    repetition = average(collect_values("exact_prefix_match_rate", default=1.0))
    soft_repetition = average([float(metrics.get("prefix_soft_match_rate", metrics.get("exact_prefix_match_rate", 1.0))) for metrics in metrics_by_run])
    prefix_similarity_avg = average(collect_values("prefix_similarity_avg"))
    prefix_similarity_p95 = average(collect_values("prefix_similarity_p95"))
    motif_turns_with_tokens = average(collect_values("motif_turns_with_tokens"))
    motif_total_tokens = average(collect_values("motif_total_tokens"))
    motif_unique_tokens = average(collect_values("motif_unique_tokens"))
    motif_overlap_count = average(collect_values("motif_overlap_count"))
    motif_reused_tokens = average(collect_values("motif_reused_tokens"))
    motif_reuse_rate = average(collect_values("motif_reuse_rate"))
    motif_novelty_rate = average(collect_values("motif_novelty_rate"))
    motif_turn_overlap_rate_avg = average(collect_values("motif_turn_overlap_rate_avg"))
    projection_stub_count_values = collect_values("projection_stub_count")
    projection_hit_rate_values = collect_values("projection_hit_rate")
    projection_waste_rate_values = collect_values("projection_waste_rate")
    projection_veto_rate_values = collect_values("projection_veto_rate")
    clarity_level_distribution = {
        level: round(
            average([float((metrics.get("clarity_level_distribution", {}) or {}).get(level, 0.0)) for metrics in metrics_by_run]),
            3,
        )
        for level in CLARITY_LEVEL_ORDER
    }
    fallback_reason_keys: List[str] = []
    for metrics in metrics_by_run:
        raw_distribution = metrics.get("fallback_reason_distribution", {})
        if not isinstance(raw_distribution, dict):
            continue
        for key in raw_distribution.keys():
            normalized = str(key or "").strip().lower()
            if normalized:
                fallback_reason_keys.append(normalized)
    fallback_reason_keys = [item for item in _dedupe_preserve_order(fallback_reason_keys)]
    if not fallback_reason_keys:
        fallback_reason_keys = ["none"]
    fallback_reason_distribution = {
        key: round(
            average([float((metrics.get("fallback_reason_distribution", {}) or {}).get(key, 0.0)) for metrics in metrics_by_run]),
            3,
        )
        for key in fallback_reason_keys
    }
    motif_penalty = motif_penalty_score(
        motif_reuse_rate=motif_reuse_rate,
        motif_turn_overlap_rate_avg=motif_turn_overlap_rate_avg,
    )
    failure = average(collect_values("failure_rate", default=1.0))
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
        "prefix_soft_match_rate": round(soft_repetition, 6),
        "prefix_similarity_avg": round(prefix_similarity_avg, 6),
        "prefix_similarity_p95": round(prefix_similarity_p95, 6),
        "motif_turns_with_tokens": round(motif_turns_with_tokens, 3),
        "motif_total_tokens": round(motif_total_tokens, 3),
        "motif_unique_tokens": round(motif_unique_tokens, 3),
        "motif_overlap_count": round(motif_overlap_count, 3),
        "motif_reused_tokens": round(motif_reused_tokens, 3),
        "motif_reuse_rate": round(motif_reuse_rate, 6),
        "motif_novelty_rate": round(motif_novelty_rate, 6),
        "motif_turn_overlap_rate_avg": round(motif_turn_overlap_rate_avg, 6),
        "motif_penalty_score": round(motif_penalty, 6),
        "projection_stub_count": round(average(projection_stub_count_values), 3),
        "projection_stub_count_p95": round(p95(projection_stub_count_values), 3),
        "projection_hit_rate": round(average(projection_hit_rate_values), 6),
        "projection_hit_rate_p95": round(p95(projection_hit_rate_values), 6),
        "projection_waste_rate": round(average(projection_waste_rate_values), 6),
        "projection_waste_rate_p95": round(p95(projection_waste_rate_values), 6),
        "projection_veto_rate": round(average(projection_veto_rate_values), 6),
        "projection_veto_rate_p95": round(p95(projection_veto_rate_values), 6),
        "clarity_level_distribution": clarity_level_distribution,
        "fallback_reason_distribution": fallback_reason_distribution,
        "stratified_metrics": _aggregate_stratified_metrics(metrics_by_run),
        "clarity_distribution_score_avg": round(
            average([float(m.get("clarity_distribution_score", clarity_distribution_score(m.get("clarity_level_distribution", {})))) for m in metrics_by_run]),
            6,
        ),
        "narrator_parse_success_rate": round(average(collect_values("narrator_parse_success_rate", default=1.0)), 6),
        "referee_decision_valid_rate": round(average(collect_values("referee_decision_valid_rate", default=1.0)), 6),
        "narrator_revise_decision_rate": round(average(collect_values("narrator_revise_decision_rate", default=0.0)), 6),
        "failure_rate": round(failure, 6),
    }


def _aggregate_stratified_metrics(metrics_by_run: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate per-source stratified metric slices across runs."""

    def _avg(values: List[float]) -> float:
        return sum(values) / float(len(values)) if values else 0.0

    def _source_aggregate(source: str) -> Dict[str, Any]:
        slices = [m.get("stratified_metrics", {}).get(source, {}) for m in metrics_by_run if isinstance(m.get("stratified_metrics", {}).get(source), dict)]
        if not slices:
            return {
                "turn_count": 0,
                "latency_ms_avg": 0.0,
                "failure_rate": 0.0,
                "projection_hit_rate": 0.0,
                "projection_waste_rate": 0.0,
                "projection_veto_rate": 0.0,
                "clarity_level_distribution": {level: 0.0 for level in CLARITY_LEVEL_ORDER},
            }
        numeric_keys = ("latency_ms_avg", "failure_rate", "projection_hit_rate", "projection_waste_rate", "projection_veto_rate")
        result: Dict[str, Any] = {
            "turn_count": int(round(_avg([float(s.get("turn_count", 0)) for s in slices]))),
        }
        for key in numeric_keys:
            result[key] = round(_avg([float(s.get(key, 0.0)) for s in slices]), 6)
        result["clarity_level_distribution"] = {
            level: round(
                _avg([float((s.get("clarity_level_distribution", {}) or {}).get(level, 0.0)) for s in slices]),
                3,
            )
            for level in CLARITY_LEVEL_ORDER
        }
        return result

    return {
        "choice": _source_aggregate("choice"),
        "freeform": _source_aggregate("freeform"),
    }


def _build_projection_health_summary(results: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate projection_health_warnings across all result records into a summary."""
    all_warnings: List[Dict[str, Any]] = []
    configs_with_warnings: List[str] = []
    for item in results:
        config_id = str(item.get("config_id", ""))
        warnings = list(item.get("projection_health_warnings", []))
        if warnings:
            configs_with_warnings.append(config_id)
            for w in warnings:
                all_warnings.append({"config_id": config_id, "warning": str(w)})
    return {
        "configs_with_warnings": configs_with_warnings,
        "warning_count": len(all_warnings),
        "warnings": all_warnings,
    }


def _clarity_gate_outcomes(results: Sequence[Dict[str, Any]], *, metrics_key: str) -> Dict[str, Any]:
    """Compute clarity quality gate fields for a phase summary.

    Returns clarity_distribution_score_avg (average across all configs) and
    clarity_health_flags (list of {config_id, warning} for degenerate configs).
    """
    scores: List[float] = []
    flags: List[Dict[str, str]] = []
    for item in results:
        config_id = str(item.get("config_id", ""))
        metrics = item.get(metrics_key, {})
        if not isinstance(metrics, dict):
            continue
        dist = metrics.get("clarity_level_distribution", {})
        score = float(metrics.get("clarity_distribution_score_avg", clarity_distribution_score(dist)))
        scores.append(score)
        warning = clarity_health_check(dist) if dist else ""
        if not warning and score < CLARITY_HEALTH_THRESHOLD:
            warning = f"clarity_distribution_score_avg={score:.4f} < {CLARITY_HEALTH_THRESHOLD} threshold"
        if warning:
            flags.append({"config_id": config_id, "warning": warning})
    avg_score = round(sum(scores) / float(len(scores)), 6) if scores else 0.0
    return {
        "clarity_distribution_score_avg": avg_score,
        "clarity_health_flags": flags,
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
            "projection_stub_count_avg": 0.0,
            "projection_stub_count_p95": 0.0,
            "projection_hit_rate_avg": 0.0,
            "projection_hit_rate_p95": 0.0,
            "projection_waste_rate_avg": 0.0,
            "projection_waste_rate_p95": 0.0,
            "projection_veto_rate_avg": 0.0,
            "projection_veto_rate_p95": 0.0,
            "observed_backend_mode": "unknown",
        }

    metrics = [item.get("metrics", {}) for item in results]

    def average_from(key: str) -> float:
        values = [float(metric.get(key, 0.0)) for metric in metrics]
        if not values:
            return 0.0
        return sum(values) / float(len(values))

    def p95_from(key: str) -> float:
        values = [float(metric.get(key, 0.0)) for metric in metrics]
        if not values:
            return 0.0
        return _percentile(values, 0.95)

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
        "projection_stub_count_avg": round(average_from("projection_stub_count"), 3),
        "projection_stub_count_p95": round(p95_from("projection_stub_count"), 3),
        "projection_hit_rate_avg": round(average_from("projection_hit_rate"), 6),
        "projection_hit_rate_p95": round(p95_from("projection_hit_rate"), 6),
        "projection_waste_rate_avg": round(average_from("projection_waste_rate"), 6),
        "projection_waste_rate_p95": round(p95_from("projection_waste_rate"), 6),
        "projection_veto_rate_avg": round(average_from("projection_veto_rate"), 6),
        "projection_veto_rate_p95": round(p95_from("projection_veto_rate"), 6),
        "observed_backend_mode": ",".join(sorted(backend_modes)) if backend_modes else "unknown",
    }


def _phase_b_candidates_from_summary(payload: Dict[str, Any], *, top_k: int) -> List[Dict[str, Any]]:
    source_rows = list(payload.get("results", []))
    if not source_rows:
        source_rows = list(payload.get("top_candidates", []))

    candidates: List[Dict[str, Any]] = []
    for item in source_rows:
        if not isinstance(item, dict):
            continue
        raw_params = item.get("parameters")
        if not isinstance(raw_params, dict):
            continue
        config_id = str(item.get("config_id", "")).strip()
        if not config_id:
            continue
        metrics_raw = item.get("metrics", {})
        metrics = dict(metrics_raw) if isinstance(metrics_raw, dict) else {}
        latency = float(metrics.get("latency_ms_avg", 0.0))
        exact_repetition = float(metrics.get("exact_prefix_match_rate", 1.0))
        soft_repetition = float(metrics.get("prefix_soft_match_rate", exact_repetition))
        motif_reuse = float(metrics.get("motif_reuse_rate", exact_repetition))
        failure = float(metrics.get("failure_rate", 1.0))
        normalized = {
            "config_id": config_id,
            "parameters": raw_params,
            "lane_budget": (dict(item.get("lane_budget")) if isinstance(item.get("lane_budget"), dict) else LaneBudgetVariant().as_dict()),
            "metrics": {
                **metrics,
                "latency_ms_avg": latency,
                "exact_prefix_match_rate": exact_repetition,
                "prefix_soft_match_rate": soft_repetition,
                "motif_reuse_rate": motif_reuse,
                "failure_rate": failure,
            },
        }
        candidates.append(normalized)

    if candidates:
        return rank_phase_results(candidates)[:top_k]

    fallback_candidates: List[Dict[str, Any]] = []
    for item in payload.get("planned", []):
        raw_params = item.get("parameters")
        if not isinstance(raw_params, dict):
            continue
        fallback_candidates.append(
            {
                "config_id": str(item.get("config_id", "")),
                "parameters": raw_params,
                "lane_budget": (dict(item.get("lane_budget")) if isinstance(item.get("lane_budget"), dict) else LaneBudgetVariant().as_dict()),
                "metrics": {
                    "latency_ms_avg": 0.0,
                    "exact_prefix_match_rate": 1.0,
                    "prefix_soft_match_rate": 1.0,
                    "motif_reuse_rate": 0.0,
                    "motif_penalty_score": 0.0,
                    "projection_stub_count": 0.0,
                    "projection_hit_rate": 0.0,
                    "projection_waste_rate": 0.0,
                    "projection_veto_rate": 0.0,
                    "failure_rate": 1.0,
                },
                "composite_score": 0.0,
            }
        )
    return fallback_candidates[:top_k]


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
    seed_schedule = _build_seed_schedule(seed_base=int(args.seed), runs_per_config=runs_per_config)
    phase_b_turns = int(args.phase_b_turns)
    runs_dir = run_dir / "phase_b" / "runs"
    logs_dir = run_dir / "phase_b" / "backend_logs"

    phase_b_results: List[Dict[str, Any]] = []
    for candidate_index, candidate in enumerate(candidates, start=1):
        config_id = str(candidate.get("config_id", f"b{candidate_index:02d}"))
        params = _coerce_parameter_set(candidate.get("parameters", {}))
        lane_budget = _coerce_lane_budget_variant(candidate.get("lane_budget"))
        # Head-to-head tuning: use the same seed set for every candidate config.
        seed_base = int(args.seed)
        per_seed_runs: List[Dict[str, Any]] = []

        print(f"[phase-b] analyzing {config_id} ({candidate_index}/{len(candidates)})")
        if args.dry_run:
            planned_seeds = list(seed_schedule)
            phase_b_results.append(
                {
                    "config_id": config_id,
                    "parameters": params.as_dict(),
                    "lane_budget": lane_budget.as_dict(),
                    "lane_budget_env_overrides": lane_budget.env_overrides(),
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
                        "prefix_soft_match_rate": 1.0,
                        "prefix_similarity_avg": 0.0,
                        "prefix_similarity_p95": 0.0,
                        "motif_turns_with_tokens": 0.0,
                        "motif_total_tokens": 0.0,
                        "motif_unique_tokens": 0.0,
                        "motif_overlap_count": 0.0,
                        "motif_reused_tokens": 0.0,
                        "motif_reuse_rate": 0.0,
                        "motif_novelty_rate": 0.0,
                        "motif_turn_overlap_rate_avg": 0.0,
                        "motif_penalty_score": 0.0,
                        "projection_stub_count": 0.0,
                        "projection_stub_count_p95": 0.0,
                        "projection_hit_rate": 0.0,
                        "projection_hit_rate_p95": 0.0,
                        "projection_waste_rate": 0.0,
                        "projection_waste_rate_p95": 0.0,
                        "projection_veto_rate": 0.0,
                        "projection_veto_rate_p95": 0.0,
                        "clarity_level_distribution": {level: 0.0 for level in CLARITY_LEVEL_ORDER},
                        "fallback_reason_distribution": {"none": 0.0},
                        "clarity_distribution_score_avg": 0.0,
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
                    lane_budget=lane_budget,
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
                    verify_clean_reset=bool(getattr(args, "verify_clean_reset", True)),
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
                env_overrides={
                    **params.env_overrides(),
                    **lane_budget.env_overrides(),
                },
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
                        lane_budget=lane_budget,
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
                        verify_clean_reset=bool(getattr(args, "verify_clean_reset", True)),
                        switch_model=bool(args.switch_model),
                        model_id=str(args.model_id or ""),
                        hard_reset=True,
                        backend_mode="spawn",
                        backend_startup_ms=float(backend_startup_ms),
                        quiet=bool(args.quiet),
                    )
                    per_seed_runs.append(run_entry)

        _validate_per_run_seed_sequence(
            per_seed_runs,
            seed_schedule,
            context="phase-b-runs",
            config_id=config_id,
        )
        aggregate_metrics = _aggregate_phase_b_metrics(per_seed_runs)
        _proj_hit = aggregate_metrics.get("projection_hit_rate")
        _proj_waste = aggregate_metrics.get("projection_waste_rate")
        _clarity = aggregate_metrics.get("clarity_distribution_score")
        composite_score = score_run_metrics(
            latency_ms_avg=float(aggregate_metrics["latency_ms_avg"]),
            exact_prefix_match_rate=float(aggregate_metrics["exact_prefix_match_rate"]),
            prefix_soft_match_rate=float(aggregate_metrics.get("prefix_soft_match_rate", aggregate_metrics["exact_prefix_match_rate"])),
            motif_reuse_rate=float(aggregate_metrics.get("motif_reuse_rate", aggregate_metrics["exact_prefix_match_rate"])),
            failure_rate=float(aggregate_metrics["failure_rate"]),
            projection_hit_rate=float(_proj_hit) if _proj_hit is not None else None,
            projection_waste_rate=float(_proj_waste) if _proj_waste is not None else None,
            clarity_distribution_score=float(_clarity) if _clarity is not None else None,
        )
        phase_b_results.append(
            {
                "config_id": config_id,
                "parameters": params.as_dict(),
                "lane_budget": lane_budget.as_dict(),
                "lane_budget_env_overrides": lane_budget.env_overrides(),
                "planned_seeds": list(seed_schedule),
                "runs": per_seed_runs,
                "aggregate_metrics": aggregate_metrics,
                "composite_score": composite_score,
            }
        )

    _validate_shared_seed_schedule(phase_b_results, seed_schedule, context="phase-b-results")
    ranked = sorted(
        phase_b_results,
        key=lambda item: (
            -float(item.get("composite_score", 0.0)),
            float(item.get("aggregate_metrics", {}).get("failure_rate", 1.0)),
            float(item.get("aggregate_metrics", {}).get("motif_reuse_rate", item.get("aggregate_metrics", {}).get("exact_prefix_match_rate", 1.0))),
            _repetition_signal(item.get("aggregate_metrics", {})),
            float(item.get("aggregate_metrics", {}).get("exact_prefix_match_rate", 1.0)),
            float(item.get("aggregate_metrics", {}).get("latency_ms_avg", float("inf"))),
        ),
    )
    motif_ranked = _rank_phase_results_by_motif_penalty(ranked, metrics_key="aggregate_metrics")
    projection_ranked = _rank_phase_results_by_projection_efficiency(ranked, metrics_key="aggregate_metrics")
    clarity_ranked = _rank_phase_results_by_clarity(ranked, metrics_key="aggregate_metrics")
    latency_ranked = _rank_phase_results_by_latency_reliability(ranked, metrics_key="aggregate_metrics")
    top_count = max(3, min(5, int(args.phase_b_top_k)))
    lane_budget_axes = dict(phase_a_payload.get("lane_budget_axes")) if isinstance(phase_a_payload.get("lane_budget_axes"), dict) else _lane_budget_axes_payload([_coerce_lane_budget_variant(candidate.get("lane_budget")) for candidate in candidates])
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
        "verify_clean_reset": bool(getattr(args, "verify_clean_reset", True)),
        "lane_matrix_preset": str(getattr(args, "lane_matrix_preset", LANE_MATRIX_PRESET_OFF)),
        "lane_budget_axes": lane_budget_axes,
        "seed_schedule": list(seed_schedule),
        "results": ranked,
        "recommended_configs": ranked[:top_count],
        "motif_ranked_results": motif_ranked,
        "recommended_motif_configs": motif_ranked[:top_count],
        "projection_ranked_results": projection_ranked,
        "recommended_projection_configs": projection_ranked[:top_count],
        "clarity_ranked_results": clarity_ranked,
        "recommended_clarity_configs": clarity_ranked[:top_count],
        "latency_ranked_results": latency_ranked,
        "recommended_latency_configs": latency_ranked[:top_count],
        "projection_health_summary": _build_projection_health_summary(ranked),
        "overhead_diagnostics": _phase_overhead_diagnostics(ranked),
        "quality_gate_outcomes": {
            "shared_seed_schedule_validated": True,
            "projection_quality_metrics_present": True,
            **_clarity_gate_outcomes(ranked, metrics_key="aggregate_metrics"),
        },
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
    parser.add_argument(
        "--lane-matrix-preset",
        choices=(LANE_MATRIX_PRESET_OFF, LANE_MATRIX_PRESET_V3_DEFAULT),
        default=LANE_MATRIX_PRESET_OFF,
        help="Optional preset for narrator/referee lanes plus projection budget axes.",
    )
    parser.add_argument(
        "--lane-narrator-models",
        default="",
        help="Comma-separated narrator lane model overrides (maps to LLM_NARRATOR_MODEL).",
    )
    parser.add_argument(
        "--lane-referee-models",
        default="",
        help="Comma-separated referee/planner lane model overrides (maps to LLM_REFEREE_MODEL).",
    )
    parser.add_argument(
        "--projection-depth-options",
        default="",
        help="Comma-separated WW_V3_PROJECTION_MAX_DEPTH sweep axis.",
    )
    parser.add_argument(
        "--projection-node-options",
        default="",
        help="Comma-separated WW_V3_PROJECTION_MAX_NODES sweep axis.",
    )
    parser.add_argument(
        "--projection-time-budget-ms-options",
        default="",
        help="Comma-separated WW_V3_PROJECTION_TIME_BUDGET_MS sweep axis.",
    )
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
    parser.add_argument(
        "--verify-clean-reset",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="After each hard reset, verify world history/projection/storylets/prefetch are empty.",
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
    print(f"[sweep] verify clean reset: {bool(getattr(args, 'verify_clean_reset', True))}")

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
        "verify_clean_reset": bool(getattr(args, "verify_clean_reset", True)),
    }
    manifest_path = run_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    print(f"[sweep] manifest: {_path_label(manifest_path)}")
    if phase_a_summary_payload is not None and args.phase == "a" and args.dry_run:
        print(f"[sweep] planned configs: {len(phase_a_summary_payload.get('planned', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
