from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from playtest_harness.long_run_harness import (
    CLARITY_HEALTH_THRESHOLD,
    CLARITY_LEVEL_ORDER,
    WorldConfig,
    _exact_prefix_repetition_metrics,
    _stratified_source_metrics,
    clarity_distribution_score,
    clarity_health_check,
)
from playtest_harness.parameter_sweep import (
    _aggregate_phase_b_metrics,
    _aggregate_stratified_metrics,
    _build_projection_health_summary,
    _clarity_gate_outcomes,
    run_phase_a,
)
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
                    projection_stub_count=1.0,
                    projection_hit_rate=0.2,
                    projection_waste_rate=0.8,
                    projection_veto_rate=0.4,
                    clarity_level_distribution={
                        "unknown": 2.0,
                        "rumor": 0.0,
                        "lead": 2.0,
                        "prepared": 1.0,
                        "committed": 4.0,
                    },
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
            "projection_stub_count": 2.0,
            "projection_stub_count_p95": 2.9,
            "projection_hit_rate": 0.4,
            "projection_hit_rate_p95": 0.58,
            "projection_waste_rate": 0.6,
            "projection_waste_rate_p95": 0.78,
            "projection_veto_rate": 0.25,
            "projection_veto_rate_p95": 0.385,
        },
    )
    assert aggregated["clarity_level_distribution"] == {
        "unknown": 1.5,
        "rumor": 0.5,
        "lead": 1.5,
        "prepared": 1.5,
        "committed": 4.5,
    }
    assert "stratified_metrics" in aggregated
    assert "choice" in aggregated["stratified_metrics"]
    assert "freeform" in aggregated["stratified_metrics"]


def test_stratified_source_metrics_choice_freeform_split() -> None:
    choice_turn = build_turn_record(
        turn=2,
        action_source="choice_button",
        action_sent="Go north",
        narrative="You head north.",
        request_duration_ms=100.0,
    )
    freeform_turn = build_turn_record(
        turn=3,
        action_source="diversity_freeform",
        action_sent="I search the room",
        narrative="You search and find nothing.",
        request_duration_ms=200.0,
    )
    result = _stratified_source_metrics([choice_turn, freeform_turn])

    assert result["choice_turn_pct"] == 0.5
    assert result["freeform_turn_pct"] == 0.5
    assert result["choice"]["turn_count"] == 1
    assert result["freeform"]["turn_count"] == 1
    assert result["choice"]["latency_ms_avg"] == 100.0
    assert result["freeform"]["latency_ms_avg"] == 200.0
    assert result["choice"]["failure_rate"] == 0.0
    assert result["freeform"]["failure_rate"] == 0.0
    for level in CLARITY_LEVEL_ORDER:
        assert level in result["choice"]["clarity_level_distribution"]
        assert level in result["freeform"]["clarity_level_distribution"]


def test_stratified_source_metrics_all_choice() -> None:
    turns = [
        build_turn_record(turn=i, action_source="choice_button", action_sent="Go", narrative="N", request_duration_ms=50.0)
        for i in range(1, 4)
    ]
    result = _stratified_source_metrics(turns)
    assert result["choice_turn_pct"] == 1.0
    assert result["freeform_turn_pct"] == 0.0
    assert result["choice"]["turn_count"] == 3
    assert result["freeform"]["turn_count"] == 0


def test_stratified_source_metrics_empty_turns() -> None:
    result = _stratified_source_metrics([])
    assert result["choice_turn_pct"] == 0.0
    assert result["freeform_turn_pct"] == 0.0
    assert result["choice"]["turn_count"] == 0
    assert result["freeform"]["turn_count"] == 0


