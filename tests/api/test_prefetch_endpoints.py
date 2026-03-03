"""Tests for prefetch control/status API endpoints."""

import time
from unittest.mock import patch

import pytest

from src.services.prefetch_service import clear_prefetch_cache, set_prefetched_stubs_for_session


@pytest.fixture(autouse=True)
def _reset_prefetch_cache():
    clear_prefetch_cache()
    yield
    clear_prefetch_cache()


def test_prefetch_trigger_endpoint_returns_stable_shape_and_schedules(client):
    with patch("src.api.game.prefetch.schedule_frontier_prefetch", return_value=True) as mock_schedule:
        started = time.perf_counter()
        response = client.post(
            "/api/prefetch/frontier",
            json={"session_id": "prefetch-trigger-session"},
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0

    assert response.status_code == 200
    assert response.json() == {"triggered": True}
    mock_schedule.assert_called_once()
    assert mock_schedule.call_args.args[0] == "prefetch-trigger-session"
    # Endpoint should return quickly because it only schedules background work.
    assert elapsed_ms < 250.0


def test_prefetch_trigger_endpoint_does_not_block_on_refresh(client):
    with patch("src.api.game.prefetch.schedule_frontier_prefetch", return_value=True), patch(
        "src.api.game.prefetch.get_frontier_status",
    ) as mock_status:
        response = client.post(
            "/api/prefetch/frontier",
            json={"session_id": "prefetch-non-blocking-session"},
        )

    assert response.status_code == 200
    assert response.json() == {"triggered": True}
    # Trigger endpoint should not call status/read APIs to do heavy work inline.
    mock_status.assert_not_called()


def test_prefetch_trigger_endpoint_returns_triggered_true_even_when_warm(client):
    with patch("src.api.game.prefetch.schedule_frontier_prefetch", return_value=False) as mock_schedule:
        response = client.post(
            "/api/prefetch/frontier",
            json={"session_id": "prefetch-warm-session"},
        )

    assert response.status_code == 200
    assert response.json() == {"triggered": True}
    mock_schedule.assert_called_once()


def test_prefetch_status_endpoint_reports_stub_count_and_ttl(client):
    set_prefetched_stubs_for_session(
        "prefetch-status-session",
        [
            {
                "storylet_id": 101,
                "title": "Cached lead",
                "premise": "A nearby clue is cached.",
                "choices": [{"label": "Follow it", "set": {}}],
            }
        ],
        context_summary={"trigger": "test"},
    )

    response = client.get("/api/prefetch/status/prefetch-status-session")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"stubs_cached", "expires_in_seconds"}
    assert payload["stubs_cached"] == 1
    assert payload["expires_in_seconds"] > 0

