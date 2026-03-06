"""Shared request-level helpers for game API endpoints."""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import Token
from typing import Mapping

from fastapi import Request

from ...services import runtime_metrics
from ...services.llm_client import get_trace_id


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
