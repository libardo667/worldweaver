import os
from src.config import Settings, settings as global_settings
from src.services.llm_client import get_model, get_base_url


def test_api_key_precedence(monkeypatch):
    """Verify that OPENROUTER_API_KEY takes precedence over others."""
    # Test case 1: Only OPENAI_API_KEY
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    s1 = Settings()
    assert s1.get_effective_api_key() == "sk-openai"

    # Test case 2: LLM_API_KEY overrides OPENAI_API_KEY
    monkeypatch.setenv("LLM_API_KEY", "sk-llm")
    s2 = Settings()
    assert s2.get_effective_api_key() == "sk-llm"

    # Test case 3: OPENROUTER_API_KEY overrides all
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter")
    s3 = Settings()
    assert s3.get_effective_api_key() == "sk-openrouter"


def test_default_settings(monkeypatch):
    """Verify code defaults without .env or ambient env overrides."""
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    defaults = Settings(_env_file=None)
    assert defaults.llm_model == "aion-labs/aion-2.0"
    assert defaults.llm_base_url == "https://openrouter.ai/api/v1"


def test_llm_client_integration():
    """Verify llm_client.py uses the global settings."""
    # Note: These call the functions in llm_client.py which use the global 'settings' instance
    assert get_model() == global_settings.llm_model
    assert get_base_url() == global_settings.llm_base_url


def test_env_override(monkeypatch):
    """Verify that environment variables actually override defaults."""
    monkeypatch.setenv("LLM_MODEL", "anthropic/claude-3-opus")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.9")

    # Needs a fresh settings instance because Pydantic loads on init
    new_settings = Settings()
    assert new_settings.llm_model == "anthropic/claude-3-opus"
    assert new_settings.llm_temperature == 0.9


if __name__ == "__main__":
    # Simple monkeypatch implementation for standalone script
    class MonkeyPatch:
        def setenv(self, key, value):
            os.environ[key] = value

        def delenv(self, key, raising=True):
            if key in os.environ:
                del os.environ[key]

    mp = MonkeyPatch()
    print("Running test_api_key_precedence...")
    test_api_key_precedence(mp)
    print("Running test_default_settings...")
    test_default_settings()
    print("Running test_llm_client_integration...")
    test_llm_client_integration()
    print("Running test_env_override...")
    test_env_override(mp)
    print("All diagnostic tests PASSED!")