def test_aggregate_stratified_metrics_averages_per_source() -> None:
    metrics_by_run = [
        {
            "stratified_metrics": {
                "choice": {"turn_count": 4, "latency_ms_avg": 100.0, "failure_rate": 0.0, "projection_hit_rate": 0.5, "projection_waste_rate": 0.5, "projection_veto_rate": 0.1, "clarity_level_distribution": {"unknown": 2, "rumor": 1, "lead": 0, "prepared": 1, "committed": 0}},
                "freeform": {"turn_count": 2, "latency_ms_avg": 200.0, "failure_rate": 0.5, "projection_hit_rate": 0.0, "projection_waste_rate": 1.0, "projection_veto_rate": 0.0, "clarity_level_distribution": {"unknown": 2, "rumor": 0, "lead": 0, "prepared": 0, "committed": 0}},
            }
        },
        {
            "stratified_metrics": {
                "choice": {"turn_count": 2, "latency_ms_avg": 200.0, "failure_rate": 0.0, "projection_hit_rate": 1.0, "projection_waste_rate": 0.0, "projection_veto_rate": 0.0, "clarity_level_distribution": {"unknown": 0, "rumor": 0, "lead": 0, "prepared": 1, "committed": 1}},
                "freeform": {"turn_count": 4, "latency_ms_avg": 150.0, "failure_rate": 0.0, "projection_hit_rate": 0.5, "projection_waste_rate": 0.5, "projection_veto_rate": 0.0, "clarity_level_distribution": {"unknown": 1, "rumor": 1, "lead": 1, "prepared": 1, "committed": 0}},
            }
        },
    ]
    result = _aggregate_stratified_metrics(metrics_by_run)
    assert result["choice"]["latency_ms_avg"] == 150.0  # avg(100.0, 200.0)
    assert result["freeform"]["latency_ms_avg"] == 175.0  # avg(200, 150)
    assert result["choice"]["projection_hit_rate"] == 0.75  # avg(0.5, 1.0)
    assert result["freeform"]["failure_rate"] == 0.25  # avg(0.5, 0.0)
    for level in CLARITY_LEVEL_ORDER:
        assert level in result["choice"]["clarity_level_distribution"]
        assert level in result["freeform"]["clarity_level_distribution"]


# --- Minor 115: clarity_distribution_score and clarity_health_check ---


def test_clarity_distribution_score_all_unknown_returns_zero() -> None:
    dist = {"unknown": 10, "rumor": 0, "lead": 0, "prepared": 0, "committed": 0}
    assert clarity_distribution_score(dist) == 0.0


def test_clarity_distribution_score_all_prepared_returns_one() -> None:
    dist = {"unknown": 0, "rumor": 0, "lead": 0, "prepared": 5, "committed": 0}
    assert clarity_distribution_score(dist) == 1.0


def test_clarity_distribution_score_mixed() -> None:
    # 4 unknown (0.0) + 4 rumor (0.25 each) = weighted 1.0 / total 8 = 0.125
    dist = {"unknown": 4, "rumor": 4, "lead": 0, "prepared": 0, "committed": 0}
    score = clarity_distribution_score(dist)
    assert abs(score - 0.125) < 1e-6


def test_clarity_distribution_score_empty_returns_zero() -> None:
    assert clarity_distribution_score({}) == 0.0
    assert clarity_distribution_score({"unknown": 0}) == 0.0


def test_clarity_distribution_score_committed_counts_full() -> None:
    dist = {"unknown": 0, "rumor": 0, "lead": 0, "prepared": 0, "committed": 3}
    assert clarity_distribution_score(dist) == 1.0


def test_clarity_health_check_all_unknown_warns() -> None:
    dist = {"unknown": 10, "rumor": 0, "lead": 0, "prepared": 0, "committed": 0}
    warning = clarity_health_check(dist)
    assert warning != ""
    assert "unknown" in warning


def test_clarity_health_check_low_score_warns() -> None:
    # Score = 0.25 * 1 / 100 = 0.0025 < 0.05 threshold
    dist = {"unknown": 99, "rumor": 1, "lead": 0, "prepared": 0, "committed": 0}
    warning = clarity_health_check(dist)
    assert warning != ""
    assert str(CLARITY_HEALTH_THRESHOLD) in warning


def test_clarity_health_check_healthy_returns_empty() -> None:
    # 5 prepared out of 10 → score = 0.5, above 0.05
    dist = {"unknown": 5, "rumor": 0, "lead": 0, "prepared": 5, "committed": 0}
    assert clarity_health_check(dist) == ""


def test_clarity_health_check_empty_returns_empty() -> None:
    assert clarity_health_check({}) == ""
    assert clarity_health_check({"unknown": 0}) == ""


def test_aggregate_phase_b_metrics_includes_clarity_score_avg() -> None:
    aggregated = _aggregate_phase_b_metrics(
        [
            {"metrics": build_phase_b_metrics(clarity_level_distribution={"unknown": 0, "rumor": 0, "lead": 0, "prepared": 5, "committed": 5})},
            {"metrics": build_phase_b_metrics(clarity_level_distribution={"unknown": 10, "rumor": 0, "lead": 0, "prepared": 0, "committed": 0})},
        ]
    )
    assert "clarity_distribution_score_avg" in aggregated
    # First run score = 1.0, second = 0.0 → avg = 0.5
    assert abs(aggregated["clarity_distribution_score_avg"] - 0.5) < 1e-6


