from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from playtest_harness.long_run_harness import (
    WorldConfig,
    _prefetch_status_complete,
    _resolve_prefetch_wait_timeout_seconds,
    build_parameter_env_overrides_from_values,
)
from playtest_harness.parameter_sweep import (
    MAX_TOKENS_RANGE,
    RECENCY_PENALTY_RANGE,
    SEMANTIC_FLOOR_RANGE,
    TEMPERATURE_RANGE,
    _aggregate_phase_b_metrics,
    generate_phase_a_parameter_sets,
    motif_penalty_score,
    rank_phase_results,
    run_phase_a,
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
            {
                "config_id": "slow-clean",
                "metrics": {
                    "latency_ms_avg": 1500.0,
                    "exact_prefix_match_rate": 0.10,
                    "failure_rate": 0.0,
                },
            },
            {
                "config_id": "fast-repetitive",
                "metrics": {
                    "latency_ms_avg": 120.0,
                    "exact_prefix_match_rate": 0.85,
                    "failure_rate": 0.0,
                },
            },
            {
                "config_id": "unstable",
                "metrics": {
                    "latency_ms_avg": 80.0,
                    "exact_prefix_match_rate": 0.05,
                    "failure_rate": 0.5,
                },
            },
        ]
    )
    assert ranked[0]["config_id"] == "slow-clean"
    assert ranked[-1]["config_id"] == "unstable"


def test_rank_phase_results_uses_motif_reuse_signal() -> None:
    ranked = rank_phase_results(
        [
            {
                "config_id": "motif-heavy",
                "metrics": {
                    "latency_ms_avg": 300.0,
                    "exact_prefix_match_rate": 0.2,
                    "motif_reuse_rate": 0.9,
                    "failure_rate": 0.0,
                },
            },
            {
                "config_id": "motif-light",
                "metrics": {
                    "latency_ms_avg": 300.0,
                    "exact_prefix_match_rate": 0.2,
                    "motif_reuse_rate": 0.1,
                    "failure_rate": 0.0,
                },
            },
        ]
    )
    assert ranked[0]["config_id"] == "motif-light"
    assert ranked[1]["config_id"] == "motif-heavy"


def test_build_parameter_env_overrides_from_values_formats_expected() -> None:
    overrides = build_parameter_env_overrides_from_values(
        llm_temperature=0.27,
        llm_max_tokens=1337,
        llm_recency_penalty=0.42,
        llm_semantic_floor_probability=0.08,
    )
    assert overrides == {
        "LLM_TEMPERATURE": "0.2700",
        "LLM_MAX_TOKENS": "1337",
        "LLM_RECENCY_PENALTY": "0.4200",
        "LLM_SEMANTIC_FLOOR_PROBABILITY": "0.0800",
    }


def test_motif_penalty_score_uses_configured_weights() -> None:
    assert motif_penalty_score(motif_reuse_rate=0.4, motif_turn_overlap_rate_avg=0.1) == 0.28


