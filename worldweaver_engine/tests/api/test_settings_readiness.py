from src.config import settings


def test_settings_readiness_missing(monkeypatch, client):
    """Test readiness when keys are missing."""
    # Force state for test
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_model", "")
    monkeypatch.setattr(settings, "enable_projection_referee_scoring", False)

    response = client.get("/api/settings/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is False
    assert "api_key" in data["missing"]
    assert "model" in data["missing"]
    runtime = data["v3_runtime"]
    assert runtime["flags"]["projection_expansion_enabled"] is True
    assert runtime["flags"]["player_hint_channel_enabled"] is False
    assert runtime["flags"]["projection_seeded_narration_enabled"] is True
    assert runtime["flags"]["projection_referee_scoring_enabled"] is False
    assert runtime["budgets"]["max_projection_depth"] == 2
    assert runtime["budgets"]["max_projection_nodes"] == 12
    assert runtime["budgets"]["projection_time_budget_ms"] == 120
    assert runtime["budgets"]["projection_ttl_seconds"] == 180


def test_settings_readiness_partial(monkeypatch, client):
    """Test readiness when only model is set."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_model", "some-model")

    response = client.get("/api/settings/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is False
    assert "api_key" in data["missing"]
    assert "model" not in data["missing"]


def test_settings_readiness_complete(monkeypatch, client):
    """Test readiness when everything is set."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(settings, "llm_model", "test-model")

    response = client.get("/api/settings/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert len(data["missing"]) == 0
    assert "v3_runtime" in data


def test_settings_readiness_v3_runtime_overrides(monkeypatch, client):
    """Readiness reports runtime flag and budget overrides for reproducible runs."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    monkeypatch.setattr(settings, "enable_frontier_prefetch", True)
    monkeypatch.setattr(settings, "enable_v3_projection_expansion", False)
    monkeypatch.setattr(settings, "enable_v3_player_hint_channel", False)
    monkeypatch.setattr(settings, "enable_v3_projection_seeded_narration", False)
    monkeypatch.setattr(settings, "v3_projection_max_depth", 4)
    monkeypatch.setattr(settings, "v3_projection_max_nodes", 33)
    monkeypatch.setattr(settings, "v3_projection_time_budget_ms", 250)
    monkeypatch.setattr(settings, "v3_projection_ttl_seconds", 600)
    monkeypatch.setattr(settings, "prefetch_ttl_seconds", 600)
    monkeypatch.setattr(settings, "enable_projection_referee_scoring", False)

    response = client.get("/api/settings/readiness")
    assert response.status_code == 200
    data = response.json()

    runtime = data["v3_runtime"]
    assert runtime["flags"]["projection_expansion_enabled"] is False
    assert runtime["flags"]["player_hint_channel_enabled"] is False
    assert runtime["flags"]["projection_seeded_narration_enabled"] is False
    assert runtime["flags"]["projection_referee_scoring_enabled"] is False
    assert runtime["budgets"]["max_projection_depth"] == 4
    assert runtime["budgets"]["max_projection_nodes"] == 33
    assert runtime["budgets"]["projection_time_budget_ms"] == 250
    assert runtime["budgets"]["projection_ttl_seconds"] == 600


def test_update_api_key(client):
    """Test updating the API key."""
    # Reset state
    settings.openrouter_api_key = ""

    response = client.post("/api/settings/key", json={"api_key": "sk-new-key"})
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert settings.openrouter_api_key == "sk-new-key"


def test_update_api_key_blank(client):
    """Test updating with a blank key should fail."""
    response = client.post("/api/settings/key", json={"api_key": "  "})
    assert response.status_code == 422


def test_settings_readiness_adaptive_pruning_flags(monkeypatch, client):
    """Readiness reports adaptive_pruning_enabled and pressure_tiers_enabled (Minor 109)."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    monkeypatch.setattr(settings, "enable_adaptive_projection_pruning", True)
    monkeypatch.setattr(settings, "enable_projection_pressure_tiers", True)
    monkeypatch.setattr(settings, "projection_pressure_prune_threshold", 0.5)
    monkeypatch.setattr(settings, "projection_pressure_stubs_only_threshold", 0.9)

    response = client.get("/api/settings/readiness")
    assert response.status_code == 200
    data = response.json()

    runtime = data["v3_runtime"]
    assert runtime["flags"]["adaptive_pruning_enabled"] is True
    assert runtime["flags"]["pressure_tiers_enabled"] is True
    assert runtime["budgets"]["projection_pressure_prune_threshold"] == 0.5
    assert runtime["budgets"]["projection_pressure_stubs_only_threshold"] == 0.9


def test_settings_readiness_adaptive_pruning_flags_off_by_default(monkeypatch, client):
    """adaptive_pruning_enabled and pressure_tiers_enabled are False by default (Minor 109)."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    monkeypatch.setattr(settings, "enable_adaptive_projection_pruning", False)
    monkeypatch.setattr(settings, "enable_projection_pressure_tiers", False)

    response = client.get("/api/settings/readiness")
    assert response.status_code == 200
    data = response.json()

    runtime = data["v3_runtime"]
    assert runtime["flags"]["adaptive_pruning_enabled"] is False
    assert runtime["flags"]["pressure_tiers_enabled"] is False
