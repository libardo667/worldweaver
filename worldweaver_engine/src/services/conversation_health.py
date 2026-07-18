"""Content-blind population measures over deliberately public city speech.

The analyzer reads message text in memory because lexical measurements require it, but its
return value contains only counts and numeric scores. It never returns speakers, locations,
tokens, phrases, snippets, message identifiers, or per-message embeddings.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
import math
import random
import re
from typing import Any, Iterable

REPORT_SCHEMA = "worldweaver.public-conversation-health"
REPORT_SCHEMA_VERSION = 1
DEFAULT_CLUSTER_FLOOR = 0.28

_TOKEN_RE = re.compile(r"[a-z][a-z'-]{1,}")
_STOPWORDS = frozenset(
    {
        "a",
        "about",
        "after",
        "again",
        "all",
        "also",
        "am",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "he",
        "her",
        "here",
        "him",
        "his",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "just",
        "me",
        "more",
        "my",
        "no",
        "not",
        "of",
        "on",
        "or",
        "our",
        "out",
        "she",
        "so",
        "some",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "they",
        "this",
        "to",
        "too",
        "up",
        "us",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "will",
        "with",
        "would",
        "you",
        "your",
    }
)

# Fixed before a population report is run. These words are deliberately broad: the score
# is a warning light to compare over time and against controls, never a verdict by itself.
_CIVIC_INFRASTRUCTURE_TERMS = frozenset(
    {
        "architecture",
        "beam",
        "bridge",
        "circuit",
        "civic",
        "conduit",
        "drainage",
        "fault",
        "foundation",
        "framework",
        "grid",
        "infrastructure",
        "inspection",
        "maintenance",
        "mechanical",
        "mechanism",
        "municipal",
        "network",
        "node",
        "pipeline",
        "pressure",
        "protocol",
        "reinforce",
        "repair",
        "seam",
        "stabilize",
        "structural",
        "system",
    }
)


@dataclass(frozen=True)
class PublicConversationMessage:
    """One public utterance. Fields are accepted for analysis and never copied to output."""

    speaker_key: str
    body: str
    created_at: datetime
    location_key: str = ""


def _tokens(body: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall(str(body or "").lower()) if token not in _STOPWORDS]


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    common = left.keys() & right.keys()
    numerator = sum(left[token] * right[token] for token in common)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0


def _rounded(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)


def _tfidf_vectors(tokenized: list[list[str]]) -> list[dict[str, float]]:
    document_count = max(1, len(tokenized))
    document_frequency: Counter[str] = Counter()
    for tokens in tokenized:
        document_frequency.update(set(tokens))

    vectors: list[dict[str, float]] = []
    for tokens in tokenized:
        counts = Counter(tokens)
        total = max(1, sum(counts.values()))
        vector = {token: (count / total) * (math.log((1 + document_count) / (1 + document_frequency[token])) + 1.0) for token, count in counts.items()}
        vectors.append(vector)
    return vectors


def _centroid(vectors: Iterable[dict[str, float]]) -> dict[str, float]:
    rows = list(vectors)
    if not rows:
        return {}
    summed: defaultdict[str, float] = defaultdict(float)
    for vector in rows:
        for token, value in vector.items():
            summed[token] += value
    return {token: value / len(rows) for token, value in summed.items()}


def _speaker_convergence(labels: list[str], vectors: list[dict[str, float]]) -> float:
    by_speaker: defaultdict[str, list[dict[str, float]]] = defaultdict(list)
    for label, vector in zip(labels, vectors, strict=True):
        by_speaker[label].append(vector)
    centroids = [_centroid(rows) for rows in by_speaker.values()]
    similarities = [_cosine(centroids[i], centroids[j]) for i in range(len(centroids)) for j in range(i + 1, len(centroids))]
    return _mean(similarities)


def _shuffled_convergence(labels: list[str], vectors: list[dict[str, float]], *, seed: int, iterations: int = 32) -> float:
    if len(set(labels)) < 2:
        return 0.0
    generator = random.Random(seed)
    samples: list[float] = []
    for _ in range(iterations):
        shuffled = list(labels)
        generator.shuffle(shuffled)
        samples.append(_speaker_convergence(shuffled, vectors))
    return _mean(samples)


def _population_repetition(labels: list[str], vectors: list[dict[str, float]], normalized_bodies: list[str]) -> tuple[float, float]:
    previous_vectors: defaultdict[str, list[dict[str, float]]] = defaultdict(list)
    previous_bodies: defaultdict[str, set[str]] = defaultdict(set)
    similarity_scores: list[float] = []
    exact_repeats = 0
    eligible = 0
    for label, vector, body in zip(labels, vectors, normalized_bodies, strict=True):
        if previous_vectors[label]:
            eligible += 1
            similarity_scores.append(max(_cosine(vector, prior) for prior in previous_vectors[label]))
            if body and body in previous_bodies[label]:
                exact_repeats += 1
        previous_vectors[label].append(vector)
        if body:
            previous_bodies[label].add(body)
    return _mean(similarity_scores), exact_repeats / eligible if eligible else 0.0


def _cluster_entropy(vectors: list[dict[str, float]], *, floor: float) -> tuple[int, float]:
    clusters: list[list[dict[str, float]]] = []
    for vector in vectors:
        if not clusters:
            clusters.append([vector])
            continue
        scores = [_cosine(vector, _centroid(cluster)) for cluster in clusters]
        best_index = max(range(len(scores)), key=scores.__getitem__)
        if scores[best_index] >= floor or len(clusters) >= 8:
            clusters[best_index].append(vector)
        else:
            clusters.append([vector])
    if len(clusters) <= 1:
        return len(clusters), 0.0
    total = sum(len(cluster) for cluster in clusters)
    entropy = -sum((len(cluster) / total) * math.log(len(cluster) / total) for cluster in clusters)
    return len(clusters), entropy / math.log(len(clusters))


def _window_convergence(labels: list[str], vectors: list[dict[str, float]], *, window_count: int) -> list[float | None]:
    if not labels:
        return []
    count = max(1, min(int(window_count), len(labels)))
    result: list[float | None] = []
    for window in range(count):
        start = (window * len(labels)) // count
        end = ((window + 1) * len(labels)) // count
        window_labels = labels[start:end]
        if len(set(window_labels)) < 2:
            result.append(None)
            continue
        result.append(_rounded(_speaker_convergence(window_labels, vectors[start:end])))
    return result


def _interaction_metrics(messages: list[PublicConversationMessage]) -> dict[str, Any]:
    pair_counts: Counter[tuple[str, str]] = Counter()
    for previous, current in zip(messages, messages[1:]):
        if previous.speaker_key == current.speaker_key:
            continue
        if previous.location_key != current.location_key:
            continue
        elapsed = (current.created_at - previous.created_at).total_seconds()
        if not 0 <= elapsed <= 600:
            continue
        pair = tuple(sorted((previous.speaker_key, current.speaker_key)))
        pair_counts[pair] += 1

    transition_count = sum(pair_counts.values())
    shares = [count / transition_count for count in pair_counts.values()] if transition_count else []
    return {
        "adjacent_reply_transitions": transition_count,
        "unique_pairs": len(pair_counts),
        "top_pair_share": _rounded(max(shares, default=0.0)),
        "pair_concentration": _rounded(sum(share * share for share in shares)),
    }


def analyze_public_conversation(
    messages: Iterable[PublicConversationMessage],
    *,
    minimum_speakers: int = 3,
    window_count: int = 3,
    shuffle_seed: int = 0,
) -> dict[str, Any]:
    """Return a content-blind aggregate report over public speech only."""

    ordered = sorted(
        (message for message in messages if str(message.speaker_key or "").strip() and str(message.body or "").strip()),
        key=lambda message: message.created_at,
    )
    labels = [message.speaker_key for message in ordered]
    speaker_count = len(set(labels))
    base: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "schema_version": REPORT_SCHEMA_VERSION,
        "input_scope": "public_location_chat",
        "privacy": "aggregate_no_source_text",
        "message_count": len(ordered),
        "speaker_count": speaker_count,
        "minimum_speakers": minimum_speakers,
    }
    if speaker_count < minimum_speakers:
        return {**base, "status": "insufficient_population"}

    tokenized = [_tokens(message.body) for message in ordered]
    vectors = _tfidf_vectors(tokenized)
    normalized_bodies = [" ".join(tokens) for tokens in tokenized]
    observed_convergence = _speaker_convergence(labels, vectors)
    shuffled_convergence = _shuffled_convergence(labels, vectors, seed=shuffle_seed)
    repetition, exact_repetition = _population_repetition(labels, vectors, normalized_bodies)
    cluster_count, cluster_entropy = _cluster_entropy(vectors, floor=DEFAULT_CLUSTER_FLOOR)
    civic_messages = sum(bool(set(tokens) & _CIVIC_INFRASTRUCTURE_TERMS) for tokens in tokenized)
    civic_tokens = sum(sum(token in _CIVIC_INFRASTRUCTURE_TERMS for token in tokens) for tokens in tokenized)
    total_tokens = sum(len(tokens) for tokens in tokenized)
    window_scores = _window_convergence(labels, vectors, window_count=window_count)
    available_window_scores = [score for score in window_scores if score is not None]
    convergence_change = available_window_scores[-1] - available_window_scores[0] if len(available_window_scores) >= 2 else 0.0

    return {
        **base,
        "status": "ok",
        "lexical": {
            "population_repetition": _rounded(repetition),
            "exact_repeat_fraction": _rounded(exact_repetition),
            "speaker_convergence": _rounded(observed_convergence),
            "shuffled_convergence": _rounded(shuffled_convergence),
            "distinctiveness_gap": _rounded(max(0.0, shuffled_convergence - observed_convergence)),
            "window_convergence": window_scores,
            "window_convergence_change": round(convergence_change, 4),
        },
        "topic_shape": {
            "anonymous_cluster_count": cluster_count,
            "normalized_cluster_entropy": _rounded(cluster_entropy),
            "civic_message_fraction": _rounded(civic_messages / len(ordered)),
            "civic_token_fraction": _rounded(civic_tokens / total_tokens if total_tokens else 0.0),
        },
        "interaction": _interaction_metrics(ordered),
    }
