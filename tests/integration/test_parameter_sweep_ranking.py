from __future__ import annotations

from playtest_harness.parameter_sweep import (
    MAX_TOKENS_RANGE,
    RECENCY_PENALTY_RANGE,
    SEMANTIC_FLOOR_RANGE,
    TEMPERATURE_RANGE,
    _phase_b_candidates_from_summary,
    generate_phase_a_parameter_sets,
    motif_penalty_score,
    rank_phase_results,
    score_run_metrics,
)
from tests.integration_harness_helpers import (
    PARAMETER_SWEEP_DEFAULT_PARAMETERS,
    build_phase_result,
)


def test_generate_phase_a_parameter_sets_bounds_and_count() -> None:
    configs = generate_phase_a_parameter_sets(count=16, seed=1234)
    assert len(configs) == 16
    assert len({tuple(sorted(item.as_dict().items())) for item in configs}) == 16

    for config in configs:
        assert TEMPERATURE_RANGE[0] <= config.llm_temperature <= TEMPERATURE_RANGE[1]
        assert MAX_TOKENS_RANGE[0] <= config.llm_max_tokens <= MAX_TOKENS_RANGE[1]
        assert RECENCY_PENALTY_RANGE[0] <= config.llm_recency_penalty <= RECENCY_PENALTY_RANGE[1]
        assert SEMANTIC_FLOOR_RANGE[0] <= config.llm_semantic_floor_probability <= SEMANTIC_FLOOR_RANGE[1]


def test_rank_phase_results_prioritizes_cleaner_runs() -> None:
    ranked = rank_phase_results(
        [
            build_phase_result(
                config_id="slow-clean",
                metrics={
                    "latency_ms_avg": 1500.0,
                    "exact_prefix_match_rate": 0.10,
                    "failure_rate": 0.0,
                },
            ),
            build_phase_result(
                config_id="fast-repetitive",
                metrics={
                    "latency_ms_avg": 120.0,
                    "exact_prefix_match_rate": 0.85,
                    "failure_rate": 0.0,
                },
            ),
            build_phase_result(
                config_id="unstable",
                metrics={
                    "latency_ms_avg": 80.0,
                    "exact_prefix_match_rate": 0.05,
                    "failure_rate": 0.5,
                },
            ),
        ]
    )
    assert ranked[0]["config_id"] == "slow-clean"
    assert ranked[-1]["config_id"] == "unstable"


def test_rank_phase_results_uses_motif_reuse_signal() -> None:
    ranked = rank_phase_results(
        [
            build_phase_result(
                config_id="motif-heavy",
                metrics={
                    "latency_ms_avg": 300.0,
                    "exact_prefix_match_rate": 0.2,
                    "motif_reuse_rate": 0.9,
                    "failure_rate": 0.0,
                },
            ),
            build_phase_result(
                config_id="motif-light",
                metrics={
                    "latency_ms_avg": 300.0,
                    "exact_prefix_match_rate": 0.2,
                    "motif_reuse_rate": 0.1,
                    "failure_rate": 0.0,
                },
            ),
        ]
    )
    assert ranked[0]["config_id"] == "motif-light"
    assert ranked[1]["config_id"] == "motif-heavy"


def test_motif_penalty_score_uses_configured_weights() -> None:
    assert motif_penalty_score(motif_reuse_rate=0.4, motif_turn_overlap_rate_avg=0.1) == 0.28


def test_score_run_metrics_penalizes_soft_prefix_repetition() -> None:
    baseline = score_run_metrics(
        latency_ms_avg=500.0,
        exact_prefix_match_rate=0.0,
        motif_reuse_rate=0.1,
        failure_rate=0.0,
    )
    soft_penalized = score_run_metrics(
        latency_ms_avg=500.0,
        exact_prefix_match_rate=0.0,
        prefix_soft_match_rate=0.8,
        motif_reuse_rate=0.1,
        failure_rate=0.0,
    )
    assert soft_penalized < baseline


def test_phase_b_candidates_from_summary_uses_score_ranked_results() -> None:
    payload = {
        "top_candidates": [
            build_phase_result(
                config_id="top-list-first-but-worse",
                parameters=PARAMETER_SWEEP_DEFAULT_PARAMETERS,
                metrics={
                    "latency_ms_avg": 900.0,
                    "exact_prefix_match_rate": 0.6,
                    "prefix_soft_match_rate": 0.8,
                    "motif_reuse_rate": 0.7,
                    "failure_rate": 0.0,
                },
            ),
        ],
        "results": [
            build_phase_result(
                config_id="better",
                parameters=PARAMETER_SWEEP_DEFAULT_PARAMETERS,
                metrics={
                    "latency_ms_avg": 350.0,
                    "exact_prefix_match_rate": 0.1,
                    "prefix_soft_match_rate": 0.2,
                    "motif_reuse_rate": 0.15,
                    "failure_rate": 0.0,
                },
            ),
            build_phase_result(
                config_id="worse",
                parameters=PARAMETER_SWEEP_DEFAULT_PARAMETERS,
                metrics={
                    "latency_ms_avg": 850.0,
                    "exact_prefix_match_rate": 0.5,
                    "prefix_soft_match_rate": 0.7,
                    "motif_reuse_rate": 0.55,
                    "failure_rate": 0.0,
                },
            ),
        ],
    }

    candidates = _phase_b_candidates_from_summary(payload, top_k=1)
    assert len(candidates) == 1
    assert candidates[0]["config_id"] == "better"
