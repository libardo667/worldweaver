"""Embedding service for computing and storing storylet vector embeddings."""

import logging
import math
import os
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models import Storylet
from .llm_client import get_llm_client, get_embedding_model, is_ai_disabled

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))

_FALLBACK_VECTOR: List[float] = [0.0] * EMBEDDING_DIMENSIONS


def embed_text(text: str) -> List[float]:
    """Embed a text string using the configured embedding model.

    Returns a fallback zero vector when AI is disabled or no API key is set.
    """
    if is_ai_disabled():
        return list(_FALLBACK_VECTOR)

    client = get_llm_client()
    if not client:
        return list(_FALLBACK_VECTOR)

    try:
        response = client.embeddings.create(
            model=get_embedding_model(),
            input=text,
            dimensions=EMBEDDING_DIMENSIONS,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error("Embedding API call failed: %s", e)
        return list(_FALLBACK_VECTOR)


def build_composite_text(storylet: Storylet) -> str:
    """Build a composite text from storylet fields for embedding.

    Combines title, text_template, choice labels, and requirement keys
    into a single string that captures the storylet's semantic content.
    """
    parts = [str(storylet.title or ""), str(storylet.text_template or "")]

    choices = storylet.choices or []
    for choice in choices:
        if isinstance(choice, dict):
            parts.append(choice.get("label", ""))

    requires = storylet.requires or {}
    if isinstance(requires, dict):
        parts.extend(f"{k}={v}" for k, v in requires.items())

    return " ".join(filter(None, parts))


def embed_storylet(storylet: Storylet) -> List[float]:
    """Compute the embedding vector for a single storylet."""
    composite = build_composite_text(storylet)
    return embed_text(composite)


def build_composite_payload_text(payload: Dict[str, Any]) -> str:
    """Build composite semantic text from a storylet payload dict."""
    parts = [str(payload.get("title", "")), str(payload.get("text_template", ""))]

    choices = payload.get("choices", [])
    if isinstance(choices, list):
        for choice in choices:
            if isinstance(choice, dict):
                parts.append(str(choice.get("label", "")))

    requires = payload.get("requires", {})
    if isinstance(requires, dict):
        parts.extend(f"{k}={v}" for k, v in requires.items())

    return " ".join(filter(None, parts))


def embed_storylet_payload(payload: Dict[str, Any]) -> List[float]:
    """Embed a storylet-like payload without requiring ORM object creation."""
    return embed_text(build_composite_payload_text(payload))


def embed_all_storylets(db: Session, batch_size: int = 20) -> int:
    """Batch-embed all storylets that have a null embedding.

    Returns the number of storylets embedded.
    """
    nulls = db.query(Storylet).filter(Storylet.embedding.is_(None)).all()
    if not nulls:
        return 0

    count = 0
    for i in range(0, len(nulls), batch_size):
        batch = nulls[i : i + batch_size]
        for storylet in batch:
            vector = embed_storylet(storylet)
            storylet.embedding = vector
            count += 1
        db.flush()

    db.commit()
    logger.info("Embedded %d storylets", count)
    return count


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
