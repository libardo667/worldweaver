#!/usr/bin/env python3
"""Unattended maturation monitor for the pen-vs-substrate cohort (v2 — trim-immune).

Lets the operator walk away: loops every --check-min, watches the run, and EXITS with a verdict
(MATURED / CAP / TROUBLE) — stopping the agent on cap/trouble so the burn can't run away. The harness
notifies on exit, so the verdict reaches the operator without polling.

v2 fixes two bugs the 1000-event ledger cap exposed in v1:
  * v1 read who-addresses-whom from the ROLLING ledger — early edges TRIM away once capped, so dyad/
    elective counts shrank to 0 (window rolling, not real). v2 reads the **durable relationship graph**
    from `kept_memory.jsonl` (never trimmed): per resident, how many distinct co-cohort peers it KEEPS
    memories about. That is the trim-immune "has a relational self" signal.
  * v1's health = ledger LINE growth — which PLATEAUS at the cap (append+trim=constant) and would
    false-TROUBLE a healthy agent. v2's health = **newest-event-ts recency** (the agent appends every
    tick; a stale newest-ts = genuinely not ticking).

Stop on STABILITY, not activity (per the brief's stop-rule): MATURED when the relationship graph is
DENSE (>= --min-residents keep about >= --peers-floor peers) AND **both growth curves have plateaued**:
  * EXTENT (who-knows-whom) — distinct-peer-links grew <= --plateau-delta for --plateau-checks checks.
  * DEPTH  (how-much-kept) — total keeps grew <= --depth-delta for --plateau-checks checks.
Requiring BOTH is the fix for the v2 over-cut: extent saturates FAST (the acquaintance graph freezes in
~1h) while DEPTH keeps pouring in (residents keep re-noticing peers they already know). Stopping on
extent alone cut the run while the very signal the experiment feeds on — keep DEPTH, which grows the
salience-symmetric choice-point slice — was still flowing. Now the run rides depth until it ALSO levels.
⚠️ CIRCADIAN CAVEAT: the runtime quiets after dark, so a dusk lull drops BOTH curves and can impersonate
saturation. The --depth-delta default (20) is well below daytime flow (~60-95 keeps/check), so a mild
evening dip still reads as "flowing"; only genuine saturation or deep night flats depth. The --max-hours
cap is the backstop. The elective-choice-point slice itself is captured durably at KEEP-recording time
(RecordingClient), not from the trimming ledger — maturation's job is a stable, DEEP relationship graph.

Usage (background):
    python3 scripts/pen_swap/monitor_grow.py --project ww_pdx_grow \\
        --residents-dir ../shards/ww_pdx_grow/residents --max-hours 10
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def _sh(cmd: list[str], timeout: float = 25.0) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def _agent_container(project: str) -> str:
    out = _sh(["docker", "ps", "--format", "{{.Names}}", "--filter", f"name={project}-agent"])
    return out.strip().splitlines()[0] if out.strip() else ""


def _newest_event_age_s(residents_dir: Path) -> float:
    """Seconds since the newest ledger event across the cohort. Robust to the rolling cap."""
    newest = ""
    for f in residents_dir.glob("*/memory/runtime_ledger.jsonl"):
        last = None
        try:
            for line in f.open():
                if line.strip():
                    last = line
            if last:
                ts = str(json.loads(last).get("ts") or "")
                if ts > newest:
                    newest = ts
        except Exception:
            pass
    if not newest:
        return 1e9
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(newest)).total_seconds()
    except Exception:
        return 1e9


def _first_names(residents_dir: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for f in residents_dir.glob("*/identity/IDENTITY.md"):
        slug = f.parent.parent.name
        try:
            line = f.open().readline().strip().lstrip("# ").strip()
            if line:
                out[slug] = line.split()[0]
        except Exception:
            pass
    return out


def _relationship_graph(residents_dir: Path) -> dict:
    """Durable, trim-immune: per resident, distinct co-cohort peers it KEEPS memories about."""
    firsts = _first_names(residents_dir)
    peers_per: dict[str, int] = {}
    total_keeps = 0
    for slug in firsts:
        kf = residents_dir / slug / "memory" / "kept_memory.jsonl"
        notes: list[str] = []
        try:
            for line in kf.open():
                if line.strip():
                    notes.append(str(json.loads(line).get("note") or ""))
        except Exception:
            pass
        total_keeps += len(notes)
        blob = " ".join(notes)
        peers = {fn for s2, fn in firsts.items() if s2 != slug and fn and re.search(r"\b" + re.escape(fn) + r"\b", blob)}
        peers_per[slug] = len(peers)
    return {
        "residents": len(firsts),
        "total_keeps": total_keeps,
        "distinct_peer_links": sum(peers_per.values()),
        "n_ge_floor": peers_per,  # filtered against the floor in the loop
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Unattended maturation monitor (v2, trim-immune).")
    ap.add_argument("--project", required=True)
    ap.add_argument("--residents-dir", required=True, type=Path)
    ap.add_argument("--max-hours", type=float, default=10.0)
    ap.add_argument("--check-min", type=float, default=20.0)
    ap.add_argument("--min-residents", type=int, default=10, help="residents that must keep about >= peers-floor peers")
    ap.add_argument("--peers-floor", type=int, default=3, help="distinct peers kept-about = a relational self")
    ap.add_argument("--plateau-delta", type=int, default=4, help="cohort distinct-peer-link (EXTENT) growth/check that counts as 'flat'")
    ap.add_argument("--depth-delta", type=int, default=20, help="total-keeps (DEPTH) growth/check that counts as 'flat'; daytime flow is ~60-95, so this only trips at genuine saturation or deep night")
    ap.add_argument("--plateau-checks", type=int, default=2, help="consecutive flat checks (BOTH extent AND depth) = plateau")
    ap.add_argument("--stale-sec", type=float, default=300.0, help="newest-event age past which the agent is 'not ticking'")
    ap.add_argument("--trouble-strikes", type=int, default=3)
    args = ap.parse_args()

    start = time.time()
    strikes = 0
    prev_links = -1
    prev_keeps = -1
    flat = 0
    dflat = 0
    print(f"[monitor] start · project={args.project} · cap={args.max_hours}h · check/{args.check_min}m · stop=stability(>= {args.min_residents} residents w/ >= {args.peers_floor} peers, EXTENT-flat AND DEPTH-flat)", flush=True)

    def stop_agent() -> None:
        c = _agent_container(args.project)
        if c:
            _sh(["docker", "stop", c], timeout=60)
            print(f"[monitor] stopped agent container {c}", flush=True)

    while True:
        time.sleep(args.check_min * 60)
        try:
            elapsed_h = (time.time() - start) / 3600.0
            container = _agent_container(args.project)
            age = _newest_event_age_s(args.residents_dir)
            pay402 = "0"
            if container:
                pay402 = _sh(["bash", "-c", f"docker logs --since {int(args.check_min * 60) + 60}s {container} 2>&1 | grep -c '402 Payment'"]).strip() or "0"
            g = _relationship_graph(args.residents_dir)
            n_ge = sum(1 for v in g["n_ge_floor"].values() if v >= args.peers_floor)
            links = g["distinct_peer_links"]
            keeps = g["total_keeps"]
            dlinks = links - prev_links if prev_links >= 0 else links
            dkeeps = keeps - prev_keeps if prev_keeps >= 0 else keeps
            flat = flat + 1 if (prev_links >= 0 and dlinks <= args.plateau_delta) else 0
            dflat = dflat + 1 if (prev_keeps >= 0 and dkeeps <= args.depth_delta) else 0
            prev_links = links
            prev_keeps = keeps
            healthy = bool(container) and age < args.stale_sec and pay402 == "0"
            print(
                f"[monitor] t={elapsed_h:.1f}h | agent={'up' if container else 'DOWN'} | newest={age:.0f}s | 402={pay402} | " f"keeps={keeps} (+{dkeeps}) | peer_links={links} (+{dlinks}) | residents>={args.peers_floor}peers: {n_ge}/{g['residents']} | ext-flat={flat}/{args.plateau_checks} dep-flat={dflat}/{args.plateau_checks}",
                flush=True,
            )

            if not healthy:
                strikes += 1
                why = "down" if not container else (f"stale {age:.0f}s" if age >= args.stale_sec else f"402x{pay402}")
                print(f"[monitor] trouble strike {strikes}/{args.trouble_strikes} ({why})", flush=True)
                if strikes >= args.trouble_strikes:
                    stop_agent()
                    print(f"[monitor] VERDICT=TROUBLE after {elapsed_h:.1f}h ({why}). Ledgers + kept_memory preserved on host.", flush=True)
                    return 2
            else:
                strikes = 0

            if n_ge >= args.min_residents and flat >= args.plateau_checks and dflat >= args.plateau_checks:
                stop_agent()
                print(f"[monitor] VERDICT=MATURED at {elapsed_h:.1f}h — dense ({n_ge}/{g['residents']} >= {args.peers_floor} peers), EXTENT plateaued AND DEPTH plateaued ({keeps} keeps, +{dkeeps}/check). Ready for KEEP recording.", flush=True)
                return 0

            if elapsed_h >= args.max_hours:
                stop_agent()
                print(f"[monitor] VERDICT=CAP at {elapsed_h:.1f}h — {n_ge}/{g['residents']} residents >= {args.peers_floor} peers, {links} peer-links, {keeps} keeps. Graph state IS the result; assess before KEEP.", flush=True)
                return 1
        except Exception as exc:  # never let a transient error kill the watch (v1 stalled silently)
            print(f"[monitor] check error (continuing): {exc.__class__.__name__}: {exc}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
