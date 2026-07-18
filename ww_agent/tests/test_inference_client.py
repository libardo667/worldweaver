from __future__ import annotations

import asyncio

import pytest

from src.inference.client import InferenceClient, InferenceError


def test_complete_omits_optional_temperature_when_model_uses_its_default():
    client = InferenceClient(
        base_url="https://inference.example/v1",
        api_key="test-key",
        default_model="test/model",
    )
    captured: dict = {}

    async def fake_post(path, payload):
        captured.update({"path": path, "payload": payload})
        return {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 1},
        }

    client._post_with_retry = fake_post

    async def run():
        try:
            return await client.complete("system", "user", temperature=None)
        finally:
            await client.close()

    assert asyncio.run(run()) == "ok"
    assert captured["path"] == "/chat/completions"
    assert "temperature" not in captured["payload"]


def test_complete_keeps_explicit_temperature():
    client = InferenceClient(
        base_url="https://inference.example/v1",
        api_key="test-key",
        default_model="test/model",
    )
    captured: dict = {}

    async def fake_post(_path, payload):
        captured.update(payload)
        return {"choices": [{"message": {"content": "ok"}}]}

    client._post_with_retry = fake_post

    async def run():
        try:
            return await client.complete("system", "user", temperature=0.25)
        finally:
            await client.close()

    assert asyncio.run(run()) == "ok"
    assert captured["temperature"] == 0.25


def test_invalid_json_keeps_response_out_of_public_error_text():
    client = InferenceClient(
        base_url="https://inference.example/v1",
        api_key="test-key",
        default_model="test/model",
    )
    private_response = '{"felt_sense":"private resident text"'

    async def fake_post(_path, _payload):
        return {"choices": [{"message": {"content": private_response}}]}

    client._post_with_retry = fake_post

    async def run():
        try:
            return await client.complete_json("system", "user")
        finally:
            await client.close()

    with pytest.raises(InferenceError) as caught:
        asyncio.run(run())

    assert "private resident text" not in str(caught.value)
    assert caught.value.private_diagnostic["response_text"] == private_response
