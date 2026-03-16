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
from dataclasses import dataclass
from contextvars import ContextVar, Token
from typing import Any, Callable, Dict, Literal, Optional, ParamSpec, TypeVar

import anyio

from ..config import settings

logger = logging.getLogger(__name__)
_TRACE_ID_CONTEXT: ContextVar[str] = ContextVar("ww_trace_id", default="")
_P = ParamSpec("_P")
_T = TypeVar("_T")

InferenceOwnerType = Literal["platform_shared", "actor_private", "agent_runtime"]
InferenceKeySource = Literal["platform", "actor", "none"]


@dataclass(frozen=True)
class InferencePolicy:
    """Explicit ownership contract for one inference call tree."""

    owner_type: InferenceOwnerType
    owner_id: str = ""
    actor_api_key: str | None = None
    allow_actor_key: bool = False
    allow_platform_fallback: bool = True


def platform_shared_policy(owner_id: str = "") -> InferencePolicy:
    return InferencePolicy(
        owner_type="platform_shared",
        owner_id=str(owner_id or "").strip(),
        actor_api_key=None,
        allow_actor_key=False,
        allow_platform_fallback=True,
    )


def actor_private_policy(
    *,
    owner_id: str = "",
    actor_api_key: str | None = None,
    allow_platform_fallback: bool = True,
) -> InferencePolicy:
    return InferencePolicy(
        owner_type="actor_private",
        owner_id=str(owner_id or "").strip(),
        actor_api_key=str(actor_api_key or "").strip() or None,
        allow_actor_key=True,
        allow_platform_fallback=bool(allow_platform_fallback),
    )


def agent_runtime_policy(owner_id: str = "") -> InferencePolicy:
    return InferencePolicy(
        owner_type="agent_runtime",
        owner_id=str(owner_id or "").strip(),
        actor_api_key=None,
        allow_actor_key=False,
        allow_platform_fallback=True,
    )


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
    trace_id = get_trace_id()
    payload: Dict[str, Any] = {
        "event": event,
        "trace_id": trace_id,
        "correlation_id": trace_id,
    }
    payload.update(fields)
    logger.info(json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str))


class _InstrumentedCompletions:
    """Proxy around chat completions that adds duration logging."""

    def __init__(
        self,
        completions: Any,
        *,
        inference_policy: InferencePolicy | None = None,
        key_source: InferenceKeySource = "none",
    ):
        self._completions = completions
        self._inference_policy = inference_policy or platform_shared_policy()
        self._key_source = key_source

    def __getattr__(self, name: str) -> Any:
        return getattr(self._completions, name)

    def create(self, *args: Any, **kwargs: Any) -> Any:
        model = str(kwargs.get("model") or get_model())
        started = time.perf_counter()
        try:
            response = self._completions.create(*args, **kwargs)
            _log_structured_event(
                "llm_call",
                operation="chat.completions.create",
                model=model,
                duration_ms=round((time.perf_counter() - started) * 1000.0, 3),
                status="ok",
                owner_type=self._inference_policy.owner_type,
                owner_id=self._inference_policy.owner_id or None,
                key_source=self._key_source,
            )
            return response
        except Exception as exc:
            _log_structured_event(
                "llm_call",
                operation="chat.completions.create",
                model=model,
                duration_ms=round((time.perf_counter() - started) * 1000.0, 3),
                status="error",
                error_type=exc.__class__.__name__,
                owner_type=self._inference_policy.owner_type,
                owner_id=self._inference_policy.owner_id or None,
                key_source=self._key_source,
            )
            raise


class _InstrumentedChat:
    """Proxy around client.chat that wraps completions.create timing."""

    def __init__(
        self,
        chat: Any,
        *,
        inference_policy: InferencePolicy | None = None,
        key_source: InferenceKeySource = "none",
    ):
        self._chat = chat
        self.completions = _InstrumentedCompletions(
            chat.completions,
            inference_policy=inference_policy,
            key_source=key_source,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat, name)


