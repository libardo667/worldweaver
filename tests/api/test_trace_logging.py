"""Trace/correlation logging coverage for request lifecycle and core events."""

import json
from types import SimpleNamespace

from src.services.llm_client import (
    _InstrumentedCompletions,
    reset_trace_id,
    set_trace_id,
)


def _json_records(caplog):
    rows = []
    for record in caplog.records:
        message = str(record.message or "").strip()
        if not message.startswith("{"):
            continue
        try:
            rows.append(json.loads(message))
        except json.JSONDecodeError:
            continue
    return rows


class TestTraceLogging:

    def test_health_request_uses_or_generates_correlation_header(self, client):
        incoming = "trace-from-client-123"
        response = client.get("/health", headers={"X-WW-Trace-Id": incoming})
        assert response.status_code == 200
        assert response.headers.get("X-WW-Trace-Id") == incoming
        assert response.headers.get("X-Correlation-Id") == incoming

    def test_next_lifecycle_logs_share_same_trace_id(self, seeded_client, caplog):
        caplog.set_level("INFO")

        response = seeded_client.post(
            "/api/next",
            json={"session_id": "trace-next-1", "vars": {"chapter": 1}},
        )
        assert response.status_code == 200

        trace_id = response.headers.get("X-WW-Trace-Id")
        assert trace_id
        assert response.headers.get("X-Correlation-Id") == trace_id

        payloads = _json_records(caplog)
        request_start = [row for row in payloads if row.get("event") == "request_start" and row.get("route") == "/api/next"]
        request_end = [row for row in payloads if row.get("event") == "request_end" and row.get("route") == "/api/next"]
        selected = [row for row in payloads if row.get("event") == "storylet_selected" and row.get("turn_type") == "next"]
        committed = [row for row in payloads if row.get("event") == "state_committed" and row.get("turn_type") == "next"]

        assert request_start and request_end
        assert request_start[-1]["trace_id"] == trace_id
        assert request_end[-1]["trace_id"] == trace_id
        assert selected and selected[-1]["trace_id"] == trace_id
        assert committed and committed[-1]["trace_id"] == trace_id

    def test_action_commit_logs_reuse_request_trace(self, seeded_client, caplog):
        seeded_client.post("/api/next", json={"session_id": "trace-action-1", "vars": {}})
        caplog.set_level("INFO")

        response = seeded_client.post(
            "/api/action",
            json={"session_id": "trace-action-1", "action": "inspect the gate"},
        )
        assert response.status_code == 200

        trace_id = response.headers.get("X-WW-Trace-Id")
        assert trace_id

        payloads = _json_records(caplog)
        committed = [row for row in payloads if row.get("event") == "state_committed" and row.get("turn_type") == "action"]
        assert committed
        assert committed[-1]["trace_id"] == trace_id

    def test_instrumented_llm_logs_llm_call_with_bound_trace(self, caplog):
        class _FakeCompletions:
            def create(self, **kwargs):
                return SimpleNamespace(ok=True)

        caplog.set_level("INFO")
        token = set_trace_id("trace-llm-001")
        try:
            instrumented = _InstrumentedCompletions(_FakeCompletions())
            instrumented.create(model="model-test")
        finally:
            reset_trace_id(token)

        payloads = _json_records(caplog)
        llm_events = [row for row in payloads if row.get("event") == "llm_call"]
        assert llm_events
        assert llm_events[-1]["trace_id"] == "trace-llm-001"
        assert llm_events[-1]["correlation_id"] == "trace-llm-001"
