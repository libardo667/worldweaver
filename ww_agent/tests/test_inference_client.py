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


def test_complete_json_recovers_one_object_with_trailing_non_json_text():
    client = InferenceClient(
        base_url="https://inference.example/v1",
        api_key="test-key",
        default_model="test/model",
    )

    async def fake_post(_path, _payload):
        return {"choices": [{"message": {"content": '{"felt_sense":"kept private","reach":null,"act":null}\n```\nDone.'}}]}

    client._post_with_retry = fake_post

    async def run():
        try:
            return await client.complete_json("system", "user")
        finally:
            await client.close()

    assert asyncio.run(run()) == {
        "felt_sense": "kept private",
        "reach": None,
        "act": None,
    }
    assert client.recovered_json_responses == 1


def test_complete_json_refuses_competing_objects_and_non_object_json():
    async def attempt(content):
        client = InferenceClient(
            base_url="https://inference.example/v1",
            api_key="test-key",
            default_model="test/model",
        )

        async def fake_post(_path, _payload):
            return {"choices": [{"message": {"content": content}}]}

        client._post_with_retry = fake_post
        try:
            with pytest.raises(InferenceError):
                await client.complete_json("system", "user")
        finally:
            await client.close()

    asyncio.run(attempt('{"act":null}\n{"act":{"kind":"move"}}'))
    asyncio.run(attempt('[{"act":null}]'))
