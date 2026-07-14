# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Embedding service for world events, facts, and other semantic records."""

import logging
import math
import os
import time
from typing import List


from .llm_client import (
    get_embedding_model,
    get_llm_client,
    get_trace_id,
    is_ai_disabled,
    platform_shared_policy,
)

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))

_FALLBACK_VECTOR: List[float] = [0.0] * EMBEDDING_DIMENSIONS


def embed_text(text: str) -> List[float]:
    """Embed a text string using the configured embedding model.

    Returns a fallback zero vector when AI is disabled or no API key is set.
    """
    started = time.perf_counter()
    model = get_embedding_model()
    if is_ai_disabled():
        logger.info(
            '{"event":"embedding_service_timing","trace_id":"%s","model":"%s","duration_ms":%.3f,"status":"ai_disabled"}',
            get_trace_id(),
            model,
            (time.perf_counter() - started) * 1000.0,
        )
        return list(_FALLBACK_VECTOR)

    client = get_llm_client(policy=platform_shared_policy(owner_id="embedding_service"))
    if not client:
        logger.info(
            '{"event":"embedding_service_timing","trace_id":"%s","model":"%s","duration_ms":%.3f,"status":"client_unavailable"}',
            get_trace_id(),
            model,
            (time.perf_counter() - started) * 1000.0,
        )
        return list(_FALLBACK_VECTOR)

    try:
        response = client.embeddings.create(
            model=model,
            input=text,
        )
        logger.info(
            '{"event":"embedding_service_timing","trace_id":"%s","model":"%s","duration_ms":%.3f,"status":"ok"}',
            get_trace_id(),
            model,
            (time.perf_counter() - started) * 1000.0,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error("Embedding API call failed: %s", e)
        logger.info(
            '{"event":"embedding_service_timing","trace_id":"%s","model":"%s","duration_ms":%.3f,"status":"error","error_type":"%s"}',
            get_trace_id(),
            model,
            (time.perf_counter() - started) * 1000.0,
            e.__class__.__name__,
        )
        return list(_FALLBACK_VECTOR)


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Pure-Python cosine similarity between two vectors.

    Returns a float in [-1, 1]. Returns 0.0 if either vector has zero magnitude.
    """
    if len(a) != len(b):
        raise ValueError(f"Vector length mismatch: {len(a)} vs {len(b)}")

    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))

    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0

    return dot / (mag_a * mag_b)
