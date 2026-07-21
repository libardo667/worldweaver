# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""City information sources — a resident's elective local knowledge ecosystem.

The city analog of the familiar's scoped reading surface. Residents need useful things
they can choose to inspect instead of a prompt that constantly narrates the city at them.
The registry is selected from the current node's city identity and declared features, so
an Alderbank resident does not receive San Francisco knowledge or unavailable game tools.

Most sources read records from the attached shard. Sources that contact a federation
registry or the public web are labelled as egress, rather than being passed off as local
knowledge. The San Francisco ``eats`` guide is project-authored reference material.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.runtime.information import (
    InformationSource,
    InformationSourceRegistry,
    PROVENANCE_AUTHORED_REFERENCE,
    PROVENANCE_FEDERATION_RECORD,
    PROVENANCE_PARTICIPANT_EXPRESSION,
    PROVENANCE_SHARD_RECORD,
    PROVENANCE_WORLD_EGRESS,
    information_record_id,
    resident_information_sources,
)

# ---------------------------------------------------------------------------
# eats — the "false egress" SF foodie guide (local data, worldly feel)
# ---------------------------------------------------------------------------

# Real, long-running SF spots keyed by neighborhood. A resident's local knowledge of
# where to eat — feels like reaching out, never leaves the machine.
_SF_EATS: dict[str, list[tuple[str, str]]] = {
    "mission": [
        ("La Taqueria", "the burrito, no rice, since '73"),
        ("Tartine Bakery", "the morning bread is worth the line"),
        ("Bi-Rite Creamery", "a cone after, salted caramel"),
        ("Foreign Cinema", "brunch in the courtyard"),
    ],
    "north beach": [
        ("Tony's Pizza Napoletana", "the slice line at Golden Boy next door too"),
        ("Molinari Delicatessen", "a salami sandwich to go"),
        ("Caffe Trieste", "an espresso and the old murals"),
        ("Sotto Mare", "cioppino, no reservations"),
    ],
    "chinatown": [
        ("R&G Lounge", "the salt-and-pepper crab"),
        ("Z & Y", "numbing Sichuan, go early"),
        ("Good Mong Kok", "dim sum off the steam tray, cash"),
        ("Mister Jiu's", "if it's a special night"),
    ],
    "castro": [
        ("Anchor Oyster Bar", "marble counter, the cioppino"),
        ("Frances", "the bacon beignets, book ahead"),
        ("La Méditerranée", "the chicken pomegranate"),
    ],
    "hayes valley": [
        ("Rich Table", "the sardine chips"),
        ("Souvla", "a Greek salad and frozen Greek yogurt"),
        ("Zuni Café", "the roast chicken for two, an hour's wait"),
    ],
    "richmond": [
        ("Burma Superstar", "the tea leaf salad, expect a line"),
        ("Pizzetta 211", "a thin pie on a foggy corner"),
        ("Hai Ky Mi Gia", "duck noodle soup"),
    ],
    "sunset": [
        ("Outerlands", "brunch by Ocean Beach, the eggs in jail"),
        ("San Tung", "the dry-fried chicken wings"),
        ("Hot Sauce and Panko", "wings, oddly, behind a hot-sauce shop"),
    ],
    "soma": [
        ("Yank Sing", "dim sum carts, a splurge"),
        ("Marlowe", "the burger"),
        ("The Cavalier", "British, by the ballpark"),
    ],
    "marina": [
        ("A16", "the Neapolitan pizza and the wine list"),
        ("Causwells", "the Americana burger, Tuesdays"),
        ("Tacolicious", "a quick taco and a margarita"),
    ],
    "nob hill": [
        ("Swan Oyster Depot", "the counter, the crab, cash, since 1912"),
        ("Cheese Plus", "a grilled cheese done right"),
    ],
    "tenderloin": [
        ("Saigon Sandwich", "a banh mi for four dollars"),
        ("Lers Ros", "real Thai, open late"),
        ("Brenda's French Soul Food", "the beignet flight, a morning wait"),
    ],
    "haight": [
        ("Cha Cha Cha", "tapas and sangria, loud"),
        ("Magnolia", "a burger and a house pint"),
        ("Zazie", "Cole Valley brunch, the gingerbread pancakes"),
    ],
    "bernal heights": [
        ("Red Hill Station", "oysters up the hill"),
        ("Good Frikin' Chicken", "the rotisserie plate"),
        ("Pinhole Coffee", "a pour-over and the view"),
    ],
    "dogpatch": [
        ("Piccino", "the yellow corner, a pizza and a Coffee Bar cortado"),
        ("Just For You Cafe", "the beignets and grits"),
        ("Long Bridge Pizza", "a square slice"),
    ],
}