class _InstrumentedEmbeddings:
    """Proxy around client.embeddings that logs create timing."""

    def __init__(
        self,
        embeddings: Any,
        *,
        inference_policy: InferencePolicy | None = None,
        key_source: InferenceKeySource = "none",
    ):
        self._embeddings = embeddings
        self._inference_policy = inference_policy or platform_shared_policy()
        self._key_source = key_source

    def __getattr__(self, name: str) -> Any:
        return getattr(self._embeddings, name)

    def create(self, *args: Any, **kwargs: Any) -> Any:
        model = str(kwargs.get("model") or get_embedding_model())
        started = time.perf_counter()
        try:
            response = self._embeddings.create(*args, **kwargs)
            _log_structured_event(
                "llm_call",
                operation="embeddings.create",
                model=model,
                duration_ms=round((time.perf_counter() - started) * 1000.0, 3),
                status="ok",
                owner_type=self._inference_policy.owner_type,
                owner_id=self._inference_policy.owner_id or None,
                key_source=self._key_source,
            )
            return response
        except Exception as exc:
            _log_structured_event(
                "llm_call",
                operation="embeddings.create",
                model=model,
                duration_ms=round((time.perf_counter() - started) * 1000.0, 3),
                status="error",
                error_type=exc.__class__.__name__,
                owner_type=self._inference_policy.owner_type,
                owner_id=self._inference_policy.owner_id or None,
                key_source=self._key_source,
            )
            raise


class _InstrumentedLLMClient:
    """Proxy around OpenAI client exposing timed chat + embedding calls."""

    def __init__(
        self,
        client: Any,
        *,
        inference_policy: InferencePolicy | None = None,
        key_source: InferenceKeySource = "none",
    ):
        self._client = client
        self._inference_policy = inference_policy or platform_shared_policy()
        self._key_source = key_source
        self.chat = _InstrumentedChat(
            client.chat,
            inference_policy=self._inference_policy,
            key_source=self._key_source,
        )
        self.embeddings = _InstrumentedEmbeddings(
            client.embeddings,
            inference_policy=self._inference_policy,
            key_source=self._key_source,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def _resolve_api_key_for_policy(
    policy: InferencePolicy | None = None,
) -> tuple[Optional[str], InferenceKeySource]:
    active_policy = policy or platform_shared_policy()
    owner_type = active_policy.owner_type

    if owner_type != "actor_private" and active_policy.allow_actor_key:
        raise ValueError(f"{owner_type} inference may not opt into actor keys.")
    if owner_type != "actor_private" and active_policy.actor_api_key:
        raise ValueError(f"{owner_type} inference may not carry an actor API key.")

    actor_key = str(active_policy.actor_api_key or "").strip()
    if owner_type == "actor_private" and active_policy.allow_actor_key and actor_key:
        return actor_key, "actor"

    if active_policy.allow_platform_fallback:
        platform_key = settings.get_effective_api_key()
        if platform_key:
            return platform_key, "platform"

    return None, "none"


def get_api_key(policy: InferencePolicy | None = None) -> Optional[str]:
    """Return the LLM API key for an explicit inference policy."""
    api_key, _ = _resolve_api_key_for_policy(policy)
    return api_key


def get_base_url() -> str:
    """Return the LLM base URL (defaults to OpenRouter)."""
    return settings.llm_base_url


def get_model() -> str:
    """Return the default chat/completion model."""
    return settings.llm_model


def get_referee_model() -> str:
    """Return model for strict planner/referee lane."""
    override = str(settings.llm_referee_model or "").strip()
    return override or get_model()


def get_narrator_model() -> str:
    """Return model for creative narrator lane."""
    override = str(settings.llm_narrator_model or "").strip()
    return override or get_model()


def get_embedding_model() -> str:
    """Return the embedding model."""
    return settings.embedding_model


def get_llm_client(policy: InferencePolicy | None = None):
    """Return an OpenAI-compatible client configured for the current provider.

    Raises ImportError if the ``openai`` package is not installed.
    Returns None if no API key is configured.
    """
    active_policy = policy or platform_shared_policy()
    api_key, key_source = _resolve_api_key_for_policy(active_policy)
    if not api_key:
        logger.warning("No LLM API key found in settings.")
        return None

    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url=get_base_url(),
    )
    return _InstrumentedLLMClient(
        client,
        inference_policy=active_policy,
        key_source=key_source,
    )


def is_ai_disabled() -> bool:
    """Check if AI calls should be skipped (tests, fast mode, disabled)."""
    return bool(os.getenv("PYTEST_CURRENT_TEST") or os.getenv("WW_DISABLE_AI") == "1" or os.getenv("WW_FAST_TEST") == "1")


async def run_inference_thread(
    fn: Callable[_P, _T],
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> _T:
    """Run blocking inference work in a worker thread from async routes."""

    def _invoke() -> _T:
        return fn(*args, **kwargs)

    return await anyio.to_thread.run_sync(_invoke)
