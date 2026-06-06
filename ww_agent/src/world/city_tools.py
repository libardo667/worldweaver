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

import re
from dataclasses import dataclass
from typing import Callable


@dataclass
class Tool:
    """One vocation: a name, a one-line affordance shown to the resident, and a local call."""

    name: str
    description: str
    run: Callable[[str], str]  # arg -> result text; local, synchronous, zero egress
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
            return {"ok": True, "result": tool.run(str(arg or "").strip()), "egress": tool.egress}
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
# Building a resident's scope
# ---------------------------------------------------------------------------

# The default city catalog. For now every resident carries it (everyone in SF eats); a
# later pass can scope tools per-character from the resident's identity, the way a
# familiar declares its tools in familiar.json.
_DEFAULT_CITY_TOOLS: list[Tool] = [_EATS_TOOL]


def build_city_tool_scope(identity=None) -> CityToolScope:
    """Build a resident's city tool scope. ``identity`` is accepted for the future
    per-character hook; today it returns the default catalog for every resident."""
    return CityToolScope(list(_DEFAULT_CITY_TOOLS))
