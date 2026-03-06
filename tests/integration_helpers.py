"""Shared helpers for integration test request/assert patterns."""

from concurrent.futures import ThreadPoolExecutor
from typing import Any


def assert_status(response: Any, expected_status: int) -> None:
    assert response.status_code == expected_status, response.json()


def assert_ok_response(response: Any) -> None:
    assert_status(response, 200)


def run_concurrent_next_and_action(
    seeded_client: Any,
    *,
    next_payload: dict[str, Any],
    action_payload: dict[str, Any],
    timeout_seconds: float = 5.0,
):
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_next = pool.submit(seeded_client.post, "/api/next", json=next_payload)
        fut_action = pool.submit(seeded_client.post, "/api/action", json=action_payload)
        return fut_next.result(timeout=timeout_seconds), fut_action.result(timeout=timeout_seconds)
