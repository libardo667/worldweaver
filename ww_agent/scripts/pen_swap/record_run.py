#!/usr/bin/env python3
"""Live KEEP recording runner for the pen-vs-substrate experiment.

Boots a rehydrated cohort against a live (isolated) backend, each resident wired
to its own ``RecordingClient`` so every world-client call it makes is teed to
``<resident>/memory/<recording>.jsonl``. Drives the cohort in **round-robin
``tick_once`` rounds** (deterministic tick count, no wall-clock racing), and runs
ONLY the cognitive core — no doula, no runtime mirror, no guild sync — so the
recording is the cognition under test and nothing else.

The recording lets us later replay this exact lived experience into copies on a
different pen (see replay_client.ReplayClient + the replay driver).

Run from the ww_agent root, with env pointing at the isolated backend, the pen,
and the embedder, e.g.:

    WW_SERVER_URL=http://localhost:8240 \\
    WW_INFERENCE_URL=https://openrouter.ai/api/v1 \\
    WW_INFERENCE_KEY=... \\
    WW_INFERENCE_MODEL=anthropic/claude-haiku-4.5 \\
    WW_EMBEDDING_URL=http://172.20.240.1:11434/v1 \\
    WW_EMBEDDING_MODEL=nomic-embed-text \\
    python scripts/pen_swap/record_run.py --residents-dir /tmp/pen_swap_public --rounds 30
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
from src.runtime.ledger import load_runtime_events  # noqa: E402
from src.world.city_tools import build_city_tool_scope  # noqa: E402
from src.world.city_world import CityWorld  # noqa: E402
from src.world.client import WorldWeaverClient  # noqa: E402

from pen_swap.replay_client import RecordingClient  # noqa: E402

logger = logging.getLogger("pen_swap.record_run")


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


def _discover(residents_dir: Path) -> list[Path]:
    """Same gate as main._discover_residents: identity/SOUL.md present, no leading _."""
    return sorted(p for p in residents_dir.iterdir() if p.is_dir() and not p.name.startswith("_") and (p / "identity" / "SOUL.md").exists())


async def _boot_one(resident_dir: Path, base_url: str, llm: InferenceClient, world_id: str, recording_name: str):
    """Start a resident on its own RecordingClient and build its cognitive core
    exactly as Resident.run() does (minus mirror/guild/doula)."""
    rc = RecordingClient(base_url, recording_path=resident_dir / "memory" / recording_name)
    resident = Resident(resident_dir, rc, llm)
    await resident.start(world_id)  # loads identity, bootstraps session, hydrates growth/guild

    identity = resident._identity
    session_id = resident._session_id
    memory_dir = resident_dir / "memory"
    city_world = CityWorld(rc, build_city_tool_scope(identity, client=rc, session_id=session_id, memory_dir=memory_dir))
    core = CognitiveCore(
        identity=identity,
        resident_dir=resident_dir,
        ww_client=city_world,
        llm=llm,
        session_id=session_id,
        pulse_model=identity.tuning.slow_model or identity.tuning.fast_model,
        pulse_temperature=identity.tuning.fast_temperature,
        anchor_gating=identity.tuning.anchor_gating,
        incubation=identity.tuning.incubation_enabled or _env_flag("WW_INCUBATION_ENABLED"),
    )
    return resident, core, rc


def _ledger_stats(memory_dir: Path) -> tuple[int, int]:
    events = load_runtime_events(memory_dir)
    kept = sum(1 for e in events if str(e.get("event_type") or "") == "memory_kept")
    return len(events), kept


async def main() -> int:
    ap = argparse.ArgumentParser(description="Live KEEP recording runner (pen-swap experiment).")
    ap.add_argument("--residents-dir", required=True, type=Path, help="rehydrated cohort dir")
    ap.add_argument("--rounds", type=int, default=30, help="round-robin tick rounds per resident")
    ap.add_argument("--recording-name", default="keep_recording.jsonl", help="per-resident recording filename")
    ap.add_argument("--limit", type=int, default=0, help="cap number of residents (0 = all) — for smoke tests")
    ap.add_argument("--ready-timeout", type=float, default=60.0)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    base_url = os.environ.get("WW_SERVER_URL", "http://localhost:8000")
    llm_url = os.environ.get("WW_INFERENCE_URL", "https://openrouter.ai/api/v1")
    llm_key = os.environ.get("WW_INFERENCE_KEY", "")
    llm_model = os.environ.get("WW_INFERENCE_MODEL", "google/gemini-3-flash-preview")
    if not llm_key:
        print("ERROR: WW_INFERENCE_KEY required (the pen)", file=sys.stderr)
        return 2
    if not os.environ.get("WW_EMBEDDING_URL"):
        print("WARNING: WW_EMBEDDING_URL unset — residents will run NEUTRAL-AFFECT (no recall/drive). Not a fidelity run.", file=sys.stderr)

    residents_dir: Path = args.residents_dir
    dirs = _discover(residents_dir)
    if args.limit:
        dirs = dirs[: args.limit]
    if not dirs:
        print(f"ERROR: no residents (identity/SOUL.md) under {residents_dir}", file=sys.stderr)
        return 2

    llm = InferenceClient(base_url=llm_url, api_key=llm_key, default_model=llm_model)
    logger.info("pen (WW_INFERENCE_MODEL) = %s | embedder = %s | residents = %d | rounds = %d", llm_model, os.environ.get("WW_EMBEDDING_URL", "<none>"), len(dirs), args.rounds)

    # Wait for the backend + a seeded world.
    probe = WorldWeaverClient(base_url=base_url)
    await probe.wait_for_ready(timeout_seconds=args.ready_timeout)
    world_id = None
    for _ in range(30):
        world_id = await probe.get_world_id()
        if world_id:
            break
        await asyncio.sleep(2.0)
    await probe.close()
    if not world_id:
        print("ERROR: no world seeded on the backend (run seed_world.py first)", file=sys.stderr)
        await llm.close()
        return 2
    logger.info("world: %s", world_id)

    booted = []
    for d in dirs:
        try:
            booted.append(await _boot_one(d, base_url, llm, world_id, args.recording_name))
            logger.info("booted %s", d.name)
        except Exception as exc:
            logger.warning("failed to boot %s: %s", d.name, exc)

    if not booted:
        await llm.close()
        return 1

    # Round-robin ticks: deterministic cadence, the cohort lives in lockstep rounds.
    logger.info("running %d rounds over %d residents ...", args.rounds, len(booted))
    for r in range(args.rounds):
        for resident, core, rc in booted:
            rc.set_tick(r)
            try:
                await core.tick_once()
            except Exception as exc:
                logger.warning("[%s] tick %d error: %s", resident.name, r, exc)
        if (r + 1) % 5 == 0:
            logger.info("round %d/%d done", r + 1, args.rounds)

    for _, _, rc in booted:
        await rc.close()
    await llm.close()

    # Report.
    print(f"\n{'resident':28} {'events':>7} {'kept':>5} {'recorded':>9}")
    print("-" * 54)
    for resident, _, _ in booted:
        md = resident._resident_dir / "memory"
        total, kept = _ledger_stats(md)
        rec_lines = sum(1 for _ in (md / args.recording_name).open()) if (md / args.recording_name).exists() else 0
        print(f"{resident.name:28} {total:>7} {kept:>5} {rec_lines:>9}")
    print("-" * 54)
    print(f"done: {len(booted)} residents, {args.rounds} rounds, pen={llm_model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
