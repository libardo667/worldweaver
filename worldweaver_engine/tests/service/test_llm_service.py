"""Tests for src/services/llm_service.py — no live API key needed."""

from unittest.mock import MagicMock


def _mock_llm_response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    return response


class _RateLimitError(Exception):
    status_code = 429
