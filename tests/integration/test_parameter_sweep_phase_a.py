from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from playtest_harness.long_run_harness import WorldConfig, build_parameter_env_overrides_from_values
from playtest_harness.parameter_sweep import run_phase_a
from tests.integration_harness_helpers import assert_metric_values


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
    assert summary["projection_ranked_results"] == []
    assert summary["top_projection_candidates"] == []
    assert summary["prefetch_wait_policy"] == "bounded"
    assert summary["prefetch_wait_timeout_seconds"] == 3.0
    assert_metric_values(
        summary["overhead_diagnostics"],
        {
            "request_latency_ms_avg": 0.0,
            "setup_total_ms_avg": 0.0,
            "projection_hit_rate_avg": 0.0,
            "projection_hit_rate_p95": 0.0,
        },
    )
    summary_path = tmp_path / "phase_a_summary.json"
    assert summary_path.exists()
