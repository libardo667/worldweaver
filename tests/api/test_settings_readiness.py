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

    response = client.get("/api/settings/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is False
    assert "api_key" in data["missing"]
    assert "model" in data["missing"]


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