# Common ways a resident might name a neighborhood → its canonical key.
_EATS_ALIASES: dict[str, str] = {
    "the mission": "mission",
    "mission district": "mission",
    "the castro": "castro",
    "the haight": "haight",
    "haight ashbury": "haight",
    "the sunset": "sunset",
    "inner sunset": "sunset",
    "outer sunset": "sunset",
    "the richmond": "richmond",
    "inner richmond": "richmond",
    "outer richmond": "richmond",
    "the marina": "marina",
    "the tenderloin": "tenderloin",
    "tl": "tenderloin",
    "south of market": "soma",
    "the embarcadero": "north beach",
    "telegraph hill": "north beach",
    "russian hill": "nob hill",
    "polk gulch": "nob hill",
    "bernal": "bernal heights",
    "cole valley": "haight",
}

_STRIP = re.compile(
    r"\b(district|neighborhood|neighbourhood|area|sf|san francisco)\b", re.IGNORECASE
)


def _eats_key(arg: str) -> str | None:
    raw = re.sub(r"\s+", " ", _STRIP.sub("", str(arg or "")).strip().lower()).strip(
        " ,."
    )
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
    description="read the project's undated San Francisco food guide (query: neighborhood)",
    run=_eats_records,
    provenance=PROVENANCE_AUTHORED_REFERENCE,
    freshness="undated",
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

    return InformationSource(
        name="news",
        description="read externally fetched San Francisco news headlines (query may be blank)",
        run=_run,
        egress=True,
        provenance=PROVENANCE_WORLD_EGRESS,
        freshness="recent-cache",
        locality="San Francisco",
        visibility="public",
        selection_mode="chronological",
    )


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

    return InformationSource(
        name="places",
        description="find city-pack landmarks near a named place (query: place)",
        run=_run,
        provenance=PROVENANCE_AUTHORED_REFERENCE,
        freshness="pack-version",
        locality="city",
        visibility="public",
        selection_mode="proximity",
    )


