#!/usr/bin/env python3
"""Watch a resident think: the Major 49 substrate + pulse, live.

Boots one CognitiveCore against a small scripted world and prints, tick by tick,
what the resident perceives, how its arousal accumulates, and — on ignition — the
felt_sense, act, and afterimage the single LLM pulse produces. This is the
loop-closure (perturbation → surprise → ignition → pulse → act → afterimage →
quiet → surprise again) made watchable.

Usage (from the ww_agent/ directory):

    # Real model — set your inference creds first:
    WW_INFERENCE_KEY=sk-... WW_INFERENCE_MODEL=google/gemini-3-flash-preview \
        python scripts/pulse_demo.py

    # Offline — no creds needed, uses a deterministic stub pulse:
    python scripts/pulse_demo.py --ticks 12 --show-prompt

    # Drive a real resident's soul instead of the built-in demo identity:
    python scripts/pulse_demo.py --resident residents/sun_li

Nothing here touches a live world server; the world is a scripted stand-in so the
rhythm can be observed in isolation.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow `from src...` when run as `python scripts/pulse_demo.py` from ww_agent/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.identity.loader import IdentityLoader, LoopTuning, ResidentIdentity  # noqa: E402
from src.runtime.cognitive_core import CognitiveCore  # noqa: E402
from src.runtime.ledger import load_runtime_events  # noqa: E402
from src.runtime.salience import IGNITION_THRESHOLD  # noqa: E402


# --------------------------------------------------------------------------
# A scripted world: a sequence of small scenes that keep surprising the resident
# --------------------------------------------------------------------------


class _Person:
    def __init__(self, name: str) -> None:
        self.name, self.role, self.last_action, self.last_seen = name, "", "", ""


class _Event:
    def __init__(self, who: str, summary: str) -> None:
        self.who, self.summary, self.ts = who, summary, ""


class _Chat:
    def __init__(self, session_id: str, display_name: str, message: str) -> None:
        self.id, self.session_id, self.display_name, self.message = 1, session_id, display_name, message
        self.ts = datetime.now(timezone.utc).isoformat()


class _Letter:
    def __init__(self, filename: str, body: str) -> None:
        self.filename, self.body = filename, body


class _Scene:
    def __init__(self, *, location, present, recent, ambient=None) -> None:
        self.location, self.role = location, "resident"
        self.present = present
        self.recent_events_here = recent
        self.location_graph = {"nodes": [], "edges": []}
        self.ambient_presence = ambient or []


# Each beat is one "moment" the world is in. The resident re-perceives the
# current beat every tick; when the world moves to the next beat, new surprise
# appears on its own.
_BEATS = [
    {
        "scene": _Scene(location="Chinatown Tea Stall", present=[_Person("Levi")], recent=[_Event("Levi", "lingered by the stall")]),
        "local_chat": [],
        "inbox": [],
        "note": "a quiet morning, one familiar face",
    },
    {
        "scene": _Scene(location="Chinatown Tea Stall", present=[_Person("Levi"), _Person("Mei"), _Person("Bao")], recent=[_Event("Mei", "set down a heavy crate"), _Event("Bao", "knocked over a stool")]),
        "local_chat": [_Chat("levi-1", "Levi", "Sun Li, can you spare a pot of jasmine?")],
        "inbox": [],
        "note": "a crowd gathers and Levi asks you directly",
    },
    {
        "scene": _Scene(location="Chinatown Tea Stall", present=[_Person("Levi"), _Person("Mei"), _Person("Bao"), _Person("Wen"), _Person("Hua")], recent=[_Event("__ambient__", "a sudden downpour starts")], ambient=[type("A", (), {"kind": "bad_weather", "label": "cold rain", "source": "weather", "intensity": 0.8})()]),
        "local_chat": [_Chat("mei-1", "Mei", "Everyone's crowding in out of the rain!")],
        "inbox": [_Letter("from_an_old_friend_1.md", "Sun Li — I'm coming back to the city next week. Tea, like before? — Rowan")],
        "note": "rain drives a crowd in; an old friend writes",
    },
]


class _ScriptedWorld:
    def __init__(self) -> None:
        self._beat = 0
        self.sent_chats: list[dict] = []
        self.sent_actions: list[str] = []
        self.moves: list[str] = []
        self.letters: list[dict] = []
        self.place_names = {"Chinatown Tea Stall", "North Beach", "the Wharf"}

    @property
    def beat(self) -> dict:
        return _BEATS[min(self._beat, len(_BEATS) - 1)]

    def advance(self) -> None:
        self._beat = min(self._beat + 1, len(_BEATS) - 1)

    async def get_scene(self, session_id):
        return self.beat["scene"]

    async def get_location_chat(self, location, since=None):
        return list(self.beat["local_chat"]) if location != "__city__" else []

    async def get_inbox(self, agent_name):
        return list(self.beat["inbox"])

    async def get_place_names(self):
        return set(self.place_names)

    async def post_location_chat(self, location, session_id, message, display_name=None):
        self.sent_chats.append({"location": location, "message": message})
        return {"id": 1}

    async def post_map_move(self, session_id, destination):
        self.moves.append(destination)
        return {"moved": True, "to_location": destination, "route_remaining": []}

    async def post_action(self, session_id, action):
        self.sent_actions.append(action)
        return type("TR", (), {"narrative": f"You {action}."})()

    async def send_letter(self, from_name, to_agent, body, session_id, *, recipient_type="agent"):
        self.letters.append({"to": to_agent, "body": body})
        return {"ok": True}


# --------------------------------------------------------------------------
# A deterministic offline pulse (used when no inference creds are configured)
# --------------------------------------------------------------------------

_FELT_LINE = re.compile(r"^\s*(\w+): \w[\w ]*\(([0-9.]+)\)\s*$", re.MULTILINE)


class _StubPulseLLM:
    """Echoes the felt substrate back as the afterimage so the loop visibly
    closes. Not intelligent — a placeholder for the real model."""

    async def complete_json(self, system_prompt, user_prompt, **kwargs):
        feats = {tag: min(float(val), 1.0) for tag, val in _FELT_LINE.findall(user_prompt)}
        feats = feats or {"vigilance": 0.5}
        top = max(feats, key=feats.get)
        act = None
        if "to you" in user_prompt:
            act = {"kind": "speak", "body": "I hear you — one moment.", "target": None}
        elif top == "vigilance":
            act = {"kind": "speak", "body": "Quite a lot happening here.", "target": None}
        return {
            "felt_sense": f"[stub] {top} is what stands out right now",
            "act": act,
            "expectations": [{"features": feats, "scope": "self", "confidence": 0.9, "half_life": 600}],
        }

    async def complete(self, *a, **k):
        return "{}"


def _make_llm():
    key = os.environ.get("WW_INFERENCE_KEY", "").strip()
    if not key:
        return _StubPulseLLM(), "stub (offline — set WW_INFERENCE_KEY for the real model)"
    from src.inference.client import InferenceClient

    url = os.environ.get("WW_INFERENCE_URL", "https://openrouter.ai/api/v1")
    model = os.environ.get("WW_INFERENCE_MODEL", "google/gemini-3-flash-preview")
    return InferenceClient(base_url=url, api_key=key, default_model=model), f"real model: {model}"


def _demo_identity() -> ResidentIdentity:
    return ResidentIdentity(
        name="sun_li",
        actor_id="demo-actor",
        soul=("You are Sun Li, who keeps a small tea stall at the edge of Chinatown. " "You are watchful and dry-humored, slow to alarm but quick to notice. You take quiet pride in the stall and in the people who pass through it."),
        canonical_soul="You are Sun Li, a watchful tea-seller in Chinatown.",
        growth_soul="",
        vibe="watchful, dry",
        core="Keeps a small tea stall at the edge of Chinatown.",
        voice_seed=["Tea?", "Mm. Sit a moment."],
        tuning=LoopTuning(),
    )


# --------------------------------------------------------------------------
# Pretty-printing one tick
# --------------------------------------------------------------------------


def _last_pulse(memory_dir: Path) -> dict | None:
    """Read the most recently routed pulse back off the canonical ledger."""
    latest = None
    for event in load_runtime_events(memory_dir):
        if str(event.get("event_type") or "").strip() == "pulse_emitted":
            latest = event.get("payload") or {}
    return (latest or {}).get("pulse") if latest else None


def _render_act(act: dict | None) -> str:
    if not act:
        return "—"
    target = f" → {act.get('target')}" if act.get("target") else ""
    return f"{act.get('kind')}{target}: \"{act.get('body')}\""


def _render_expectations(pulse: dict) -> str:
    parts = []
    for exp in pulse.get("expectations") or []:
        feats = ", ".join(f"{t}={round(float(v), 2)}" for t, v in (exp.get("features") or {}).items())
        parts.append(f"{exp.get('scope')}{{{feats}}}")
    return "; ".join(parts) or "—"


def _print_tick(n: int, brief: dict, result: dict, pulse: dict | None) -> None:
    loc = brief.get("location") or "?"
    present = ", ".join(brief.get("present") or []) or "no one"
    heard = "; ".join(f"{h['speaker']}: \"{h['message']}\"" + (" (to you)" if h.get("is_direct") else "") for h in (brief.get("heard") or []))
    bar_n = min(int((result["arousal_level"] / max(IGNITION_THRESHOLD, 1e-6)) * 12), 12)
    bar = "█" * bar_n + "·" * (12 - bar_n)
    print(f"\n── tick {n:>2}  ·  {loc}  ·  present: {present}")
    if heard:
        print(f"     heard: {heard}")
    if brief.get("inbox_count"):
        print(f"     inbox: {brief['inbox_count']} letter(s) waiting")
    flag = "  ▲ IGNITION" if result["ignited"] else ""
    print(f"     arousal [{bar}] {result['arousal_level']:.2f}/{IGNITION_THRESHOLD:.1f}{flag}")
    if result["ignited"] and pulse is not None:
        gate = (result.get("pulse_routed") or {}).get("gate_decisions") or []
        print(f"     felt: {pulse.get('felt_sense', '')}")
        print(f"     act:  {_render_act(pulse.get('act'))}")
        print(f"     afterimage: {_render_expectations(pulse)}")
        if gate:
            print(f"     self_delta gate: {', '.join(g['kind'] + '=' + g['verdict'] for g in gate)}")
    elif result["ignited"]:
        print("     (ignited, but the pulse produced nothing — refracting)")


async def _run(args) -> None:
    identity = IdentityLoader.load(Path(args.resident)) if args.resident else _demo_identity()
    llm, label = _make_llm()
    world = _ScriptedWorld()

    with tempfile.TemporaryDirectory() as tmp:
        resident_dir = Path(tmp) / identity.name
        (resident_dir / "memory").mkdir(parents=True, exist_ok=True)
        core = CognitiveCore(identity=identity, resident_dir=resident_dir, ww_client=world, llm=llm, session_id=f"{identity.name}-demo")
        memory_dir = resident_dir / "memory"

        print(f"\nWatching {identity.display_name} think  ·  pulse source: {label}")
        print(f"ignition threshold: {IGNITION_THRESHOLD}  ·  world beats: {len(_BEATS)}")

        t0 = datetime(2026, 6, 2, 9, 0, 0, tzinfo=timezone.utc)
        beat_advanced = 0
        for n in range(1, args.ticks + 1):
            now = (t0 + timedelta(seconds=n * args.tick_seconds)).isoformat()
            result = await core.tick_once(now=now)
            brief = core._producer.latest_perception  # noqa: SLF001
            if args.show_prompt and result["ignited"]:
                print("\n----- assembled pulse prompt -----")
                print(core._producer.render_prompt_for_debug())  # noqa: SLF001
                print("----------------------------------")
            pulse = _last_pulse(memory_dir) if result["ignited"] else None
            _print_tick(n, brief, result, pulse)
            # Advance the world a beat shortly after each ignition (and once early)
            # so there is always fresh surprise to watch.
            if result["ignited"] or (n == 2 and beat_advanced == 0):
                world.advance()
                beat_advanced += 1

        print(f"\nworld acts emitted — chat: {len(world.sent_chats)}, actions: {len(world.sent_actions)}, moves: {len(world.moves)}, letters: {len(world.letters)}")
        if isinstance(llm, _StubPulseLLM) is False:
            await llm.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch a resident's substrate+pulse rhythm.")
    parser.add_argument("--ticks", type=int, default=10, help="how many cognitive ticks to run")
    parser.add_argument("--tick-seconds", type=float, default=20.0, help="virtual seconds between ticks (affects arousal decay)")
    parser.add_argument("--resident", type=str, default="", help="path to a resident dir to load a real soul (optional)")
    parser.add_argument("--show-prompt", action="store_true", help="print the assembled pulse prompt on each ignition")
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
