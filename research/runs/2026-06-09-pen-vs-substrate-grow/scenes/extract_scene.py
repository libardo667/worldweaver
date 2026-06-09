#!/usr/bin/env python3
"""Scene extractor — reconstruct a cohort-wide event from the KEEP run's per-resident ledgers.

Reusable on purpose: point it at the live recording dir now (mid-run snapshot) or at the frozen
recording at completion; same code → same artifact. It reads each resident's runtime_ledger.jsonl,
keeps only events at/after --since (the fresh-world boot, NOT the carried maturation history), and
emits an ordered transcript + the scene metrics (channel mix, directed person→person edges, keeps).

The point of the artifact: a natural experiment captured in this run — a shared high-salience event
(the Albina structural emergency) where the cohort's designated D2 ISOLATE (Mateo Villanueva) became
the most-addressed person *because the world put him at the epicenter*, not because of relationships.
That is the salience-gradient confound `portraits/choice_points.py` subtracts out — so this scene is
the worked example of WHY the primary metric is the salience-SYMMETRIC subset, not the raw edge graph.

Usage:
    python3 extract_scene.py --residents-dir /tmp/keep_d2_280 \
        --since 2026-06-09T19:27:00+00:00 \
        --roster ../D2-checkpoint/roster.tsv \
        --out-dir albina-structural-event
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent


def norm(x: str) -> str:
    return re.sub(r"[\s_\-]+", " ", str(x or "").strip().lower())


def load_roster(path: Path) -> dict[str, str]:
    roster: dict[str, str] = {}
    if path and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) >= 2:
                roster[parts[0]] = parts[1]
    return roster


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--residents-dir", type=Path, required=True, help="dir of <slug>/memory/runtime_ledger.jsonl")
    ap.add_argument("--since", default="2026-06-09T19:27:00+00:00", help="ISO cutoff: keep events at/after this (the fresh-world boot)")
    ap.add_argument("--roster", type=Path, default=HERE.parent / "D2-checkpoint" / "roster.tsv")
    ap.add_argument("--out-dir", type=Path, required=True, help="artifact dir (created under scenes/)")
    a = ap.parse_args()

    cut = datetime.fromisoformat(a.since)
    roster = load_roster(a.roster)
    rd: Path = a.residents_dir
    slugs = sorted(p.name for p in rd.iterdir() if (p / "memory" / "runtime_ledger.jsonl").exists())
    if not slugs:
        print(f"no resident ledgers under {rd}")
        return 1
    if not roster:
        roster = {s: s for s in slugs}

    name2slug = {norm(roster.get(s, s)): s for s in slugs}
    firsts: dict[str, list[str]] = collections.defaultdict(list)
    for s in slugs:
        firsts[norm(roster.get(s, s)).split(" ")[0]].append(s)

    def resolve(tgt: str) -> str | None:
        tn = norm(tgt)
        if tn in name2slug:
            return name2slug[tn]
        if tn in firsts and len(firsts[tn]) == 1:
            return firsts[tn][0]
        return None

    acts: list[tuple[str, str, str, str]] = []  # ts, speaker_slug, target, body
    keeps: collections.Counter = collections.Counter()
    keep_notes: dict[str, list[str]] = collections.defaultdict(list)
    chan: collections.Counter = collections.Counter()
    edges: collections.Counter = collections.Counter()
    max_tick = 0

    for s in slugs:
        for line in (rd / s / "memory" / "runtime_ledger.jsonl").open(encoding="utf-8"):
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                if datetime.fromisoformat(d["ts"]) < cut:
                    continue
            except (KeyError, ValueError):
                continue
            et = d.get("event_type")
            pl = d.get("payload", {}) or {}
            if et == "memory_kept":
                keeps[s] += 1
                if pl.get("note"):
                    keep_notes[s].append(str(pl["note"]))
            elif et == "pulse_act_emitted" and pl.get("kind") == "speak":
                tgt = str(pl.get("target") or "").strip()
                body = str(pl.get("body") or "")
                acts.append((d["ts"], s, tgt, body))
                tn = norm(tgt)
                rs = resolve(tgt)
                if tn in ("city", "__city__", ""):
                    chan["city/broadcast"] += 1
                elif rs is not None:
                    chan["person"] += 1
                    edges[(s, rs)] += 1
                elif "dm" in tn:
                    chan["dm"] += 1
                else:
                    chan[f"room/{tgt}"] += 1
        # max recorded tick (for snapshot labeling)
        rec = rd / s / "memory" / "keep_recording.jsonl"
        if rec.exists():
            for line in rec.open(encoding="utf-8"):
                try:
                    max_tick = max(max_tick, int(json.loads(line).get("tick", 0)))
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass

    acts.sort()
    out = HERE / a.out_dir
    out.mkdir(parents=True, exist_ok=True)

    with (out / "scene_transcript.tsv").open("w", encoding="utf-8") as fh:
        fh.write("ts\tspeaker\ttarget\tbody\n")
        for ts, s, tgt, body in acts:
            fh.write(f"{ts}\t{roster.get(s, s)}\t{tgt}\t{body}\n")

    recip = {f"{roster.get(a_,a_)}->{roster.get(b_,b_)}": v for (a_, b_), v in edges.most_common()}
    metrics = {
        "residents_dir": str(rd),
        "since": a.since,
        "snapshot_tick": max_tick,
        "n_speak_acts": len(acts),
        "channel_mix": dict(chan.most_common()),
        "keeps_total": sum(keeps.values()),
        "keeps_per_resident": {roster.get(s, s): keeps[s] for s in sorted(keeps, key=lambda x: -keeps[x])},
        "top_person_edges": dict(list(recip.items())[:25]),
        "recipient_in_degree": dict(collections.Counter(roster.get(b, b) for (a_, b), v in edges.items() for _ in range(v)).most_common(10)),
    }
    (out / "scene_metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"snapshot tick ~{max_tick} | {len(acts)} speak acts | channel mix {dict(chan.most_common())}")
    print(f"recipient in-degree (top): {metrics['recipient_in_degree']}")
    print(f"wrote {out/'scene_transcript.tsv'} and {out/'scene_metrics.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
