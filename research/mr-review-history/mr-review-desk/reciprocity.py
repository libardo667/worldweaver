#!/usr/bin/env python3
"""reciprocity.py — addressed-AND-answered turn-taking reader for a frozen cohort.

The `three_axis` CONTACT axis computes *outwardness* (an utterance aimed at a named
person), not *engagement*. This reader separates the two and computes the thing that
actually carries a "we": does the addressed party answer back?

For a cohort root (a dir containing `residents/<name>/memory/runtime_ledger.jsonl`):

  - speak volume, and what fraction is addressed to a PERSON vs broadcast to 'city'
  - OUTWARDNESS  = person-addressed speaks / total speaks  (what three_axis sees)
  - RECIPROCITY  = of A->B person-addressed utterances, the fraction that B later
                   answers with a B->A person-addressed utterance  (the real signal)
  - pair-lenient = of ordered pairs (A->B) that occur, fraction whose reverse (B->A)
                   occurs at all  (the trivially-satisfied number; reported to expose it)
  - moves        = physical move acts (the venture motor signal)

Usage:  reciprocity.py <cohort_root> [<cohort_root> ...]
A cohort_root is a directory that contains a `residents/` subtree.
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

# answer windows (seconds) for the turn-taking sensitivity band; None = unbounded-forward
WINDOWS = [300, 900, 1800, 3600, None]


def _parse_ts(ts):
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _display_names(root):
    """resident_dir -> display name (IDENTITY.md H1)."""
    names = {}
    rdir = os.path.join(root, "residents")
    for d in sorted(os.listdir(rdir)):
        idp = os.path.join(rdir, d, "identity", "IDENTITY.md")
        nm = d
        if os.path.exists(idp):
            with open(idp) as fh:
                first = fh.readline().strip()
            if first.startswith("#"):
                nm = first.lstrip("# ").strip()
        names[d] = nm
    return names


def _utterances(root, names):
    """Yield (speaker_display, target_display_or_'city', ts, kind) over the cohort, ts-sorted."""
    rows = []
    moves = 0
    speaks = 0
    person_speaks = 0
    rdir = os.path.join(root, "residents")
    for d in sorted(os.listdir(rdir)):
        lp = os.path.join(rdir, d, "memory", "runtime_ledger.jsonl")
        if not os.path.exists(lp):
            continue
        speaker = names.get(d, d)
        for line in open(lp):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("event_type") != "pulse_act_emitted":
                continue
            p = e.get("payload", {}) or {}
            k = p.get("kind")
            if k == "move":
                moves += 1
            if k != "speak":
                continue
            speaks += 1
            target = p.get("target")
            if target and target != "city":
                person_speaks += 1
                rows.append((speaker, target, e.get("ts", ""), k))
    rows.sort(key=lambda r: r[2])
    return rows, moves, speaks, person_speaks


def analyze(root):
    names = _display_names(root)
    rows, moves, speaks, person_speaks = _utterances(root, names)

    # windowed per-utterance turn-taking: A->B "answered" if B emits B->A within W seconds
    # index B->A occurrences by (speaker, target) -> sorted datetime list
    by_pair = defaultdict(list)
    for spk, tgt, ts, _ in rows:
        dt = _parse_ts(ts)
        if dt is not None:
            by_pair[(spk, tgt)].append(dt)
    for k in by_pair:
        by_pair[k].sort()

    n_addr = len(rows)
    band = {}
    for win in WINDOWS:
        answered = 0
        for spk, tgt, ts, _ in rows:
            dt = _parse_ts(ts)
            if dt is None:
                continue
            backs = by_pair.get((tgt, spk), [])
            if win is None:
                hit = any(b > dt for b in backs)
            else:
                hit = any(0 < (b - dt).total_seconds() <= win for b in backs)
            if hit:
                answered += 1
        band[win] = (answered, 100.0 * answered / n_addr if n_addr else 0.0)

    # pair-lenient: ordered pairs whose reverse occurs at all (the trivially-satisfied number)
    ordered_pairs = set(by_pair.keys())
    reciprocated_pairs = sum(1 for (a, b) in ordered_pairs if (b, a) in by_pair)

    return {
        "people": len(names),
        "speaks": speaks,
        "person_addressed": person_speaks,
        "city_broadcast_speaks": speaks - person_speaks,
        "moves": moves,
        "outwardness_pct": (100.0 * person_speaks / speaks) if speaks else 0.0,
        "addressed_utterances": n_addr,
        "band": band,
        "ordered_pairs": len(ordered_pairs),
        "pair_lenient_pct": (100.0 * reciprocated_pairs / len(ordered_pairs)) if ordered_pairs else 0.0,
    }


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    for root in argv:
        r = analyze(root)
        label = os.path.basename(os.path.normpath(root))
        print(f"=== {label} ===  people={r['people']}")
        print(f"  speaks={r['speaks']}  person-addressed={r['person_addressed']}  "
              f"city-broadcast={r['city_broadcast_speaks']}  moves={r['moves']}")
        print(f"  OUTWARDNESS (person-addressed / speaks) : {r['outwardness_pct']:.1f}%   "
              f"(what three_axis CONTACT sees)")
        print(f"  TURN-TAKING band (A->B answered by B->A within window, of {r['addressed_utterances']} addressed):")
        for win in WINDOWS:
            ans, pct = r["band"][win]
            wl = "unbounded" if win is None else f"{win // 60:>2}min"
            print(f"      within {wl:>9}: {pct:5.1f}%  ({ans})")
        print(f"  pair-lenient (reverse pair exists at all): {r['pair_lenient_pct']:.1f}%   "
              f"({r['ordered_pairs']} ordered pairs)  <- trivially satisfied, not a signal")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
