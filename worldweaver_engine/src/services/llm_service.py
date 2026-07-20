# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Shared retried LLM calls."""

import logging
import json
import time
from typing import Any, Dict, List, Optional

from . import runtime_metrics
from .llm_client import get_trace_id, platform_shared_policy
from ..config import settings

logger = logging.getLogger(__name__)


def _shared_inference_policy(owner_id: str) -> Any:
    return platform_shared_policy(owner_id=owner_id)


_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_RETRYABLE_ERROR_NAMES = {"APITimeoutError", "APIConnectionError", "RateLimitError"}

# Callers choose the temperature explicitly for their own generation task.


def _coerce_non_negative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(round(value)))
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return 0
        try:
            return max(0, int(round(float(stripped))))
        except ValueError:
            return 0
    return 0


def _extract_token_usage(response: Any) -> Dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    if isinstance(usage, dict):
        prompt_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
        completion_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
        total_tokens = usage.get("total_tokens")
    else:
        prompt_tokens = getattr(
            usage, "prompt_tokens", getattr(usage, "input_tokens", None)
        )
        completion_tokens = getattr(
            usage,
            "completion_tokens",
            getattr(usage, "output_tokens", None),
        )
        total_tokens = getattr(usage, "total_tokens", None)

    input_tokens = _coerce_non_negative_int(prompt_tokens)
    output_tokens = _coerce_non_negative_int(completion_tokens)
    total = _coerce_non_negative_int(total_tokens) or input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
    }


def _log_llm_call_metrics(
    *,
    operation: str,
    model: str,
    duration_ms: float,
    status: str,
    attempt: int,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    error_type: Optional[str] = None,
) -> None:
    safe_attempt = _coerce_non_negative_int(attempt) or 1
    safe_input_tokens = _coerce_non_negative_int(input_tokens)
    safe_output_tokens = _coerce_non_negative_int(output_tokens)
    safe_total_tokens = _coerce_non_negative_int(total_tokens)

    payload: Dict[str, Any] = {
        "event": "llm_service_call_metrics",
        "component": "llm_service",
        "operation": operation,
        "trace_id": get_trace_id(),
        "model": model,
        "status": status,
        "duration_ms": round(max(0.0, float(duration_ms)), 3),
        "attempt": int(safe_attempt),
        "input_tokens": int(safe_input_tokens),
        "output_tokens": int(safe_output_tokens),
        "total_tokens": int(safe_total_tokens),
    }
    if error_type:
        payload["error_type"] = str(error_type)

    logger.info(json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str))
    runtime_metrics.record_llm_call(
        component="llm_service",
        operation=operation,
        model=model,
        duration_ms=duration_ms,
        status=status,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        trace_id=get_trace_id(),
    )


def _is_retryable_llm_error(exc: Exception) -> bool:
    """Return True when an LLM exception should be retried."""
    if isinstance(exc, TimeoutError):
        return True

    if exc.__class__.__name__ in _RETRYABLE_ERROR_NAMES:
        return True

    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int) and status_code in _RETRYABLE_STATUS_CODES:
        return True

    message = str(exc).lower()
    if "timed out" in message or "timeout" in message:
        return True
    if "rate limit" in message or "429" in message:
        return True

    return False


def _chat_completion_with_retry(
    client: Any,
    *,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout: int,
    response_format: Optional[Dict[str, str]] = None,
    metric_operation: str = "unknown",
) -> Any:
    """Call chat completions with timeout/retry for transient failures."""
    max_retries = max(0, int(settings.llm_retries))
    backoff_seconds = 1.0

    for attempt in range(max_retries + 1):
        started = time.perf_counter()
        try:
            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "timeout": timeout,
                "frequency_penalty": float(settings.llm_frequency_penalty),
                "presence_penalty": float(settings.llm_presence_penalty),
            }
            if response_format:
                kwargs["response_format"] = response_format
            response = client.chat.completions.create(**kwargs)
            usage = _extract_token_usage(response)
            _log_llm_call_metrics(
                operation=metric_operation,
                model=model,
                duration_ms=(time.perf_counter() - started) * 1000.0,
                status="ok",
                attempt=attempt + 1,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                total_tokens=usage["total_tokens"],
            )
            return response
        except Exception as exc:
            _log_llm_call_metrics(
                operation=metric_operation,
                model=model,
                duration_ms=(time.perf_counter() - started) * 1000.0,
                status="error",
                attempt=attempt + 1,
                error_type=exc.__class__.__name__,
            )
            is_last_attempt = attempt >= max_retries
            if is_last_attempt or not _is_retryable_llm_error(exc):
                raise

            logger.warning(
                "Transient LLM error (attempt %d/%d): %s",
                attempt + 1,
                max_retries + 1,
                exc,
            )
            time.sleep(backoff_seconds)
            backoff_seconds *= 2.0
