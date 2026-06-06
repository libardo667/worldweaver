"""City tools — a resident's local vocations (the things it can *do* besides chatter).

The city analog of the familiar tool surface (`the-stable/src/familiar/tool_scope.py`).
The breakthrough that gave the familiars a craft was not the specific tools — it was
having *something to find out and reason over*; the March field journal documented the
opposite (residents with nothing to do but talk, looping "HI!" and mirroring). These give
a San Francisco resident a small, local, zero-egress craft.

**Local-first, by construction.** Every tool here is computed locally and sends nothing off
the machine — the ``eats`` guide is "false egress": it gives the worldly *feel* of looking up
where to eat (real SF spots) with none of the actual reach. The egress×goal×learning rule
(the-stable minor 54) stays honored — no tool here leaves the box.
"""

from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Union


@dataclass
class Tool:
    """One vocation: a name, a one-line affordance shown to the resident, and a call.

    ``run`` takes the resident's argument string and returns result text. It may be
    synchronous (``eats``, ``recall`` — local) or asynchronous (``news``, ``places``,
    ``investigate`` — they read the world through the client). ``CityToolScope.call``
    awaits it either way.
    """

    name: str
    description: str
    run: Callable[[str], Union[str, Awaitable[str]]]
    egress: bool = False  # always False here — kept for symmetry with the familiar surface


class CityToolScope:
    """A resident's set of city tools. ``list``/``names`` advertise them; ``call`` runs one."""

    def __init__(self, tools: list[Tool]):
        self._tools: dict[str, Tool] = {t.name: t for t in tools}

    def list(self) -> list[Tool]:
        return list(self._tools.values())

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    def __bool__(self) -> bool:
        return bool(self._tools)

    async def call(self, name: str, arg: str) -> dict:
        tool = self._tools.get(str(name or "").strip().lower())
        if tool is None:
            return {"ok": False, "result": f"There's no '{name}' to use here."}
        try:
            result = tool.run(str(arg or "").strip())
            if inspect.isawaitable(result):
                result = await result
            return {"ok": True, "result": str(result), "egress": tool.egress}
        except Exception:
            return {"ok": False, "result": f"The {name} didn't come to anything just now."}


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


def _eats(arg: str) -> str:
    key = _eats_key(arg)
    if key is None:
        named = str(arg or "").strip()
        where = f"'{named}'" if named else "nowhere in particular"
        return (
            f"You can't place {where} on the map well enough to know its tables. "
            "Name a San Francisco neighborhood you actually know — the Mission, North Beach, "
            "the Sunset — and you'll know where to eat there."
        )
    spots = _SF_EATS[key][:3]
    label = key.title()
    parts = "; ".join(f"{name} ({note})" for name, note in spots)
    return f"Around {label}, you'd do well at: {parts}."


_EATS_TOOL = Tool(
    name="eats",
    description='find a bite near a San Francisco neighborhood — act do: "use eats <neighborhood>"',
    run=_eats,
)


# ---------------------------------------------------------------------------
# recall — perception turned inward: a resident reads its own accrued mind
# ---------------------------------------------------------------------------
# Reads the substrate's own ledger — the SAME local files the substrate appends to
# every tick (the mind's only state). Read-only, writes nothing, touches only the self:
# the safest, most grounded reach there is. (Not a bolted-on text artifact — it IS the
# substrate, the same on a city shard as on a local familiar.)

def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    except OSError:
        pass
    return out


def _recall(memory_dir: Path, query: str) -> str:
    kept = [str(k.get("note") or "").strip() for k in _read_jsonl(memory_dir / "kept_memory.jsonl")]
    kept = [k for k in kept if k]
    feelings: list[str] = []
    for event in _read_jsonl(memory_dir / "runtime_ledger.jsonl"):
        if str(event.get("event_type") or "") == "felt_sense_logged":
            felt = str((event.get("payload") or {}).get("felt_sense") or "").strip()
            if felt:
                feelings.append(felt)
    q = str(query or "").strip().lower()
    if not q:
        if not kept and not feelings:
            return "You look back, and the road is still short — little kept yet."
        parts: list[str] = []
        if kept:
            parts.append("You've kept: " + "; ".join(kept[-3:]) + ".")
        if feelings:
            parts.append(f"Lately you've felt: {feelings[-1]}.")
        return " ".join(parts)
    hits = [k for k in kept if q in k.lower()] + [f for f in feelings if q in f.lower()]
    if not hits:
        return f"Nothing comes back about '{str(query).strip()}'."
    return f"On '{str(query).strip()}': " + "; ".join(hits[-4:]) + "."


def _make_recall_tool(memory_dir: Path) -> Tool:
    return Tool(
        name="recall",
        description='look back over your own kept memories and how you have felt — act do: "use recall <a word or theme, or leave blank>"',
        run=lambda arg: _recall(memory_dir, arg),
    )


# ---------------------------------------------------------------------------
# world-facing tools — read the world through the client (the server DB)
# ---------------------------------------------------------------------------

def _make_news_tool(client: Any) -> Tool:
    async def _run(_arg: str) -> str:
        headlines = await client.get_news()
        if not headlines:
            return "Nothing much in the news right now."
        return "Word around the city: " + "; ".join(str(h) for h in headlines[:4]) + "."
    return Tool(name="news", description='catch the day\'s San Francisco news — act do: "use news"', run=_run)


def _make_places_tool(client: Any) -> Tool:
    async def _run(arg: str) -> str:
        place = str(arg or "").strip()
        if not place:
            return "Name a place to look around — a neighborhood or a landmark."
        names = await client.get_nearby_landmarks(place)
        if not names:
            return f"Nothing notable turns up near {place}."
        return f"Near {place}: " + ", ".join(str(n) for n in names[:6]) + "."
    return Tool(name="places", description='see what landmarks are near a place — act do: "use places <a place>"', run=_run)


def _make_investigate_tool(client: Any, session_id: str) -> Tool:
    async def _run(arg: str) -> str:
        query = str(arg or "").strip()
        if not query:
            return "What do you want to look into?"
        facts = await client.get_world_facts(query, session_id=session_id or None, limit=5)
        summaries = [str(getattr(f, "summary", "") or "").strip() for f in facts]
        summaries = [s for s in summaries if s]
        if not summaries:
            return f"You turn it over, but nothing about '{query}' comes to light."
        return f"On '{query}': " + " ".join(summaries) + "."
    return Tool(name="investigate", description='look into the world\'s history and goings-on — act do: "use investigate <what you want to know>"', run=_run)


# ---------------------------------------------------------------------------
# Building a resident's scope
# ---------------------------------------------------------------------------

def build_city_tool_scope(
    identity: Any = None,
    *,
    client: Any = None,
    session_id: str = "",
    memory_dir: Path | None = None,
) -> CityToolScope:
    """Build a resident's city tool scope.

    ``eats`` is universal (everyone in SF eats). ``recall`` is granted when the
    resident's memory dir is known (its own mind to look back over). The world-facing
    tools (``news``, ``places``, ``investigate``) are granted when a world client is
    available. ``identity`` is the future per-character hook — today every resident
    carries the same catalog, the way a familiar would declare its tools in familiar.json.
    """
    tools: list[Tool] = [_EATS_TOOL]
    if memory_dir is not None:
        tools.append(_make_recall_tool(memory_dir))
    if client is not None:
        tools.append(_make_news_tool(client))
        tools.append(_make_places_tool(client))
        tools.append(_make_investigate_tool(client, session_id))
    return CityToolScope(tools)
