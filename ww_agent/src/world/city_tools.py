# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""City information sources — a resident's elective local knowledge ecosystem.

The city analog of the familiar's scoped reading surface.
The breakthrough that gave the familiars a craft was not the specific sources — it was
having *something to find out and reason over*; the March field journal documented the
opposite (residents with nothing to do but talk, looping "HI!" and mirroring). These give
a San Francisco resident a small, named, zero-egress information ecology.

**Local-first, by construction.** Every source here is computed locally and sends nothing off
the machine — the ``eats`` guide is "false egress": it gives the worldly *feel* of looking up
where to eat (real SF spots) with none of the actual reach. The egress×goal×learning rule
(the-stable minor 54) stays honored — no source here leaves the box.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.runtime.drive import SLICE_WEIGHTS, _cosine
from src.runtime.information import (
    InformationSource,
    InformationSourceRegistry,
    information_record_id,
    resident_information_sources,
)


@dataclass
class _DriveHolder:
    """A late-bound slot for the resident's drive vector. The source registry is built in
    resident.py before the CognitiveCore exists; the core builds the drive vector lazily
    on its first tick and then binds it here, so the ``chatter`` pull can rank the
    citywide feed by soul-resonance. Until bound (or with no embedder), ``drive`` is
    None and the pull falls back to recency — never dark."""

    drive: Any = None


class CitySourceRegistry(InformationSourceRegistry):
    """City-contributed providers over the shared resident source registry."""

    def __init__(self, sources: list[InformationSource], *, drive_holder: "_DriveHolder | None" = None):
        super().__init__(sources)
        self._drive_holder = drive_holder

    def bind_drive(self, drive: Any) -> None:
        """Late-bind the resident's drive vector (the core calls this once it's built)."""
        if self._drive_holder is not None:
            self._drive_holder.drive = drive

# ---------------------------------------------------------------------------
# eats — the "false egress" SF foodie guide (local data, worldly feel)
# ---------------------------------------------------------------------------

# Real, long-running SF spots keyed by neighborhood. A resident's local knowledge of
# where to eat — feels like reaching out, never leaves the machine.
_SF_EATS: dict[str, list[tuple[str, str]]] = {
    "mission": [("La Taqueria", "the burrito, no rice, since '73"), ("Tartine Bakery", "the morning bread is worth the line"), ("Bi-Rite Creamery", "a cone after, salted caramel"), ("Foreign Cinema", "brunch in the courtyard")],
    "north beach": [("Tony's Pizza Napoletana", "the slice line at Golden Boy next door too"), ("Molinari Delicatessen", "a salami sandwich to go"), ("Caffe Trieste", "an espresso and the old murals"), ("Sotto Mare", "cioppino, no reservations")],
    "chinatown": [("R&G Lounge", "the salt-and-pepper crab"), ("Z & Y", "numbing Sichuan, go early"), ("Good Mong Kok", "dim sum off the steam tray, cash"), ("Mister Jiu's", "if it's a special night")],
    "castro": [("Anchor Oyster Bar", "marble counter, the cioppino"), ("Frances", "the bacon beignets, book ahead"), ("La Méditerranée", "the chicken pomegranate")],
    "hayes valley": [("Rich Table", "the sardine chips"), ("Souvla", "a Greek salad and frozen Greek yogurt"), ("Zuni Café", "the roast chicken for two, an hour's wait")],
    "richmond": [("Burma Superstar", "the tea leaf salad, expect a line"), ("Pizzetta 211", "a thin pie on a foggy corner"), ("Hai Ky Mi Gia", "duck noodle soup")],
    "sunset": [("Outerlands", "brunch by Ocean Beach, the eggs in jail"), ("San Tung", "the dry-fried chicken wings"), ("Hot Sauce and Panko", "wings, oddly, behind a hot-sauce shop")],
    "soma": [("Yank Sing", "dim sum carts, a splurge"), ("Marlowe", "the burger"), ("The Cavalier", "British, by the ballpark")],
    "marina": [("A16", "the Neapolitan pizza and the wine list"), ("Causwells", "the Americana burger, Tuesdays"), ("Tacolicious", "a quick taco and a margarita")],
    "nob hill": [("Swan Oyster Depot", "the counter, the crab, cash, since 1912"), ("Cheese Plus", "a grilled cheese done right")],
    "tenderloin": [("Saigon Sandwich", "a banh mi for four dollars"), ("Lers Ros", "real Thai, open late"), ("Brenda's French Soul Food", "the beignet flight, a morning wait")],
    "haight": [("Cha Cha Cha", "tapas and sangria, loud"), ("Magnolia", "a burger and a house pint"), ("Zazie", "Cole Valley brunch, the gingerbread pancakes")],
    "bernal heights": [("Red Hill Station", "oysters up the hill"), ("Good Frikin' Chicken", "the rotisserie plate"), ("Pinhole Coffee", "a pour-over and the view")],
    "dogpatch": [("Piccino", "the yellow corner, a pizza and a Coffee Bar cortado"), ("Just For You Cafe", "the beignets and grits"), ("Long Bridge Pizza", "a square slice")],
}

