"""Tests for the steward-side model registry."""

from src.services.model_registry import (
    MODEL_REGISTRY,
    estimate_session_cost,
    get_model_info,
    list_available_models,
)

# ---------------------------------------------------------------------------
# model_registry unit tests
# ---------------------------------------------------------------------------


class TestModelRegistry:
    def test_registry_has_at_least_5_models(self):
        assert len(MODEL_REGISTRY) >= 5

    def test_every_model_has_required_fields(self):
        required = {"label", "tier", "input_per_m", "output_per_m", "context_window", "creative_quality", "notes"}
        for model_id, info in MODEL_REGISTRY.items():
            missing = required - set(info.keys())
            assert not missing, f"{model_id} missing fields: {missing}"

    def test_free_models_have_zero_cost(self):
        for model_id, info in MODEL_REGISTRY.items():
            if info["tier"] == "free":
                assert info["input_per_m"] == 0.0
                assert info["output_per_m"] == 0.0

    def test_estimate_session_cost_free_model(self):
        result = estimate_session_cost("arcee-ai/trinity-large-preview:free", turns=10)
        assert result["total_cost_usd"] == 0.0
        assert result["turns"] == 10
        assert result["input_tokens"] > 0
        assert result["output_tokens"] > 0

    def test_estimate_session_cost_paid_model(self):
        result = estimate_session_cost("anthropic/claude-sonnet-4", turns=10)
        assert result["total_cost_usd"] > 0.0
        assert result["tier"] == "standard"

    def test_estimate_session_cost_unknown_model(self):
        result = estimate_session_cost("unknown/model-xyz", turns=5)
        assert result["total_cost_usd"] == 0.0
        assert result["tier"] == "unknown"

    def test_estimate_session_cost_with_world_gen(self):
        without = estimate_session_cost("anthropic/claude-sonnet-4", turns=10, include_world_gen=False)
        with_gen = estimate_session_cost("anthropic/claude-sonnet-4", turns=10, include_world_gen=True)
        assert with_gen["total_cost_usd"] > without["total_cost_usd"]

    def test_get_model_info_known(self):
        info = get_model_info("deepseek/deepseek-r1")
        assert info is not None
        assert info["label"] == "DeepSeek R1"

    def test_get_model_info_unknown(self):
        assert get_model_info("unknown/model") is None

    def test_list_available_models_sorted_by_cost(self):
        models = list_available_models()
        costs = [m["estimated_10_turn_cost_usd"] for m in models]
        assert costs == sorted(costs), "Models should be sorted by cost"

    def test_list_available_models_has_all_registry_entries(self):
        models = list_available_models()
        assert len(models) == len(MODEL_REGISTRY)
