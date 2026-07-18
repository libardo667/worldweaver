from src.config import settings


def test_settings_readiness_reports_missing_shard_infrastructure(monkeypatch, client):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_model", "")
    monkeypatch.setattr(settings, "enable_projection_referee_scoring", False)
    # The dev/test env supplies a real jwt_secret; force it absent so the
    # runtime_missing assertion below exercises the missing-secret path.
    monkeypatch.setattr(settings, "jwt_secret", "")

    response = client.get("/api/settings/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is False
    assert data["startup_ready"] is False
    assert data["missing"] == data["runtime_missing"]
    assert "jwt_secret" in data["runtime_missing"]
    assert all(check["code"] not in {"api_key", "model", "demo_access", "observer_mode"} for check in data["checks"])
    assert any(check["code"] == "public_url" for check in data["checks"])
    assert data["shard"]["city_id"] == settings.city_id
    runtime = data["v3_runtime"]
    assert runtime["flags"]["projection_expansion_enabled"] is True
    assert runtime["flags"]["player_hint_channel_enabled"] is False
    assert runtime["flags"]["projection_seeded_narration_enabled"] is True
    assert runtime["flags"]["projection_referee_scoring_enabled"] is False
    assert runtime["budgets"]["max_projection_depth"] == 2
    assert runtime["budgets"]["max_projection_nodes"] == 12
    assert runtime["budgets"]["projection_time_budget_ms"] == 120
    assert runtime["budgets"]["projection_ttl_seconds"] == 180


def test_missing_resident_inference_does_not_block_human_world_actions(monkeypatch, client):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_model", "")
    monkeypatch.setattr(settings, "jwt_secret", "test-secret")
    monkeypatch.setattr(settings, "data_encryption_key", "enc-key")
    monkeypatch.setattr(settings, "federation_url", "http://example.test")
    monkeypatch.setattr(settings, "public_url", "http://shard.example.test")

    response = client.get("/api/settings/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["startup_ready"] is True
    assert data["missing"] == []
    checks = {check["code"]: check for check in data["checks"]}
    assert checks["agent_inference_key"]["ok"] is False
    assert checks["agent_inference_model"]["ok"] is False
    assert "Human world actions still work" in checks["agent_inference_key"]["message"]


def test_settings_readiness_complete(monkeypatch, client):
    """Test readiness when everything is set."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    monkeypatch.setattr(settings, "jwt_secret", "test-secret")
    monkeypatch.setattr(settings, "data_encryption_key", "enc-key")
    monkeypatch.setattr(settings, "federation_url", "http://example.test")
    monkeypatch.setattr(settings, "public_url", "http://shard.example.test")

    response = client.get("/api/settings/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["startup_ready"] is True
    assert len(data["missing"]) == 0
    assert len(data["runtime_missing"]) == 0
    assert "v3_runtime" in data


def test_settings_readiness_world_shard_marks_city_checks_not_required(monkeypatch, client):
    """World shard diagnostics should not imply city-only federation config is missing."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    monkeypatch.setattr(settings, "jwt_secret", "test-secret")
    monkeypatch.setattr(settings, "data_encryption_key", "enc-key")
    monkeypatch.setattr(settings, "shard_type", "world")
    monkeypatch.setattr(settings, "city_id", "ww_world")
    monkeypatch.setattr(settings, "federation_url", "")
    monkeypatch.setattr(settings, "public_url", "")
    monkeypatch.setattr(settings, "federation_token", "")

    response = client.get("/api/settings/readiness")
    assert response.status_code == 200
    data = response.json()
    checks = {check["code"]: check for check in data["checks"]}

    assert data["startup_ready"] is True
    assert data["runtime_missing"] == []
    assert data["shard"]["shard_id"] == "ww_world"
    assert checks["federation_url"]["ok"] is True
    assert "Not required on the world shard" in checks["federation_url"]["message"]
    assert checks["public_url"]["ok"] is True
    assert "Not required on the world shard" in checks["public_url"]["message"]
    assert checks["federation_token"]["ok"] is True
    assert "Not required on the world shard" in checks["federation_token"]["message"]


def test_settings_readiness_v3_runtime_overrides(monkeypatch, client):
    """Readiness reports runtime flag and budget overrides for reproducible runs."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    monkeypatch.setattr(settings, "enable_v3_projection_expansion", False)
    monkeypatch.setattr(settings, "enable_v3_player_hint_channel", False)
    monkeypatch.setattr(settings, "enable_v3_projection_seeded_narration", False)
    monkeypatch.setattr(settings, "v3_projection_max_depth", 4)
    monkeypatch.setattr(settings, "v3_projection_max_nodes", 33)
    monkeypatch.setattr(settings, "v3_projection_time_budget_ms", 250)
    monkeypatch.setattr(settings, "v3_projection_ttl_seconds", 600)
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
