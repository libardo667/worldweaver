"""Integration tests for Major 104 — v3 lane-matrix and projection-budget sweep harness.

Covers:
- Lane/budget axis expansion shape and deduplication
- Deterministic seed schedule parity across compared configs
- Phase-A manifest field shape (lane_budget_axes, seed_schedule, planned_seeds)
- Secondary ranking correctness for projection quality
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from playtest_harness.parameter_sweep import (
    LANE_MATRIX_PRESET_OFF,
    LANE_MATRIX_PRESET_V3_DEFAULT,
    LaneBudgetVariant,
    _build_seed_schedule,
    _lane_budget_axes_payload,
    _rank_phase_results_by_projection_efficiency,
    _resolve_lane_budget_variants,
    _validate_shared_seed_schedule,
    run_phase_a,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_args(**overrides) -> SimpleNamespace:
    """Return a minimal dry-run phase-A args namespace."""
    defaults = dict(
        phase_a_configs=2,
        phase_a_turns=10,
        phase_b_top_k=2,
        seed=20260101,
        dry_run=True,
        reuse_backend=False,
        base_url="http://127.0.0.1:8000/api",
        spawn_port=8010,
        startup_timeout=5.0,
        storylet_count=10,
        diversity_every=8,
        diversity_chance=0.15,
        request_timeout_seconds=60.0,
        prefetch_wait_policy="bounded",
        prefetch_wait_timeout_seconds=3.0,
        switch_model=False,
        model_id="",
        quiet=True,
        lane_narrator_models=None,
        lane_referee_models=None,
        projection_depth_options=None,
        projection_node_options=None,
        projection_time_budget_ms_options=None,
        lane_matrix_preset=LANE_MATRIX_PRESET_OFF,
        _resolved_lane_budget_variants=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _world():
    from playtest_harness.long_run_harness import WorldConfig

    return WorldConfig(
        scenario_id="test",
        scenario_title="Test World",
        theme="test theme",
        role="adventurer",
        description="A world for testing.",
        key_elements=["stone", "mist"],
        tone="neutral",
    )


# ---------------------------------------------------------------------------
# Phase 1 — Lane/budget axis expansion shape (Major 104)
# ---------------------------------------------------------------------------


class TestLaneBudgetAxisExpansion:
    def test_empty_axes_yields_single_default_variant(self) -> None:
        args = _base_args()
        variants = _resolve_lane_budget_variants(args)
        assert len(variants) == 1
        v = variants[0]
        assert v.llm_narrator_model is None
        assert v.llm_referee_model is None
        assert v.v3_projection_max_nodes is None

    def test_narrator_model_axis_produces_one_variant_per_model(self) -> None:
        args = _base_args(lane_narrator_models="model-a,model-b")
        variants = _resolve_lane_budget_variants(args)
        narrator_models = [v.llm_narrator_model for v in variants]
        assert "model-a" in narrator_models
        assert "model-b" in narrator_models

    def test_narrator_x_referee_cross_product(self) -> None:
        args = _base_args(lane_narrator_models="na,nb", lane_referee_models="ra,rb")
        variants = _resolve_lane_budget_variants(args)
        assert len(variants) == 4
        pairs = {(v.llm_narrator_model, v.llm_referee_model) for v in variants}
        assert ("na", "ra") in pairs
        assert ("na", "rb") in pairs
        assert ("nb", "ra") in pairs
        assert ("nb", "rb") in pairs

    def test_projection_budget_axis_expands_correctly(self) -> None:
        args = _base_args(projection_node_options="6,12", projection_depth_options="2")
        variants = _resolve_lane_budget_variants(args)
        node_values = {v.v3_projection_max_nodes for v in variants}
        assert 6 in node_values
        assert 12 in node_values
        assert all(v.v3_projection_max_depth == 2 for v in variants)

    def test_v3_default_preset_yields_multiple_variants(self) -> None:
        args = _base_args(lane_matrix_preset=LANE_MATRIX_PRESET_V3_DEFAULT)
        variants = _resolve_lane_budget_variants(args)
        assert len(variants) >= 2, "v3-default preset must produce at least 2 lane variants"

    def test_duplicate_axis_values_are_deduplicated(self) -> None:
        args = _base_args(projection_node_options="8,8,12")
        variants = _resolve_lane_budget_variants(args)
        node_values = [v.v3_projection_max_nodes for v in variants]
        assert node_values.count(8) == 1

    def test_lane_budget_axes_payload_shape(self) -> None:
        variants = [
            LaneBudgetVariant(llm_narrator_model="na", llm_referee_model="ra", v3_projection_max_nodes=8),
            LaneBudgetVariant(llm_narrator_model="nb", llm_referee_model="rb", v3_projection_max_nodes=12),
        ]
        payload = _lane_budget_axes_payload(variants)
        assert "llm_narrator_models" in payload
        assert "llm_referee_models" in payload
        assert "v3_projection_max_nodes_options" in payload
        assert "na" in payload["llm_narrator_models"]
        assert "nb" in payload["llm_narrator_models"]
        assert 8 in payload["v3_projection_max_nodes_options"]
        assert 12 in payload["v3_projection_max_nodes_options"]


# ---------------------------------------------------------------------------
# Phase 2 — Deterministic seed parity (Major 104)
# ---------------------------------------------------------------------------


class TestSeedScheduleParity:
    def test_build_seed_schedule_is_deterministic(self) -> None:
        s1 = _build_seed_schedule(seed_base=100, runs_per_config=3)
        s2 = _build_seed_schedule(seed_base=100, runs_per_config=3)
        assert s1 == s2

    def test_build_seed_schedule_length_matches_runs_per_config(self) -> None:
        schedule = _build_seed_schedule(seed_base=42, runs_per_config=5)
        assert len(schedule) == 5

    def test_seed_schedule_is_contiguous_from_base(self) -> None:
        schedule = _build_seed_schedule(seed_base=1000, runs_per_config=4)
        assert schedule == [1000, 1001, 1002, 1003]

    def test_validate_shared_seed_schedule_passes_matching_rows(self) -> None:
        schedule = [10, 11, 12]
        rows = [
            {"config_id": "a", "planned_seeds": [10, 11, 12]},
            {"config_id": "b", "planned_seeds": [10, 11, 12]},
        ]
        # Must not raise
        _validate_shared_seed_schedule(rows, schedule, context="test")

    def test_validate_shared_seed_schedule_raises_on_mismatch(self) -> None:
        import pytest

        schedule = [10, 11, 12]
        rows = [
            {"config_id": "a", "planned_seeds": [10, 11, 12]},
            {"config_id": "b", "planned_seeds": [10, 11, 99]},
        ]
        with pytest.raises(ValueError, match="seed schedule mismatch"):
            _validate_shared_seed_schedule(rows, schedule, context="test")

    def test_validate_shared_seed_schedule_skips_rows_without_seeds(self) -> None:
        schedule = [5, 6]
        rows = [{"config_id": "a"}, {"config_id": "b", "planned_seeds": [5, 6]}]
        # Must not raise — rows without seeds are not validated
        _validate_shared_seed_schedule(rows, schedule, context="test")


# ---------------------------------------------------------------------------
# Phase 3 — Manifest field shape (Major 104)
# ---------------------------------------------------------------------------


class TestPhaseAManifestShape:
    def test_phase_a_dry_run_summary_includes_seed_schedule(self, tmp_path: Path) -> None:
        summary = run_phase_a(_base_args(), run_dir=tmp_path, world=_world())
        assert "seed_schedule" in summary
        assert isinstance(summary["seed_schedule"], list)
        assert len(summary["seed_schedule"]) >= 1

    def test_phase_a_dry_run_summary_includes_lane_budget_axes(self, tmp_path: Path) -> None:
        summary = run_phase_a(_base_args(), run_dir=tmp_path, world=_world())
        assert "lane_budget_axes" in summary
        axes = summary["lane_budget_axes"]
        assert "llm_narrator_models" in axes
        assert "llm_referee_models" in axes
        assert "v3_projection_max_nodes_options" in axes

    def test_phase_a_planned_rows_carry_seed_schedule(self, tmp_path: Path) -> None:
        summary = run_phase_a(_base_args(), run_dir=tmp_path, world=_world())
        planned = summary.get("planned", [])
        assert planned, "Expected at least one planned config"
        for row in planned:
            assert "seed_schedule" in row, f"planned row missing seed_schedule: {row.keys()}"
            assert isinstance(row["seed_schedule"], list)

    def test_phase_a_summary_quality_gate_includes_seed_validated(self, tmp_path: Path) -> None:
        summary = run_phase_a(_base_args(), run_dir=tmp_path, world=_world())
        gate = summary.get("quality_gate_outcomes", {})
        assert gate.get("shared_seed_schedule_validated") is True

    def test_phase_a_with_lane_models_axis_manifest_captures_models(self, tmp_path: Path) -> None:
        args = _base_args(lane_narrator_models="model-x,model-y")
        summary = run_phase_a(args, run_dir=tmp_path, world=_world())
        axes = summary["lane_budget_axes"]
        assert "model-x" in axes["llm_narrator_models"]
        assert "model-y" in axes["llm_narrator_models"]


# ---------------------------------------------------------------------------
# Phase 3 — Secondary projection-quality ranking (Major 104)
# ---------------------------------------------------------------------------


class TestProjectionQualityRanking:
    def _make_run(self, config_id: str, hit_rate: float, waste_rate: float, veto_rate: float = 0.0) -> dict:
        return {
            "config_id": config_id,
            "metrics": {
                "projection_hit_rate": hit_rate,
                "projection_waste_rate": waste_rate,
                "projection_veto_rate": veto_rate,
                "total_turns": 10,
            },
        }

    def test_higher_hit_rate_ranks_better(self) -> None:
        results = [
            self._make_run("low", hit_rate=0.2, waste_rate=0.1),
            self._make_run("high", hit_rate=0.8, waste_rate=0.1),
        ]
        ranked = _rank_phase_results_by_projection_efficiency(results)
        assert ranked[0]["config_id"] == "high"

    def test_lower_waste_rate_ranks_better_when_hit_rates_equal(self) -> None:
        results = [
            self._make_run("wasteful", hit_rate=0.5, waste_rate=0.5),
            self._make_run("efficient", hit_rate=0.5, waste_rate=0.1),
        ]
        ranked = _rank_phase_results_by_projection_efficiency(results)
        assert ranked[0]["config_id"] == "efficient"

    def test_ranking_is_stable_for_identical_metrics(self) -> None:
        results = [
            self._make_run("a", hit_rate=0.5, waste_rate=0.2),
            self._make_run("b", hit_rate=0.5, waste_rate=0.2),
        ]
        ranked = _rank_phase_results_by_projection_efficiency(results)
        assert len(ranked) == 2

    def test_empty_results_returns_empty_list(self) -> None:
        assert _rank_phase_results_by_projection_efficiency([]) == []

    def test_single_result_returns_itself(self) -> None:
        run = self._make_run("only", hit_rate=0.6, waste_rate=0.3)
        ranked = _rank_phase_results_by_projection_efficiency([run])
        assert len(ranked) == 1
        assert ranked[0]["config_id"] == "only"
