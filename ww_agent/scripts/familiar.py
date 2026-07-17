#!/usr/bin/env python3
"""Run one WorldWeaver resident through the shared host, starting at its hearth.

This is an operational compatibility command for the local portrait and offline
smoke mode. It does not compose a second kind of agent: ``src.resident.Resident``
owns the same identity, core, ledger, hearth, and city travel used by the normal
daemon. Optional keeper/file/weather grants come from ``hearth.json``.

Usage (from the repository root):

    # offline smoke test (deterministic stub mind, a few ticks):
    python dev.py run ww_agent/scripts/familiar.py --ticks 4 --pause 0.2

    # live, against a local Ollama, as a daemon:
    export WW_INFERENCE_URL=http://localhost:11434/v1 WW_INFERENCE_KEY=ollama \
           WW_INFERENCE_MODEL=qwen2.5:7b-instruct
    python dev.py run ww_agent/scripts/familiar.py --tick 30

Whisper to it from anywhere:
    echo '{"ts":"'$(date -Iseconds)'","text":"Cinder, are you there?"}' \
        >> ww_agent/familiar/cinder/whispers.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.familiar.config import HearthConfig  # noqa: E402
from src.runtime.circadian import chronotype, circadian_state  # noqa: E402
from src.runtime.ledger import load_runtime_events  # noqa: E402
from src.runtime.memory import memories as kept_memories  # noqa: E402
from src.runtime.workshop import Workshop  # noqa: E402
from src.resident import Resident  # noqa: E402
from src.world.client import WorldWeaverClient  # noqa: E402

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


def _legacy_runner_config(home_dir: Path) -> dict:
    """Old launcher-only model/chronotype knobs retained during config migration."""
    path = home_dir / "familiar.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _make_mind(model_override: str | None = None):
    key = os.environ.get("WW_INFERENCE_KEY", "").strip()
    model = (model_override or os.environ.get("WW_INFERENCE_MODEL", "qwen2.5:7b-instruct")).strip()
    if not key:
        return _StubMind(), f"stub (offline — set WW_INFERENCE_KEY for the real mind; wanted {model})"
    from src.inference.client import InferenceClient

    url = os.environ.get("WW_INFERENCE_URL", "http://localhost:11434/v1")
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


_FILESCOPE_CACHE: dict[str, tuple[float, dict]] = {}


def _filescope_summary(world: Any, home_dir: Path) -> dict | None:
    """What this familiar may read, for the portrait's FileScope viewer: each root
    and a shallow tree of its non-ignored entries (secrets & .gitignore already
    hidden by FileScope itself). Recomputed at most once a minute — the filesystem
    walk is bounded, but not worth doing every tick."""
    fs = getattr(world, "_file_scope", None)
    if fs is None or not getattr(fs, "roots", None):
        return None
    key = str(home_dir)
    nowt = datetime.now(timezone.utc).timestamp()
    cached = _FILESCOPE_CACHE.get(key)
    if cached and nowt - cached[0] < 60.0:
        return cached[1]
    roots = []
    for root in fs.roots:
        try:
            entries = fs.tree(str(root), max_depth=2, max_entries=80)
        except Exception:
            entries = []
        roots.append({"name": root.name, "path": str(root), "entries": entries})
    summary = {"roots": roots, "note": "read-only · secrets & .gitignore hidden"}
    _FILESCOPE_CACHE[key] = (nowt, summary)
    return summary


def _write_state(
    state_path: Path,
    *,
    home_dir: Path,
    identity: Any,
    world: Any,
    brief: dict,
    result: dict,
    tick: int,
) -> dict:
    g = brief.get("grounding") or {}
    wake = float(brief.get("wakefulness") if brief.get("wakefulness") is not None else 1.0)
    ct = chronotype(
        identity.name,
        explicit=_legacy_runner_config(home_dir).get("chronotype"),
    )
    rest = float((g.get("rest_pressure") if isinstance(g, dict) else None) or 0.0)
    pulse = _last_pulse(world.home_dir / "memory") or {}
    awake = wake >= 0.4
    spoken_lines = list(getattr(world, "spoken", []) or [])
    spoken = spoken_lines[-1]["text"] if spoken_lines else None
    shop = Workshop(home_dir / "workshop")
    state = {
        "name": identity.display_name,
        "place": str(getattr(world, "place", "") or brief.get("location") or ""),
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
        "journal_tail": _journal_tail(home_dir),
        "workshop": shop.summary(),
        "drawings": shop.drawings(limit=6),
        "memories": [{"note": m["note"], "ts": m.get("kept_ts")} for m in kept_memories(home_dir / "memory", limit=200)],
        "exchange": _recent_exchange(home_dir),
        "filescope": _filescope_summary(world, home_dir),
        "anchor_gating": bool(identity.tuning.anchor_gating),
    }
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


async def _run(args) -> None:
    home_dir = Path(args.home).resolve()
    if not home_dir.is_absolute():
        home_dir = Path(__file__).resolve().parent.parent / args.home
    if not (home_dir / "identity").exists():
        print(f"no resident at {home_dir} (need an identity directory)")
        return

    cfg = _legacy_runner_config(home_dir)
    hearth = HearthConfig.load(home_dir)
    hearth = replace(
        hearth,
        place=str(args.place).strip() if args.place else hearth.place,
        keeper=str(args.keeper).strip() if args.keeper is not None else hearth.keeper,
        weather=bool(args.weather) if args.weather is not None else hearth.weather,
    )
    mind, label = _make_mind((args.model or "").strip() or cfg.get("model"))
    world_client = WorldWeaverClient(base_url=os.environ.get("WW_SERVER_URL", "http://localhost:8000"))
    state_path = home_dir / "state.json"

    async def observe_tick(identity, world, core, result, tick) -> None:
        brief = core._producer.latest_perception  # noqa: SLF001 - portrait diagnostics
        state = _write_state(
            state_path,
            home_dir=home_dir,
            identity=identity,
            world=world,
            brief=brief,
            result=result,
            tick=tick,
        )
        mark = " ▲" if state["ignited"] else " ✦" if state.get("fervor") else " ❍" if state["settled"] else ""
        line = f"  {state['local_time']} {state['mood']:<10} arousal {state['arousal']:.2f}{mark}"
        if state["felt_sense"]:
            line += f"  — {state['felt_sense'][:70]}"
        print(line)
        if state.get("last_spoken"):
            print(f'             “{state["last_spoken"]}”')

    resident = Resident(
        home_dir,
        world_client,
        mind,
        hearth_config=hearth,
        tick_seconds=args.tick,
        tick_observer=observe_tick,
    )
    await resident.start("", default_attachment="hearth")
    identity = resident.identity
    if hearth.read_roots:
        print(f"· read scope: {', '.join(str(root) for root in hearth.read_roots)} " "(read-only; secrets & ignore rules hidden)")
    ct = chronotype(identity.name, explicit=cfg.get("chronotype"))
    kind = "lark" if ct < -0.5 else "owl" if ct > 0.5 else "even-keeled"
    print(f"· waking {identity.display_name} through the shared resident host " f"at {hearth.place}  ·  mind: {label}")
    print(f"· chronotype {ct:+.1f}h ({kind})  ·  it is {datetime.now().astimezone().strftime('%H:%M')} — wakefulness {circadian_state(datetime.now().hour, ct)['wakefulness']:.2f}")
    if hearth.keeper:
        print(f"· whisper to it:  echo '{{\"ts\":\"...\",\"text\":\"...\"}}' >> {home_dir / 'whispers.jsonl'}")

    if identity.tuning.anchor_gating:
        print("· anchor-gating ON (experimental): drive-resonant concrete anchors may drive arousal")

    stop = asyncio.Event()
    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
    except (NotImplementedError, RuntimeError):
        pass

    run_task = asyncio.create_task(
        resident.run(
            max_ticks=max(0, int(args.ticks)),
            pause_seconds=args.pause if args.ticks else None,
        ),
        name=f"resident:{resident.name}:single",
    )
    stop_task = asyncio.create_task(stop.wait(), name="resident:signal")
    try:
        done, _pending = await asyncio.wait(
            {run_task, stop_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if stop_task in done and not run_task.done():
            run_task.cancel()
        await run_task
    except asyncio.CancelledError:
        pass
    finally:
        stop_task.cancel()
        if not run_task.done():
            run_task.cancel()
        await asyncio.gather(run_task, stop_task, return_exceptions=True)
        if hasattr(mind, "close"):
            await mind.close()
        await world_client.close()
        print(f"· {identity.display_name} banks the embers. (state at {state_path})")


def main() -> None:
    p = argparse.ArgumentParser(description="Run one WorldWeaver resident through the shared host, starting at its hearth.")
    p.add_argument("--home", default="ww_agent/familiar/cinder", help="the resident home (identity, memory, workshop, optional hearth.json)")
    p.add_argument("--place", default=None, help="temporary override for hearth.json place")
    p.add_argument("--keeper", default=None, help="temporary override for hearth.json keeper; omitted means no invented keeper")
    weather = p.add_mutually_exclusive_group()
    weather.add_argument("--weather", dest="weather", action="store_true", help="temporarily enable local weather")
    weather.add_argument("--no-weather", dest="weather", action="store_false", help="temporarily disable local weather")
    p.set_defaults(weather=None)
    p.add_argument("--model", default="", help="override the model retained in legacy familiar.json")
    p.add_argument("--tick", type=float, default=30.0, help="seconds between ticks (daemon cadence)")
    p.add_argument("--ticks", type=int, default=0, help="stop after N ticks (0 = run forever); uses --pause between them")
    p.add_argument("--pause", type=float, default=0.5, help="seconds between ticks when --ticks is set")
    asyncio.run(_run(p.parse_args()))


if __name__ == "__main__":
    main()