# Common ways a resident might name a neighborhood → its canonical key.
_EATS_ALIASES: dict[str, str] = {
    "the mission": "mission", "mission district": "mission", "the castro": "castro",
    "the haight": "haight", "haight ashbury": "haight", "the sunset": "sunset",
    "inner sunset": "sunset", "outer sunset": "sunset", "the richmond": "richmond",
    "inner richmond": "richmond", "outer richmond": "richmond", "the marina": "marina",
    "the tenderloin": "tenderloin", "tl": "tenderloin", "south of market": "soma",
    "the embarcadero": "north beach", "telegraph hill": "north beach", "russian hill": "nob hill",
    "polk gulch": "nob hill", "bernal": "bernal heights", "cole valley": "haight",
}

_STRIP = re.compile(r"\b(district|neighborhood|neighbourhood|area|sf|san francisco)\b", re.IGNORECASE)


def _eats_key(arg: str) -> str | None:
    raw = re.sub(r"\s+", " ", _STRIP.sub("", str(arg or "")).strip().lower()).strip(" ,.")
    if not raw:
        return None
    if raw in _SF_EATS:
        return raw
    if raw in _EATS_ALIASES:
        return _EATS_ALIASES[raw]
    # embedded as a whole word/phrase: "24th and mission" -> mission. Word-boundary only,
    # so a short alias ("tl") can't match inside an unrelated word ("a-tl-antis").
    for key in _SF_EATS:
        if re.search(rf"\b{re.escape(key)}\b", raw):
            return key
    for alias, key in _EATS_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", raw):
            return key
    return None


def _eats_records(arg: str) -> dict[str, Any]:
    key = _eats_key(arg)
    if key is None:
        return {"ok": False, "reason": "unknown_neighborhood", "records": []}
    return {
        "records": [
            {
                "record_id": f"eats:{key}:{index}",
                "title": name,
                "content": note,
                "freshness": "stable",
                "locality": key,
                "selection_mode": "neighborhood_match",
            }
            for index, (name, note) in enumerate(_SF_EATS[key][:3], start=1)
        ]
    }


_EATS_SOURCE = InformationSource(
    name="eats",
    description="find a bite near a San Francisco neighborhood (query: neighborhood)",
    run=_eats_records,
    freshness="stable",
    locality="San Francisco",
    selection_mode="neighborhood_match",
)


# ---------------------------------------------------------------------------
# world-facing sources — read the world through the client (the server DB)
# ---------------------------------------------------------------------------


def _make_news_source(client: Any) -> InformationSource:
    async def _run(_arg: str) -> dict[str, Any]:
        headlines = await client.get_news()
        return {
            "records": [
                {
                    "record_id": information_record_id("news", headline),
                    "title": "city news",
                    "content": str(headline),
                    "selection_mode": "chronological",
                }
                for headline in headlines[:4]
            ]
        }

    return InformationSource(name="news", description="catch the day's San Francisco news (query may be blank)", run=_run, locality="San Francisco", visibility="public", selection_mode="chronological")


def _make_places_source(client: Any) -> InformationSource:
    async def _run(arg: str) -> dict[str, Any]:
        place = str(arg or "").strip()
        if not place:
            return {"ok": False, "reason": "query_required", "records": []}
        names = await client.get_nearby_landmarks(place)
        return {
            "records": [
                {
                    "record_id": information_record_id("places", place.lower(), name),
                    "title": str(name),
                    "content": f"near {place}",
                    "locality": place,
                    "selection_mode": "proximity",
                }
                for name in names[:6]
            ]
        }

    return InformationSource(name="places", description="see what landmarks are near a place (query: place)", run=_run, locality="city", visibility="public", selection_mode="proximity")


# ---------------------------------------------------------------------------
# chatter — the CHOSEN channel (Major 60): a drive-filtered pull on citywide chat
# ---------------------------------------------------------------------------
# The city no longer pushes its chatter into every mind (that broadcast topology made
# the topic-monoculture). Instead a resident *chooses* to listen, and what it hears is
# ranked by resonance with its own soul — curiosity rationing focus. It can also follow
# a specific resonant peer by name (the relational "we" is a curiosity subscription to a
# mind, not a topic-feed). Content-blind diversity is the separate, unchosen channel
# (perception's overheard floor + traversal); this is the chosen one.


async def _drive_scores(drive: Any, texts: list[str]) -> list[float]:
    """Soul-resonance score for each text: one batched embed of all candidates, each
    scored by its weighted peak cosine against the resident's identity fragments.
    Returns parallel zeros when there is no drive vector / embedder (recency fallback)."""
    if drive is None or getattr(drive, "is_empty", lambda: True)() or not texts:
        return [0.0] * len(texts)
    try:
        vecs = await drive.embedder.embed(texts)
    except Exception:
        return [0.0] * len(texts)
    scores: list[float] = []
    for v in vecs:
        if not v:
            scores.append(0.0)
            continue
        best = 0.0
        for name, frags in drive.slices.items():
            weight = SLICE_WEIGHTS.get(name, 0.3)
            for _frag_text, frag_vec in frags:
                best = max(best, weight * _cosine(v, frag_vec))
        scores.append(round(best, 4))
    return scores


