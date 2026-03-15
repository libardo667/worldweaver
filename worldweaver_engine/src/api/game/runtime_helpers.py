"""Shared request-level helpers for game API endpoints."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import sys
import time
import uuid
from contextvars import Token
from typing import Any, Awaitable, Callable, Mapping, MutableMapping

from fastapi import Request

from ...services import runtime_metrics
from ...services.llm_client import get_trace_id


@dataclass(slots=True)
class RouteRuntimeContext:
    """Request-local runtime context used by endpoint wrappers."""

    trace_id: str
    metrics_route_token: Token
    request_started: float
    timings_ms: dict[str, float] = field(default_factory=dict)


def active_trace_id(request: Request | None = None) -> str:
    """Resolve the active trace id from request state/context or generate one."""
    if request is not None:
        req_trace = str(getattr(request.state, "trace_id", "")).strip()
        if req_trace:
            return req_trace

    trace_id = str(get_trace_id() or "").strip()
    if trace_id and trace_id != "no-trace":
        return trace_id
    return uuid.uuid4().hex


def begin_route_runtime(
    *,
    route: str,
    response: Any | None = None,
    request: Request | None = None,
    timing_seed: Mapping[str, float] | None = None,
) -> RouteRuntimeContext:
    """Initialize trace/header/metrics state for one request handler."""
    trace_id = active_trace_id(request)
    metrics_route_token = runtime_metrics.bind_metrics_route(route)
    if response is not None and hasattr(response, "headers"):
        response.headers.setdefault("X-WW-Trace-Id", trace_id)
    timings_ms = dict(timing_seed) if timing_seed else {}
    return RouteRuntimeContext(
        trace_id=trace_id,
        metrics_route_token=metrics_route_token,
        request_started=time.perf_counter(),
        timings_ms=timings_ms,
    )


def finalize_request_metrics(
    *,
    route: str,
    trace_id: str,
    session_id: str,
    request_started: float,
    timings_ms: Mapping[str, float],
    metrics_route_token: Token,
    logger: logging.Logger,
    status: str | None = None,
) -> None:
    """Record route duration, emit structured timing log, and reset route context."""
    route_key = str(route or "").strip()
    duration_ms = round((time.perf_counter() - request_started) * 1000.0, 3)
    final_status = ("error" if str(status or "").strip().lower() == "error" else "ok") if status is not None else ("error" if sys.exc_info()[0] is not None else "ok")
    runtime_metrics.record_route_timing(route_key, duration_ms, status=final_status)
    logger.info(
        json.dumps(
            {
                "event": "request_timing",
                "route": route_key,
                "trace_id": trace_id,
                "session_id": session_id,
                "duration_ms": duration_ms,
                "timings_ms": dict(timings_ms),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    runtime_metrics.reset_metrics_route(metrics_route_token)


def record_timing_ms(
    timings_ms: MutableMapping[str, float] | None,
    key: str,
    started: float,
) -> None:
    """Record one timing sample if a timing collector is present."""
    if timings_ms is None:
        return
    timings_ms[key] = round((time.perf_counter() - started) * 1000.0, 3)


def _prefetch_warning_message_suffix(warning_context: str) -> str:
    context = str(warning_context or "").strip()
    if not context:
        return ""
    return f" ({context})"


async def schedule_prefetch_async_best_effort(
    *,
    session_id: str,
    trigger: str,
    bind: Any,
    timings_ms: MutableMapping[str, float] | None,
    logger: logging.Logger,
    run_inference_thread_fn: Callable[..., Awaitable[Any]],
    schedule_prefetch_fn: Callable[..., Any],
    warning_context: str = "",
    timing_key: str = "schedule_prefetch",
) -> None:
    """Best-effort async prefetch scheduling with consistent timing capture."""
    prefetch_started = time.perf_counter()
    try:
        await run_inference_thread_fn(
            schedule_prefetch_fn,
            session_id,
            trigger=trigger,
            bind=bind,
        )
    except Exception as exc:
        logger.debug(
            "Could not schedule frontier prefetch%s: %s",
            _prefetch_warning_message_suffix(warning_context),
            exc,
        )
    finally:
        record_timing_ms(timings_ms, timing_key, prefetch_started)


def schedule_prefetch_sync_best_effort(
    *,
    session_id: str,
    trigger: str,
    bind: Any,
    timings_ms: MutableMapping[str, float] | None,
    logger: logging.Logger,
    schedule_prefetch_fn: Callable[..., Any],
    warning_context: str = "",
    timing_key: str = "schedule_prefetch",
) -> None:
    """Best-effort sync prefetch scheduling with consistent timing capture."""
    prefetch_started = time.perf_counter()
    try:
        schedule_prefetch_fn(
            session_id,
            trigger=trigger,
            bind=bind,
        )
    except Exception as exc:
        logger.debug(
            "Could not schedule frontier prefetch%s: %s",
            _prefetch_warning_message_suffix(warning_context),
            exc,
        )
    finally:
        record_timing_ms(timings_ms, timing_key, prefetch_started)
