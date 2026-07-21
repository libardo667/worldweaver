# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class InferenceError(Exception):
    """Safe public inference failure with optional private trace detail."""

    def __init__(self, message: str, *, private_diagnostic: Any = None) -> None:
        super().__init__(message)
        self.private_diagnostic = private_diagnostic


class InferenceClient:
    """
    Thin async wrapper around an OpenRouter-compatible chat completions API.
    Shared by all residents and all loops. Stateless — context comes from caller.

    The agent never knows this exists. All prompt construction happens in the
    loop layer; this client just sends text and returns text.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        default_model: str = "google/gemini-flash-1.5",
        timeout: float = 60.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._default_model = default_model
        # Lightweight usage accounting — lets callers measure real token cost
        # (e.g. the cost-curve harness) without re-plumbing every call site.
        self.last_usage: dict[str, Any] = {}
        self.total_calls = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.recovered_json_responses = 0
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout),
        )

    @property
    def default_model_id(self) -> str:
        """The model identifier used when a caller supplies no override."""

        return self._default_model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = 0.7,
        max_tokens: int = 300,
        response_format: dict[str, Any] | None = None,
        images: list[str] | None = None,
    ) -> str:
        """
        Send a chat completion. Returns the assistant message text.
        Retries on transient errors (429, 500, 502, 503).

        ``response_format`` is passed through to the API when set — e.g.
        ``{"type": "json_object"}`` to constrain the model to a single JSON
        object (portable across OpenAI-compatible backends, including Ollama).

        ``images`` (Major 55 sight) are image URLs / data URIs attached to the user
        turn as OpenAI-style multimodal content parts. ``None`` (a text-only mind, or a
        world that withholds images) sends a plain string content — the default. The
        producer only passes images for a vision-capable resident; a text-only resident
        always passes ``None`` and this path is unchanged.
        """
        if images:
            user_content: Any = [{"type": "text", "text": user_prompt}]
            user_content += [
                {"type": "image_url", "image_url": {"url": str(url)}}
                for url in images
                if str(url or "").strip()
            ]
        else:
            user_content = user_prompt
        payload = {
            "model": model or self._default_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": max_tokens,
        }
        # Reasoning-oriented and provider-routed models do not all accept a
        # sampling temperature.  ``None`` means "use the model default" and,
        # importantly, leaves the optional field out of the wire request.
        if temperature is not None:
            payload["temperature"] = temperature
        if response_format is not None:
            payload["response_format"] = response_format

        response = await self._post_with_retry("/chat/completions", payload)
        content = response["choices"][0]["message"]["content"]

        usage = response.get("usage", {}) or {}
        self.last_usage = dict(usage)
        self.total_calls += 1
        self.total_prompt_tokens += int(usage.get("prompt_tokens") or 0)
        self.total_completion_tokens += int(usage.get("completion_tokens") or 0)
        logger.debug(
            "inference: model=%s tokens=%s+%s",
            payload["model"],
            usage.get("prompt_tokens", "?"),
            usage.get("completion_tokens", "?"),
        )

        return content

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> dict:
        """
        Like complete(), but parses the response as JSON.
        Strips markdown fences if present. Raises InferenceError on parse failure.

        Use sparingly — "respond with JSON" is the most visible seam.
        Prefer complete() + lightweight parsing where possible.
        """
        text = await self.complete(system_prompt, user_prompt, **kwargs)
        # Some models/providers (esp. small ones with response_format) return no
        # content at all. Fail closed with InferenceError (callers catch it and skip
        # the pulse) rather than crashing the daemon on None.strip().
        if not text or not str(text).strip():
            raise InferenceError("Model returned an empty response (no content).")
        text = str(text).strip()

        # Strip markdown fences if the model wrapped the JSON
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        try:
            decoded = json.loads(text)
        except json.JSONDecodeError as e:
            decoded = None
            if e.msg == "Extra data":
                try:
                    candidate, end = json.JSONDecoder().raw_decode(text)
                    trailing = text[end:].strip()
                except json.JSONDecodeError:
                    candidate, trailing = None, ""
                # Some provider-routed models honor the requested JSON object
                # and then append a closing fence or prose. The first object is
                # still unambiguous and schema-checked by the caller. Do not,
                # however, choose between two competing JSON values.
                after_fence = trailing.removeprefix("```").strip()
                if (
                    isinstance(candidate, dict)
                    and trailing
                    and not after_fence.startswith(("{", "["))
                ):
                    self.recovered_json_responses += 1
                    logger.warning(
                        "inference: ignored trailing text after one valid JSON object"
                    )
                    decoded = candidate
            if decoded is None:
                raise InferenceError(
                    f"Response was not valid JSON: {e}",
                    private_diagnostic={
                        "response_text": text,
                        "json_error": str(e),
                    },
                ) from e
        if not isinstance(decoded, dict):
            raise InferenceError(
                "Response JSON was not an object.",
                private_diagnostic={"response_text": text},
            )
        return decoded

    async def _post_with_retry(
        self,
        path: str,
        payload: dict,
        *,
        max_retries: int = 2,
    ) -> dict:
        retryable = {429, 500, 502, 503}
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                resp = await self._client.post(path, json=payload)

                if resp.status_code in retryable:
                    delay = 2**attempt
                    logger.warning(
                        "inference: HTTP %s, retrying in %ss (attempt %s/%s)",
                        resp.status_code,
                        delay,
                        attempt + 1,
                        max_retries + 1,
                    )
                    await asyncio.sleep(delay)
                    last_error = httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}", request=resp.request, response=resp
                    )
                    continue

                resp.raise_for_status()
                return resp.json()

            except httpx.TimeoutException as e:
                last_error = e
                if attempt < max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                raise InferenceError("Inference request timed out") from e

        raise InferenceError(
            f"Inference failed after {max_retries + 1} attempts"
        ) from last_error

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> InferenceClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()
