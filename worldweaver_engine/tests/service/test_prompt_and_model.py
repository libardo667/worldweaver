"""Tests for model_registry, prompt_library, and settings API endpoints."""

import inspect
import pytest

from src.services.model_registry import (
    MODEL_REGISTRY,
    estimate_session_cost,
    get_model_info,
    list_available_models,
)
from src.services import prompt_library

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


# ---------------------------------------------------------------------------
# prompt_library unit tests
# ---------------------------------------------------------------------------


class TestPromptLibrary:
    def test_narrative_voice_spec_is_nonempty(self):
        assert len(prompt_library.NARRATIVE_VOICE_SPEC) > 100

    def test_build_action_system_prompt(self):
        result = prompt_library.build_action_system_prompt()
        assert "narrate" in result.lower()
        assert "NARRATIVE VOICE" in result

    def test_action_stage_prompts_preserve_the_mutation_boundary(self):
        intent = prompt_library.build_action_intent_system_prompt()
        narration = prompt_library.build_action_narration_system_prompt()
        assert "delta may include only" in intent
        assert "may not propose new state mutations" in narration

    def test_entry_cards_prompt_uses_bounded_world_evidence(self):
        system, user = prompt_library.build_entry_cards_prompt(
            ["A bell rang."],
            ["The market is open."],
            ["Maya"],
            known_locations=["Market"],
        )
        assert "exactly 4 cards" in system
        assert "A bell rang." in user
        assert "Market" in user

    def test_build_scene_card_sensory_palette_is_deterministic(self):
        palette = prompt_library.build_scene_card_sensory_palette(
            {
                "location": "rust_gutters",
                "cast_on_stage": ["Kora-7", "Vane"],
                "immediate_stakes": "Signal loss is imminent.",
                "constraints_or_affordances": ["Weather hazard: acid rain"],
            }
        )
        assert set(palette.keys()) == {"smell", "sound", "tactile", "material", "object_hint"}
        assert "rust_gutters" in palette["smell"]

    def test_motif_auditor_and_revision_prompts_exist(self):
        auditor = prompt_library.build_motif_auditor_system_prompt()
        revision = prompt_library.build_motif_revision_system_prompt()
        assert "decision" in auditor
        assert "Return JSON only" in auditor
        assert "single key: text" in revision


# ---------------------------------------------------------------------------
# settings_api integration tests
# ---------------------------------------------------------------------------


class TestSettingsAPI:
    """Test model API endpoints via the FastAPI test client."""

    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI app."""
        import os

        os.environ["WW_DISABLE_AI"] = "1"  # Don't need real LLM
        from fastapi.testclient import TestClient
        from main import app

        return TestClient(app)

    def test_list_models(self, client):
        resp = client.get("/api/models")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 5
        # Check first model has expected fields
        first = data[0]
        assert "model_id" in first
        assert "label" in first
        assert "tier" in first
        assert "estimated_10_turn_cost_usd" in first

    def test_get_current_model(self, client):
        resp = client.get("/api/model")
        assert resp.status_code == 200
        data = resp.json()
        assert "model_id" in data
        assert "ai_enabled" in data
        assert "estimated_session_cost" in data

    def test_switch_model(self, client):
        resp = client.put(
            "/api/model",
            json={"model_id": "arcee-ai/trinity-large-preview:free"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["current_model"] == "arcee-ai/trinity-large-preview:free"
        assert data["estimated_10_turn_cost_usd"] == 0.0

        # Verify the switch persisted
        resp2 = client.get("/api/model")
        assert resp2.json()["model_id"] == "arcee-ai/trinity-large-preview:free"

    def test_switch_to_unknown_model(self, client):
        resp = client.put(
            "/api/model",
            json={"model_id": "custom/my-fine-tuned-model"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "not in registry" in data["message"]

    def test_switch_model_empty_id_rejected(self, client):
        resp = client.put("/api/model", json={"model_id": ""})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Major 110: narrator temperature lane-contract regression tests
# ---------------------------------------------------------------------------


def test_llm_service_lane_temperature_comment_documents_contract() -> None:
    """The lane-temperature contract comment block must still be present."""
    from src.services import llm_service

    source = inspect.getsource(llm_service)
    assert "LLM_NARRATOR_TEMPERATURE" in source
    assert "LLM_REFEREE_TEMPERATURE" in source
    assert "settings.llm_temperature (LLM_TEMPERATURE) is not used in this module" in source
