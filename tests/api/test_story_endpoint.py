"""Targeted tests for /api/next endpoint execution behavior."""

from unittest.mock import AsyncMock, patch


class TestStoryEndpoint:

    def test_next_uses_non_blocking_inference_wrapper(self, seeded_client):
        resolved = {
            "response": {
                "text": "Thread-offloaded next-turn resolution completed.",
                "choices": [{"label": "Continue", "set": {}}],
                "vars": {"location": "start"},
            },
            "debug": None,
        }

        async def _offload(fn, *args, **kwargs):
            if getattr(fn, "__name__", "") == "_resolve_next_turn":
                return resolved
            return True

        wrapper_mock = AsyncMock(side_effect=_offload)
        with patch("src.api.game.story.run_inference_thread", wrapper_mock):
            response = seeded_client.post(
                "/api/next",
                json={"session_id": "next-thread-wrapper", "vars": {}},
            )

        assert response.status_code == 200
        assert response.json()["text"] == resolved["response"]["text"]
        assert wrapper_mock.await_count >= 2
        assert wrapper_mock.await_args_list[0].args[0].__name__ == "_resolve_next_turn"

    def test_next_timeout_bubbles_as_error_without_contract_drift(self, seeded_client):
        wrapper_mock = AsyncMock(side_effect=TimeoutError("timed out"))
        with patch("src.api.game.story.run_inference_thread", wrapper_mock):
            response = seeded_client.post(
                "/api/next",
                json={"session_id": "next-timeout-wrapper", "vars": {}},
            )

        assert response.status_code == 500
        assert wrapper_mock.await_count == 1
