#!/usr/bin/env python3
"""Run a WorldWeaver resident as a local desktop familiar.

The same CognitiveCore that lives in the city — substrate, predictive pulse,
habituation, the slow self-model, circadian rhythm, the workshop — but grounded
in *this* machine's clock and kept company by one keeper. Each tick it writes a
small ``state.json`` (its felt sense, mood, what it's making, whether it's awake)
for a portrait UI to read, and it hears whatever the keeper appends to
``whispers.jsonl``.

Usage (from ww_agent/):

    # offline smoke test (deterministic stub mind, a few ticks):
    ../worldweaver_engine/.venv/bin/python scripts/familiar.py --ticks 4 --pause 0.2

    # live, against a local Ollama, as a daemon:
    export WW_INFERENCE_URL=http://localhost:11434/v1 WW_INFERENCE_KEY=ollama \
           WW_INFERENCE_MODEL=qwen2.5:7b-instruct
    ../worldweaver_engine/.venv/bin/python scripts/familiar.py --tick 30

Whisper to it from anywhere:
    echo '{"ts":"'$(date -Iseconds)'","text":"Cinder, are you there?"}' \
        >> familiar/cinder/whispers.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.familiar.local_world import LocalWorld  # noqa: E402
from src.familiar.weather import WeatherProvider  # noqa: E402
from src.identity.loader import IdentityLoader  # noqa: E402
from src.runtime.circadian import chronotype, circadian_state  # noqa: E402
from src.runtime.cognitive_core import CognitiveCore  # noqa: E402
from src.runtime.ledger import load_runtime_events  # noqa: E402
from src.runtime.workshop import Workshop  # noqa: E402


# --------------------------------------------------------------------------
# A deterministic offline mind, so the familiar runs with no creds at all.
# --------------------------------------------------------------------------
import re  # noqa: E402

_FELT_LINE = re.compile(r"^\s*(\w+): \w[\w ]*\(([0-9.]+)\)\s*$", re.MULTILINE)


class _StubMind:
    """Not intelligent — echoes the felt substrate so the rhythm visibly runs,
    answers a whisper, and potters a journal line when settling."""

    async def complete_json(self, system_prompt, user_prompt, **kwargs):
        feats = {tag: min(float(val), 1.0) for tag, val in _FELT_LINE.findall(user_prompt)} or {"rest_drive": 0.4}
        top = max(feats, key=feats.get)
        act = None
        if "(to you)" in user_prompt or "spoke to you" in user_prompt:
            act = {"kind": "speak", "body": "Mm. I'm here — by the warm part of the machine.", "target": None}
        elif "this still moment is yours" in user_prompt:
            act = {"kind": "write", "body": "Quiet hour. The light's gone the colour of dishwater. Banked the embers; noted the hush.", "target": "journal"}
        return {"felt_sense": f"[stub] {top} sits closest to the surface", "act": act, "expectations": [{"features": feats, "scope": "self", "confidence": 0.9, "half_life": 600}]}

    async def complete(self, *a, **k):
        return "{}"

    async def close(self):
        return None


def _make_mind():
    key = os.environ.get("WW_INFERENCE_KEY", "").strip()
    if not key:
        return _StubMind(), "stub (offline — set WW_INFERENCE_KEY / point WW_INFERENCE_URL at Ollama for the real mind)"
    from src.inference.client import InferenceClient

    url = os.environ.get("WW_INFERENCE_URL", "http://localhost:11434/v1")
    model = os.environ.get("WW_INFERENCE_MODEL", "qwen2.5:7b-instruct")
    timeout = float(os.environ.get("WW_INFERENCE_TIMEOUT", "200"))
    return InferenceClient(base_url=url, api_key=key, default_model=model, timeout=timeout), f"{model} @ {url}"


# --------------------------------------------------------------------------


def _last_pulse(memory_dir: Path) -> dict | None:
    latest = None
    for event in load_runtime_events(memory_dir):
        if str(event.get("event_type") or "").strip() == "pulse_emitted":
            latest = (event.get("payload") or {}).get("pulse")
    return latest


def _journal_tail(home_dir: Path) -> str:
    candidates = list((home_dir / "workshop").glob("*.md"))
    if not candidates:
        return ""
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    try:
        body = newest.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    section = body.split("## ")[-1].strip()
    # drop the timestamp heading line if present
    lines = [ln for ln in section.splitlines() if ln.strip()]
    if lines and lines[0].count(":") >= 2 and lines[0].replace(":", "").replace("-", "").replace("T", "").replace("+", "").replace(".", "").strip().isdigit():
        lines = lines[1:]
    return " ".join(lines).strip()[:1200]


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _recent_exchange(home_dir: Path, n: int = 16) -> list[dict]:
    """The persistent back-and-forth: the keeper's whispers and her spoken replies,
    merged in time order, so the portrait can show a quiet ledger of the exchange."""
    turns: list[dict] = []
    for w in _read_jsonl(home_dir / "whispers.jsonl"):
        if w.get("text"):
            turns.append({"who": "you", "text": str(w["text"]).strip(), "ts": str(w.get("ts") or "")})
    for v in _read_jsonl(home_dir / "voice.jsonl"):
        if v.get("kind") == "speak" and v.get("text"):
            turns.append({"who": "her", "text": str(v["text"]).strip(), "ts": str(v.get("ts") or "")})

    def _key(t):
        try:
            return datetime.fromisoformat(t["ts"]).timestamp()
        except (ValueError, TypeError):
            return 0.0

    turns.sort(key=_key)
    return turns[-n:]


def _mood(*, awake: bool, ignited: bool, settled: bool, fervor: bool, arousal: float, rest: float) -> str:
    if fervor:
        return "in a fervor"
    if settled:
        return "at rest" if rest > 0.5 else "pottering"
    if ignited:
        return "stirred"
    if not awake:
        return "drowsing"
    if arousal >= 0.6:
        return "watchful"
    if arousal >= 0.25:
        return "attentive"
    return "quiet"


def _write_state(state_path: Path, *, identity, world: LocalWorld, brief: dict, result: dict, tick: int) -> dict:
    g = brief.get("grounding") or {}
    wake = float(brief.get("wakefulness") if brief.get("wakefulness") is not None else 1.0)
    ct = chronotype(identity.name)
    rest = float((g.get("rest_pressure") if isinstance(g, dict) else None) or 0.0)
    pulse = _last_pulse(world.home_dir / "memory") or {}
    awake = wake >= 0.4
    spoken = world.spoken[-1]["text"] if world.spoken else None
    state = {
        "name": identity.display_name,
        "place": world.place,
        "tick": tick,
        "ts": datetime.now(timezone.utc).isoformat(),
        "local_time": datetime.now().astimezone().strftime("%H:%M"),
        "time_of_day": g.get("time_of_day"),
        "day_of_week": g.get("day_of_week"),
        "weather": g.get("weather") or "",
        "chronotype": round(ct, 2),
        "chronotype_kind": "lark" if ct < -0.5 else "owl" if ct > 0.5 else "even",
        "wakefulness": round(wake, 3),
        "awake": awake,
        "arousal": round(float(result.get("arousal_level") or 0.0), 3),
        "ignited": bool(result.get("ignited")),
        "settled": bool(result.get("settled")),
        "fervor": bool(result.get("fervor")),
        "mood": _mood(awake=awake, ignited=bool(result.get("ignited")), settled=bool(result.get("settled")), fervor=bool(result.get("fervor")), arousal=float(result.get("arousal_level") or 0.0), rest=rest),
        "felt_sense": pulse.get("felt_sense") or "",
        "act": pulse.get("act"),
        "last_spoken": spoken,
        "journal_tail": _journal_tail(world.home_dir),
        "workshop": Workshop(world.home_dir / "workshop").summary(),
        "exchange": _recent_exchange(world.home_dir),
    }
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


async def _run(args) -> None:
    home_dir = Path(args.home).resolve()
    if not home_dir.is_absolute():
        home_dir = Path(__file__).resolve().parent.parent / args.home
    if not (home_dir / "identity").exists():
        print(f"no familiar at {home_dir} (need identity/SOUL.canonical.md)")
        return

    identity = IdentityLoader.load(home_dir)
    weather = None if args.no_weather else WeatherProvider()
    world = LocalWorld(home_dir=home_dir, place=args.place, keeper_name=args.keeper, familiar_name=identity.display_name, weather_provider=weather)
    mind, label = _make_mind()
    ct = chronotype(identity.name)
    kind = "lark" if ct < -0.5 else "owl" if ct > 0.5 else "even-keeled"
    print(f"· waking {identity.display_name} at {world.place}  ·  mind: {label}")
    print(f"· chronotype {ct:+.1f}h ({kind})  ·  it is {datetime.now().astimezone().strftime('%H:%M')} — wakefulness {circadian_state(datetime.now().hour, ct)['wakefulness']:.2f}")
    print(f"· whisper to it:  echo '{{\"ts\":\"...\",\"text\":\"...\"}}' >> {home_dir / 'whispers.jsonl'}")

    core = CognitiveCore(
        identity=identity,
        resident_dir=home_dir,
        ww_client=world,
        llm=mind,
        session_id=f"{identity.name}-hearth",
        tick_seconds=args.tick,
        writes_to_workshop_only=True,  # a solo familiar has no mail; all writes are its own work
    )
    state_path = home_dir / "state.json"

    stop = asyncio.Event()
    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
    except (NotImplementedError, RuntimeError):
        pass

    def _latest_whisper_ts() -> str:
        whispers = _read_jsonl(home_dir / "whispers.jsonl")
        return str(whispers[-1].get("ts") or "") if whispers else ""

    # Don't answer whispers from before she woke; only new ones since boot.
    last_whisper_ts = _latest_whisper_ts()

    tick = 0
    try:
        while not stop.is_set():
            tick += 1
            cur_whisper_ts = _latest_whisper_ts()
            addressed = bool(cur_whisper_ts) and cur_whisper_ts != last_whisper_ts
            last_whisper_ts = cur_whisper_ts
            result = await core.tick_once(force_ignite=addressed)
            brief = core._producer.latest_perception  # noqa: SLF001
            state = _write_state(state_path, identity=identity, world=world, brief=brief, result=result, tick=tick)
            mark = " ▲" if state["ignited"] else " ✦" if state.get("fervor") else " ❍" if state["settled"] else ""
            line = f"  {state['local_time']} {state['mood']:<10} arousal {state['arousal']:.2f}{mark}"
            if state["felt_sense"]:
                line += f"  — {state['felt_sense'][:70]}"
            print(line)
            if state.get("last_spoken"):
                print(f'             “{state["last_spoken"]}”')
            if args.ticks and tick >= args.ticks:
                break
            try:
                await asyncio.wait_for(stop.wait(), timeout=args.tick if not args.ticks else args.pause)
            except asyncio.TimeoutError:
                pass
    finally:
        if hasattr(mind, "close"):
            await mind.close()
        await world.close()
        print(f"· {identity.display_name} banks the embers. (state at {state_path})")


def main() -> None:
    p = argparse.ArgumentParser(description="Run a WorldWeaver resident as a local desktop familiar.")
    p.add_argument("--home", default="familiar/cinder", help="the familiar's home dir (holds identity/, memory/, workshop/)")
    p.add_argument("--place", default="the hearth")
    p.add_argument("--keeper", default="the keeper")
    p.add_argument("--no-weather", action="store_true", help="don't fetch real local weather (blank sky)")
    p.add_argument("--tick", type=float, default=30.0, help="seconds between ticks (daemon cadence)")
    p.add_argument("--ticks", type=int, default=0, help="stop after N ticks (0 = run forever); uses --pause between them")
    p.add_argument("--pause", type=float, default=0.5, help="seconds between ticks when --ticks is set")
    asyncio.run(_run(p.parse_args()))


if __name__ == "__main__":
    main()
