from __future__ import annotations

from playtest_harness.long_run_harness import _exact_prefix_repetition_metrics
from playtest_harness.parameter_sweep import _aggregate_phase_b_metrics
from tests.integration_harness_helpers import (
    assert_metric_values,
    build_phase_b_metrics,
    build_turn_record,
)


def test_exact_prefix_repetition_metrics_expose_soft_matches() -> None:
    turns = [
        build_turn_record(
            turn=1,
            action_sent="A",
            narrative="Acrid smoke curls through the rusted vents while neon reflections tremble.",
            request_duration_ms=10.0,
        ),
        build_turn_record(
            turn=2,
            action_sent="B",
            narrative="Acrid haze drifts through rusted vents as neon glow trembles on wet steel.",
            request_duration_ms=11.0,
        ),
    ]

    metrics = _exact_prefix_repetition_metrics(turns, prefix_chars=80, soft_match_threshold=0.2)
    assert metrics["exact_prefix_match_rate"] == 0.0
    assert metrics["prefix_soft_match_rate"] > 0.0
    assert metrics["prefix_similarity_avg"] > 0.0


def test_aggregate_phase_b_metrics_includes_overhead_fields() -> None:
    aggregated = _aggregate_phase_b_metrics(
        [
            {
                "metrics": build_phase_b_metrics(),
            },
            {
                "metrics": build_phase_b_metrics(
                    latency_ms_avg=200.0,
                    latency_ms_p95=260.0,
                    request_latency_ms_avg=200.0,
                    request_latency_ms_p95=260.0,
                    prefetch_wait_ms_total=70.0,
                    prefetch_wait_ms_avg=14.0,
                    prefetch_wait_ms_p95=24.0,
                    turn_wallclock_ms_avg=240.0,
                    turn_wallclock_ms_p95=300.0,
                    harness_overhead_ms_total=110.0,
                    harness_overhead_ms_avg_per_request=22.0,
                    hard_reset_ms=16.0,
                    bootstrap_ms=48.0,
                    setup_total_ms=66.0,
                    non_setup_non_prefetch_overhead_ms_total=20.0,
                    exact_prefix_match_rate=0.4,
                    prefix_soft_match_rate=0.6,
                    prefix_similarity_avg=0.5,
                    prefix_similarity_p95=0.7,
                    motif_turns_with_tokens=6.0,
                    motif_total_tokens=30.0,
                    motif_unique_tokens=18.0,
                    motif_overlap_count=12.0,
                    motif_reused_tokens=12.0,
                    motif_reuse_rate=0.4,
                    motif_novelty_rate=0.6,
                    motif_turn_overlap_rate_avg=0.35,
                    failure_rate=0.1,
                ),
            },
        ]
    )
    assert_metric_values(
        aggregated,
        {
            "latency_ms_avg": 150.0,
            "prefetch_wait_ms_avg": 12.0,
            "turn_wallclock_ms_avg": 185.0,
            "harness_overhead_ms_total": 95.0,
            "setup_total_ms": 60.5,
            "bootstrap_ms": 44.0,
            "hard_reset_ms": 14.0,
            "prefix_soft_match_rate": 0.5,
            "prefix_similarity_avg": 0.4,
            "prefix_similarity_p95": 0.6,
            "motif_total_tokens": 27.5,
            "motif_unique_tokens": 19.0,
            "motif_overlap_count": 8.5,
            "motif_reuse_rate": 0.3,
            "motif_novelty_rate": 0.7,
            "motif_penalty_score": 0.3,
        },
    )
