#!/usr/bin/env python3
"""Boot ONE real resident against a running backend and watch it think.

Unlike pulse_demo (scripted stub world), this drives the real WorldWeaverClient
against a live backend: real scene, real grounding (SF time + weather), real
session, real LLM pulse. Optionally injects a passerby's chat so you can watch
the resident perceive it and respond in the actual world.

Usage (from the repository root, with the backend running and creds in ww_agent/.env):

    set -a && . <(sed 's/\r$//' ww_agent/.env) && set +a
    python dev.py run ww_agent/scripts/live_boot.py \
        --resident sun_li --ticks 6 --inject "Excuse me — is the tea stall open?"

It makes real outbound calls (backend + LLM). Keep --ticks small.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.inference.client import InferenceClient  # noqa: E402
from src.runtime.cognitive_core import CognitiveCore  # noqa: E402
from src.runtime.ledger import load_runtime_events  # noqa: E402
from src.runtime.salience import IGNITION_THRESHOLD  # noqa: E402
from src.resident import Resident  # noqa: E402
from src.world.client import WorldWeaverClient  # noqa: E402


def _last_pulse(memory_dir: Path) -> dict | None:
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


async def _run(args) -> None:
    server_url = os.environ.get("WW_SERVER_URL", "http://localhost:8000")
    llm_url = os.environ.get("WW_INFERENCE_URL", "https://openrouter.ai/api/v1")
    llm_key = os.environ.get("WW_INFERENCE_KEY", "").strip()
    llm_model = os.environ.get("WW_INFERENCE_MODEL", "google/gemini-3-flash-preview")
    residents_root = Path(os.environ.get("WW_RESIDENTS_DIR", "residents"))
    if not residents_root.is_absolute():
        residents_root = Path(__file__).resolve().parent.parent / residents_root
    resident_dir = residents_root / args.resident

    if not llm_key:
        print("WW_INFERENCE_KEY is empty — set it (source .env) so the pulse can fire.")
        return
    if not resident_dir.exists():
        print(f"resident dir not found: {resident_dir}")
        return

    llm_timeout = float(os.environ.get("WW_INFERENCE_TIMEOUT", "60"))
    ww = WorldWeaverClient(base_url=server_url)
    llm = InferenceClient(base_url=llm_url, api_key=llm_key, default_model=llm_model, timeout=llm_timeout)

    try:
        if not await ww.health():
            print(f"backend not healthy at {server_url}")
            return
        world_id = await ww.get_world_id() or ""
        print(f"backend: {server_url}  ·  world: {world_id or '(none)'}  ·  model: {llm_model}")

        resident = Resident(resident_dir, ww, llm)
        await resident.start(world_id)
        identity = resident._identity  # noqa: SLF001
        session_id = resident._session_id  # noqa: SLF001
        memory_dir = resident_dir / "memory"
        print(f"booted {identity.display_name}  ·  session {session_id}")

        core = CognitiveCore(identity=identity, resident_dir=resident_dir, ww_client=ww, llm=llm, session_id=session_id)

        location = ""
        for n in range(1, args.ticks + 1):
            # Inject a passerby's chat at the chosen tick so there is something to
            # perceive and (maybe) respond to.
            if args.inject and n == args.inject_at and location:
                await ww.post_location_chat(location=location, session_id="passerby-live-demo", message=args.inject, display_name=args.inject_from)
                print(f'\n   « injected at {location}: {args.inject_from}: "{args.inject}" »')

            result = await core.tick_once()
            brief = core._producer.latest_perception  # noqa: SLF001
            location = str(brief.get("location") or location)
            g = brief.get("grounding") or {}
            when = " · ".join(p for p in (g.get("time_of_day"), g.get("weather")) if p)
            present = ", ".join(brief.get("present") or []) or "no one"
            heard = "; ".join(f"{h['speaker']}: \"{h['message']}\"" + (" (to you)" if h.get("is_direct") else "") for h in (brief.get("heard") or []))
            bar_n = min(int((result["arousal_level"] / max(IGNITION_THRESHOLD, 1e-6)) * 12), 12)
            bar = "█" * bar_n + "·" * (12 - bar_n)
            print(f"\n── tick {n:>2}  ·  {location or '?'}  ·  present: {present}" + (f"  ·  {when}" if when else ""))
            if heard:
                print(f"     heard: {heard}")
            if brief.get("inbox_count"):
                print(f"     inbox: {brief['inbox_count']} letter(s)")
            flag = "  ▲ IGNITION" if result["ignited"] else ""
            print(f"     arousal [{bar}] {result['arousal_level']:.2f}/{IGNITION_THRESHOLD:.1f}{flag}")
            if result.get("pulse_routed"):
                pulse = _last_pulse(memory_dir) or {}
                print(f"     felt: {pulse.get('felt_sense', '')}")
                print(f"     act:  {_render_act(pulse.get('act'))}")
                print(f"     afterimage: {_render_expectations(pulse)}")
                if result.get("act_executed"):
                    print(f"     → world: {result['act_executed']}")
            await asyncio.sleep(args.pause)
    finally:
        await llm.close()
        await ww.close()


def main() -> None:
    p = argparse.ArgumentParser(description="Boot one real resident against a live backend.")
    p.add_argument("--resident", default="sun_li")
    p.add_argument("--ticks", type=int, default=6)
    p.add_argument("--pause", type=float, default=1.0, help="seconds between ticks")
    p.add_argument("--inject", default="", help="a passerby chat line to inject")
    p.add_argument("--inject-at", type=int, default=2, help="tick to inject at")
    p.add_argument("--inject-from", default="A passerby", help="display name of the injected speaker")
    asyncio.run(_run(p.parse_args()))


if __name__ == "__main__":
    main()
