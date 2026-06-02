"""The drive vector: affect from the constitution-anchored soul (Major 49, Phase 4).

A resident's affect is not generic. It is read from the *embedding space of its
own identity docs*, in three rigidity slices (Major 42):

- **constitution** — the canonical soul: hard, dominant, immutable.
- **growth** — matured, lived-in additions: stable.
- **reverie** — transient interior anchors: light, decaying.

Given a moment (what is happening + what surprised me), the drive vector answers
*"what in me does this touch?"* — the fragment of the resident's own nature that
most resonates, weighted so the constitution dominates. That is what lets twelve
minds in the same room respond as twelve people instead of one: each is pulled
toward its *own* gravity, not the loudest voice nearby.

It is cheap — embeddings are computed once for the slices (cached) and once per
ignition for the moment; no per-tick LLM. The embedder is pluggable: a real one
(any OpenAI-compatible ``/v1/embeddings`` endpoint, e.g. a local Ollama
``nomic-embed-text``) or a deterministic offline one for tests. With no embedder,
the drive vector is simply absent and behaviour falls back to neutral affect.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

logger = logging.getLogger(__name__)

# The constitution dominates; growth is stable; reverie is a light, transient pull.
SLICE_WEIGHTS = {"constitution": 1.0, "growth": 0.55, "reverie": 0.35}
# A proposed self-edit must resonate at least this much with the constitution to
# be accepted ungated; below it, the gate tempers it (it isn't grounded in core).
CONTRADICTION_FLOOR = 0.12


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


def _l2norm(vec: list[float]) -> list[float]:
    mag = math.sqrt(sum(x * x for x in vec))
    if mag <= 0.0:
        return vec
    return [x / mag for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


# Transient grounding that sometimes gets baked into a canonical soul (weather,
# time of day, temperature). It is not character, and it resonates with any
# atmospheric moment — so it is dropped from the drive vector's fragments, which
# should reach for who the resident *is*, not what the sky is doing right now.
_GROUNDING_RX = re.compile(
    r"\bright now\b|\b\d{1,3}\s*degrees\b|\b(partly cloudy|sunny|foggy|overcast|rainy|drizzl|clear sky)\b"
    r"|\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b.{0,40}\b(morning|afternoon|evening|night)\b",
    re.IGNORECASE,
)


def _fragment(text_or_list: Any) -> list[str]:
    """Split a slice into resonant fragments (sentences / reverie lines),
    dropping transient grounding boilerplate so character resonates, not weather."""
    if isinstance(text_or_list, (list, tuple, set)):
        items = [str(t).strip() for t in text_or_list]
    else:
        items = re.split(r"(?<=[.!?])\s+|\n+", str(text_or_list or ""))
    out: list[str] = []
    for frag in (s.strip() for s in items):
        if len(frag) < 12 or _GROUNDING_RX.search(frag):
            continue
        out.append(frag)
    return out[:48]


_STOPWORDS = frozenset(
    "a an the and or but of to in on at with for is are was were be been my your his her its their this that it as by from "
    "have has had no not all so do does did i you he she we they them me him us our".split()
)


class DeterministicEmbedder:
    """Offline, deterministic embeddings (signed feature hashing over content
    words). Not semantic — for tests and offline runs; distinct text → distinct
    vectors, shared content words → higher cosine. Stopwords are dropped so
    unrelated sentences don't share spurious overlap. Swap in a real model
    (e.g. Ollama ``nomic-embed-text``) for meaningful affect."""

    def __init__(self, dim: int = 256) -> None:
        self._dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def _vec(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        for token in re.findall(r"[a-z0-9']+", str(text).lower()):
            if token in _STOPWORDS or len(token) < 2:
                continue
            digest = hashlib.md5(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self._dim
            vec[idx] += 1.0 if (digest[4] & 1) else -1.0
        return _l2norm(vec)


class RemoteEmbedder:
    """Embeddings from any OpenAI-compatible ``/v1/embeddings`` endpoint."""

    def __init__(self, *, base_url: str, api_key: str, model: str, timeout: float = 30.0) -> None:
        self._model = model
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=httpx.Timeout(timeout),
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = await self._client.post("/embeddings", json={"model": self._model, "input": list(texts)})
        resp.raise_for_status()
        data = resp.json().get("data") or []
        return [_l2norm([float(x) for x in (item.get("embedding") or [])]) for item in data]

    async def close(self) -> None:
        await self._client.aclose()


@dataclass
class DriveVector:
    """One resident's affect, read from its own embedded identity slices."""

    embedder: Embedder
    # slice name -> list of (fragment text, unit embedding)
    slices: dict[str, list[tuple[str, list[float]]]]

    @classmethod
    async def build(
        cls,
        *,
        embedder: Embedder,
        constitution: str,
        growth: str = "",
        reveries: Any = (),
    ) -> "DriveVector":
        slices: dict[str, list[tuple[str, list[float]]]] = {}
        for name, source in (("constitution", constitution), ("growth", growth), ("reverie", reveries)):
            frags = _fragment(source)
            vecs = await embedder.embed(frags) if frags else []
            slices[name] = [(frag, vec) for frag, vec in zip(frags, vecs) if vec]
        return cls(embedder=embedder, slices=slices)

    def is_empty(self) -> bool:
        return not any(self.slices.values())

    async def resonance(self, moment: str, *, top_k: int = 2) -> dict[str, Any]:
        """What in this resident does the moment touch?

        Returns the most-resonant fragments (constitution-weighted), per-slice
        peak alignment, and an overall magnitude — the resident's own pull on
        this moment, distinct from anyone else's.
        """
        text = str(moment or "").strip()
        if not text or self.is_empty():
            return {"magnitude": 0.0, "resonant": [], "by_slice": {}}
        embedded = await self.embedder.embed([text])
        query = embedded[0] if embedded else []
        if not query:
            return {"magnitude": 0.0, "resonant": [], "by_slice": {}}

        scored: list[tuple[str, float, str, float]] = []  # slice, weight, fragment, cosine
        by_slice: dict[str, float] = {}
        for name, frags in self.slices.items():
            weight = SLICE_WEIGHTS.get(name, 0.3)
            peak = 0.0
            for frag_text, vec in frags:
                cos = _cosine(query, vec)
                scored.append((name, weight, frag_text, cos))
                peak = max(peak, cos)
            if frags:
                by_slice[name] = round(peak, 4)

        scored.sort(key=lambda s: -(s[1] * s[3]))
        top = [s for s in scored if s[3] > 0.0][:top_k]
        magnitude = round(top[0][1] * top[0][3], 4) if top else 0.0
        return {
            "magnitude": magnitude,
            "resonant": [{"slice": s[0], "text": s[2], "score": round(s[3], 4)} for s in top],
            "by_slice": by_slice,
        }

    async def contradiction_check(self, kind: str, body: str) -> str | None:
        """Gate hook: an identity edit must be grounded in the constitution.

        Phase 1's structural invariant already forbids touching canonical soul;
        this adds a semantic floor — an edit that barely resonates with the core
        is tempered (``clamp``) rather than accepted as if it were the resident's
        own. Strong opposition detection is a later refinement; this catches
        edits that simply are not rooted in who the resident is.
        """
        result = await self.resonance(str(body or ""))
        constitution_score = float(result.get("by_slice", {}).get("constitution") or 0.0)
        if constitution_score < CONTRADICTION_FLOOR:
            return "clamp"
        return None