def test_run_phase_a_dry_run_plans_configs(tmp_path: Path) -> None:
    world = WorldConfig(
        scenario_id="cyberpunk",
        scenario_title="Neon Pursuit",
        theme="cyberpunk noir",
        role="rogue AI hunter",
        description="Rain-soaked city with unstable AI traces.",
        key_elements=["neon", "rain", "drones"],
        tone="gritty",
    )
    args = SimpleNamespace(
        phase_a_configs=4,
        phase_a_turns=20,
        phase_b_top_k=4,
        seed=20260305,
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
    summary = run_phase_a(args, run_dir=tmp_path, world=world)
    assert summary["dry_run"] is True
    assert len(summary["planned"]) == 4
    assert summary["results"] == []
    assert len(summary["top_candidates"]) == 0
    assert summary["motif_ranked_results"] == []
    assert summary["top_motif_candidates"] == []
    assert summary["prefetch_wait_policy"] == "bounded"
    assert summary["prefetch_wait_timeout_seconds"] == 3.0
    assert summary["overhead_diagnostics"]["request_latency_ms_avg"] == 0.0
    assert summary["overhead_diagnostics"]["setup_total_ms_avg"] == 0.0
    summary_path = tmp_path / "phase_a_summary.json"
    assert summary_path.exists()


def test_prefetch_status_complete_uses_stable_shape_fields() -> None:
    assert _prefetch_status_complete({"stubs_cached": 1, "expires_in_seconds": 0}) is True
    assert _prefetch_status_complete({"stubs_cached": 0, "expires_in_seconds": 10}) is True
    assert _prefetch_status_complete({"stubs_cached": 0, "expires_in_seconds": 0}) is False


def test_prefetch_status_complete_honors_legacy_field_when_present() -> None:
    assert _prefetch_status_complete({"prefetch_complete": True}) is True
    assert _prefetch_status_complete({"prefetch_complete": False, "stubs_cached": 99, "expires_in_seconds": 99}) is False


def test_resolve_prefetch_wait_timeout_defaults_by_policy() -> None:
    assert _resolve_prefetch_wait_timeout_seconds(policy="off", configured=None) == 0.0
    assert _resolve_prefetch_wait_timeout_seconds(policy="bounded", configured=None) > 0.0
    assert _resolve_prefetch_wait_timeout_seconds(policy="strict", configured=None) >= 10.0
    assert _resolve_prefetch_wait_timeout_seconds(policy="bounded", configured=2.5) == 2.5


def test_aggregate_phase_b_metrics_includes_overhead_fields() -> None:
    aggregated = _aggregate_phase_b_metrics(
        [
            {
                "metrics": {
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
            },
            {
                "metrics": {
                    "latency_ms_avg": 200.0,
                    "latency_ms_p95": 260.0,
                    "request_latency_ms_avg": 200.0,
                    "request_latency_ms_p95": 260.0,
                    "prefetch_wait_ms_total": 70.0,
                    "prefetch_wait_ms_avg": 14.0,
                    "prefetch_wait_ms_p95": 24.0,
                    "turn_wallclock_ms_avg": 240.0,
                    "turn_wallclock_ms_p95": 300.0,
                    "harness_overhead_ms_total": 110.0,
                    "harness_overhead_ms_avg_per_request": 22.0,
                    "switch_model_ms": 0.0,
                    "hard_reset_ms": 16.0,
                    "bootstrap_ms": 48.0,
                    "setup_total_ms": 66.0,
                    "non_setup_non_prefetch_overhead_ms_total": 20.0,
                    "exact_prefix_match_rate": 0.4,
                    "motif_turns_with_tokens": 6.0,
                    "motif_total_tokens": 30.0,
                    "motif_unique_tokens": 18.0,
                    "motif_overlap_count": 12.0,
                    "motif_reused_tokens": 12.0,
                    "motif_reuse_rate": 0.4,
                    "motif_novelty_rate": 0.6,
                    "motif_turn_overlap_rate_avg": 0.35,
                    "failure_rate": 0.1,
                }
            },
        ]
    )
    assert aggregated["latency_ms_avg"] == 150.0
    assert aggregated["prefetch_wait_ms_avg"] == 12.0
    assert aggregated["turn_wallclock_ms_avg"] == 185.0
    assert aggregated["harness_overhead_ms_total"] == 95.0
    assert aggregated["setup_total_ms"] == 60.5
    assert aggregated["bootstrap_ms"] == 44.0
    assert aggregated["hard_reset_ms"] == 14.0
    assert aggregated["motif_total_tokens"] == 27.5
    assert aggregated["motif_unique_tokens"] == 19.0
    assert aggregated["motif_overlap_count"] == 8.5
    assert aggregated["motif_reuse_rate"] == 0.3
    assert aggregated["motif_novelty_rate"] == 0.7
    assert aggregated["motif_penalty_score"] == 0.3
