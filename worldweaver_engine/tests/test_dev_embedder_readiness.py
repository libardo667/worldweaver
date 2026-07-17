from scripts.dev import _ollama_has_model


def test_ollama_readiness_requires_the_configured_model():
    payload = {"models": [{"name": "nomic-embed-text:latest"}]}

    assert _ollama_has_model(payload, "nomic-embed-text") is True
    assert _ollama_has_model(payload, "different-model") is False
    assert _ollama_has_model({"models": []}, "nomic-embed-text") is False
