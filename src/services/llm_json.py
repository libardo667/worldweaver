"""Shared JSON extraction and schema validation helpers for LLM outputs."""

from __future__ import annotations

import json
import re
from enum import StrEnum
from typing import Any, Iterable, TypeVar

from pydantic import BaseModel, ValidationError

_ModelT = TypeVar("_ModelT", bound=BaseModel)


class LLMJsonErrorCategory(StrEnum):
    """Machine-readable categories for model JSON parsing/validation failures."""

    EMPTY_CONTENT = "empty_content"
    JSON_DECODE_FAILED = "json_decode_failed"
    EXPECTED_OBJECT = "expected_object"
    EXPECTED_ARRAY = "expected_array"
    SCHEMA_VALIDATION_FAILED = "schema_validation_failed"


class LLMJsonError(ValueError):
    """Structured exception for JSON extraction and schema validation failures."""

    def __init__(
        self,
        category: LLMJsonErrorCategory,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.details = details or {}

    @property
    def error_category(self) -> str:
        return str(self.category)


def strip_markdown_code_fences(text: str) -> str:
    """Remove wrapping markdown code fences if present."""
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def extract_json_value(text: str) -> Any:
    """Extract the first valid JSON value from raw model text."""
    cleaned = strip_markdown_code_fences(text)
    if not cleaned:
        raise LLMJsonError(
            LLMJsonErrorCategory.EMPTY_CONTENT,
            "LLM returned empty content",
        )

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for match in re.finditer(r"[\[{]", cleaned):
        start_idx = match.start()
        try:
            value, _ = decoder.raw_decode(cleaned[start_idx:])
            return value
        except json.JSONDecodeError:
            continue

    raise LLMJsonError(
        LLMJsonErrorCategory.JSON_DECODE_FAILED,
        "No valid JSON found in model response",
    )


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse model output into a JSON object."""
    value = extract_json_value(text)
    if not isinstance(value, dict):
        raise LLMJsonError(
            LLMJsonErrorCategory.EXPECTED_OBJECT,
            "Expected JSON object in model response",
            details={"actual_type": type(value).__name__},
        )
    return value


def extract_json_array(
    text: str,
    *,
    wrapper_keys: Iterable[str] = (),
) -> list[Any]:
    """Parse model output into a JSON array, optionally from object wrappers."""
    value = extract_json_value(text)
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in wrapper_keys:
            candidate = value.get(str(key))
            if isinstance(candidate, list):
                return candidate
    raise LLMJsonError(
        LLMJsonErrorCategory.EXPECTED_ARRAY,
        "Expected JSON array in model response",
        details={"actual_type": type(value).__name__},
    )


def validate_with_model(payload: Any, model_type: type[_ModelT]) -> _ModelT:
    """Validate payload with a Pydantic model and normalize error surface."""
    try:
        return model_type.model_validate(payload)
    except ValidationError as exc:
        raise LLMJsonError(
            LLMJsonErrorCategory.SCHEMA_VALIDATION_FAILED,
            "Model output failed schema validation",
            details={"errors": exc.errors()},
        ) from exc
