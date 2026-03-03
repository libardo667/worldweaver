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
import json
import logging
import time
from contextvars import ContextVar, Token
from typing import Any, Dict, Optional

from ..config import settings

logger = logging.getLogger(__name__)
_TRACE_ID_CONTEXT: ContextVar[str] = ContextVar("ww_trace_id", default="")


def set_trace_id(trace_id: str) -> Token:
    """Bind a request-scoped trace identifier to the current context."""
    return _TRACE_ID_CONTEXT.set(str(trace_id or "").strip())


def reset_trace_id(token: Token) -> None:
    """Reset request-scoped trace identifier context."""
    _TRACE_ID_CONTEXT.reset(token)


def get_trace_id() -> str:
    """Read the current request-scoped trace identifier."""
    trace_id = _TRACE_ID_CONTEXT.get()
    if trace_id:
        return trace_id
    return "no-trace"


def _log_structured_event(event: str, **fields: Any) -> None:
    """Emit a one-line JSON log payload for latency instrumentation."""
    payload: Dict[str, Any] = {
        "event": event,
        "trace_id": get_trace_id(),
    }
    payload.update(fields)
    logger.info(json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str))


class _InstrumentedCompletions:
    """Proxy around chat completions that adds duration logging."""

    def __init__(self, completions: Any):
        self._completions = completions

    def __getattr__(self, name: str) -> Any:
        return getattr(self._completions, name)

    def create(self, *args: Any, **kwargs: Any) -> Any:
        model = str(kwargs.get("model") or get_model())
        started = time.perf_counter()
        try:
            response = self._completions.create(*args, **kwargs)
            _log_structured_event(
                "llm_chat_timing",
                model=model,
                duration_ms=round((time.perf_counter() - started) * 1000.0, 3),
                status="ok",
            )
            return response
        except Exception as exc:
            _log_structured_event(
                "llm_chat_timing",
                model=model,
                duration_ms=round((time.perf_counter() - started) * 1000.0, 3),
                status="error",
                error_type=exc.__class__.__name__,
            )
            raise


class _InstrumentedChat:
    """Proxy around client.chat that wraps completions.create timing."""

    def __init__(self, chat: Any):
        self._chat = chat
        self.completions = _InstrumentedCompletions(chat.completions)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat, name)


class _InstrumentedEmbeddings:
    """Proxy around client.embeddings that logs create timing."""

    def __init__(self, embeddings: Any):
        self._embeddings = embeddings

    def __getattr__(self, name: str) -> Any:
        return getattr(self._embeddings, name)

    def create(self, *args: Any, **kwargs: Any) -> Any:
        model = str(kwargs.get("model") or get_embedding_model())
        started = time.perf_counter()
        try:
            response = self._embeddings.create(*args, **kwargs)
            _log_structured_event(
                "llm_embedding_timing",
                model=model,
                duration_ms=round((time.perf_counter() - started) * 1000.0, 3),
                status="ok",
            )
            return response
        except Exception as exc:
            _log_structured_event(
                "llm_embedding_timing",
                model=model,
                duration_ms=round((time.perf_counter() - started) * 1000.0, 3),
                status="error",
                error_type=exc.__class__.__name__,
            )
            raise


class _InstrumentedLLMClient:
    """Proxy around OpenAI client exposing timed chat + embedding calls."""

    def __init__(self, client: Any):
        self._client = client
        self.chat = _InstrumentedChat(client.chat)
        self.embeddings = _InstrumentedEmbeddings(client.embeddings)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


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

    client = OpenAI(
        api_key=api_key,
        base_url=get_base_url(),
    )
    return _InstrumentedLLMClient(client)


def is_ai_disabled() -> bool:
    """Check if AI calls should be skipped (tests, fast mode, disabled)."""
    return bool(
        os.getenv("PYTEST_CURRENT_TEST")
        or os.getenv("DW_DISABLE_AI") == "1"
        or os.getenv("DW_FAST_TEST") == "1"
    )
