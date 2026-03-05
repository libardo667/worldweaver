"""In-memory runtime metrics for local tuning and diagnostics."""

from __future__ import annotations

import threading
from collections import deque
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any, Dict, List

_MAX_ROUTE_SAMPLES = 120
_MAX_RECENT_LLM_EVENTS = 80
_ROUTE_CONTEXT: ContextVar[str] = ContextVar("ww_metrics_route", default="")
_LOCK = threading.Lock()

_ROUTE_METRICS: Dict[str, Dict[str, Any]] = {}
_LLM_CALL_DURATIONS_MS: deque[float] = deque(maxlen=_MAX_RECENT_LLM_EVENTS)
_RECENT_LLM_EVENTS: deque[Dict[str, Any]] = deque(maxlen=_MAX_RECENT_LLM_EVENTS)
_LLM_TOTAL_CALLS = 0
_LLM_TOTAL_ERRORS = 0


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    idx = int(round((len(sorted_values) - 1) * percentile))
    idx = max(0, min(idx, len(sorted_values) - 1))
    return float(sorted_values[idx])


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


def _ensure_route(route: str) -> Dict[str, Any]:
    if route not in _ROUTE_METRICS:
        _ROUTE_METRICS[route] = {
            "requests": 0,
            "errors": 0,
            "duration_total_ms": 0.0,
            "duration_samples_ms": deque(maxlen=_MAX_ROUTE_SAMPLES),
            "last_duration_ms": 0.0,
            "llm_calls": 0,
            "llm_errors": 0,
            "llm_input_tokens": 0,
            "llm_output_tokens": 0,
            "llm_total_tokens": 0,
            "updated_at": "",
        }
    return _ROUTE_METRICS[route]


def bind_metrics_route(route: str) -> Token:
    """Bind request route to current context for LLM metrics attribution."""
    return _ROUTE_CONTEXT.set(str(route or "").strip())


def reset_metrics_route(token: Token) -> None:
    """Reset request route context."""
    try:
        _ROUTE_CONTEXT.reset(token)
    except ValueError:
        # Streaming responses can hop execution contexts; fall back to clear.
        _ROUTE_CONTEXT.set("")


def get_bound_metrics_route() -> str:
    """Get bound request route for current context."""
    return str(_ROUTE_CONTEXT.get() or "").strip()


def record_route_timing(route: str, duration_ms: float, status: str = "ok") -> None:
    route_key = str(route or "").strip()
    if not route_key:
        return

    duration = max(0.0, float(duration_ms))
    status_text = "error" if str(status or "").strip().lower() == "error" else "ok"
    now = _utc_now_iso()

    with _LOCK:
        row = _ensure_route(route_key)
        row["requests"] += 1
        if status_text == "error":
            row["errors"] += 1
        row["duration_total_ms"] += duration
        row["duration_samples_ms"].append(duration)
        row["last_duration_ms"] = duration
        row["updated_at"] = now


def record_llm_call(
    *,
    component: str,
    operation: str,
    model: str,
    duration_ms: float,
    status: str,
    input_tokens: Any = None,
    output_tokens: Any = None,
    total_tokens: Any = None,
    trace_id: str = "",
) -> None:
    """Record one LLM call sample and aggregate route/counter metrics."""
    global _LLM_TOTAL_CALLS, _LLM_TOTAL_ERRORS

    duration = max(0.0, float(duration_ms))
    status_text = "error" if str(status or "").strip().lower() == "error" else "ok"
    route = get_bound_metrics_route()

    in_tokens = _coerce_non_negative_int(input_tokens)
    out_tokens = _coerce_non_negative_int(output_tokens)
    total = _coerce_non_negative_int(total_tokens)
    if total == 0:
        total = in_tokens + out_tokens

    now = _utc_now_iso()
    event = {
        "ts": now,
        "component": str(component or "").strip() or "unknown",
        "operation": str(operation or "").strip() or "unknown",
        "route": route or "unbound",
        "model": str(model or "").strip() or "unknown",
        "status": status_text,
        "duration_ms": round(duration, 3),
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
        "total_tokens": total,
    }
    if trace_id:
        normalized_trace = str(trace_id).strip()
        event["trace_id"] = normalized_trace
        event["correlation_id"] = normalized_trace

    with _LOCK:
        _LLM_TOTAL_CALLS += 1
        if status_text == "error":
            _LLM_TOTAL_ERRORS += 1
        _LLM_CALL_DURATIONS_MS.append(duration)
        _RECENT_LLM_EVENTS.append(event)

        if route:
            row = _ensure_route(route)
            row["llm_calls"] += 1
            if status_text == "error":
                row["llm_errors"] += 1
            row["llm_input_tokens"] += in_tokens
            row["llm_output_tokens"] += out_tokens
            row["llm_total_tokens"] += total
            row["updated_at"] = now


def get_metrics_snapshot() -> Dict[str, Any]:
    """Return serializable diagnostics snapshot."""
    with _LOCK:
        routes: Dict[str, Any] = {}
        for route, row in sorted(_ROUTE_METRICS.items()):
            samples = list(row["duration_samples_ms"])
            requests = int(row["requests"])
            errors = int(row["errors"])
            routes[route] = {
                "requests": requests,
                "errors": errors,
                "avg_duration_ms": round(
                    (float(row["duration_total_ms"]) / requests) if requests else 0.0,
                    3,
                ),
                "p95_duration_ms": round(_percentile(samples, 0.95), 3),
                "last_duration_ms": round(float(row["last_duration_ms"]), 3),
                "llm_calls": int(row["llm_calls"]),
                "llm_errors": int(row["llm_errors"]),
                "llm_input_tokens": int(row["llm_input_tokens"]),
                "llm_output_tokens": int(row["llm_output_tokens"]),
                "llm_total_tokens": int(row["llm_total_tokens"]),
                "updated_at": row.get("updated_at") or "",
            }

        llm_samples = list(_LLM_CALL_DURATIONS_MS)
        llm_calls = int(_LLM_TOTAL_CALLS)
        llm_errors = int(_LLM_TOTAL_ERRORS)
        llm = {
            "calls": llm_calls,
            "errors": llm_errors,
            "avg_duration_ms": round(
                (sum(llm_samples) / len(llm_samples)) if llm_samples else 0.0,
                3,
            ),
            "p95_duration_ms": round(_percentile(llm_samples, 0.95), 3),
            "recent": list(_RECENT_LLM_EVENTS),
        }

    return {
        "event": "runtime_metrics_snapshot",
        "generated_at": _utc_now_iso(),
        "routes": routes,
        "llm": llm,
    }


def reset_metrics() -> None:
    """Reset all in-memory metrics (test-only utility)."""
    global _LLM_TOTAL_CALLS, _LLM_TOTAL_ERRORS
    with _LOCK:
        _ROUTE_METRICS.clear()
        _LLM_CALL_DURATIONS_MS.clear()
        _RECENT_LLM_EVENTS.clear()
        _LLM_TOTAL_CALLS = 0
        _LLM_TOTAL_ERRORS = 0
