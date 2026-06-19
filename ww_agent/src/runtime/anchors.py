# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Anchors: the concrete things a resident's inner world is actually about (Major 51).

The substrate predicts in five generic drives (vigilance, social_pull,
mobility_drive, correspondence_pull, rest_drive). They resonate ~equally with any
soul, so drive-weighted prediction scoring (prediction.py) cannot tell skilled
prediction from dull-world prediction — ``claim_mattering`` comes out flat. The
richness is all in the PROSE: Cinder's "the keeper", "the cooling room", "the tea
in my cup"; Maker's "the vigilance traces", "the work", "the perimeter". Nothing
in the substrate's feature space is *about* any of them.

This lifts those concrete anchors out of a resident's own perception and felt
sense so they can become predictable, scorable features — a vocabulary that is
*this resident's*, not every resident's. An anchor the soul is drawn to ("the
keeper") and one it is indifferent to ("the dust") embed to very different points;
that gradient is exactly what drive-weighting needs to bite.

Pure text → anchors; no LLM. The extractor is deliberately shallow — article-headed
noun phrases plus the concrete entities perception already names (present residents,
event actors, speakers) — with abstract function-nouns filtered. Salience is by
recurrence: what a resident keeps returning to rises. Granular but bounded; the
caller caps how many anchors reach the substrate per tick.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.runtime.ledger import append_runtime_event, load_runtime_events

# Realized-anchor snapshots are the ground truth the offline scorer reconciles
# predicted anchors against. Rate-limited like the baseline so the open vocabulary
# does not write the ledger every tick.
ANCHOR_SNAPSHOT_INTERVAL_SECONDS = 60.0
ANCHOR_SCOPE = "anchors"

# "the cooling room", "a copper button", "the keeper's voice" — an article (or
# possessive) followed by up to three lowercase words. felt_sense tends to be
# lowercase, so this is the workhorse; proper-name capitalization is unreliable.
_ARTICLE_NP = re.compile(r"\b(?:the|a|an|my|your|our|her|his|its|their)\s+([a-z][a-z']*(?:\s+[a-z][a-z']*){0,3})", re.IGNORECASE)

# Words that end a noun phrase or are not themselves anchors — prepositions and
# conjunctions (split the phrase), plus abstract/function nouns that are about
# *feeling* rather than a concrete thing in the world.
# Prepositions/conjunctions/pronouns that end a noun phrase, plus auxiliaries and
# the commonest copular verbs — so "the house has settled" cuts to "house", not
# "house has settled". (Full verb detection needs POS; this catches the leakage.)
_PREPS = {
    "in", "on", "of", "at", "with", "to", "for", "and", "or", "but", "as", "by", "from", "into", "that",
    "which", "who", "like", "than", "is", "are", "was", "were", "it", "i", "me", "my", "so",
    "has", "have", "had", "having", "be", "been", "being", "do", "does", "did", "will", "would",
    "hums", "settled", "settles", "holds", "holding", "feels", "felt", "goes", "gone", "went",
}
_ABSTRACT = {
    "moment", "sense", "feeling", "feelings", "way", "ways", "thing", "things", "kind", "sort", "bit", "lot",
    "part", "point", "idea", "nothing", "everything", "something", "anything", "self", "one", "time", "times",
    "while", "more", "less", "rest", "edge", "edges", "side", "middle", "end", "start", "place", "places",
}
_MIN_WORD_LEN = 3


def _normalize_phrase(raw: str) -> str:
    words = [w for w in re.split(r"\s+", raw.strip().lower()) if w]
    # trim trailing prepositions/fillers ("tea in my" -> "tea")
    while words and words[-1] in _PREPS:
        words.pop()
    # cut the phrase at the first internal preposition ("voice against the cooling" -> "voice")
    cut: list[str] = []
    for w in words:
        if w in _PREPS:
            break
        cut.append(w)
    words = cut[:3]
    if not words:
        return ""
    head = words[-1]
    # reject if the phrase is anchored on an abstract/function word at either end
    # ("the moment passed" -> first word abstract; "a kind" -> head abstract)
    if head in _ABSTRACT or words[0] in _ABSTRACT or len(head) < _MIN_WORD_LEN:
        return ""
    return " ".join(words)


def _clean_entity(raw: str) -> str:
    """A lighter normalizer for already-concrete named entities (present residents,
    speakers): lowercase and de-underscore, but keep short names ('Li', 'Bo')."""
    s = re.sub(r"\s+", " ", str(raw or "").replace("_", " ").strip().lower())
    return s if s and s not in _ABSTRACT else ""


def extract_anchors(texts: Any, *, structured: Any = (), top_k: int = 10) -> list[dict[str, Any]]:
    """The concrete anchors a resident is dwelling on, by recurrence.

    ``texts`` are prose (felt_sense lines, journal bodies); ``structured`` are
    already-concrete entity names perception hands over (present residents, event
    actors, speakers) — these count double, being unambiguous. Returns up to
    ``top_k`` ``{anchor, salience}`` (salience in ``[0, 1]``, normalized to the
    most-recurrent anchor).
    """
    counts: Counter[str] = Counter()
    for text in texts or []:
        for m in _ARTICLE_NP.finditer(str(text or "")):
            phrase = _normalize_phrase(m.group(1))
            if phrase:
                counts[phrase] += 1
    for ent in structured or []:
        phrase = _clean_entity(ent)
        if phrase:
            counts[phrase] += 2  # named entities are unambiguous anchors
    if not counts:
        return []
    top = counts.most_common(top_k)
    peak = top[0][1] or 1
    return [{"anchor": anchor, "salience": round(n / peak, 4)} for anchor, n in top]


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def record_anchors(memory_dir: Path, anchors: list[dict[str, Any]], *, now: Any = None, events: list[dict[str, Any]] | None = None) -> bool:
    """Snapshot the resident's currently-salient anchors to the ledger as the
    realized field the offline scorer reconciles predictions against. Rate-limited
    to one per ``ANCHOR_SNAPSHOT_INTERVAL``; returns whether a snapshot was written."""
    if not anchors:
        return False
    now_dt = _parse_dt(now) or datetime.now(timezone.utc)
    if events is None:
        events = load_runtime_events(memory_dir)
    last: datetime | None = None
    for e in events:
        if str(e.get("event_type") or "").strip() == "anchor_observed":
            ts = _parse_dt((e.get("payload") or {}).get("observed_ts")) or _parse_dt(e.get("ts"))
            if ts is not None and (last is None or ts > last):
                last = ts
    if last is not None and (now_dt - last).total_seconds() < ANCHOR_SNAPSHOT_INTERVAL_SECONDS:
        return False
    append_runtime_event(
        memory_dir,
        event_type="anchor_observed",
        payload={"observed_ts": now_dt.isoformat(), "anchors": [{"anchor": a["anchor"], "salience": a.get("salience", 1.0)} for a in anchors]},
    )
    return True
