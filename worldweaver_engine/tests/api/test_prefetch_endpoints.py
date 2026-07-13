"""Tests for prefetch control/status API endpoints."""

import time
from unittest.mock import patch

import pytest

from src.services.prefetch_service import clear_prefetch_cache


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


def test_prefetch_trigger_endpoint_returns_triggered_true_even_when_warm(client):
    with patch("src.api.game.prefetch.schedule_frontier_prefetch", return_value=False) as mock_schedule:
        response = client.post(
            "/api/prefetch/frontier",
            json={"session_id": "prefetch-warm-session"},
        )

    assert response.status_code == 200
    assert response.json() == {"triggered": True}
    mock_schedule.assert_called_once()


# NOTE: GET /prefetch/status/{session_id} and the trigger/status isolation test were
# removed in Major 83 slice 2 (the status route had no callers; the prefetch module no
# longer imports any status reader, so the "does not block on refresh" property is
# structural). The status *service* (get_frontier_status) is still exercised via the
# bootstrap/invalidation tests in test_game_endpoints.py.
