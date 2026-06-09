#!/usr/bin/env python3
"""Substrate-parity trace — the REAL faithfulness gate (Mr. Review §1).

0/0 read-drainage proves the replay's READ PATTERN matches; it does NOT prove that
``perceive()`` parsed the same perception or that ``_recall()`` returned the same set.
This proves the latter directly, and deterministically.

Method — isolate the substrate computation from BOTH pen stochasticity and wall-clock:
  * **null-act fixed pen** — a stub that returns `{felt_sense, act:null, keep:[]}` (no LLM, no
    network). No acts + no keeps ⇒ the kept-memory store stays constant across ticks, so
    ``recalled`` is a pure function of the (served) perception.
  * **force_ignite every tick** — guarantees the perceive→recall path runs each tick, cleanly
    aligned tick-for-tick.
  * **synthetic clock** — a deterministic `now` per tick, so the time-decayed integrals
    (arousal/surprise) are reproducible rather than wall-clock-driven.

Then replay the SAME recording TWICE on byte-identical pristine copies and assert the per-tick
**(heard, recalled)** sequences are identical. `heard` (served) and `recalled` (relevance over a
constant memory store) carry no timestamps and no time-decay, so any divergence is harness
infidelity in perception/retrieval — exactly the gap §1 names. Arousal/surprise are logged for
visibility (they ARE time-sensitive) but are not gated on byte-identity.

Usage (from ww_agent root; needs the embedder for recall, NOT a pen):
    WW_EMBEDDING_URL=http://172.20.240.1:11434/v1 WW_EMBEDDING_MODEL=nomic-embed-text \\
    python3 scripts/pen_swap/parity_trace.py \\
        --keep-dir ../shards/ww_pdx_keep/residents \\
        --pristine-dir /tmp/arm_pristine --rounds 30 --out /tmp/parity_trace.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_AGENT_ROOT))
sys.path.insert(0, str(_AGENT_ROOT / "scripts"))

from src.resident import Resident  # noqa: E402
from src.runtime.cognitive_core import CognitiveCore  # noqa: E402
from src.runtime.ledger import load_runtime_events  # noqa: E402
from src.runtime.salience import derive_arousal  # noqa: E402
from src.world.city_tools import build_city_tool_scope  # noqa: E402
from src.world.city_world import CityWorld  # noqa: E402

from pen_swap.replay_client import ReplayClient  # noqa: E402

_BASE = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)


class _NullPen:
    """Deterministic stub: every pulse is a no-op (no act, no keep), no network."""

    async def complete_json(self, system_prompt: str, user_prompt: str, *, model: Any = None, temperature: float = 0.0, max_tokens: Any = None, response_format: Any = None, images: Any = None) -> dict[str, Any]:
        return {"felt_sense": "[parity-trace fixed null pen]", "act": None, "keep": []}

    async def close(self) -> None:
        return None


def _heard_key(brief: dict[str, Any]) -> list[list[str]]:
    return sorted([str(h.get("speaker") or ""), str(h.get("message") or "")] for h in (brief.get("heard") or []))


def _last_surprise(events: list[dict[str, Any]]) -> float:
    for e in reversed(events):
        if str(e.get("event_type") or "") == "surprise_observed":
            p = e.get("payload") if isinstance(e.get("payload"), dict) else {}
            try:
                return round(float(p.get("magnitude") or 0.0), 6)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


async def _trace_resident(arm_resident: Path, keep_resident: Path, recording_name: str, rounds: int) -> list[dict[str, Any]]:
    recording = keep_resident / "memory" / recording_name
    if not recording.exists():
        return []
    # Seed stdlib RNG per resident so the content-blind overheard slice (and any other
    # random.* in the pulse path) draws identically across the two runs — isolating
    # harness faithfulness from legitimate-but-unseeded perception randomness.
    random.seed(20260609)
    rc = ReplayClient.from_recording(recording)
    resident = Resident(arm_resident, rc, _NullPen())  # type: ignore[arg-type]
    await resident.start("")
    identity = resident._identity
    memory_dir = arm_resident / "memory"
    city_world = CityWorld(rc, build_city_tool_scope(identity, client=rc, session_id=resident._session_id, memory_dir=memory_dir))
    core = CognitiveCore(
        identity=identity,
        resident_dir=arm_resident,
        ww_client=city_world,
        llm=_NullPen(),  # type: ignore[arg-type]
        session_id=resident._session_id,
        pulse_model=None,
        pulse_temperature=0.0,
    )

    captured: list[list[str]] = []
    orig_recall = core._producer._recall

    async def _wrapped_recall() -> list[str]:
        r = await orig_recall()
        captured.append(sorted(r))
        return r

    core._producer._recall = _wrapped_recall  # type: ignore[method-assign]

    rows: list[dict[str, Any]] = []
    for t in range(rounds):
        rc.set_tick(t)
        before = len(captured)
        await core.tick_once(now=_BASE + timedelta(seconds=t * 20), force_ignite=True)
        events = load_runtime_events(memory_dir)
        brief = getattr(core._producer, "latest_perception", {}) or {}
        recalled = captured[-1] if len(captured) > before else []
        rows.append(
            {
                "tick": t,
                "heard": _heard_key(brief),
                "recalled": recalled,
                "n_recalled": len(recalled),
                "surprise": _last_surprise(events),
                "arousal": round(float(derive_arousal(events, now=_BASE + timedelta(seconds=t * 20)).get("level") or 0.0), 6),
            }
        )
    await rc.close()
    return rows


async def _run_once(label: str, pristine_dir: Path, keep_dir: Path, recording_name: str, rounds: int, limit: int) -> dict[str, list[dict[str, Any]]]:
    """Copy pristine -> a fresh temp cohort, trace every resident, return name -> rows."""
    tmp = Path(tempfile.mkdtemp(prefix=f"parity_{label}_"))
    run_dir = tmp / "residents"
    shutil.copytree(pristine_dir, run_dir)
    residents = sorted(p for p in run_dir.iterdir() if p.is_dir() and (p / "identity" / "SOUL.md").exists())
    if limit:
        residents = residents[:limit]
    out: dict[str, list[dict[str, Any]]] = {}
    for r in residents:
        kr = keep_dir / r.name
        if kr.exists():
            out[r.name] = await _trace_resident(r, kr, recording_name, rounds)
    shutil.rmtree(tmp, ignore_errors=True)
    return out


def _signal(rows: list[dict[str, Any]]) -> list[tuple]:
    """The deterministic, gated signal: (heard, recalled) per tick. No timestamps, no decay."""
    return [(json.dumps(r["heard"], sort_keys=True), json.dumps(r["recalled"], sort_keys=True)) for r in rows]


async def main() -> int:
    ap = argparse.ArgumentParser(description="Substrate-parity trace: prove perception+recall are reproduced deterministically on replay.")
    ap.add_argument("--keep-dir", required=True, type=Path, help="KEEP cohort with recordings")
    ap.add_argument("--pristine-dir", required=True, type=Path, help="fresh pristine cohort to copy (run rehydrate.py first)")
    ap.add_argument("--rounds", type=int, required=True, help="ticks to trace (== KEEP rounds)")
    ap.add_argument("--recording-name", default="keep_recording.jsonl")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", type=Path, default=Path("/tmp/parity_trace.jsonl"))
    args = ap.parse_args()

    if not os.environ.get("WW_EMBEDDING_URL"):
        print("ERROR: WW_EMBEDDING_URL required (recall needs the embedder)", file=sys.stderr)
        return 2

    print("=== run A ===")
    run_a = await _run_once("A", args.pristine_dir, args.keep_dir, args.recording_name, args.rounds, args.limit)
    print("=== run B (identical inputs) ===")
    run_b = await _run_once("B", args.pristine_dir, args.keep_dir, args.recording_name, args.rounds, args.limit)

    # Write run A as the trace artifact.
    with args.out.open("w", encoding="utf-8") as fh:
        for name, rows in run_a.items():
            for row in rows:
                fh.write(json.dumps({"resident": name, **row}, ensure_ascii=False) + "\n")

    # Gate: per-resident (heard, recalled) sequences identical A vs B.
    print(f"\n{'resident':26} {'ticks':>6} {'heard==':>8} {'recalled==':>11} {'verdict':>9}")
    print("-" * 64)
    all_pass = True
    for name in run_a:
        a, b = _signal(run_a[name]), _signal(run_b.get(name, []))
        heard_eq = [x[0] for x in a] == [x[0] for x in b]
        rec_eq = [x[1] for x in a] == [x[1] for x in b]
        ok = heard_eq and rec_eq and len(a) == len(b)
        all_pass = all_pass and ok
        print(f"{name:26} {len(a):>6} {str(heard_eq):>8} {str(rec_eq):>11} {'PASS' if ok else 'FAIL':>9}")
        if not ok:
            for i, (x, y) in enumerate(zip(a, b)):
                if x != y:
                    print(f"      first divergence @tick {i}: heard{'=' if x[0]==y[0] else '≠'} recalled{'=' if x[1]==y[1] else '≠'}")
                    break
    print("-" * 64)
    print(f"PARITY GATE (perception + recall reproduced deterministically): {'PASS' if all_pass else 'FAIL'}")
    print(f"trace written: {args.out}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
