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
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime

# answer windows (seconds) for the turn-taking sensitivity band; None = unbounded-forward
WINDOWS = [300, 900, 1800, 3600, None]
# windows that get the chance-baseline null + dyad concentration (the headline is 5 min)
NULL_WINDOWS = [300, 900]
NULL_DRAWS = 400          # Mr. Review's count; reproducible via NULL_SEED
NULL_SEED = 12345


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


MIN_PERCEIVED_OVERTURES = 20  # below this the perceived-conditioned rate is INCONCLUSIVE (a power gate, not a bias fix)


def perceived_conditioned(root):
    """Major 66 perceived-conditioned reciprocity (Mr. Review's locked secondary metric).

    numerator   = person-addressed overtures a resident PERCEIVED *and ANSWERED* (the answer
                  carries an `in_reply_to` reply-edge pointing at the overture's stable id).
    denominator = person-addressed overtures the resident actually PERCEIVED (`is_direct`
                  heard packets) — channel-agnostic (room speech + city broadcast).
    Conditions on DELIVERY, not co-presence: don't penalize A for B never hearing. Both halves
    live in the same resident's ledger, linked by the backend msg id — no cross-resident match.
    """
    import glob
    denom = 0
    answered = 0
    dyads = Counter()
    for f in glob.glob(os.path.join(root, "residents", "*", "memory", "runtime_ledger.jsonl")):
        perceived = {}        # overture_id -> sender (is_direct overtures TO this resident)
        answered_ids = set()  # overture ids this resident replied to
        for line in open(f):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            et = e.get("event_type")
            p = e.get("payload", {}) or {}
            if et == "packet_emitted" and p.get("packet_type") in ("chat_heard", "city_chat_heard"):
                inner = p.get("payload", {}) or {}
                if inner.get("is_direct") and inner.get("id"):
                    perceived[str(inner["id"])] = str(inner.get("speaker") or "")
            elif et in ("chat_sent", "city_broadcast_sent", "speech_carried") and p.get("in_reply_to"):
                answered_ids.add(str(p["in_reply_to"]))
        denom += len(perceived)
        me = os.path.basename(os.path.dirname(os.path.dirname(f)))
        for oid, sender in perceived.items():
            if oid in answered_ids:
                answered += 1
                dyads[frozenset((me, sender))] += 1
    top = max(dyads.values()) if dyads else 0
    return {
        "perceived_overtures": denom,
        "answered": answered,
        "rate_pct": (100.0 * answered / denom) if denom else 0.0,
        "dyads": len(dyads),
        "top_dyad_share_pct": (100.0 * top / answered) if answered else 0.0,
        "inconclusive": denom < MIN_PERCEIVED_OVERTURES,
    }


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


def _answered_count(rows_dt, window):
    """rows_dt: list of (speaker, target, datetime). A->B answered iff a later B->A within window."""
    by_pair = defaultdict(list)
    for spk, tgt, dt in rows_dt:
        by_pair[(spk, tgt)].append(dt)
    answered = 0
    for spk, tgt, dt in rows_dt:
        backs = by_pair.get((tgt, spk), ())
        if window is None:
            if any(b > dt for b in backs):
                answered += 1
        elif any(0 < (b - dt).total_seconds() <= window for b in backs):
            answered += 1
    return answered


def _shuffle_null(rows_dt, window, draws=NULL_DRAWS, seed=NULL_SEED):
    """Degree-preserving target-shuffle null (Mr. Review's control). Hold each speaker's
    volume and the global in-degree (target multiset) fixed; permute who-addresses-whom;
    recompute the answer rate. Asks: is real turn-taking above what same-volume co-present
    chatter would produce? Returns null mean/pct and z = (REAL - null_mean) / null_sd."""
    n = len(rows_dt)
    if n < 2:
        return {"null_pct": 0.0, "z": 0.0, "draws": 0}
    rng = random.Random(seed)
    speakers = [r[0] for r in rows_dt]
    targets = [r[1] for r in rows_dt]
    dts = [r[2] for r in rows_dt]
    counts = []
    for _ in range(draws):
        shuf = targets[:]
        rng.shuffle(shuf)
        counts.append(_answered_count(list(zip(speakers, shuf, dts)), window))
    mean = statistics.fmean(counts)
    sd = statistics.pstdev(counts)
    real = _answered_count(rows_dt, window)
    z = (real - mean) / sd if sd > 0 else 0.0
    return {"null_pct": 100.0 * mean / n, "z": z, "draws": draws}