def _make_chatter_source(client: Any, holder: "_DriveHolder", session_id: str) -> InformationSource:
    def _message_record(message: Any, *, score: float, selection_mode: str) -> dict[str, Any]:
        message_id = str(getattr(message, "id", "") or "")
        speaker = str(getattr(message, "display_name", "") or "").strip()
        return {
            "record_id": f"chat:{message_id}" if message_id else f"chat:{getattr(message, 'session_id', '')}:{getattr(message, 'ts', '')}",
            "title": speaker,
            "content": str(getattr(message, "message", "") or "").strip(),
            "observed_at": str(getattr(message, "ts", "") or ""),
            "freshness": "live",
            "locality": "citywide",
            "visibility": "public",
            "selection_mode": selection_mode,
            "metadata": {"speaker": speaker, "session_id": str(getattr(message, "session_id", "") or ""), "resonance_score": round(float(score), 4)},
        }

    async def _run(arg: str) -> dict[str, Any]:
        query = str(arg or "").strip()
        try:
            messages = await client.get_location_chat("__city__")
        except Exception:
            return {"ok": False, "reason": "source_unavailable", "records": []}
        pool = [m for m in messages if str(getattr(m, "session_id", "") or "") != session_id and str(getattr(m, "message", "") or "").strip()]
        if not pool:
            return {"records": [], "selection_mode": "chronological"}
        # Follow a specific peer: the argument names someone speaking (the relational pull).
        if query:
            ql = query.lower()
            by_peer = [m for m in pool if ql in str(getattr(m, "display_name", "") or "").lower()]
            if by_peer:
                return {"selection_mode": "named_peer", "records": [_message_record(message, score=0.0, selection_mode="named_peer") for message in by_peer[-4:]]}
        # Otherwise rank the recent feed by soul-resonance (blank) or topic+resonance (a word).
        recent = pool[-14:]
        bodies = [str(m.message or "").strip() for m in recent]
        scores = await _drive_scores(holder.drive, bodies)
        if query:
            ql = query.lower()
            scores = [s + (0.5 if ql in body.lower() else 0.0) for s, body in zip(scores, bodies)]
        ranked = sorted(zip(recent, scores), key=lambda pair: -pair[1])
        if all(s <= 0.0 for _m, s in ranked):  # no resonance available → recency
            ranked = list(zip(reversed(recent), [0.0] * len(recent)))
            selection_mode = "chronological"
        elif query:
            selection_mode = "query_plus_soul_resonance"
        else:
            selection_mode = "soul_resonance"
        top = ranked[:4]
        return {"selection_mode": selection_mode, "records": [_message_record(message, score=score, selection_mode=selection_mode) for message, score in top]}

    return InformationSource(
        name="chatter",
        description="listen in on citywide chatter (query: a name or topic, or blank)",
        run=_run,
        locality="citywide",
        visibility="public",
        selection_mode="soul_resonance",
    )


def _make_investigate_source(client: Any, session_id: str) -> InformationSource:
    async def _run(arg: str) -> dict[str, Any]:
        query = str(arg or "").strip()
        if not query:
            return {"ok": False, "reason": "query_required", "records": []}
        facts = await client.get_world_facts(query, session_id=session_id or None, limit=5)
        return {
            "records": [
                {
                    "record_id": information_record_id("world-fact", summary),
                    "title": query,
                    "content": summary,
                    "freshness": "historical",
                    "locality": "world",
                    "visibility": "shared",
                    "selection_mode": "text_match",
                }
                for fact in facts
                if (summary := str(getattr(fact, "summary", "") or "").strip())
            ]
        }

    return InformationSource(name="investigate", description="look into the world's history and goings-on (query: what you want to know)", run=_run, freshness="historical", locality="world", visibility="shared", selection_mode="text_match")


# ---------------------------------------------------------------------------
# Building a resident's registry
# ---------------------------------------------------------------------------


def build_city_source_registry(
    identity: Any = None,
    *,
    client: Any = None,
    session_id: str = "",
    memory_dir: Path | None = None,
) -> CitySourceRegistry:
    """Build a resident's named city information-source registry.

    ``eats`` is universal (everyone in SF eats). ``recall`` is granted when the
    resident's memory dir is known (its own mind to look back over). The world-facing
    sources (``news``, ``places``, ``investigate``) are granted when a world client is
    available. ``identity`` is the future per-character hook — today every resident
    carries the same catalog, the way a familiar declares its sources in familiar.json.
    """
    holder = _DriveHolder()
    sources: list[InformationSource] = [_EATS_SOURCE]
    if memory_dir is not None:
        sources.extend(resident_information_sources(memory_dir))
    if client is not None:
        sources.append(_make_news_source(client))
        sources.append(_make_places_source(client))
        sources.append(_make_investigate_source(client, session_id))
        sources.append(_make_chatter_source(client, holder, session_id))
    return CitySourceRegistry(sources, drive_holder=holder)
