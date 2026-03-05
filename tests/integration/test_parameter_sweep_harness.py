from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from playtest_harness.long_run_harness import (
    WorldConfig,
    build_parameter_env_overrides_from_values,
)
from playtest_harness.parameter_sweep import (
    MAX_TOKENS_RANGE,
    RECENCY_PENALTY_RANGE,
    SEMANTIC_FLOOR_RANGE,
    TEMPERATURE_RANGE,
    generate_phase_a_parameter_sets,
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
        switch_model=False,
        model_id="",
        quiet=True,
    )
    summary = run_phase_a(args, run_dir=tmp_path, world=world)
    assert summary["dry_run"] is True
    assert len(summary["planned"]) == 4
    assert summary["results"] == []
    assert len(summary["top_candidates"]) == 0
    summary_path = tmp_path / "phase_a_summary.json"
    assert summary_path.exists()
