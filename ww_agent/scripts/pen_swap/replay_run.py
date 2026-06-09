#!/usr/bin/env python3
"""Replay driver for the pen-vs-substrate experiment (KEEP' / SWAP arms).

Replays a KEEP recording into a FRESH pristine cohort on a chosen pen, OFFLINE
(no backend — the ReplayClient serves every world read from the recording). Each
arm answers: given KEEP's byte-identical lived experience, what does *this* pen
keep and whom does it engage?

Faithfulness essentials handled here:
  * **Session id reuse.** Recorded read paths embed KEEP's session id
    (``/scene/<sid>``). The arm resident must reuse it or every read misses, so we
    copy KEEP's ``session_id.txt`` into the arm; ``start()`` then validates it
    against the recording (get_scene served) and reuses it instead of bootstrapping.
  * **Pristine start.** The arm dir must be a fresh rehydration (pristine arcon) —
    run rehydrate.py --out <arm-dir> first. The replay adds the arm's own keeps on
    top of the identical initial state.
  * **Parity gate.** A same-pen replay (KEEP') should consume the recording with
    ZERO misses and drain the read queues. Misses / leftovers are reported; for the
    KEEP' parity arm they must be ~0 or the keying is unfaithful and no divergence
    number counts yet.

The embedder must be reachable (recall/drive) — same as the KEEP run. The pen is
``WW_INFERENCE_MODEL``.

Usage (from ww_agent root), e.g. the KEEP' parity arm:
    rm -rf /tmp/arm_keepprime && python3 scripts/pen_swap/rehydrate.py \\
        --out /tmp/arm_keepprime --source ../research/runs/2026-06-08-armC-ab/cast \\
        --ledger-from ../research/runs/2026-06-08-armC-ab/ledgers/arcon
    WW_INFERENCE_MODEL=anthropic/claude-haiku-4.5 WW_INFERENCE_KEY=... \\
    WW_EMBEDDING_URL=http://172.20.240.1:11434/v1 WW_EMBEDDING_MODEL=nomic-embed-text \\
    python3 scripts/pen_swap/replay_run.py --arm-dir /tmp/arm_keepprime \\
        --keep-dir ../shards/ww_pdx_keep/residents --rounds 30 --label keepprime
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_AGENT_ROOT))
sys.path.insert(0, str(_AGENT_ROOT / "scripts"))

from src.inference.client import InferenceClient  # noqa: E402
from src.resident import Resident  # noqa: E402
from src.runtime.cognitive_core import CognitiveCore  # noqa: E402
from src.runtime.memory import memories  # noqa: E402
from src.world.city_tools import build_city_tool_scope  # noqa: E402
from src.world.city_world import CityWorld  # noqa: E402

from pen_swap.replay_client import ReplayClient, perception_seed  # noqa: E402

logger = logging.getLogger("pen_swap.replay_run")


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


def _discover(d: Path) -> list[Path]:
    return sorted(p for p in d.iterdir() if p.is_dir() and not p.name.startswith("_") and (p / "identity" / "SOUL.md").exists())


def _initial_kept_notes(memory_dir: Path) -> set[str]:
    return {r["note"].strip().lower() for r in memories(memory_dir, limit=10000)}


async def _replay_one(arm_resident: Path, keep_resident: Path, llm: InferenceClient, recording_name: str, rounds: int):
    """Replay one resident's KEEP recording on the arm's pen. Returns a result dict."""
    # Replay bootstraps a FRESH session (matching KEEP's boot exactly); the new sid's
    # timestamp differs, but ReplayClient normalizes the sid out of paths so reads still
    # match the recording. (Copying KEEP's sid instead would make boot *validate* via an
    # extra get_scene, shifting the scene queue off-by-one — see DESIGN/parity notes.)
    memory_dir = arm_resident / "memory"
    initial_keeps = _initial_kept_notes(memory_dir)

    # 3) ReplayClient seeded from KEEP's recording
    recording = keep_resident / "memory" / recording_name
    if not recording.exists():
        return {"name": arm_resident.name, "error": f"no recording at {recording}"}
    rc = ReplayClient.from_recording(recording)

    resident = Resident(arm_resident, rc, llm)
    await resident.start("")  # world_id unused: session reused & validated against the recording

    identity = resident._identity
    session_id = resident._session_id
    city_world = CityWorld(rc, build_city_tool_scope(identity, client=rc, session_id=session_id, memory_dir=memory_dir))
    core = CognitiveCore(
        identity=identity,
        resident_dir=arm_resident,
        ww_client=city_world,
        llm=llm,
        session_id=session_id,
        pulse_model=identity.tuning.slow_model or identity.tuning.fast_model,
        pulse_temperature=identity.tuning.fast_temperature,
        anchor_gating=identity.tuning.anchor_gating,
        incubation=identity.tuning.incubation_enabled or _env_flag("WW_INCUBATION_ENABLED"),
    )

    for r in range(rounds):
        rc.set_tick(r)
        try:
            # Decouple perception's content-blind overheard draw from the module-global RNG
            # (which the pulse path churns differently per pen) — a stable per-(resident,tick)
            # seed so every arm draws the SAME slice and the only inter-arm difference is the pen.
            await core.tick_once(perception_seed=perception_seed(arm_resident.name, r))
        except Exception as exc:
            logger.warning("[%s] replay tick %d error: %s", arm_resident.name, r, exc)

    await rc.close()

    final_keeps = _initial_kept_notes(memory_dir)
    new_keeps = sorted(final_keeps - initial_keeps)
    leftover_reads = sum(len(q) for q in rc._read_queues.values())
    miss_paths = sorted({f"{m}" for m in rc.misses})
    leftover_paths = sorted(f"{k[1]} x{len(q)}" for k, q in rc._read_queues.items() if q)
    return {
        "name": arm_resident.name,
        "misses": len(rc.misses),
        "miss_paths": miss_paths,
        "leftover_reads": leftover_reads,
        "leftover_paths": leftover_paths,
        "captured_writes": len(rc.captured_writes),
        "initial_keeps": len(initial_keeps),
        "new_keeps": len(new_keeps),
        "new_keep_notes": new_keeps,
    }


async def main() -> int:
    ap = argparse.ArgumentParser(description="Replay a KEEP recording into a pristine arm on a chosen pen.")
    ap.add_argument("--arm-dir", required=True, type=Path, help="fresh pristine cohort (run rehydrate.py first)")
    ap.add_argument("--keep-dir", required=True, type=Path, help="KEEP cohort with recordings + session ids")
    ap.add_argument("--rounds", type=int, required=True, help="must equal the KEEP run's rounds")
    ap.add_argument("--recording-name", default="keep_recording.jsonl")
    ap.add_argument("--label", default="arm")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    pen = os.environ.get("WW_INFERENCE_MODEL", "google/gemini-3-flash-preview")
    key = os.environ.get("WW_INFERENCE_KEY", "")
    if not key:
        print("ERROR: WW_INFERENCE_KEY required (the arm's pen)", file=sys.stderr)
        return 2
    if not os.environ.get("WW_EMBEDDING_URL"):
        print("ERROR: WW_EMBEDDING_URL required for a fidelity replay (recall/drive)", file=sys.stderr)
        return 2

    llm = InferenceClient(base_url=os.environ.get("WW_INFERENCE_URL", "https://openrouter.ai/api/v1"), api_key=key, default_model=pen)
    arm_residents = _discover(args.arm_dir)
    if args.limit:
        arm_residents = arm_residents[: args.limit]
    logger.info("ARM '%s' | pen=%s | residents=%d | rounds=%d | recording<-%s", args.label, pen, len(arm_residents), args.rounds, args.keep_dir)

    results = []
    for ar in arm_residents:
        kr = args.keep_dir / ar.name
        if not kr.exists():
            logger.warning("no KEEP recording dir for %s — skipping", ar.name)
            continue
        results.append(await _replay_one(ar, kr, llm, args.recording_name, args.rounds))

    await llm.close()

    # Report
    print(f"\n=== ARM '{args.label}' (pen={pen}) ===")
    print(f"{'resident':26} {'miss':>5} {'left':>5} {'writes':>7} {'newkeep':>8}")
    print("-" * 56)
    tot_miss = tot_left = tot_new = 0
    for r in results:
        if "error" in r:
            print(f"{r['name']:26} ERROR: {r['error']}")
            continue
        print(f"{r['name']:26} {r['misses']:>5} {r['leftover_reads']:>5} {r['captured_writes']:>7} {r['new_keeps']:>8}")
        if r["miss_paths"]:
            print(f"      miss: {r['miss_paths']}")
        if r["leftover_paths"]:
            print(f"      left: {r['leftover_paths']}")
        tot_miss += r["misses"]
        tot_left += r["leftover_reads"]
        tot_new += r["new_keeps"]
    print("-" * 56)
    print(f"{'TOTAL':26} {tot_miss:>5} {tot_left:>5} {'':>7} {tot_new:>8}")
    print(f"\nPARITY signal (KEEP' should be ~0 misses & ~0 leftover): misses={tot_miss}, leftover_reads={tot_left}")
    print(f"new keeps this arm: {tot_new} across {len(results)} residents")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
