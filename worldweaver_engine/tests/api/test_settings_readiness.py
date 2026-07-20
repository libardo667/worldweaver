from src.config import settings


def test_settings_readiness_reports_missing_shard_infrastructure(monkeypatch, client):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_model", "")
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
    assert all(
        check["code"] not in {"api_key", "model", "demo_access", "observer_mode"}
        for check in data["checks"]
    )
    assert any(check["code"] == "public_url" for check in data["checks"])
    assert data["shard"]["city_id"] == settings.city_id


def test_missing_resident_inference_does_not_block_human_world_actions(
    monkeypatch, client
):
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
    assert checks["email_delivery"]["severity"] == "info"
    assert checks["agent_inference_key"]["ok"] is False
    assert checks["agent_inference_model"]["ok"] is False
    assert checks["agent_inference_key"]["severity"] == "info"
    assert (
        "Bounded resident runners verify their own key"
        in checks["agent_inference_key"]["message"]
    )


def test_required_email_verification_blocks_readiness_without_delivery(
    monkeypatch, client
):
    monkeypatch.setattr(settings, "jwt_secret", "test-secret")
    monkeypatch.setattr(settings, "data_encryption_key", "enc-key")
    monkeypatch.setattr(settings, "federation_url", "http://example.test")
    monkeypatch.setattr(settings, "public_url", "http://shard.example.test")
    monkeypatch.setattr(settings, "require_email_verification", True)
    monkeypatch.setattr(settings, "resend_api_key", "")
    monkeypatch.setattr(settings, "resend_from_email", "")

    data = client.get("/api/settings/readiness").json()
    checks = {check["code"]: check for check in data["checks"]}

    assert data["startup_ready"] is False
    assert "email_delivery" in data["runtime_missing"]
    assert checks["email_delivery"]["label"] == "Email verification"
    assert checks["email_delivery"]["severity"] == "error"
    assert checks["email_delivery"]["ok"] is False


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


def test_settings_readiness_world_shard_marks_city_checks_not_required(
    monkeypatch, client
):
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
    monkeypatch.setattr(settings, "node_private_key_path", None)

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
    assert checks["federation_auth"]["ok"] is True
    assert "Not required on the world shard" in checks["federation_auth"]["message"]


def test_configured_node_key_must_exist_and_be_private(monkeypatch, client, tmp_path):
    key_path = tmp_path / "node.key"
    key_path.write_text("not-secret-enough\n", encoding="utf-8")
    key_path.chmod(0o644)
    monkeypatch.setattr(settings, "shard_type", "city")
    monkeypatch.setattr(settings, "node_private_key_path", str(key_path))
    monkeypatch.setattr(settings, "jwt_secret", "test-secret")
    monkeypatch.setattr(settings, "data_encryption_key", "enc-key")
    monkeypatch.setattr(settings, "federation_url", "http://example.test")
    monkeypatch.setattr(settings, "public_url", "http://shard.example.test")

    data = client.get("/api/settings/readiness").json()
    checks = {check["code"]: check for check in data["checks"]}

    assert data["startup_ready"] is False
    assert "node_identity" in data["runtime_missing"]
    assert checks["node_identity"]["ok"] is False
    assert "readable by other users" in checks["node_identity"]["message"]
