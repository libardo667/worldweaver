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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

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
        self.who, self.summary, self.ts = who, summary, datetime.now(timezone.utc).isoformat()


class _Chat:
    def __init__(self, session_id: str, display_name: str, message: str, ts: str) -> None:
        self.id, self.session_id, self.display_name, self.message, self.ts = 1, session_id, display_name, message, ts


class _Scene:
    def __init__(self, *, location: str, present: list[Any], recent: list[Any]) -> None:
        self.location, self.role = location, "familiar"
        self.present = present
        self.recent_events_here = recent
        self.location_graph = {"nodes": [], "edges": []}
        self.ambient_presence = []


class _ActionResult:
    def __init__(self, narrative: str) -> None:
        self.narrative = narrative


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
    ) -> None:
        self.home_dir = Path(home_dir)
        self.home_dir.mkdir(parents=True, exist_ok=True)
        self.place = place
        self.keeper_name = keeper_name
        self.familiar_name = str(familiar_name or "").strip()
        self._first_name = self.familiar_name.split(" ", 1)[0].lower()
        self._weather = weather_provider
        self._whispers_path = self.home_dir / "whispers.jsonl"
        self._voice_path = self.home_dir / "voice.jsonl"
        # Recent things the familiar said / did, for the portrait to show.
        self.spoken: list[dict[str, Any]] = []
        self.gestures: list[dict[str, Any]] = []

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
        return _Scene(location=self.place, present=present, recent=recent)

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
        return [_Chat(self.KEEPER_SESSION, self.keeper_name, self._as_direct(w["text"]), w["ts"]) for w in self._recent_whispers()]

    async def get_inbox(self, agent_name: str) -> list[Any]:
        return []

    async def get_place_names(self) -> set[str]:
        return {self.place}

    # --- the voice sink (familiar → keeper) ------------------------------

    def _record_voice(self, kind: str, text: str) -> None:
        entry = {"ts": datetime.now(timezone.utc).isoformat(), "kind": kind, "text": text}
        (self.spoken if kind == "speak" else self.gestures).append(entry)
        try:
            with self._voice_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    async def post_location_chat(self, location: str, session_id: str, message: str, display_name: str | None = None) -> dict[str, Any]:
        self._record_voice("speak", message)
        return {"id": 1}

    async def post_map_move(self, session_id: str, destination: str) -> dict[str, Any]:
        # A familiar keeps to its hearth; movement is a gentle no-op.
        return {"moved": False, "to_location": self.place, "route_remaining": []}

    async def post_action(self, session_id: str, action: str) -> _ActionResult:
        self._record_voice("do", action)
        return _ActionResult(f"You {action}.")

    async def send_letter(self, from_name: str, to_agent: str, body: str, session_id: str, *, recipient_type: str = "agent") -> dict[str, Any]:
        self._record_voice("write", f"(to {to_agent}) {body}")
        return {"ok": True}

    # --- lifecycle parity with WorldWeaverClient -------------------------

    async def health(self) -> bool:
        return True

    async def get_world_id(self) -> str:
        return "hearth"

    async def close(self) -> None:
        return None
