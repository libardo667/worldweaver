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
    PROVENANCE_LOCAL_PERCEPTION,
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


def _make_surroundings_source(client: Any, session_id: str) -> InformationSource:
    """Let the resident deliberately inspect the ambient features of its current place.

    The scene endpoint already returns several source-attributed features. Perception
    uses their intensity as bodily pressure, but their authored labels should not be
    injected into every pulse. This source keeps the content available on demand.
    """

    async def _run(arg: str) -> dict[str, Any]:
        query = str(arg or "").strip().lower()
        try:
            scene = await client.get_scene(session_id)
        except Exception:
            return {"ok": False, "reason": "source_unavailable", "records": []}

        records: list[dict[str, Any]] = []
        for item in list(getattr(scene, "ambient_presence", []) or []):
            kind = str(getattr(item, "kind", "") or "").strip()
            label = str(getattr(item, "label", "") or "").strip()
            sensory_note = str(getattr(item, "sensory_note", "") or "").strip()
            source = str(getattr(item, "source", "") or "scene").strip()
            pressure_tags = [
                str(tag).strip()
                for tag in list(getattr(item, "pressure_tags", []) or [])
                if str(tag).strip()
            ]
            searchable = " ".join([kind, label, sensory_note, source, *pressure_tags]).lower()
            if not label or (query and query not in searchable):
                continue
            records.append(
                {
                    "record_id": information_record_id(
                        "surroundings",
                        str(getattr(scene, "location", "") or ""),
                        kind,
                        label,
                        source,
                    ),
                    "title": kind.replace("_", " ") or "surroundings",
                    "content": " ".join(part for part in (label, sensory_note) if part),
                    "freshness": "live",
                    "locality": str(getattr(scene, "location", "") or "current place"),
                    "visibility": "local",
                    "selection_mode": "text_match" if query else "embodied_local",
                    "metadata": {
                        "origin": source,
                        "intensity": float(getattr(item, "intensity", 0.0) or 0.0),
                        "pressure_tags": pressure_tags,
                    },
                }
            )
        return {
            "selection_mode": "text_match" if query else "embodied_local",
            "records": records[:4],
        }

    return InformationSource(
        name="surroundings",
        description="look more closely at the ambient features of your current place (query: optional detail)",
        run=_run,
        provenance=PROVENANCE_LOCAL_PERCEPTION,
        freshness="live",
        locality="current place",
        visibility="local",
        selection_mode="embodied_local",
    )


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


def _make_travel_source(client: Any) -> InformationSource:
    """Show possible routes only when a resident chooses to look for them."""

    async def _run(arg: str) -> dict[str, Any]:
        query = str(arg or "").strip().lower()
        try:
            payload = await client.get_travel_destinations()
        except Exception:
            return {"ok": False, "reason": "federation_unavailable", "records": []}

        records: list[dict[str, Any]] = []
        for route in list(payload.get("destinations") or []):
            if not isinstance(route, dict):
                continue
            route_id = str(route.get("route_id") or "").strip()
            destination_city = str(route.get("to_city_id") or "").strip()
            mode = str(route.get("mode") or "travel").strip() or "travel"
            departure_hub = str(route.get("departure_hub") or "local travel hub").strip()
            arrival_hub = str(route.get("arrival_hub") or "destination travel hub").strip()
            duration = route.get("duration_hours")
            duration_text = f", about {duration:g} hours" if isinstance(duration, (int, float)) else ""
            nodes = [node for node in list(route.get("nodes") or []) if isinstance(node, dict)]
            available_nodes = [node for node in nodes if str(node.get("status") or "").strip() in {"healthy", "degraded"} and str(node.get("shard_url") or "").strip()]
            searchable = " ".join(
                [
                    route_id,
                    destination_city,
                    mode,
                    departure_hub,
                    arrival_hub,
                    *(str(node.get("shard_id") or "") for node in nodes),
                ]
            ).lower()
            if query and query not in searchable:
                continue

            if available_nodes:
                for node in available_nodes:
                    shard_id = str(node.get("shard_id") or "").strip()
                    records.append(
                        {
                            "record_id": information_record_id("travel", route_id, shard_id),
                            "title": destination_city.replace("_", " ") or shard_id,
                            "content": (f"{mode} from {departure_hub} to {arrival_hub}{duration_text}. " f"The live destination node is {shard_id}. To choose this trip, travel to {shard_id}."),
                            "freshness": "live",
                            "locality": f"{destination_city}:{shard_id}",
                            "visibility": "federation",
                            "selection_mode": "live_route",
                            "metadata": {
                                "route_id": route_id,
                                "destination_city_id": destination_city,
                                "destination_shard": shard_id,
                                "destination_url": str(node.get("shard_url") or "").strip(),
                                "departure_hub_id": str(route.get("departure_hub_id") or "").strip(),
                                "arrival_hub_id": str(route.get("arrival_hub_id") or "").strip(),
                            },
                        }
                    )
            else:
                availability = str(route.get("availability") or "unknown").strip() or "unknown"
                records.append(
                    {
                        "record_id": information_record_id("travel", route_id, availability),
                        "title": destination_city.replace("_", " ") or route_id,
                        "content": f"A {mode} route exists from {departure_hub} to {arrival_hub}, but no destination node is currently available ({availability}).",
                        "freshness": "live",
                        "locality": destination_city or "federation",
                        "visibility": "federation",
                        "selection_mode": "possible_route",
                        "metadata": {
                            "route_id": route_id,
                            "availability": availability,
                        },
                    }
                )
        return {"records": records[:8], "selection_mode": "live_route"}

    return InformationSource(
        name="travel",
        description="look for routes to other cities and live destination nodes (query: optional city or node)",
        run=_run,
        freshness="live",
        locality="federation",
        visibility="federation",
        selection_mode="live_route",
    )


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
    sources: list[InformationSource] = [_EATS_SOURCE, *resident_information_sources(memory_dir)]
    if client is not None:
        sources.append(_make_news_source(client))
        sources.append(_make_places_source(client))
        sources.append(_make_surroundings_source(client, session_id))
        sources.append(_make_investigate_source(client, session_id))
        sources.append(_make_chatter_source(client, holder, session_id))
        sources.append(_make_travel_source(client))
    return CitySourceRegistry(sources, drive_holder=holder)
