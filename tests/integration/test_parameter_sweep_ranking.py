from __future__ import annotations

from playtest_harness.parameter_sweep import (
    MAX_TOKENS_RANGE,
    NARRATOR_TEMPERATURE_RANGE,
    RECENCY_PENALTY_RANGE,
    REFEREE_TEMPERATURE_RANGE,
    SEMANTIC_FLOOR_RANGE,
    _rank_phase_results_by_clarity,
    _rank_phase_results_by_projection_efficiency,
    _phase_b_candidates_from_summary,
    check_run_projection_health,
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
        assert NARRATOR_TEMPERATURE_RANGE[0] <= config.llm_narrator_temperature <= NARRATOR_TEMPERATURE_RANGE[1]
        assert REFEREE_TEMPERATURE_RANGE[0] <= config.llm_referee_temperature <= REFEREE_TEMPERATURE_RANGE[1]
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


# ---------------------------------------------------------------------------
# Major 111: composite score with projection quality
# ---------------------------------------------------------------------------


def test_score_run_metrics_projection_params_affect_score() -> None:
    """Providing projection params changes score vs neutral default."""
    base = score_run_metrics(
        latency_ms_avg=500.0,
        exact_prefix_match_rate=0.1,
        failure_rate=0.0,
    )
    good_proj = score_run_metrics(
        latency_ms_avg=500.0,
        exact_prefix_match_rate=0.1,
        failure_rate=0.0,
        projection_hit_rate=0.9,
        projection_waste_rate=0.1,
    )
    bad_proj = score_run_metrics(
        latency_ms_avg=500.0,
        exact_prefix_match_rate=0.1,
        failure_rate=0.0,
        projection_hit_rate=0.0,
        projection_waste_rate=1.0,
    )
    assert good_proj > base, "good projection should score above neutral"
    assert bad_proj < base, "bad projection should score below neutral"


def test_score_run_metrics_neutral_when_no_projection_params() -> None:
    """When projection and clarity params are both None, both default to 0.5 (neutral)."""
    s = score_run_metrics(
        latency_ms_avg=0.0,
        exact_prefix_match_rate=0.0,
        failure_rate=0.0,
    )
    # With neutral projection (0.5) and neutral clarity (0.5), perfect other components:
    # (1.0*0.50) + (1.0*0.20) + (1.0*0.05) + (1.0*0.05) + (0.5*0.10) + (0.5*0.10) = 0.90
    assert abs(s - 0.90) < 1e-5


def test_score_run_metrics_weights_sum_correctly() -> None:
    """Verify weight rebalancing: perfect score with good projection and clarity = 1.0."""
    s = score_run_metrics(
        latency_ms_avg=0.0,
        exact_prefix_match_rate=0.0,
        failure_rate=0.0,
        projection_hit_rate=1.0,
        projection_waste_rate=0.0,
        clarity_distribution_score=1.0,
    )
    assert abs(s - 1.0) < 1e-5


def test_check_run_projection_health_high_waste_warns() -> None:
    warnings = check_run_projection_health(
        {"projection_waste_rate": 0.95, "projection_hit_rate": 0.05},
        turn_count=20,
    )
    assert any("waste" in w for w in warnings)


def test_check_run_projection_health_no_prepared_warns() -> None:
    warnings = check_run_projection_health(
        {
            "projection_waste_rate": 0.5,
            "projection_hit_rate": 0.5,
            "clarity_level_distribution": {"unknown": 10, "rumor": 0, "lead": 0, "prepared": 0, "committed": 0},
        },
        turn_count=20,
    )
    assert any("prepared" in w or "committed" in w for w in warnings)


def test_check_run_projection_health_zero_hit_rate_many_turns_warns() -> None:
    warnings = check_run_projection_health(
        {"projection_waste_rate": 0.5, "projection_hit_rate": 0.0},
        turn_count=15,
    )
    assert any("hit_rate" in w for w in warnings)


def test_check_run_projection_health_healthy_no_warnings() -> None:
    warnings = check_run_projection_health(
        {
            "projection_waste_rate": 0.3,
            "projection_hit_rate": 0.7,
            "clarity_level_distribution": {"unknown": 2, "rumor": 1, "lead": 1, "prepared": 5, "committed": 1},
        },
        turn_count=10,
    )
    assert warnings == []


def test_rank_phase_results_by_clarity_prefers_higher_clarity_score() -> None:
    ranked = _rank_phase_results_by_clarity(
        [
            build_phase_result(
                config_id="all-unknown",
                metrics={"clarity_level_distribution": {"unknown": 10, "rumor": 0, "lead": 0, "prepared": 0, "committed": 0}, "failure_rate": 0.0, "latency_ms_avg": 100.0},
            ),
            build_phase_result(
                config_id="mostly-prepared",
                metrics={"clarity_level_distribution": {"unknown": 1, "rumor": 0, "lead": 0, "prepared": 9, "committed": 0}, "failure_rate": 0.0, "latency_ms_avg": 100.0},
            ),
        ],
    )
    assert ranked[0]["config_id"] == "mostly-prepared"
    assert ranked[-1]["config_id"] == "all-unknown"


def test_projection_ranking_prefers_low_waste_and_veto() -> None:
    ranked = _rank_phase_results_by_projection_efficiency(
        [
            build_phase_result(
                config_id="projection-noisy",
                metrics={
                    "projection_hit_rate": 0.3,
                    "projection_waste_rate": 0.7,
                    "projection_veto_rate": 0.4,
                    "failure_rate": 0.0,
                    "latency_ms_avg": 180.0,
                },
            ),
            build_phase_result(
                config_id="projection-efficient",
                metrics={
                    "projection_hit_rate": 0.8,
                    "projection_waste_rate": 0.2,
                    "projection_veto_rate": 0.05,
                    "failure_rate": 0.0,
                    "latency_ms_avg": 220.0,
                },
            ),
        ],
        metrics_key="metrics",
    )
    assert ranked[0]["config_id"] == "projection-efficient"