def test_clarity_gate_outcomes_flags_degenerate_configs() -> None:
    results = [
        {
            "config_id": "cfg_good",
            "metrics": {"clarity_level_distribution": {"unknown": 2, "rumor": 0, "lead": 0, "prepared": 8, "committed": 0}},
        },
        {
            "config_id": "cfg_bad",
            "metrics": {"clarity_level_distribution": {"unknown": 100, "rumor": 0, "lead": 0, "prepared": 0, "committed": 0}},
        },
    ]
    outcomes = _clarity_gate_outcomes(results, metrics_key="metrics")
    assert "clarity_distribution_score_avg" in outcomes
    assert "clarity_health_flags" in outcomes
    flag_configs = [f["config_id"] for f in outcomes["clarity_health_flags"]]
    assert "cfg_bad" in flag_configs
    assert "cfg_good" not in flag_configs


def test_clarity_gate_outcomes_no_flags_when_all_healthy() -> None:
    results = [
        {
            "config_id": "cfg_a",
            "metrics": {"clarity_level_distribution": {"unknown": 0, "rumor": 0, "lead": 0, "prepared": 5, "committed": 5}},
        },
    ]
    outcomes = _clarity_gate_outcomes(results, metrics_key="metrics")
    assert outcomes["clarity_health_flags"] == []
    assert outcomes["clarity_distribution_score_avg"] == 1.0


# ---------------------------------------------------------------------------
# Major 111: projection_health_summary and clarity_ranked_results in summaries
# ---------------------------------------------------------------------------


def _make_args(tmp_path: Path, **overrides: object) -> SimpleNamespace:
    base = dict(
        phase_a_configs=2,
        phase_a_turns=20,
        phase_b_top_k=2,
        seed=42,
        dry_run=True,
        reuse_backend=False,
        base_url="http://127.0.0.1:8000/api",
        spawn_port=8010,
        startup_timeout=5.0,
        storylet_count=15,
        diversity_every=8,
        diversity_chance=0.15,
        request_timeout_seconds=240.0,
        prefetch_wait_policy="bounded",
        prefetch_wait_timeout_seconds=3.0,
        switch_model=False,
        model_id="",
        quiet=True,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


_WORLD = WorldConfig(
    scenario_id="cyberpunk",
    scenario_title="Neon Pursuit",
    theme="cyberpunk noir",
    role="rogue AI hunter",
    description="Rain-soaked city.",
    key_elements=["neon"],
    tone="gritty",
)


def test_phase_a_summary_includes_projection_health_summary(tmp_path: Path) -> None:
    summary = run_phase_a(_make_args(tmp_path), run_dir=tmp_path, world=_WORLD)
    assert "projection_health_summary" in summary
    phc = summary["projection_health_summary"]
    assert "configs_with_warnings" in phc
    assert "warning_count" in phc
    assert "warnings" in phc
    assert isinstance(phc["warnings"], list)


def test_phase_a_summary_includes_clarity_ranked_results(tmp_path: Path) -> None:
    summary = run_phase_a(_make_args(tmp_path), run_dir=tmp_path, world=_WORLD)
    assert "clarity_ranked_results" in summary
    assert isinstance(summary["clarity_ranked_results"], list)
    assert "top_clarity_candidates" in summary
    assert isinstance(summary["top_clarity_candidates"], list)


def test_build_projection_health_summary_aggregates_warnings() -> None:
    results = [
        {"config_id": "a01", "projection_health_warnings": ["projection_waste_rate=0.95 > 0.90 threshold"]},
        {"config_id": "a02", "projection_health_warnings": []},
        {"config_id": "a03", "projection_health_warnings": ["no turns reached prepared or committed clarity level", "projection_hit_rate=0.0 for 15 turns"]},
    ]
    summary = _build_projection_health_summary(results)
    assert summary["warning_count"] == 3
    assert set(summary["configs_with_warnings"]) == {"a01", "a03"}
    assert len(summary["warnings"]) == 3


def test_build_projection_health_summary_empty_results() -> None:
    summary = _build_projection_health_summary([])
    assert summary["warning_count"] == 0
    assert summary["configs_with_warnings"] == []
    assert summary["warnings"] == []


def test_build_projection_health_summary_no_warnings() -> None:
    results = [{"config_id": "a01", "projection_health_warnings": []}]
    summary = _build_projection_health_summary(results)
    assert summary["warning_count"] == 0
    assert summary["configs_with_warnings"] == []
