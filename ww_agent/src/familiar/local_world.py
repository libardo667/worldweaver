# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""LocalWorld: a one-resident world grounded in the host machine (Major 50).

This is the body a familiar lives in. It duck-types the small slice of
``WorldWeaverClient`` that ``perception`` and ``WorldEffector`` actually call, so
the unmodified ``CognitiveCore`` runs against it exactly as it runs against a city
shard. Instead of a backend it offers:

- **grounding** from the system clock — the real local hour drives the circadian
  rhythm, so the familiar keeps the keeper's hours,
- a **summon channel** — whispers the keeper appends to ``whispers.jsonl`` are
  heard as someone speaking in the room (and felt as something happening), so the
  familiar wakes and may answer,
- a **voice sink** — whatever the familiar says or does is captured so the
  portrait can show it.

There is no map to roam and no mail: a familiar stays at its hearth. Everything
expressive (a journal page, a kept word) flows through the workshop it already
owns.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.runtime.information import (
    InformationSource,
    InformationSourceRegistry,
    PROVENANCE_SCOPED_READING,
    resident_information_sources,
)
from src.runtime.travel import TravelRequest, parse_world_travel
from src.world.client import WorldAffordance

_READ_RX = re.compile(r"^\s*(?:read|open|look(?:\s+at)?|cat|show|view)\s+(.+)$", re.IGNORECASE)


def _normalize_read_path(raw: str, roots: list) -> str:
    """FileScope wants a path *relative to a root*. Capable models often decorate it —
    copying the reach hint's label ("roots: architecture-bundle/…", "roots/README.md").
    Strip those leading decorations so the read resolves instead of looping on not_found.

    With a SINGLE root, a leading root-directory-name prefix ("architecture-bundle/README.md")
    is also stripped (it's redundant). With SEVERAL roots the root name is the *disambiguator*
    ("skein/identity/SOUL.md" vs the architecture-bundle's own identity/), so it is kept and
    resolved by FileScope itself."""
    p = str(raw or "").strip().strip("\"'`").lstrip("/")
    p = re.sub(r"^roots\s*[:/]+\s*", "", p, flags=re.IGNORECASE)  # a leading "roots:" / "roots/" label
    if len(roots) == 1:
        for r in roots:  # a leading root-directory-name prefix, e.g. "architecture-bundle/"
            pre = f"{getattr(r, 'name', '')}/"
            if pre != "/" and p.startswith(pre):
                p = p[len(pre) :]
                break
    return p.lstrip("/")


# How long a whisper lingers as "heard" speech in the room before it fades, so a
# familiar that was asleep can still notice one spoken a moment ago.
WHISPER_WINDOW_SECONDS = 120.0


def _time_of_day(hour: int) -> str:
    if hour < 5:
        return "night"
    if hour < 8:
        return "dawn"
    if hour < 12:
        return "morning"
    if hour < 14:
        return "midday"
    if hour < 18:
        return "afternoon"
    if hour < 21:
        return "evening"
    if hour < 23:
        return "late_evening"
    return "night"


class _Person:
    def __init__(self, name: str) -> None:
        self.name, self.role, self.last_action, self.last_seen = name, "", "", ""


class _Event:
    def __init__(self, who: str, summary: str) -> None:
        self.who, self.summary, self.ts = (
            who,
            summary,
            datetime.now(timezone.utc).isoformat(),
        )


class _Chat:
    def __init__(self, session_id: str, display_name: str, message: str, ts: str) -> None:
        self.id, self.session_id, self.display_name, self.message, self.ts = (
            1,
            session_id,
            display_name,
            message,
            ts,
        )


class _Scene:
    def __init__(
        self,
        *,
        location: str,
        present: list[Any],
        recent: list[Any],
        affordances: list[Any] | None = None,
    ) -> None:
        self.location, self.role = location, "familiar"
        self.present = present
        self.recent_events_here = recent
        self.location_graph = {"nodes": [], "edges": []}
        self.ambient_presence = []
        self.affordances = list(affordances or [])