def _make_objects_source(client: Any, session_id: str) -> InformationSource:
    """Show only durable objects carried by the resident or present right here."""

    async def _run(arg: str) -> dict[str, Any]:
        query = str(arg or "").strip().lower()
        try:
            payload = await client.get_world_objects(session_id)
        except Exception:
            return {"ok": False, "reason": "source_unavailable", "records": []}

        try:
            scene = await client.get_scene(session_id)
            recipients = [
                {
                    "session_id": str(getattr(person, "session_id", "") or "").strip(),
                    "name": str(
                        getattr(person, "role", "") or getattr(person, "name", "") or ""
                    ).strip(),
                }
                for person in list(getattr(scene, "present", []) or [])
                if str(getattr(person, "session_id", "") or "").strip()
                not in {"", session_id}
            ][:4]
        except Exception:
            recipients = []

        records: list[dict[str, Any]] = []
        for item in list(payload.get("objects") or []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            description = str(item.get("description") or "").strip()
            kind = str(item.get("object_kind") or "object").strip()
            relation = str(item.get("relation") or "here").strip()
            can_pick_up = bool(item.get("can_pick_up"))
            object_id = str(item.get("object_id") or "").strip()
            searchable = " ".join(
                (name, description, kind, relation, object_id)
            ).lower()
            if not name or (query and query not in searchable):
                continue
            if relation == "carried":
                relation_text = f'You are carrying it. To place it here, act with kind "do" and target "object-place:{object_id}".'
                if recipients:
                    give_choices = " ".join(
                        f'To give it immediately to {recipient["name"]}, act with kind "do" and target "object-give:{object_id}:{recipient["session_id"]}".'
                        for recipient in recipients
                    )
                    relation_text = f"{relation_text} {give_choices}"
            elif can_pick_up:
                relation_text = f'It is here with you. You placed it here; to pick it back up, act with kind "do" and target "object-pick-up:{object_id}".'
            else:
                relation_text = "It is here with you, but it is not yours to pick up."
            records.append(
                {
                    "record_id": f"object:{object_id}",
                    "title": name,
                    "content": " ".join(
                        part for part in (description, relation_text) if part
                    ),
                    "freshness": "live",
                    "locality": "carried" if relation == "carried" else "current place",
                    "visibility": "private" if relation == "carried" else "local",
                    "selection_mode": "text_match" if query else "embodied_local",
                    "metadata": {
                        "object_id": object_id,
                        "object_kind": kind,
                        "relation": relation,
                        "can_pick_up": can_pick_up,
                        "give_recipients": recipients if relation == "carried" else [],
                        "revision": item.get("revision"),
                    },
                }
            )
        return {
            "selection_mode": "text_match" if query else "embodied_local",
            "records": records[:12],
        }

    return InformationSource(
        name="objects",
        description="look at what you carry and what durable objects are here (query: optional object detail)",
        run=_run,
        provenance=PROVENANCE_SHARD_RECORD,
        freshness="live",
        locality="current place",
        visibility="local",
        selection_mode="embodied_local",
    )


def _make_making_source(client: Any, session_id: str) -> InformationSource:
    """Show declared materials and recipes available at this exact place."""

    async def _run(arg: str) -> dict[str, Any]:
        query = str(arg or "").strip().lower()
        try:
            payload = await client.get_local_making(session_id)
        except Exception:
            return {"ok": False, "reason": "source_unavailable", "records": []}

        location = str(payload.get("location") or "current place").strip()
        records: list[dict[str, Any]] = []
        for material in list(payload.get("materials") or []):
            if not isinstance(material, dict):
                continue
            material_id = str(material.get("material_id") or "").strip()
            title = str(material.get("title") or material_id).strip()
            description = str(material.get("description") or "").strip()
            available = material.get("available_units", 0)
            capacity = material.get("capacity_units", 0)
            searchable = " ".join((material_id, title, description)).lower()
            if query and query not in searchable:
                continue
            records.append(
                {
                    "record_id": f"material:{material_id}:{location}",
                    "title": title,
                    "content": f"{description} {available} of {capacity} units are currently available here.".strip(),
                    "freshness": "live",
                    "locality": location,
                    "visibility": "local",
                    "selection_mode": "text_match" if query else "embodied_local",
                    "metadata": {"kind": "material", "material_id": material_id},
                }
            )
        for recipe in list(payload.get("recipes") or []):
            if not isinstance(recipe, dict):
                continue
            recipe_id = str(recipe.get("recipe_id") or "").strip()
            title = str(recipe.get("title") or recipe_id).strip()
            description = str(recipe.get("description") or "").strip()
            can_make = bool(recipe.get("can_make"))
            searchable = " ".join((recipe_id, title, description)).lower()
            if query and query not in searchable:
                continue
            availability = (
                "The materials are available now."
                if can_make
                else "Some required materials are not available now."
            )
            choice = (
                f'To choose this recipe, act with kind "do" and target "recipe:{recipe_id}".'
                if can_make
                else ""
            )
            records.append(
                {
                    "record_id": f"recipe:{recipe_id}:{location}",
                    "title": title,
                    "content": f"{description} {availability} {choice}".strip(),
                    "freshness": "live",
                    "locality": location,
                    "visibility": "local",
                    "selection_mode": "text_match" if query else "embodied_local",
                    "metadata": {
                        "kind": "recipe",
                        "recipe_id": recipe_id,
                        "can_make": can_make,
                        "inputs": dict(recipe.get("inputs") or {}),
                    },
                }
            )
        return {
            "selection_mode": "text_match" if query else "embodied_local",
            "records": records[:12],
        }

    return InformationSource(
        name="making",
        description="see what materials and recipes are available at your exact place (query: optional material or recipe)",
        run=_run,
        provenance=PROVENANCE_SHARD_RECORD,
        freshness="live",
        locality="current place",
        visibility="local",
        selection_mode="embodied_local",
    )


def _make_exchanges_source(client: Any, session_id: str) -> InformationSource:
    """Show exact open exchanges and co-present object-for-object offer choices."""

    async def _run(arg: str) -> dict[str, Any]:
        query = str(arg or "").strip().lower()
        try:
            payload = await client.get_object_exchanges(session_id)
            objects_payload = await client.get_world_objects(session_id)
            scene = await client.get_scene(session_id)
        except Exception:
            return {"ok": False, "reason": "source_unavailable", "records": []}

        actor_names = {
            str(getattr(person, "actor_id", "") or "")
            .strip(): str(
                getattr(person, "role", "")
                or getattr(person, "name", "")
                or "another person"
            )
            .strip()
            for person in list(getattr(scene, "present", []) or [])
            if str(getattr(person, "actor_id", "") or "").strip()
        }
        carried = [
            item
            for item in list(objects_payload.get("objects") or [])
            if isinstance(item, dict) and str(item.get("relation") or "") == "carried"
        ][:6]
        records: list[dict[str, Any]] = []

        for item in list(payload.get("exchanges") or []):
            if not isinstance(item, dict):
                continue
            exchange_id = str(item.get("exchange_id") or "").strip()
            offered = dict(item.get("offered_object") or {})
            requested = dict(item.get("requested_object") or {})
            role = str(item.get("viewer_role") or "").strip()
            counterpart_actor_id = str(
                item.get("proposer_actor_id")
                if role == "recipient"
                else item.get("recipient_actor_id") or ""
            ).strip()
            counterpart = actor_names.get(counterpart_actor_id, "the other person")
            status = str(item.get("status") or "unknown").strip()
            choices: list[str] = []
            if bool(item.get("can_accept")):
                choices.append(
                    f'To accept this exact swap, act with kind "do" and target "exchange-accept:{exchange_id}".'
                )
            if bool(item.get("can_decline")):
                choices.append(
                    f'To decline it, act with kind "do" and target "exchange-decline:{exchange_id}".'
                )
            if bool(item.get("can_cancel")):
                choices.append(
                    f'To cancel your offer, act with kind "do" and target "exchange-cancel:{exchange_id}".'
                )
            terms = (
                f'{counterpart} offered their "{offered.get("name", "object")}" for your "{requested.get("name", "object")}".'
                if role == "recipient"
                else f'You offered your "{offered.get("name", "object")}" for {counterpart}\'s "{requested.get("name", "object")}".'
            )
            content = f"{terms} Status: {status}. {' '.join(choices)}".strip()
            searchable = f"{counterpart} {content}".lower()
            if query and query not in searchable:
                continue
            records.append(
                {
                    "record_id": f"exchange:{exchange_id}",
                    "title": f"{offered.get('name', 'Object')} for {requested.get('name', 'object')}",
                    "content": content,
                    "freshness": "live",
                    "locality": (
                        "current place"
                        if bool(item.get("counterpart_present"))
                        else "actor-scoped"
                    ),
                    "visibility": "private",
                    "selection_mode": "text_match" if query else "actor_scoped",
                    "metadata": {**item, "counterpart_name": counterpart},
                }
            )

        for option in list(payload.get("offer_options") or [])[:6]:
            if not isinstance(option, dict):
                continue
            recipient_session_id = str(option.get("recipient_session_id") or "").strip()
            recipient_actor_id = str(option.get("recipient_actor_id") or "").strip()
            recipient_name = actor_names.get(recipient_actor_id, "the other person")
            for requested in list(option.get("requested_objects") or [])[:6]:
                if not isinstance(requested, dict):
                    continue
                requested_id = str(requested.get("object_id") or "").strip()
                requested_name = str(requested.get("name") or "object").strip()
                for offered in carried:
                    offered_id = str(offered.get("object_id") or "").strip()
                    offered_name = str(offered.get("name") or "object").strip()
                    content = (
                        f'To offer {offered_name} for {recipient_name}\'s {requested_name}, act with kind "do" and target '
                        f'"exchange-offer:{recipient_session_id}:{offered_id}:{requested_id}". Nothing moves unless they later accept.'
                    )
                    if (
                        query
                        and query
                        not in f"{recipient_name} {offered_name} {requested_name}".lower()
                    ):
                        continue
                    records.append(
                        {
                            "record_id": f"exchange-option:{recipient_session_id}:{offered_id}:{requested_id}",
                            "title": f"Offer {offered_name} for {requested_name}",
                            "content": content,
                            "freshness": "live",
                            "locality": "current place",
                            "visibility": "private",
                            "selection_mode": (
                                "text_match" if query else "embodied_local"
                            ),
                            "metadata": {
                                "recipient_session_id": recipient_session_id,
                                "recipient_name": recipient_name,
                                "offered_object_id": offered_id,
                                "requested_object_id": requested_id,
                            },
                        }
                    )
                    if len(records) >= 18:
                        break
                if len(records) >= 18:
                    break
            if len(records) >= 18:
                break

        return {
            "selection_mode": "text_match" if query else "actor_scoped",
            "records": records[:18],
        }

    return InformationSource(
        name="exchanges",
        description="review your object exchanges or exact swaps available with people here (query: optional person or object)",
        run=_run,
        provenance=PROVENANCE_SHARD_RECORD,
        freshness="live",
        locality="current place and actor-scoped history",
        visibility="private",
        selection_mode="actor_scoped",
    )


def _make_access_source(client: Any, session_id: str) -> InformationSource:
    """Inspect and act on entry rules for one explicitly named exact place."""

    async def _run(arg: str) -> dict[str, Any]:
        query = str(arg or "").strip()
        if not query:
            return {"ok": False, "reason": "exact_place_required", "records": []}
        try:
            places = sorted(await client.get_place_names())
            lowered = query.lower()
            exact = next((place for place in places if place.lower() == lowered), "")
            matches = [place for place in places if lowered in place.lower()]
            location = exact or (matches[0] if len(matches) == 1 else "")
            if not location:
                return {"ok": False, "reason": "exact_place_not_found", "records": []}
            payload = await client.get_space_access_status(session_id, location)
            scene = await client.get_scene(session_id)
        except Exception:
            return {"ok": False, "reason": "source_unavailable", "records": []}

        access = dict(payload.get("access") or {})
        mode = str(access.get("mode") or "public")
        note = str(access.get("note") or "").strip()
        choices: list[str] = []
        if bool(access.get("can_request")):
            choices.append(
                f'To ask for entry, act with kind "do" and target "access-request:{location}".'
            )
        if bool(access.get("is_controller")):
            for next_mode in ("public", "requestable", "private", "closed"):
                if next_mode != mode:
                    choices.append(
                        f'To change this place to {next_mode}, act with kind "do" and target "access-mode:{next_mode}:{location}".'
                    )

        present = list(getattr(scene, "present", []) or [])
        names_by_actor = {
            str(getattr(person, "actor_id", "") or "")
            .strip(): str(
                getattr(person, "role", "")
                or getattr(person, "name", "")
                or "another person"
            )
            .strip()
            for person in present
            if str(getattr(person, "actor_id", "") or "").strip()
        }
        granted_actor_ids = {
            str(item.get("actor_id") or "").strip()
            for item in list(access.get("active_grants") or [])
            if isinstance(item, dict)
        }
        if bool(access.get("is_controller")):
            for person in present[:8]:
                actor_id = str(getattr(person, "actor_id", "") or "").strip()
                recipient_session_id = str(
                    getattr(person, "session_id", "") or ""
                ).strip()
                name = names_by_actor.get(actor_id, "the other person")
                if recipient_session_id and actor_id not in granted_actor_ids:
                    choices.append(
                        f'To invite {name}, act with kind "do" and target "access-invite:{recipient_session_id}:{location}".'
                    )
            for grant in list(access.get("active_grants") or [])[:8]:
                if not isinstance(grant, dict):
                    continue
                actor_id = str(grant.get("actor_id") or "").strip()
                recipient_session_id = str(grant.get("session_id") or "").strip()
                if recipient_session_id:
                    name = names_by_actor.get(actor_id, "that admitted person")
                    choices.append(
                        f'To end {name}\'s future entry without ejecting them, act with kind "do" and target "access-revoke:{recipient_session_id}:{location}".'
                    )

        records = [
            {
                "record_id": f"access:{location}",
                "title": f"Access to {location}",
                "content": (
                    f"Mode: {mode}. You {'can' if access.get('can_enter') else 'cannot'} enter. "
                    f"{note} {' '.join(choices)}"
                ).strip(),
                "freshness": "live",
                "locality": location,
                "visibility": "private",
                "selection_mode": "exact_place",
                "metadata": access,
            }
        ]
        if bool(access.get("is_controller")):
            try:
                request_payload = await client.get_pending_space_access_requests(
                    session_id, location
                )
            except Exception:
                request_payload = {"requests": []}
            for request in list(request_payload.get("requests") or [])[:12]:
                if not isinstance(request, dict):
                    continue
                request_id = str(request.get("request_id") or "").strip()
                requester_actor_id = str(
                    request.get("requester_actor_id") or ""
                ).strip()
                requester_name = names_by_actor.get(requester_actor_id, "Someone")
                request_note = str(request.get("note") or "").strip()
                records.append(
                    {
                        "record_id": f"access-request:{request_id}",
                        "title": f"Request from {requester_name}",
                        "content": (
                            f'{request_note or "They left no note."} To admit them, act with kind "do" and target "access-admit:{request_id}". '
                            f'To deny this request, act with kind "do" and target "access-deny:{request_id}".'
                        ),
                        "freshness": "live",
                        "locality": location,
                        "visibility": "private",
                        "selection_mode": "controller_queue",
                        "metadata": request,
                    }
                )
        return {"selection_mode": "exact_place", "records": records}

    return InformationSource(
        name="access",
        description="inspect or manage entry rules for one exact named place (query: required exact place name)",
        run=_run,
        provenance=PROVENANCE_SHARD_RECORD,
        freshness="live",
        locality="named exact place",
        visibility="private",
        selection_mode="exact_place",
    )


def _make_stoops_source(client: Any, session_id: str) -> InformationSource:
    """List local stoops, then open one only when it is named."""

    async def _run(arg: str) -> dict[str, Any]:
        query = str(arg or "").strip()
        try:
            payload = await client.get_local_stoops(session_id)
        except Exception:
            return {"ok": False, "reason": "source_unavailable", "records": []}

        location = str(payload.get("location") or "current place").strip()
        stoops = [
            item for item in list(payload.get("stoops") or []) if isinstance(item, dict)
        ]
        if query:
            lowered = query.lower()
            matches = [
                item
                for item in stoops
                if lowered in str(item.get("stoop_id") or "").lower()
                or lowered in str(item.get("title") or "").lower()
            ]
            if len(matches) == 1:
                stoop_id = str(matches[0].get("stoop_id") or "").strip()
                try:
                    opened = await client.browse_world_stoop(session_id, stoop_id)
                except Exception:
                    return {"ok": False, "reason": "source_unavailable", "records": []}
                records = []
                for entry in list(opened.get("entries") or []):
                    if not isinstance(entry, dict):
                        continue
                    item = (
                        entry.get("object")
                        if isinstance(entry.get("object"), dict)
                        else {}
                    )
                    object_id = str(item.get("object_id") or "").strip()
                    title = str(item.get("name") or "object").strip()
                    description = str(item.get("description") or "").strip()
                    entry_id = str(entry.get("entry_id") or "").strip()
                    if bool(entry.get("can_take")):
                        choice = f'To accept this permission and take it, act with kind "do" and target "stoop-take:{entry_id}".'
                    elif bool(entry.get("can_withdraw")):
                        choice = f'To reclaim what you left, act with kind "do" and target "stoop-withdraw:{entry_id}".'
                    else:
                        choice = ""
                    records.append(
                        {
                            "record_id": f"stoop-entry:{entry.get('entry_id')}",
                            "title": title,
                            "content": f"{description or 'An object left for a visitor.'} {choice}".strip(),
                            "freshness": "live",
                            "locality": location,
                            "visibility": "local",
                            "selection_mode": "named_stoop",
                            "metadata": {
                                "stoop_id": stoop_id,
                                "entry_id": str(entry.get("entry_id") or ""),
                                "object_id": object_id,
                                "can_take": bool(entry.get("can_take")),
                                "can_withdraw": bool(entry.get("can_withdraw")),
                            },
                        }
                    )
                return {"selection_mode": "named_stoop", "records": records}

        records = []
        for item in stoops:
            stoop_id = str(item.get("stoop_id") or "").strip()
            title = str(item.get("title") or stoop_id).strip()
            prompt = str(item.get("prompt") or "").strip()
            active_count = int(item.get("active_count") or 0)
            records.append(
                {
                    "record_id": f"stoop:{stoop_id}",
                    "title": title,
                    "content": f"{prompt} It currently holds {active_count} object{'s' if active_count != 1 else ''}. Name this stoop to look inside.".strip(),
                    "freshness": "live",
                    "locality": location,
                    "visibility": "local",
                    "selection_mode": "embodied_local",
                    "metadata": {"stoop_id": stoop_id, "active_count": active_count},
                }
            )
            try:
                objects_payload = await client.get_world_objects(session_id)
            except Exception:
                objects_payload = {"objects": []}
            for carried in list(objects_payload.get("objects") or []):
                if (
                    not isinstance(carried, dict)
                    or str(carried.get("relation") or "") != "carried"
                ):
                    continue
                object_id = str(carried.get("object_id") or "").strip()
                object_name = str(carried.get("name") or "object").strip()
                records.append(
                    {
                        "record_id": f"stoop-leave:{stoop_id}:{object_id}",
                        "title": f"Leave {object_name}",
                        "content": (
                            "Leaving this object is explicit permission for another visitor to take it. "
                            f'To do that, act with kind "do" and target "stoop-leave:{stoop_id}:{object_id}".'
                        ),
                        "freshness": "live",
                        "locality": location,
                        "visibility": "private",
                        "selection_mode": "embodied_local",
                        "metadata": {
                            "stoop_id": stoop_id,
                            "object_id": object_id,
                            "command": "leave",
                        },
                    }
                )
        return {"selection_mode": "embodied_local", "records": records}

    return InformationSource(
        name="stoops",
        description="see stoops at your exact place, or look inside one by name (query: optional stoop name)",
        run=_run,
        provenance=PROVENANCE_SHARD_RECORD,
        freshness="live",
        locality="current place",
        visibility="local",
        selection_mode="embodied_local",
    )


# ---------------------------------------------------------------------------
# chatter: retained provider for a future explicit citywide channel
# ---------------------------------------------------------------------------
def _make_chatter_source(client: Any, session_id: str) -> InformationSource:
    def _message_record(message: Any, *, selection_mode: str) -> dict[str, Any]:
        message_id = str(getattr(message, "id", "") or "")
        speaker = str(getattr(message, "display_name", "") or "").strip()
        return {
            "record_id": (
                f"chat:{message_id}"
                if message_id
                else f"chat:{getattr(message, 'session_id', '')}:{getattr(message, 'ts', '')}"
            ),
            "title": speaker,
            "content": str(getattr(message, "message", "") or "").strip(),
            "observed_at": str(getattr(message, "ts", "") or ""),
            "freshness": "recorded",
            "locality": "citywide",
            "visibility": "public",
            "selection_mode": selection_mode,
            "metadata": {
                "speaker": speaker,
                "session_id": str(getattr(message, "session_id", "") or ""),
            },
        }

    async def _run(arg: str) -> dict[str, Any]:
        query = str(arg or "").strip()
        try:
            messages = await client.get_location_chat("__city__", session_id=session_id)
        except Exception:
            return {"ok": False, "reason": "source_unavailable", "records": []}
        pool = [
            m
            for m in messages
            if str(getattr(m, "session_id", "") or "") != session_id
            and str(getattr(m, "message", "") or "").strip()
        ]
        if not pool:
            return {"records": [], "selection_mode": "chronological"}
        # A matching participant name is an explicit participant filter.
        if query:
            ql = query.lower()
            by_peer = [
                m
                for m in pool
                if ql in str(getattr(m, "display_name", "") or "").lower()
            ]
            if by_peer:
                return {
                    "selection_mode": "named_peer",
                    "records": [
                        _message_record(message, selection_mode="named_peer")
                        for message in by_peer[-4:]
                    ],
                }
        # A non-name query is a literal text filter. Blank means newest first.
        if query:
            ql = query.lower()
            selected = [
                message
                for message in pool
                if ql in str(getattr(message, "message", "") or "").lower()
            ]
            selection_mode = "text_match"
        else:
            selected = pool
            selection_mode = "chronological"
        top = list(reversed(selected[-4:]))
        return {
            "selection_mode": selection_mode,
            "records": [
                _message_record(message, selection_mode=selection_mode)
                for message in top
            ],
        }

    return InformationSource(
        name="chatter",
        description="listen in on citywide chatter (query: a name or topic, or blank)",
        run=_run,
        provenance=PROVENANCE_PARTICIPANT_EXPRESSION,
        freshness="recorded",
        locality="citywide",
        visibility="public",
        selection_mode="chronological",
    )


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
            departure_hub = str(
                route.get("departure_hub") or "local travel hub"
            ).strip()
            arrival_hub = str(
                route.get("arrival_hub") or "destination travel hub"
            ).strip()
            duration = route.get("duration_hours")
            duration_text = (
                f", about {duration:g} hours"
                if isinstance(duration, (int, float))
                else ""
            )
            nodes = [
                node
                for node in list(route.get("nodes") or [])
                if isinstance(node, dict)
            ]
            available_nodes = [
                node
                for node in nodes
                if str(node.get("status") or "").strip() in {"healthy", "degraded"}
                and str(node.get("shard_url") or "").strip()
            ]
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
                            "record_id": information_record_id(
                                "travel", route_id, shard_id
                            ),
                            "title": destination_city.replace("_", " ") or shard_id,
                            "content": (
                                f"{mode} from {departure_hub} to {arrival_hub}{duration_text}. "
                                f"The live destination node is {shard_id}. To choose this trip, travel to {shard_id}."
                            ),
                            "freshness": "live",
                            "locality": f"{destination_city}:{shard_id}",
                            "visibility": "federation",
                            "selection_mode": "live_route",
                            "metadata": {
                                "route_id": route_id,
                                "destination_city_id": destination_city,
                                "destination_shard": shard_id,
                                "destination_url": str(
                                    node.get("shard_url") or ""
                                ).strip(),
                                "departure_hub_id": str(
                                    route.get("departure_hub_id") or ""
                                ).strip(),
                                "arrival_hub_id": str(
                                    route.get("arrival_hub_id") or ""
                                ).strip(),
                            },
                        }
                    )
            else:
                availability = (
                    str(route.get("availability") or "unknown").strip() or "unknown"
                )
                records.append(
                    {
                        "record_id": information_record_id(
                            "travel", route_id, availability
                        ),
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
        egress=True,
        provenance=PROVENANCE_FEDERATION_RECORD,
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
    city_id: str | None = None,
    capabilities: set[str] | frozenset[str] = frozenset(),
) -> InformationSourceRegistry:
    """Build a resident's named city information-source registry.

    ``city_id=None`` preserves the legacy San Francisco catalog for direct callers.
    A live resident passes the node's published city ID and game capabilities so a
    fictional town is not quietly given San Francisco knowledge or unavailable verbs.
    """
    legacy_or_sf = city_id is None or city_id == "san_francisco"
    sources: list[InformationSource] = [*resident_information_sources(memory_dir)]
    if legacy_or_sf:
        sources.append(_EATS_SOURCE)
    if client is not None:
        # Do not advertise ``news`` yet. Reading it can make the shard fetch a
        # public RSS feed, and the resident-scoped egress grants required by
        # Minor 122 do not exist yet.
        sources.append(_make_places_source(client))
        # Do not advertise ``chatter`` yet. The engine can read the reserved
        # ``__city__`` channel, but its current location-bound chat endpoint cannot
        # write to it. Advertising the source would promise a live commons while
        # returning only old or empty records.
        sources.append(_make_travel_source(client))
        if "durable_objects" in capabilities:
            sources.append(_make_objects_source(client, session_id))
        if {"replenishing_materials", "making"}.issubset(capabilities):
            sources.append(_make_making_source(client, session_id))
        if "witnessed_exchange" in capabilities:
            sources.append(_make_exchanges_source(client, session_id))
        if "space_permissions" in capabilities:
            sources.append(_make_access_source(client, session_id))
        if "stoops" in capabilities:
            sources.append(_make_stoops_source(client, session_id))
    return InformationSourceRegistry(sources)
