#!/usr/bin/env python3
"""Rehydrate a matured resident cohort into an isolated experiment dir.

Clones complete, bootable resident homes (identity/ + memory/) from a source
cohort into a fresh ``residents/`` directory the KEEP recording run can boot,
stripping the session binding so each resident rejoins a fresh, isolated world.

Two modes:

  * **clean-copy (default)** — copy the full resident home from a single coherent
    source (e.g. ``shards/ww_pdx_deal/residents``). Ledger and derived caches
    agree by construction; no rebuild needed. The safest, definitely-faithful path.

  * **--ledger-from DIR** — keep the source identity but swap in a different
    ``runtime_ledger.jsonl`` per resident (e.g. the PUBLIC, cold-verifiable arcon
    ledgers under ``research/runs/.../ledgers/arcon/<name>.jsonl.gz``), then
    regenerate the compat projections from the new ledger via the runtime's own
    ``rebuild_runtime_artifacts``. NOTE: ``kept_memory.jsonl`` coherence under a
    ledger swap is not yet verified — treat it as a parity-check item.

A valid resident home is gated by ``identity/SOUL.md`` (see main._discover_residents).

Usage (from the ww_agent root):
    python scripts/pen_swap/rehydrate.py --out /tmp/pen_swap_keep \\
        [--source ../shards/ww_pdx_deal/residents] \\
        [--names-file <file> | --names a,b,c] \\
        [--ledger-from ../research/runs/2026-06-08-armC-ab/ledgers/arcon] \\
        [--force]
"""
from __future__ import annotations

import argparse
import gzip
import json
import shutil
import sys
from pathlib import Path

_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent
_REPO_ROOT = _AGENT_ROOT.parent
sys.path.insert(0, str(_AGENT_ROOT))

DEFAULT_SOURCE = _REPO_ROOT / "shards" / "ww_pdx_deal" / "residents"
ARMC_CAST_DIR = _REPO_ROOT / "research" / "runs" / "2026-06-08-armC-ab" / "cast"

# Per-resident files that bind to a specific (dead) world/session — never carry them.
_DROP_FILES = ("session_id.txt",)
# Derived caches regenerated from the ledger when --ledger-from swaps it.
_DERIVED_CACHES = (
    "runtime_projection.json",
    "subjective_projection.json",
    "memory_projection.json",
    "subjective_facts.json",
    "cognitive_projection.json",
    "runtime_snapshot.json",
    "perception_state.json",
    "kept_memory.jsonl",
)


def _resolve_names(args: argparse.Namespace, source: Path) -> list[str]:
    if args.names:
        return [n.strip() for n in args.names.split(",") if n.strip()]
    if args.names_file:
        return [ln.strip() for ln in Path(args.names_file).read_text(encoding="utf-8").splitlines() if ln.strip()]
    if ARMC_CAST_DIR.is_dir():
        return sorted(p.name for p in ARMC_CAST_DIR.iterdir() if p.is_dir())
    # Fall back to every complete resident in the source.
    return sorted(p.name for p in source.iterdir() if p.is_dir() and (p / "identity" / "SOUL.md").exists())


def _ledger_event_stats(ledger_path: Path) -> tuple[int, int]:
    """(total events, memory_kept count) for a runtime_ledger.jsonl."""
    total = kept = 0
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        total += 1
        try:
            if json.loads(line).get("event_type") == "memory_kept":
                kept += 1
        except json.JSONDecodeError:
            pass
    return total, kept


def _swap_ledger(memory_dir: Path, ledger_src: Path) -> None:
    """Replace runtime_ledger.jsonl with ledger_src (decompressing .gz), drop
    derived caches, and rebuild projections from the new ledger."""
    target = memory_dir / "runtime_ledger.jsonl"
    if ledger_src.suffix == ".gz":
        with gzip.open(ledger_src, "rt", encoding="utf-8") as fh:
            target.write_text(fh.read(), encoding="utf-8")
    else:
        shutil.copyfile(ledger_src, target)
    for cache in _DERIVED_CACHES:
        (memory_dir / cache).unlink(missing_ok=True)
    from src.runtime.ledger import rebuild_runtime_artifacts  # lazy: only this path needs the runtime

    rebuild_runtime_artifacts(memory_dir)


def _find_ledger(ledger_from: Path, name: str) -> Path | None:
    for cand in (ledger_from / f"{name}.jsonl.gz", ledger_from / f"{name}.jsonl", ledger_from / name / "memory" / "runtime_ledger.jsonl"):
        if cand.exists():
            return cand
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Rehydrate a matured resident cohort into an isolated experiment dir.")
    ap.add_argument("--out", required=True, type=Path, help="output residents/ dir to create")
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help=f"source residents dir (default: {DEFAULT_SOURCE})")
    ap.add_argument("--names", help="comma-separated resident names")
    ap.add_argument("--names-file", help="file with one resident name per line")
    ap.add_argument("--ledger-from", type=Path, help="swap in runtime_ledger.jsonl per resident from this dir (e.g. public arcon ledgers)")
    ap.add_argument("--force", action="store_true", help="overwrite --out if it exists")
    args = ap.parse_args()

    source: Path = args.source
    if not source.is_dir():
        print(f"ERROR: source not found: {source}", file=sys.stderr)
        return 2

    out: Path = args.out
    if out.exists():
        if not args.force:
            print(f"ERROR: {out} exists (use --force to overwrite)", file=sys.stderr)
            return 2
        shutil.rmtree(out)
    out.mkdir(parents=True)

    names = _resolve_names(args, source)
    print(f"rehydrating {len(names)} residents: {source} -> {out}" + (f"  (ledger swap from {args.ledger_from})" if args.ledger_from else "  (clean copy)"))

    ok = 0
    skipped: list[str] = []
    print(f"\n{'resident':28} {'events':>7} {'kept':>5}  soul")
    print("-" * 52)
    for name in names:
        src_dir = source / name
        if not (src_dir / "identity" / "SOUL.md").exists():
            skipped.append(f"{name} (no identity/SOUL.md in source)")
            continue

        dst_dir = out / name
        shutil.copytree(src_dir / "identity", dst_dir / "identity")
        if (src_dir / "memory").is_dir():
            shutil.copytree(src_dir / "memory", dst_dir / "memory")
        else:
            (dst_dir / "memory").mkdir(parents=True)
        for drop in _DROP_FILES:
            (dst_dir / drop).unlink(missing_ok=True)

        if args.ledger_from:
            led = _find_ledger(args.ledger_from, name)
            if led is None:
                shutil.rmtree(dst_dir)
                skipped.append(f"{name} (no ledger in {args.ledger_from})")
                continue
            _swap_ledger(dst_dir / "memory", led)

        ledger_path = dst_dir / "memory" / "runtime_ledger.jsonl"
        total, kept = _ledger_event_stats(ledger_path) if ledger_path.exists() else (0, 0)
        soul_ok = (dst_dir / "identity" / "SOUL.md").exists()
        print(f"{name:28} {total:>7} {kept:>5}  {'yes' if soul_ok else 'NO'}")
        ok += 1

    print("-" * 52)
    print(f"rehydrated {ok}/{len(names)} residents into {out}")
    if skipped:
        print("skipped:")
        for s in skipped:
            print(f"  - {s}")
    # Boot-readiness check mirrors main._discover_residents.
    bootable = sorted(p.name for p in out.iterdir() if p.is_dir() and (p / "identity" / "SOUL.md").exists())
    print(f"bootable (identity/SOUL.md present): {len(bootable)}/{ok}")
    return 0 if ok and len(bootable) == ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