def _concentration(rows_dt, window):
    """Distinct dyads carrying the answered utterances @window, and the top dyad's share."""
    by_pair = defaultdict(list)
    for spk, tgt, dt in rows_dt:
        by_pair[(spk, tgt)].append(dt)
    dyad = Counter()
    total = 0
    for spk, tgt, dt in rows_dt:
        backs = by_pair.get((tgt, spk), ())
        hit = any(b > dt for b in backs) if window is None else any(0 < (b - dt).total_seconds() <= window for b in backs)
        if hit:
            total += 1
            dyad[frozenset((spk, tgt))] += 1
    top = max(dyad.values()) if dyad else 0
    return {"answered": total, "dyads": len(dyad), "top_dyad_share_pct": (100.0 * top / total) if total else 0.0}


def analyze(root):
    names = _display_names(root)
    rows, moves, speaks, person_speaks = _utterances(root, names)
    rows_dt = [(spk, tgt, _parse_ts(ts)) for spk, tgt, ts, _ in rows]
    rows_dt = [r for r in rows_dt if r[2] is not None]
    n_addr = len(rows)

    band = {win: (_answered_count(rows_dt, win), 100.0 * _answered_count(rows_dt, win) / n_addr if n_addr else 0.0) for win in WINDOWS}

    by_pair = defaultdict(list)
    for spk, tgt, dt in rows_dt:
        by_pair[(spk, tgt)].append(dt)
    ordered_pairs = set(by_pair.keys())
    reciprocated_pairs = sum(1 for (a, b) in ordered_pairs if (b, a) in by_pair)

    null = {w: _shuffle_null(rows_dt, w) for w in NULL_WINDOWS}
    conc = {w: _concentration(rows_dt, w) for w in NULL_WINDOWS}

    return {
        "people": len(names),
        "speaks": speaks,
        "person_addressed": person_speaks,
        "city_broadcast_speaks": speaks - person_speaks,
        "moves": moves,
        "outwardness_pct": (100.0 * person_speaks / speaks) if speaks else 0.0,
        "addressed_utterances": n_addr,
        "band": band,
        "null": null,
        "concentration": conc,
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
        print("  vs degree-preserving target-shuffle NULL  (engagement = z>2 AND >=3 dyads AND top-share<50%):")
        for win in NULL_WINDOWS:
            ans, pct = r["band"][win]
            nz = r["null"][win]
            c = r["concentration"][win]
            verdict = "ABOVE chance" if nz["z"] > 2 else ("at/below chance" if nz["z"] < 1 else "marginal")
            wl = f"{win // 60}min"
            print(f"      @{wl:>5}: REAL {pct:4.1f}% ({ans})  vs NULL {nz['null_pct']:4.1f}%  z {nz['z']:+.1f}  -> {verdict}")
            print(f"             carried by {c['dyads']} dyad(s), top-dyad share {c['top_dyad_share_pct']:.0f}%")
        print(f"  pair-lenient (reverse pair exists at all): {r['pair_lenient_pct']:.1f}%   "
              f"({r['ordered_pairs']} ordered pairs)  <- trivially satisfied, not a signal")
        pc = perceived_conditioned(root)
        gate = "  [INCONCLUSIVE: too few perceived overtures]" if pc["inconclusive"] else ""
        print("  PERCEIVED-CONDITIONED reply-edge (Major 66 secondary; deliver-conditioned, no window):")
        print(f"      answered {pc['answered']} / {pc['perceived_overtures']} perceived overtures-to-self = "
              f"{pc['rate_pct']:.1f}%{gate}")
        print(f"      carried by {pc['dyads']} dyad(s), top-dyad share {pc['top_dyad_share_pct']:.0f}%  "
              f"(engagement bar: >=3 dyads & top-share<50%)")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
