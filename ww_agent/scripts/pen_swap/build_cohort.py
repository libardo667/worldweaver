#!/usr/bin/env python3
"""Batch-build a structurally-diverse, CLUSTERED cohort for the pen-vs-substrate maturation.

The doula's founding bootstrap spreads residents ONE per empty location (it skips any location
with total_agents>=1) — the opposite of the clustering the experiment needs (multiple established
peers co-present → elective choice points). This builder reuses the doula's exact de-novo generation
(demographic pools → dealt hand → _SEED_SYSTEM_DEALT_HAND soul → _IDENTITY_PROSE_SYSTEM → scaffold)
but FORCES N residents into K clusters (N/K per location), so local co-presence + local speech routing
(effectors: non-'city' targets post to the local location) can grow real dyads.

Single-pen, hand-only (diverse occupations, no world-fact decay loop). Output is a ready-to-boot
residents/ dir; launch the maturation agent with WW_DOULA=0 (fixed cast — no mid-run handoff).

Usage (from ww_agent root):
    set -a; source ../shards/ww_pdx_grow/.env; set +a
    python3 scripts/pen_swap/build_cohort.py --out ../shards/ww_pdx_grow/residents \\
        --server http://localhost:8260 --count 16 --clusters 4
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_AGENT_ROOT))

from src.inference.client import InferenceClient  # noqa: E402
from src.loops.doula import (  # noqa: E402
    _AGE_BANDS,
    _DISPOSITIONS_GIVEN,
    _IDENTITY_PROSE_SYSTEM,
    _NAME_TRADITIONS,
    _ORIGINS,
    _SEED_SYSTEM_DEALT_HAND,
    _TEMPERAMENTS,
)
from src.runtime.naming import slugify_resident_name  # noqa: E402
from src.world.client import WorldWeaverClient  # noqa: E402


def _looks_like_name(s: str) -> bool:
    parts = s.split()
    return 1 < len(parts) <= 4 and all(p[:1].isalpha() for p in parts) and len(s) <= 60


async def _pick_clusters(server: str, k: int) -> list[str]:
    """k distinct real place-names, spaced through the sorted list for separation."""
    ww = WorldWeaverClient(base_url=server)
    try:
        names = sorted(await ww.get_place_names())
    finally:
        await ww.close()
    names = [n for n in names if n and n.strip()]
    if len(names) < k:
        raise SystemExit(f"only {len(names)} place-names; need {k}")
    step = max(1, len(names) // (k + 1))
    return [names[step * (i + 1)] for i in range(k)]


async def _build_one(llm: InferenceClient, name_model: str, home_location: str, recent_surnames: list[str]) -> dict | None:
    tradition = random.choice(_NAME_TRADITIONS)
    age = random.choice(_AGE_BANDS)
    temperament = random.choice(_TEMPERAMENTS)
    disposition = random.choice(_DISPOSITIONS_GIVEN)
    origin = random.choice(_ORIGINS)
    avoid = ", ".join(dict.fromkeys(recent_surnames[-12:])) or "none yet"
    try:
        name_raw = await llm.complete(
            system_prompt=("You are naming a resident of a real, working Portland neighborhood. " f"Give one plausible full name (first and last) in the {tradition} naming tradition. " f"Do NOT reuse any of these recently-used surnames: {avoid}. " "Reply with the name only — no explanation, punctuation, or quotes."),
            user_prompt=f"They live and work around {home_location.replace('_', ' ')}.",
            model=name_model,
            temperature=0.95,
            max_tokens=12,
        )
    except Exception as e:
        print(f"  name gen failed @ {home_location}: {e}", file=sys.stderr)
        return None
    name = name_raw.strip().strip("\"'").strip()
    if not _looks_like_name(name) or name.lower() == home_location.replace("_", " ").lower():
        print(f"  rejected name {name!r} @ {home_location}", file=sys.stderr)
        return None

    dealt_hand = f"- heritage: a {tradition} background\n- age: {age}\n- temper born with: {temperament}\n- how they handle a room: {disposition}\n- came up: {origin}"
    user_prompt = f"The hand {name} was dealt:\n{dealt_hand}\n\nWhere they are now:\n- This person lives around {home_location.replace('_', ' ')}."
    try:
        soul = (await llm.complete(system_prompt=_SEED_SYSTEM_DEALT_HAND, user_prompt=user_prompt, temperature=0.7, max_tokens=600)).strip()
        prose = (await llm.complete(system_prompt=_IDENTITY_PROSE_SYSTEM, user_prompt=f"Here is who this person turned out to be:\n{soul}", temperature=0.5, max_tokens=150)).strip()
    except Exception as e:
        print(f"  soul/prose gen failed for {name}: {e}", file=sys.stderr)
        return None
    return {"name": name, "soul": soul, "prose": prose, "home_location": home_location, "tradition": tradition, "age": age}


def _scaffold(out: Path, r: dict) -> None:
    rd = out / slugify_resident_name(r["name"])
    idd = rd / "identity"
    idd.mkdir(parents=True, exist_ok=True)
    (idd / "resident_id.txt").write_text(f"{uuid.uuid4()}\n", encoding="utf-8")
    (idd / "SOUL.canonical.md").write_text(r["soul"] + "\n", encoding="utf-8")
    (idd / "SOUL.md").write_text(r["soul"] + "\n", encoding="utf-8")
    ts = datetime.now(timezone.utc).isoformat()
    idm = f"# {r['name']}\n\n- **Spawned-By:** build_cohort\n- **Spawned-At:** {ts}\n- **origin:** novel\n- **home_location:** {r['home_location']}\n\n{r['prose']}\n"
    (idd / "IDENTITY.md").write_text(idm, encoding="utf-8")
    tuning = {"_comment": f"build_cohort cohort member ({r['tradition']}, {r['age']})", "wander": {"enabled": True, "seconds": 600, "temperature": 0.6}, "home_location": r["home_location"]}
    (idd / "tuning.json").write_text(json.dumps(tuning, indent=4, ensure_ascii=False), encoding="utf-8")
    (idd / "entry_location.txt").write_text(r["home_location"], encoding="utf-8")
    (rd / "memory").mkdir(parents=True, exist_ok=True)


async def main() -> int:
    ap = argparse.ArgumentParser(description="Batch-build a clustered, structurally-diverse cohort.")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--server", required=True, help="backend URL (for place-names)")
    ap.add_argument("--count", type=int, default=16)
    ap.add_argument("--clusters", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20260609)
    args = ap.parse_args()

    key = os.environ.get("WW_INFERENCE_KEY", "")
    if not key:
        print("ERROR: WW_INFERENCE_KEY required (source the shard .env)", file=sys.stderr)
        return 2
    pen = os.environ.get("WW_INFERENCE_MODEL", "google/gemini-3-flash-preview")
    random.seed(args.seed)
    llm = InferenceClient(base_url=os.environ.get("WW_INFERENCE_URL", "https://openrouter.ai/api/v1"), api_key=key, default_model=pen)

    clusters = await _pick_clusters(args.server, args.clusters)
    print(f"pen={pen} | count={args.count} | clusters({args.clusters})={clusters}")
    args.out.mkdir(parents=True, exist_ok=True)

    recent: list[str] = []
    built: list[dict] = []
    for i in range(args.count):
        home = clusters[i % args.clusters]
        r = None
        for _attempt in range(3):
            r = await _build_one(llm, pen, home, recent)
            if r:
                break
        if not r:
            print(f"  SKIP slot {i} @ {home} (gen failed x3)", file=sys.stderr)
            continue
        recent.append(r["name"].split()[-1])
        _scaffold(args.out, r)
        built.append(r)
        print(f"  [{len(built):2}/{args.count}] {r['name']:28} home={home}")
    await llm.close()

    # report cluster balance
    from collections import Counter

    bal = Counter(r["home_location"] for r in built)
    print("\ncluster balance:")
    for loc, n in bal.items():
        print(f"  {loc:24} {n}")
    bootable = sum(1 for r in built if (args.out / slugify_resident_name(r["name"]) / "identity" / "SOUL.md").exists())
    print(f"\nbuilt {len(built)}/{args.count}; bootable (SOUL.md present): {bootable}")
    return 0 if bootable == len(built) and built else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
