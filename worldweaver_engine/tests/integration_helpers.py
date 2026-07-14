"""Shared helpers for integration test request/assert patterns."""

from typing import Any


def assert_status(response: Any, expected_status: int) -> None:
    assert response.status_code == expected_status, response.json()


def assert_status_in(response: Any, expected_statuses: tuple[int, ...]) -> None:
    assert response.status_code in expected_statuses, response.json()


def assert_ok_response(response: Any) -> None:
    assert_status(response, 200)
