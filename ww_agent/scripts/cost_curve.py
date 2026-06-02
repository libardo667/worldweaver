#!/usr/bin/env python3
"""Measure the central claim: cost scales with surprise, not with ticks.

Runs one resident through two worlds of identical length — a CALM world (stable,
predictable) and a BUSY world (something new every tick) — and counts how often
the substrate actually ignites the LLM pulse. Because the pulse fires only on
prediction error, the LLM-call rate (and therefore the bill) tracks novelty, not
elapsed time.

With real inference creds (WW_INFERENCE_KEY) it also captures real token usage
per pulse and projects a cost per resident-hour at a given tick cadence — the
number worth quoting. Offline it still reports the ignition-rate curve, which is
the load-bearing, model-independent result.

Usage (from ww_agent/):
    set -a && . <(sed 's/\r$//' .env) && set +a
    ../worldweaver_engine/.venv/bin/python scripts/cost_curve.py --ticks 12
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.identity.loader import LoopTuning, ResidentIdentity  # noqa: E402
from src.inference.client import InferenceClient  # noqa: E402
from src.runtime.cognitive_core import CognitiveCore  # noqa: E402

T0 = datetime(2026, 6, 2, 9, 0, 0, tzinfo=timezone.utc)


class _Person:
    def __init__(self, name):
        self.name, self.role, self.last_action, self.last_seen = name, "", "", ""


class _Event:
    def __init__(self, who, summary):
        self.who, self.summary, self.ts = who, summary, ""


class _Chat:
    def __init__(self, sid, name, msg):
        self.id, self.session_id, self.display_name, self.message = 1, sid, name, msg
        self.ts = datetime.now(timezone.utc).isoformat()


class _Scene:
    def __init__(self, *, location, present, recent):
        self.location, self.role, self.present = location, "resident", present
        self.recent_events_here = recent
        self.location_graph = {"nodes": [], "edges": []}
        self.ambient_presence = []


class _World:
    """A world driven by a callable that produces the (scene, chat) for tick n."""

    def __init__(self, beat_fn):
        self._beat_fn = beat_fn
        self._tick = 0
        self._cur = beat_fn(0)

    async def get_scene(self, session_id):
        self._cur = self._beat_fn(self._tick)
        self._tick += 1
        return self._cur["scene"]

    async def get_location_chat(self, location, since=None):
        return list(self._cur["chat"]) if location != "__city__" else []

    async def get_inbox(self, agent_name):
        return []

    async def get_grounding(self):
        return {"time_of_day": "morning", "weather": "clear", "temperature_f": 58}

    async def get_place_names(self):
        return set()

    async def post_location_chat(self, location, session_id, message, display_name=None):
        return {"id": 1}

    async def post_map_move(self, session_id, destination):
        return {"moved": False}

    async def post_action(self, session_id, action):
        return type("TR", (), {"narrative": ""})()

    async def send_letter(self, **k):
        return {"ok": True}


def _calm_beat(n: int) -> dict:
    # The same quiet scene every tick: one familiar face, nothing new.
    return {"scene": _Scene(location="Tea Stall", present=[_Person("Levi")], recent=[]), "chat": []}


def _busy_beat(n: int) -> dict:
    # Something new every tick: a shifting crowd and a fresh remark.
    crowd = [_Person(name) for name in (["Levi", "Mei", "Bao", "Wen", "Hua"])[: 2 + (n % 4)]]
    speaker = ["Mei", "Bao", "Wen", "Hua", "Levi"][n % 5]
    return {
        "scene": _Scene(location="Tea Stall", present=crowd, recent=[_Event(speaker, f"did something new (#{n})")]),
        "chat": [_Chat(f"{speaker}-{n}", speaker, f"Sun Li! {speaker} here — did you hear about {['the parade','the fire','the festival','the protest','the market'][n % 5]}?")],
    }


class _StubLLM:
    async def complete_json(self, system_prompt, user_prompt, **kwargs):
        import re

        feats = {t: min(float(v), 1.0) for t, v in re.findall(r"^\s*(\w+): \w[\w ]*\(([0-9.]+)\)\s*$", user_prompt, re.MULTILINE)} or {"vigilance": 0.5}
        return {"felt_sense": "noted", "act": None, "expectations": [{"features": feats, "scope": "self", "confidence": 0.9, "half_life": 600}]}

    async def complete(self, *a, **k):
        return "{}"


def _identity() -> ResidentIdentity:
    return ResidentIdentity(name="sun_li", actor_id="cost", soul="You are Sun Li, a watchful tea-seller.", canonical_soul="You are Sun Li.", growth_soul="", vibe="watchful", core="", voice_seed=[], tuning=LoopTuning())


def _make_llm():
    key = os.environ.get("WW_INFERENCE_KEY", "").strip()
    if not key:
        return _StubLLM(), "stub (offline)"
    url = os.environ.get("WW_INFERENCE_URL", "https://openrouter.ai/api/v1")
    model = os.environ.get("WW_INFERENCE_MODEL", "google/gemini-3-flash-preview")
    timeout = float(os.environ.get("WW_INFERENCE_TIMEOUT", "60"))
    return InferenceClient(base_url=url, api_key=key, default_model=model, timeout=timeout), model


async def _run_scenario(name: str, beat_fn, llm, *, ticks: int, tick_seconds: float) -> dict:
    world = _World(beat_fn)
    ignitions = 0
    p0 = getattr(llm, "total_prompt_tokens", 0)
    c0 = getattr(llm, "total_completion_tokens", 0)
    with tempfile.TemporaryDirectory() as tmp:
        resident_dir = Path(tmp) / "sun_li"
        (resident_dir / "memory").mkdir(parents=True, exist_ok=True)
        core = CognitiveCore(identity=_identity(), resident_dir=resident_dir, ww_client=world, llm=llm, session_id="cost")
        for n in range(1, ticks + 1):
            now = (T0 + timedelta(seconds=n * tick_seconds)).isoformat()
            result = await core.tick_once(now=now)
            if result["ignited"]:
                ignitions += 1
    prompt_tokens = getattr(llm, "total_prompt_tokens", 0) - p0
    completion_tokens = getattr(llm, "total_completion_tokens", 0) - c0
    return {"name": name, "ticks": ticks, "ignitions": ignitions, "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}


def _project(scn: dict, *, tick_seconds: float, price_in: float, price_out: float) -> dict:
    ticks_per_hour = 3600.0 / tick_seconds
    calls_per_hour = (scn["ignitions"] / scn["ticks"]) * ticks_per_hour if scn["ticks"] else 0.0
    tokens = scn["prompt_tokens"] + scn["completion_tokens"]
    cost_per_call = ((scn["prompt_tokens"] * price_in) + (scn["completion_tokens"] * price_out)) / 1_000_000.0 / max(scn["ignitions"], 1) if scn["ignitions"] else 0.0
    cost_per_hour = cost_per_call * calls_per_hour
    return {"calls_per_hour": calls_per_hour, "tokens": tokens, "cost_per_call": cost_per_call, "cost_per_hour": cost_per_hour}


async def _main(args) -> None:
    llm, label = _make_llm()
    real = isinstance(llm, InferenceClient)
    print(f"\nCost curve — pulse source: {label}  ·  cadence: 1 tick / {args.tick_seconds:.0f}s  ·  {args.ticks} ticks/scenario")
    if real:
        print(f"price: ${args.price_in}/Mtok in, ${args.price_out}/Mtok out (illustrative — set to your model's rates)")

    calm = await _run_scenario("calm", _calm_beat, llm, ticks=args.ticks, tick_seconds=args.tick_seconds)
    busy = await _run_scenario("busy", _busy_beat, llm, ticks=args.ticks, tick_seconds=args.tick_seconds)

    print(f"\n{'scenario':<8} {'ticks':>6} {'ignitions':>10} {'LLM calls/tick':>15} {'calls/hour':>11}", end="")
    print(f" {'tokens':>8} {'$/resident-hour':>16}" if real else "")
    for scn in (calm, busy):
        pr = _project(scn, tick_seconds=args.tick_seconds, price_in=args.price_in, price_out=args.price_out)
        row = f"{scn['name']:<8} {scn['ticks']:>6} {scn['ignitions']:>10} {scn['ignitions']/scn['ticks']:>15.2f} {pr['calls_per_hour']:>11.1f}"
        if real:
            row += f" {pr['tokens']:>8} {('$%.4f' % pr['cost_per_hour']):>16}"
        print(row)

    ratio = busy["ignitions"] / max(calm["ignitions"], 1)
    print(f"\nbusy ignites ~{ratio:.0f}x as often as calm — the LLM bill tracks surprise, not ticks.")
    if real:
        cp = _project(calm, tick_seconds=args.tick_seconds, price_in=args.price_in, price_out=args.price_out)
        bp = _project(busy, tick_seconds=args.tick_seconds, price_in=args.price_in, price_out=args.price_out)
        print(f"projected: calm ≈ ${cp['cost_per_hour']:.4f}/resident-hour, busy ≈ ${bp['cost_per_hour']:.4f}/resident-hour.")
        await llm.close()


def main() -> None:
    p = argparse.ArgumentParser(description="Measure cost-scales-with-surprise.")
    p.add_argument("--ticks", type=int, default=12)
    p.add_argument("--tick-seconds", type=float, default=20.0)
    p.add_argument("--price-in", type=float, default=0.10, help="$ per million input tokens")
    p.add_argument("--price-out", type=float, default=0.40, help="$ per million output tokens")
    asyncio.run(_main(p.parse_args()))


if __name__ == "__main__":
    main()
