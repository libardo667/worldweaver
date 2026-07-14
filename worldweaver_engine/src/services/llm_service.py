# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Shared retried LLM calls and world-entry card generation."""

import logging
import json
import time
from typing import Any, Dict, List, Optional

from . import runtime_metrics
from .llm_client import (
    get_llm_client,
    get_narrator_model,
    get_trace_id,
    platform_shared_policy,
)
from ..config import settings

logger = logging.getLogger(__name__)


def _shared_inference_policy(owner_id: str) -> Any:
    return platform_shared_policy(owner_id=owner_id)


_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_RETRYABLE_ERROR_NAMES = {"APITimeoutError", "APIConnectionError", "RateLimitError"}

# Lane-temperature contract:
#   Narrator calls  → settings.llm_narrator_temperature  (LLM_NARRATOR_TEMPERATURE, default 0.8)
#   Referee calls   → settings.llm_referee_temperature   (LLM_REFEREE_TEMPERATURE,  default 0.2)
# settings.llm_temperature (LLM_TEMPERATURE) is not used in this module; all calls are
# lane-routed.


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
        prompt_tokens = getattr(usage, "prompt_tokens", getattr(usage, "input_tokens", None))
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


# ---------------------------------------------------------------------------
# World entry cards
# ---------------------------------------------------------------------------


def generate_entry_cards(
    event_summaries: list[str],
    fact_summaries: list[str],
    existing_session_labels: list[str],
    world_name: str = "the world",
    known_locations: list[str] | None = None,
) -> dict:
    """Generate a world snapshot + 4 role cards for the entry screen."""
    from .prompt_library import build_entry_cards_prompt
    from .llm_json import extract_json_object

    _FALLBACK = {
        "snapshot": "The world stirs with quiet tension. Somewhere nearby, machinery groans against old stone.",
        "cards": [
            {
                "name": "The Newcomer",
                "role": "Stranger passing through",
                "flavor": "You arrived on the last supply run and haven't decided whether to stay.",
                "location": "market_square",
                "entry_action": "I step off the supply cart and look around, trying to get my bearings.",
            },
            {
                "name": "The Engineer",
                "role": "Infrastructure specialist",
                "flavor": "You know how these old systems work. You've seen what happens when they fail.",
                "location": "cistern_rim",
                "entry_action": "I crouch near the main junction and press my ear to the pipe, listening.",
            },
            {
                "name": "The Trader",
                "role": "Independent merchant",
                "flavor": "Your ledger knows every debt in this part of the Lows. Someone owes you answers.",
                "location": "market_square",
                "entry_action": "I spread my wares on the stall cloth and wait, watching who approaches.",
            },
            {
                "name": "The Watcher",
                "role": "Quiet observer",
                "flavor": "You notice things others don't. Right now, something is very wrong.",
                "location": "silt_flats",
                "entry_action": "I find a vantage point and observe the activity below without moving.",
            },
        ],
    }

    try:
        client = get_llm_client(policy=_shared_inference_policy("build_entry_cards"))
        if not client:
            return _FALLBACK

        from . import settings as _settings

        model = get_narrator_model()
        system_prompt, user_prompt = build_entry_cards_prompt(
            event_summaries=event_summaries,
            fact_summaries=fact_summaries,
            existing_session_labels=existing_session_labels,
            world_name=world_name,
            known_locations=known_locations,
        )

        response = _chat_completion_with_retry(
            client=client,
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=_settings.llm_narrator_temperature,
            max_tokens=1200,
            timeout=_settings.llm_timeout_seconds,
            operation="generate_entry_cards",
        )

        raw = response.choices[0].message.content or ""
        parsed = extract_json_object(raw)
        if not parsed:
            return _FALLBACK

        snapshot = str(parsed.get("snapshot", "")).strip()
        cards_raw = parsed.get("cards", [])
        if not snapshot or not isinstance(cards_raw, list) or len(cards_raw) < 2:
            return _FALLBACK

        cards = []
        for card in cards_raw[:4]:
            if not isinstance(card, dict):
                continue
            cards.append(
                {
                    "name": str(card.get("name", "")).strip(),
                    "role": str(card.get("role", "")).strip(),
                    "flavor": str(card.get("flavor", "")).strip(),
                    "location": str(card.get("location", "")).strip(),
                    "entry_action": str(card.get("entry_action", "")).strip(),
                }
            )

        if len(cards) < 2:
            return _FALLBACK

        return {"snapshot": snapshot, "cards": cards}

    except Exception as exc:
        logger.debug("generate_entry_cards failed (fallback): %s", exc)
        return _FALLBACK
