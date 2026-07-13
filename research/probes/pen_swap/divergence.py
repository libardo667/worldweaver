#!/usr/bin/env python3
"""Memory-curation divergence metric for the pen-vs-substrate experiment.

Given several arm cohorts that all started from the IDENTICAL pristine state and
lived the IDENTICAL recorded experience (KEEP live, KEEP'/SWAP* replayed), ask:
does a swapped pen keep *different memories* than KEEP — more than same-pen
stochastic variation does?

Per resident, per arm: the NEW keeps = its final durable kept-memory set minus the
shared pristine-initial set. Content alignment between KEEP and another arm X:

    align(KEEP, X) = mean over k in KEEP_new of  max over x in X_new of cos(emb(k), emb(x))

i.e. "is each memory KEEP chose to keep echoed by something X kept?" Embeddings via
the SAME embedder the run used (nomic-embed-text), so this is deterministic.

The verdict is RELATIVE, not absolute:
    align(KEEP, KEEP')  = the same-pen NOISE FLOOR (LLMs are stochastic)
    align(KEEP, SWAP*)  = the test
If align(KEEP,SWAP) ~ align(KEEP,KEEP')  -> curation is pen-robust (substrate carries it).
If align(KEEP,SWAP) << align(KEEP,KEEP') -> the pen shapes what's kept (thesis weakened).
A swap claim requires the gap to hold across >=2 SWAP pens (capability != self).

This leans on an embedder, which is the register-round hazard — admissible ONLY
because the KEEP' arm calibrates it. Report coverage (residents with keeps in both
arms); thin coverage => the measure is underpowered, a result about the *measure*.

Usage (from ww_agent root):
    WW_EMBEDDING_URL=http://172.20.240.1:11434/v1 WW_EMBEDDING_MODEL=nomic-embed-text \\
    python3 scripts/pen_swap/divergence.py \\
        --initial /tmp/arm_pristine \\
        --keep ../shards/ww_pdx_keep/residents \\
        --arm keepprime=/tmp/arm_keepprime --arm swapGemini=/tmp/arm_swap_gemini ...
"""
from __future__ import annotations

import argparse
import asyncio
import math
import os
import sys
from pathlib import Path

_AGENT_ROOT = Path(__file__).resolve().parents[3] / "ww_agent"
sys.path.insert(0, str(_AGENT_ROOT))

from src.runtime.drive import RemoteEmbedder  # noqa: E402
from src.runtime.memory import memories  # noqa: E402


def _new_keeps(arm_resident: Path, initial_notes: set[str]) -> list[str]:
    """Keep notes present in this arm but not in the shared pristine-initial set."""
    out = []
    for r in memories(arm_resident / "memory", limit=10000):
        note = r["note"].strip()
        if note and note.lower() not in initial_notes:
            out.append(note)
    return out


def _initial_notes(resident: Path) -> set[str]:
    return {r["note"].strip().lower() for r in memories(resident / "memory", limit=10000)}


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))  # embedder returns L2-normalized vectors


async def _embed_all(embedder, texts: list[str]) -> dict[str, list[float]]:
    uniq = sorted(set(texts))
    if not uniq:
        return {}
    vecs = await embedder.embed(uniq)
    return dict(zip(uniq, vecs))


def _alignment(keep_notes: list[str], other_notes: list[str], emb: dict[str, list[float]]) -> float | None:
    if not keep_notes or not other_notes:
        return None
    sims = []
    for k in keep_notes:
        kv = emb.get(k)
        if not kv:
            continue
        best = max((_cos(kv, emb[o]) for o in other_notes if o in emb), default=0.0)
        sims.append(best)
    return sum(sims) / len(sims) if sims else None


async def main() -> int:
    ap = argparse.ArgumentParser(description="Memory-curation divergence across pen-swap arms.")
    ap.add_argument("--initial", required=True, type=Path, help="pristine cohort dir (shared initial keeps)")
    ap.add_argument("--keep", required=True, type=Path, help="KEEP cohort dir")
    ap.add_argument("--arm", action="append", default=[], help="name=dir for each replay arm (incl keepprime)")
    args = ap.parse_args()

    url = os.environ.get("WW_EMBEDDING_URL")
    model = os.environ.get("WW_EMBEDDING_MODEL", "nomic-embed-text")
    if not url:
        print("ERROR: WW_EMBEDDING_URL required", file=sys.stderr)
        return 2
    embedder = RemoteEmbedder(base_url=url, api_key=os.environ.get("WW_EMBEDDING_KEY", "ollama"), model=model)

    arms: dict[str, Path] = {"KEEP": args.keep}
    for spec in args.arm:
        name, _, d = spec.partition("=")
        arms[name] = Path(d)

    residents = sorted(p.name for p in args.keep.iterdir() if p.is_dir() and (p / "identity" / "SOUL.md").exists())

    # Gather new keeps per (arm, resident).
    new: dict[str, dict[str, list[str]]] = {a: {} for a in arms}
    for name in residents:
        init = _initial_notes(args.initial / name)
        for a, d in arms.items():
            rd = d / name
            new[a][name] = _new_keeps(rd, init) if rd.exists() else []

    # Embed everything once.
    all_notes = [n for a in arms for name in residents for n in new[a].get(name, [])]
    emb = await _embed_all(embedder, all_notes)
    await embedder.close()

    # Per-arm keep volume.
    print("=== new-keep volume per arm ===")
    for a in arms:
        tot = sum(len(new[a][name]) for name in residents)
        covered = sum(1 for name in residents if new[a][name])
        print(f"  {a:16} keeps={tot:4d}  residents_with_keeps={covered}/{len(residents)}")

    # Alignment of each arm to KEEP (per resident, then averaged over covered residents).
    print("\n=== content alignment to KEEP (1.0=identical content, lower=divergent) ===")
    print(f"{'arm':16} {'mean_align':>11} {'covered':>8}   (KEEP' = same-pen noise floor)")
    print("-" * 60)
    floor = None
    for a in arms:
        if a == "KEEP":
            continue
        per = []
        for name in residents:
            al = _alignment(new["KEEP"][name], new[a][name], emb)
            if al is not None:
                per.append(al)
        mean = sum(per) / len(per) if per else float("nan")
        print(f"{a:16} {mean:>11.3f} {len(per):>8}")
        if a.lower().startswith("keepprime") or a.lower() == "keep'":
            floor = mean

    if floor is not None and not math.isnan(floor):
        print(f"\nNoise floor (KEEP vs KEEP') = {floor:.3f}")
        print("Read: a SWAP arm well BELOW the floor = pen shapes curation; ~AT the floor = substrate-carried.")
    else:
        print("\n(no KEEP' arm given or no overlap — cannot calibrate the noise floor yet)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
