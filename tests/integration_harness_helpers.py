"""Shared helpers for integration tests that exercise harness tooling."""

from __future__ import annotations

from typing import Any, Iterable

from playtest_harness.long_run_harness import TurnRecord


NARRATIVE_EVAL_METRIC_KEYS = (
    "memory_carryover_score",
    "divergence_score",
    "freeform_coherence_score",
    "contradiction_free_score",
    "arc_adherence_score",
    "identity_stability_score",
    "repetition_window_guard_score",
    "stall_repetition_score",
    "narrative_command_success_rate",
)


_PHASE_B_METRICS_BASE = {
    "latency_ms_avg": 100.0,
    "latency_ms_p95": 140.0,
    "request_latency_ms_avg": 100.0,
    "request_latency_ms_p95": 140.0,
    "prefetch_wait_ms_total": 50.0,
    "prefetch_wait_ms_avg": 10.0,
    "prefetch_wait_ms_p95": 20.0,
    "turn_wallclock_ms_avg": 130.0,
    "turn_wallclock_ms_p95": 180.0,
    "harness_overhead_ms_total": 80.0,
    "harness_overhead_ms_avg_per_request": 16.0,
    "switch_model_ms": 0.0,
    "hard_reset_ms": 12.0,
    "bootstrap_ms": 40.0,
    "setup_total_ms": 55.0,
    "non_setup_non_prefetch_overhead_ms_total": 15.0,
    "exact_prefix_match_rate": 0.2,
    "prefix_soft_match_rate": 0.4,
    "prefix_similarity_avg": 0.3,
    "prefix_similarity_p95": 0.5,
    "motif_turns_with_tokens": 5.0,
    "motif_total_tokens": 25.0,
    "motif_unique_tokens": 20.0,
    "motif_overlap_count": 5.0,
    "motif_reused_tokens": 5.0,
    "motif_reuse_rate": 0.2,
    "motif_novelty_rate": 0.8,
    "motif_turn_overlap_rate_avg": 0.25,
    "failure_rate": 0.0,
}


def assert_metric_keys_present(metrics: dict[str, Any], expected_keys: Iterable[str]) -> None:
    missing = [key for key in expected_keys if key not in metrics]
    assert not missing, f"Missing metric keys: {missing}"


def build_phase_b_metrics(**overrides: float) -> dict[str, float]:
    metrics = dict(_PHASE_B_METRICS_BASE)
    metrics.update(overrides)
    return metrics


def build_turn_record(
    *,
    turn: int,
    action_sent: str,
    narrative: str,
    request_duration_ms: float,
) -> TurnRecord:
    return TurnRecord(
        turn=turn,
        phase="next",
        action_source="choice_button",
        action_sent=action_sent,
        narrative=narrative,
        ack_line="",
        plausible=True,
        choices=[],
        state_changes={},
        vars={},
        diagnostics={},
        request_duration_ms=request_duration_ms,
        prefetch_wait_duration_ms=0.0,
        turn_duration_ms=request_duration_ms,
        request_status="ok",
        request_error="",
    )
