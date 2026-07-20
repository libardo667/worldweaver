import pytest

from src.services.llm_client import (
    InferencePolicy,
    _resolve_api_key_for_policy,
    agent_runtime_policy,
    platform_shared_policy,
)


@pytest.fixture(autouse=True)
def _isolate_llm_key_env(monkeypatch):
    # get_effective_api_key() reads os.environ before settings attributes, so these
    # key-resolution tests must not see ambient or test-leaked LLM key env vars.
    for var in ("OPENROUTER_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)


def test_platform_shared_policy_uses_platform_key(monkeypatch):
    monkeypatch.setattr(
        "src.services.llm_client.settings.openrouter_api_key", "sk-platform"
    )

    key, source = _resolve_api_key_for_policy(
        platform_shared_policy(owner_id="shared-op")
    )

    assert key == "sk-platform"
    assert source == "platform"


def test_agent_runtime_policy_uses_platform_key(monkeypatch):
    monkeypatch.setattr(
        "src.services.llm_client.settings.openrouter_api_key", "sk-platform"
    )

    key, source = _resolve_api_key_for_policy(
        agent_runtime_policy(owner_id="resident-123")
    )

    assert key == "sk-platform"
    assert source == "platform"


def test_policy_can_explicitly_disable_platform_inference(monkeypatch):
    monkeypatch.setattr(
        "src.services.llm_client.settings.openrouter_api_key", "sk-platform"
    )

    key, source = _resolve_api_key_for_policy(
        InferencePolicy(owner_type="agent_runtime", allow_platform_fallback=False)
    )

    assert key is None
    assert source == "none"
