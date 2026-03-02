"""Centralized LLM client factory.

All services that need an LLM should call ``get_llm_client()`` rather than
instantiating their own OpenAI client. This keeps the provider, API key,
base URL, and default model in one place.

Configuration is managed via ``src.config.settings``.

Supported OpenRouter models (Reputable):
    - deepseek/deepseek-r1           (Default / Best for JSON)
    - anthropic/claude-3.5-sonnet    (High Quality)
    - openai/gpt-4o                  (Standard)
    - meta-llama/llama-3.3-70b-instruct (Open Source)
    - google/gemini-2.0-pro-exp-02-05:free (Free/Fast)
"""

import os
import logging
from typing import Optional

from ..config import settings

logger = logging.getLogger(__name__)


def get_api_key() -> Optional[str]:
    """Return the LLM API key using centralized settings."""
    return settings.get_effective_api_key()


def get_base_url() -> str:
    """Return the LLM base URL (defaults to OpenRouter)."""
    return settings.llm_base_url


def get_model() -> str:
    """Return the default chat/completion model."""
    return settings.llm_model


def get_embedding_model() -> str:
    """Return the embedding model."""
    return settings.embedding_model


def get_llm_client():
    """Return an OpenAI-compatible client configured for the current provider.

    Raises ImportError if the ``openai`` package is not installed.
    Returns None if no API key is configured.
    """
    api_key = get_api_key()
    if not api_key:
        logger.warning("No LLM API key found in settings.")
        return None

    from openai import OpenAI

    return OpenAI(
        api_key=api_key,
        base_url=get_base_url(),
    )


def is_ai_disabled() -> bool:
    """Check if AI calls should be skipped (tests, fast mode, disabled)."""
    return bool(
        os.getenv("PYTEST_CURRENT_TEST")
        or os.getenv("DW_DISABLE_AI") == "1"
        or os.getenv("DW_FAST_TEST") == "1"
    )
