#!/usr/bin/env python3
"""Unattended maturation monitor for the pen-vs-substrate cohort.

Lets the operator walk away: loops every --check-min, watches the run, and EXITS with a verdict
(MATURED / CAP / TROUBLE) — stopping the agent on cap or trouble so the burn can't run away. The
harness notifies on exit, so the verdict reaches the operator without polling.

Signals (all read from the host-bind-mounted ledgers + docker, no extra instrumentation):
  * HEALTH — agent container up; ledgers growing (the WSL docker-orphan scar: a dead-but-billing
    agent shows as no ledger growth); zero `402 Payment` in agent logs.
  * DYADS — reciprocated address pairs per resident (R->P and P->R), with the brief's concentration
    bar (>=3 distinct dyads, top-dyad share < 50%). The first stop-line.
  * ELECTIVE SLICE (proxy) — person-addressed acts to an established peer who was NOT the most-recent
    heard speaker (i.e. not reply-reflex), summed per resident. A floor-estimate of the pilot-first
    salience-symmetric slice (live co-presence isn't in the ledger; the full measure is computed
    offline from recorded get_scene later). The second stop-line / go-no-go.

Exit: MATURED when BOTH stop-lines clear for >= --min-residents; CAP at --max-hours; TROUBLE on a
dead/stalled/402 agent persisting --trouble-strikes checks. On CAP/TROUBLE/MATURED it `docker stop`s
the agent (the run's ledgers survive on the host).

Usage (background):
    python3 scripts/pen_swap/monitor_grow.py --project ww_pdx_grow \\
        --residents-dir ../shards/ww_pdx_grow/residents --max-hours 10
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from collections import defaultdict
from pathlib import Path


def _sh(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return ""


def _agent_container(project: str) -> str:
    out = _sh(["docker", "ps", "--format", "{{.Names}}", "--filter", f"name={project}-agent"])
    return out.strip().splitlines()[0] if out.strip() else ""


def _ledger_lines(residents_dir: Path) -> int:
    total = 0
    for f in residents_dir.glob("*/memory/runtime_ledger.jsonl"):
        try:
            total += sum(1 for _ in f.open())
        except Exception:
            pass
    return total


def _addr_events(residents_dir: Path) -> dict[str, list[tuple[str, str]]]:
    """Per resident: ordered (addressed_peer, recent_speaker) for each person-addressed act.
    recent_speaker = the speaker of the last heard line before the act (reply-reflex tell)."""
    out: dict[str, list[tuple[str, str]]] = {}
    for f in residents_dir.glob("*/memory/runtime_ledger.jsonl"):
        name = f.parent.parent.name
        acts: list[tuple[str, str]] = []
        last_speaker = ""
        try:
            for line in f.open():
                if not line.strip():
                    continue
                e = json.loads(line)
                et = str(e.get("event_type") or "")
                p = e.get("payload") if isinstance(e.get("payload"), dict) else {}
                if et == "packet_emitted":
                    sp = str((p.get("speaker") or "")).strip().lower()
                    if sp:
                        last_speaker = sp
                elif et in {"chat_sent", "speech_carried", "city_broadcast_sent"}:
                    tgt = str((p.get("addressed") or p.get("recipient") or "")).strip().lower()
                    if tgt and tgt not in {"city", "__city__", "citywide", "broadcast"}:
                        acts.append((tgt, last_speaker))
        except Exception:
            pass
        out[name] = acts
    return out


def _analyze(residents_dir: Path) -> dict:
    addr = _addr_events(residents_dir)
    names = {n.strip().lower(): n for n in addr}
    # directed address counts A->B
    directed: dict[tuple[str, str], int] = defaultdict(int)
    for a, acts in addr.items():
        al = a.strip().lower()
        for tgt, _recent in acts:
            directed[(al, tgt)] += 1
    # reciprocated dyads + per-resident concentration
    per_dyads: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for (a, b), n in directed.items():
        if directed.get((b, a), 0) > 0 and a in names and b in names:
            per_dyads[a].append((b, n + directed.get((b, a), 0)))
    dyad_ok = 0
    for a, dyads in per_dyads.items():
        if len(dyads) >= 3:
            tot = sum(n for _, n in dyads)
            top = max(n for _, n in dyads)
            if tot and top / tot < 0.5:
                dyad_ok += 1
    # elective-slice proxy: addressed an ESTABLISHED peer (reciprocated) who was NOT the recent speaker
    established = {a: {b for b, _ in per_dyads.get(a, [])} for a in names}
    elective: dict[str, int] = defaultdict(int)
    for a, acts in addr.items():
        al = a.strip().lower()
        for tgt, recent in acts:
            if tgt in established.get(al, set()) and tgt != recent:
                elective[al] += 1
    return {
        "residents": len(addr),
        "addr_acts": sum(len(v) for v in addr.values()),
        "dyad_ok_residents": dyad_ok,
        "elective_total": sum(elective.values()),
        "elective_full": dict(elective),
        "elective_per": dict(sorted(elective.items(), key=lambda kv: -kv[1])[:5]),
        "reciprocated_pairs": sum(len(v) for v in per_dyads.values()) // 2,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Unattended maturation monitor.")
    ap.add_argument("--project", required=True, help="docker compose project (e.g. ww_pdx_grow)")
    ap.add_argument("--residents-dir", required=True, type=Path)
    ap.add_argument("--compose-file", default="")
    ap.add_argument("--max-hours", type=float, default=10.0)
    ap.add_argument("--check-min", type=float, default=20.0)
    ap.add_argument("--min-residents", type=int, default=6, help="residents that must clear both stop-lines")
    ap.add_argument("--target-elective", type=int, default=8, help="per-resident elective-slice floor")
    ap.add_argument("--trouble-strikes", type=int, default=3)
    args = ap.parse_args()

    start = time.time()
    last_lines = _ledger_lines(args.residents_dir)
    strikes = 0
    print(f"[monitor] start · project={args.project} · cap={args.max_hours}h · check every {args.check_min}m", flush=True)

    def stop_agent() -> None:
        c = _agent_container(args.project)
        if c:
            _sh(["docker", "stop", c])
            print(f"[monitor] stopped agent container {c}", flush=True)

    while True:
        time.sleep(args.check_min * 60)
        elapsed_h = (time.time() - start) / 3600.0
        container = _agent_container(args.project)
        lines = _ledger_lines(args.residents_dir)
        grew = lines - last_lines
        last_lines = lines
        logs = _sh(["bash", "-c", f"docker logs --since {int(args.check_min*60)+60}s {container} 2>&1 | grep -c '402 Payment'"]) if container else "0"
        pay402 = logs.strip() or "0"
        a = _analyze(args.residents_dir)
        elective_ok = sum(1 for n in a["elective_full"].values() if n >= args.target_elective)
        print(
            f"[monitor] t={elapsed_h:.1f}h | agent={'up' if container else 'DOWN'} | ledger+{grew} | 402={pay402} | " f"recip_pairs={a['reciprocated_pairs']} | dyad_ok={a['dyad_ok_residents']} | elective_total={a['elective_total']} | top_elective={a['elective_per']}",
            flush=True,
        )

        # TROUBLE: agent down, or no growth, or 402s
        if (not container) or grew <= 0 or pay402 != "0":
            strikes += 1
            print(f"[monitor] trouble strike {strikes}/{args.trouble_strikes} (agent={'up' if container else 'down'}, grew={grew}, 402={pay402})", flush=True)
            if strikes >= args.trouble_strikes:
                stop_agent()
                print(f"[monitor] VERDICT=TROUBLE after {elapsed_h:.1f}h — agent unhealthy. Ledgers preserved on host.", flush=True)
                return 2
        else:
            strikes = 0

        # MATURED: both stop-lines for enough residents
        if a["dyad_ok_residents"] >= args.min_residents and elective_ok >= args.min_residents:
            stop_agent()
            print(f"[monitor] VERDICT=MATURED at {elapsed_h:.1f}h — {a['dyad_ok_residents']} dyad-ok, {elective_ok} elective-ok residents.", flush=True)
            return 0

        # CAP
        if elapsed_h >= args.max_hours:
            stop_agent()
            print(f"[monitor] VERDICT=CAP at {elapsed_h:.1f}h — stop-lines not both cleared (dyad_ok={a['dyad_ok_residents']}, elective_total={a['elective_total']}). The slice size IS the pilot-first result.", flush=True)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
