from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from playtest_harness.long_run_harness import WorldConfig, build_parameter_env_overrides_from_values
from playtest_harness.parameter_sweep import (
    MAX_TOKENS_RANGE,
    NARRATOR_TEMPERATURE_RANGE,
    RECENCY_PENALTY_RANGE,
    REFEREE_TEMPERATURE_RANGE,
    SEMANTIC_FLOOR_RANGE,
    SweepParameterSet,
    generate_phase_a_parameter_sets,
    run_phase_a,
)
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


# ---------------------------------------------------------------------------
# Major 110: per-lane temperature axes
# ---------------------------------------------------------------------------


def test_phase_a_narrator_temperature_in_range() -> None:
    configs = generate_phase_a_parameter_sets(count=16, seed=100)
    for config in configs:
        assert NARRATOR_TEMPERATURE_RANGE[0] <= config.llm_narrator_temperature <= NARRATOR_TEMPERATURE_RANGE[1], (
            f"llm_narrator_temperature={config.llm_narrator_temperature} outside {NARRATOR_TEMPERATURE_RANGE}"
        )


def test_phase_a_referee_temperature_in_range() -> None:
    configs = generate_phase_a_parameter_sets(count=16, seed=100)
    for config in configs:
        assert REFEREE_TEMPERATURE_RANGE[0] <= config.llm_referee_temperature <= REFEREE_TEMPERATURE_RANGE[1], (
            f"llm_referee_temperature={config.llm_referee_temperature} outside {REFEREE_TEMPERATURE_RANGE}"
        )


def test_phase_a_other_axes_in_range() -> None:
    configs = generate_phase_a_parameter_sets(count=16, seed=100)
    for config in configs:
        assert MAX_TOKENS_RANGE[0] <= config.llm_max_tokens <= MAX_TOKENS_RANGE[1]
        assert RECENCY_PENALTY_RANGE[0] <= config.llm_recency_penalty <= RECENCY_PENALTY_RANGE[1]
        assert SEMANTIC_FLOOR_RANGE[0] <= config.llm_semantic_floor_probability <= SEMANTIC_FLOOR_RANGE[1]


def test_phase_a_narrator_and_referee_are_independent() -> None:
    """Narrator and referee temperatures must not be identical across all configs."""
    configs = generate_phase_a_parameter_sets(count=16, seed=7)
    diffs = [abs(c.llm_narrator_temperature - c.llm_referee_temperature) for c in configs]
    assert max(diffs) > 0.05, "narrator and referee temperatures appear identical across all configs"


def test_phase_a_no_legacy_llm_temperature_field() -> None:
    """SweepParameterSet must not expose the legacy llm_temperature field."""
    config = generate_phase_a_parameter_sets(count=1, seed=0)[0]
    assert not hasattr(config, "llm_temperature"), (
        "SweepParameterSet still has deprecated llm_temperature field"
    )


def test_phase_a_as_dict_contains_per_lane_keys() -> None:
    config = generate_phase_a_parameter_sets(count=1, seed=0)[0]
    d = config.as_dict()
    assert "llm_narrator_temperature" in d
    assert "llm_referee_temperature" in d
    assert "llm_temperature" not in d


def test_env_overrides_injects_narrator_and_referee_temperature() -> None:
    params = SweepParameterSet(
        llm_narrator_temperature=0.9,
        llm_referee_temperature=0.15,
        llm_max_tokens=1200,
        llm_recency_penalty=0.3,
        llm_semantic_floor_probability=0.05,
    )
    overrides = params.env_overrides()
    assert overrides["LLM_NARRATOR_TEMPERATURE"] == "0.9000"
    assert overrides["LLM_REFEREE_TEMPERATURE"] == "0.1500"


def test_env_overrides_does_not_inject_llm_temperature() -> None:
    """The sweep path must not set LLM_TEMPERATURE to avoid masking per-lane settings."""
    params = SweepParameterSet(
        llm_narrator_temperature=0.7,
        llm_referee_temperature=0.2,
        llm_max_tokens=1400,
        llm_recency_penalty=0.2,
        llm_semantic_floor_probability=0.1,
    )
    overrides = params.env_overrides()
    assert "LLM_TEMPERATURE" not in overrides


def test_build_env_overrides_per_lane_suppresses_legacy_temp() -> None:
    """When per-lane temps are provided, LLM_TEMPERATURE must not be injected."""
    overrides = build_parameter_env_overrides_from_values(
        llm_temperature=0.5,
        llm_narrator_temperature=0.8,
        llm_referee_temperature=0.2,
    )
    assert "LLM_NARRATOR_TEMPERATURE" in overrides
    assert "LLM_REFEREE_TEMPERATURE" in overrides
    assert "LLM_TEMPERATURE" not in overrides


def test_build_env_overrides_legacy_temp_when_no_per_lane() -> None:
    """When only llm_temperature is provided (no per-lane), LLM_TEMPERATURE is injected."""
    overrides = build_parameter_env_overrides_from_values(llm_temperature=0.6)
    assert overrides["LLM_TEMPERATURE"] == "0.6000"
    assert "LLM_NARRATOR_TEMPERATURE" not in overrides
    assert "LLM_REFEREE_TEMPERATURE" not in overrides


def test_build_env_overrides_single_per_lane_suppresses_legacy() -> None:
    """Even a single per-lane temp suppresses LLM_TEMPERATURE injection."""
    overrides_narrator = build_parameter_env_overrides_from_values(
        llm_temperature=0.5,
        llm_narrator_temperature=0.9,
    )
    assert "LLM_NARRATOR_TEMPERATURE" in overrides_narrator
    assert "LLM_TEMPERATURE" not in overrides_narrator

    overrides_referee = build_parameter_env_overrides_from_values(
        llm_temperature=0.5,
        llm_referee_temperature=0.1,
    )
    assert "LLM_REFEREE_TEMPERATURE" in overrides_referee
    assert "LLM_TEMPERATURE" not in overrides_referee


def test_dry_run_planned_parameters_use_per_lane_temps(tmp_path: Path) -> None:
    """Phase A dry-run planned records must use per-lane temperature keys."""
    world = WorldConfig(
        scenario_id="cyberpunk",
        scenario_title="Neon Pursuit",
        theme="cyberpunk noir",
        role="rogue AI hunter",
        description="Rain-soaked city.",
        key_elements=["neon"],
        tone="gritty",
    )
    args = SimpleNamespace(
        phase_a_configs=4,
        phase_a_turns=20,
        phase_b_top_k=4,
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
    summary = run_phase_a(args, run_dir=tmp_path, world=world)
    for plan_row in summary["planned"]:
        params = plan_row["parameters"]
        assert "llm_narrator_temperature" in params
        assert "llm_referee_temperature" in params
        assert "llm_temperature" not in params
        assert NARRATOR_TEMPERATURE_RANGE[0] <= params["llm_narrator_temperature"] <= NARRATOR_TEMPERATURE_RANGE[1]
        assert REFEREE_TEMPERATURE_RANGE[0] <= params["llm_referee_temperature"] <= REFEREE_TEMPERATURE_RANGE[1]
        env = plan_row["env_overrides"]
        assert "LLM_NARRATOR_TEMPERATURE" in env
        assert "LLM_REFEREE_TEMPERATURE" in env
        assert "LLM_TEMPERATURE" not in env