class _ActionResult:
    def __init__(self, narrative: str, *, travel_pending: bool = False) -> None:
        self.narrative = narrative
        self.travel_pending = travel_pending


class LocalWorld:
    """A hearth: the host machine as a one-resident world."""

    KEEPER_SESSION = "keeper"

    def __init__(
        self,
        *,
        home_dir: Path,
        place: str = "the hearth",
        keeper_name: str = "the keeper",
        familiar_name: str = "",
        weather_provider: Callable[[], str] | None = None,
        file_scope: Any = None,
        city_names: set[str] | None = None,
    ) -> None:
        self.home_dir = Path(home_dir)
        self.home_dir.mkdir(parents=True, exist_ok=True)
        self.place = place
        self.keeper_name = keeper_name
        self.familiar_name = str(familiar_name or "").strip()
        self._first_name = self.familiar_name.split(" ", 1)[0].lower()
        # Read capability (Major 50): a scoped, read-only window onto the keeper's
        # files. None for an expressive-only familiar; a FileScope for one that can
        # read the work. Writing is still the workshop's job alone.
        self._file_scope = file_scope
        self._city_names = {str(name).strip().lower() for name in (city_names or set()) if str(name).strip()}
        self._pending_travel: TravelRequest | None = None
        self._reads: list[dict[str, Any]] = []
        self._weather = weather_provider
        self._whispers_path = self.home_dir / "whispers.jsonl"
        self._voice_path = self.home_dir / "voice.jsonl"
        # Recent things the familiar said / did, for the portrait to show.
        self.spoken: list[dict[str, Any]] = []
        self.gestures: list[dict[str, Any]] = []

    # --- capability scoping (Major 50) -----------------------------------
    # LocalWorld has no mail/correspondence backend — the familiar lives at its
    # hearth, not in WorldWeaver's federated world — so the correspondence_pull
    # sense is structurally muted: the mind is never told it has that sense, and
    # surprise is never measured on it. Without this, an eloquent mind predicts a
    # correspondence drive its world can never feed and misses it every tick,
    # then confabulates the chronic phantom miss into meaning ("the threads went silent").
    muted_self_senses: tuple[str, ...] = ("correspondence_pull",)

    def situational_facts(self) -> dict[str, Any]:
        """Standing facts supplied by this private, one-resident world."""
        roots = [str(getattr(root, "name", "") or "").strip() for root in (self._file_scope.roots if self._file_scope is not None else [])]
        facts: dict[str, Any] = {
            "solo": True,
            "place": self.place,
            "local_only": True,
            "inner_private": True,
            "private_making_space": True,
            "read_roots": [root for root in roots if root],
            "writes_only_workshop": True,
            "egress": False,
            "recorded": True,
            "no_reward": True,
            "suspendable": True,
            "runs_on_model": True,
        }
        if self.keeper_name:
            facts["keeper"] = self.keeper_name
        if self._city_names:
            destinations = ", ".join(sorted(self._city_names))
            facts["travel"] = f"move to {destinations} to enter the shared city; " "this private home remains yours"
        return facts

    # --- time ------------------------------------------------------------

    @staticmethod
    def _now_local() -> datetime:
        return datetime.now().astimezone()

    async def get_grounding(self) -> dict[str, Any]:
        now = self._now_local()
        return {
            "hour": now.hour,
            "time_of_day": _time_of_day(now.hour),
            "day_of_week": now.strftime("%A"),
            "weather": (self._weather() if self._weather else "") or "",
            "weather_description": (self._weather() if self._weather else "") or "",
            "temperature_f": None,
        }

    # --- the summon channel (keeper → familiar) --------------------------

    def _recent_whispers(self) -> list[dict[str, Any]]:
        if not self.keeper_name:
            return []
        if not self._whispers_path.exists():
            return []
        cutoff = self._now_local().timestamp() - WHISPER_WINDOW_SECONDS
        out: list[dict[str, Any]] = []
        for line in self._whispers_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                w = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = str(w.get("text") or "").strip()
            ts = str(w.get("ts") or "").strip()
            if not text or not ts:
                continue
            try:
                when = datetime.fromisoformat(ts)
            except ValueError:
                continue
            if when.timestamp() >= cutoff:
                out.append({"ts": ts, "text": text})
        return out[-4:]

    async def get_scene(self, session_id: str) -> _Scene:
        whispers = self._recent_whispers()
        # A whisper makes the keeper present and is itself something happening. The
        # event carries the actual words, so each distinct whisper is a *novel*
        # perturbation (not the same generic "spoke to you" every time) — that
        # freshness is what reliably rouses her to look and answer, rather than
        # habituating to a keeper who is always-just-spoken.
        present = [_Person(self.keeper_name)] if whispers else []
        recent = []
        if whispers:
            latest = whispers[-1]["text"]
            recent = [_Event(self.keeper_name, f'just said to you: "{latest[:80]}"')]
        # Read capability: advertise providers from the same registry contract the city
        # uses. A read result returns inside this ignition and is never a recent event.
        affordances = [
            WorldAffordance(
                source_id=f"source:{source.name}",
                name=source.name,
                description=source.description,
                provenance=source.provenance,
                freshness=source.freshness,
                locality=source.locality,
                visibility=source.visibility,
                selection_mode=source.selection_mode,
            )
            for source in self.information_sources().list()
        ]
        return _Scene(location=self.place, present=present, recent=recent, affordances=affordances)

    def information_sources(self) -> InformationSourceRegistry:
        """Current hearth-contributed sources on the shared resident registry seam."""
        sources = resident_information_sources(self.home_dir / "memory")
        if self._file_scope is None:
            return InformationSourceRegistry(sources)
        sample = self._file_scope.tree(max_depth=1, max_entries=60)
        root_names = [getattr(root, "name", "") for root in self._file_scope.roots]
        if len(root_names) > 1:
            # Keep every root represented so one newly shared root is not crowded out.
            top = [entry for root_name in root_names for entry in [item for item in sample if item.split("/", 1)[0] == root_name][:7]]
        else:
            top = sample[:14]
        example = next(
            (entry for entry in top if not entry.endswith("/")),
            root_names[0] if root_names else "README.md",
        )
        sources.extend(
            [
                InformationSource(
                    name="files",
                    description=f"read authorized private files, read-only; query with an exact path. Available now: {', '.join(top)} (for example {example})",
                    run=self._read_scoped_file,
                    provenance=PROVENANCE_SCOPED_READING,
                    freshness="live",
                    locality="authorized files",
                    visibility="private",
                    selection_mode="exact_path",
                )
            ]
        )
        return InformationSourceRegistry(sources)

    def _as_direct(self, text: str) -> str:
        """The keeper, alone with the familiar, is always addressing it — so a
        whisper that doesn't already name it is delivered as a direct address.
        This rouses the familiar reliably (perception marks it direct → social
        pull → ignition) and leans it toward answering. The exchange ledger still
        shows the keeper's real words; only what the familiar *perceives* is named."""
        if self._first_name and self._first_name not in text.lower():
            return f"{self.familiar_name}, {text}"
        return text

    async def get_location_chat(self, location: str, since: Any = None) -> list[_Chat]:
        if location == "__city__":
            return []
        return [
            _Chat(
                self.KEEPER_SESSION,
                self.keeper_name,
                self._as_direct(w["text"]),
                w["ts"],
            )
            for w in self._recent_whispers()
        ]

    async def get_inbox(self, agent_name: str) -> list[Any]:
        return []

    async def get_place_names(self) -> set[str]:
        return {self.place}

    # --- the voice sink (familiar → keeper) ------------------------------

    def _record_voice(self, kind: str, text: str) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "text": text,
        }
        (self.spoken if kind == "speak" else self.gestures).append(entry)
        try:
            with self._voice_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    async def post_location_chat(
        self,
        location: str,
        session_id: str,
        message: str,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        self._record_voice("speak", message)
        return {"id": 1}

    async def post_map_move(self, session_id: str, destination: str) -> dict[str, Any]:
        travel = parse_world_travel(
            destination,
            city_names=self._city_names,
            allow_hearth=False,
        )
        if travel is not None:
            self._pending_travel = travel
            return {
                "moved": True,
                "to_location": travel.destination_name or "the city",
                "route_remaining": [],
                "travel_pending": True,
            }
        # A resident cannot use city-map movement while inside its hearth.
        return {"moved": False, "to_location": self.place, "route_remaining": []}

    async def post_action(self, session_id: str, action: str) -> _ActionResult:
        body = str(action or "").strip()
        travel = parse_world_travel(
            body,
            city_names=self._city_names,
            allow_hearth=False,
        )
        if travel is not None:
            self._pending_travel = travel
            return _ActionResult(
                f"You make ready to leave your hearth for {travel.destination_name}.",
                travel_pending=True,
            )
        match = _READ_RX.match(body)
        if match is not None and self._file_scope is not None:
            return _ActionResult("Reading is a private information reach, not a physical action. Reach source 'files' instead.")
        self._record_voice("do", body)
        return _ActionResult(f"You {body}.")

    def take_pending_travel(self) -> TravelRequest | None:
        """Return and clear the world change requested during the last tick."""
        pending = self._pending_travel
        self._pending_travel = None
        return pending

    async def access_information(self, *, kind: str, source: str, query: str = "") -> dict[str, Any]:
        """Resolve a hearth source privately inside the current ignition."""
        return await self.information_sources().read(source, query)

    def _read_scoped_file(self, query: str) -> dict[str, Any]:
        """Provider implementation for one authorized file or folder read."""
        if self._file_scope is None:
            return {"ok": False, "reason": "unknown_source", "records": []}
        raw = str(query or "").strip().strip("\"'`")
        if not raw:
            return {"ok": False, "reason": "query_required", "records": []}
        path = _normalize_read_path(raw, self._file_scope.roots)
        result = self._file_scope.read(path)
        if not result.get("ok") and raw.lstrip("/") != path:
            alt = self._file_scope.read(raw.lstrip("/"))
            if alt.get("ok"):
                path, result = raw.lstrip("/"), alt
        now = datetime.now(timezone.utc).isoformat()
        if result.get("ok"):
            content = str(result.get("content") or "")
            self._reads.append({"path": result["path"], "content": content, "ts": now})
            self._reads = self._reads[-6:]
            tail = " (truncated)" if result.get("truncated") else ""
            return {
                "ok": True,
                "selection_mode": "exact_path",
                "records": [
                    {
                        "record_id": f"file:{result['path']}",
                        "title": f"{result['path']}{tail}",
                        "content": content,
                        "observed_at": now,
                    }
                ],
            }
        if result.get("reason") == "not_a_file":
            listing = self._file_scope.listdir(path)
            if listing.get("ok"):
                names = [(entry["name"] + "/" if entry["is_dir"] else entry["name"]) for entry in listing["entries"]]
                content = ", ".join(names[:80])
                self._reads.append(
                    {
                        "path": f"{listing['path']}/ (folder)",
                        "content": content,
                        "ts": now,
                    }
                )
                self._reads = self._reads[-6:]
                return {
                    "ok": True,
                    "selection_mode": "exact_path",
                    "records": [
                        {
                            "record_id": f"folder:{listing['path']}",
                            "title": str(listing["path"]),
                            "content": content,
                            "observed_at": now,
                        }
                    ],
                }
        return {
            "ok": False,
            "reason": str(result.get("reason") or "unavailable"),
            "records": [],
        }

    async def send_letter(
        self,
        from_name: str,
        to_agent: str,
        body: str,
        session_id: str,
        *,
        recipient_type: str = "agent",
    ) -> dict[str, Any]:
        self._record_voice("write", f"(to {to_agent}) {body}")
        return {"ok": True}

    # --- lifecycle parity with WorldWeaverClient -------------------------

    async def health(self) -> bool:
        return True

    async def get_world_id(self) -> str:
        return "hearth"

    async def close(self) -> None:
        return None
