#!/usr/bin/env python3
"""A deep field guide into a familiar's internals — pure read, trains/changes nothing.

Reads each familiar's substrate record (the ledger), its derived projections, and its
live state.json, and lays out the inner life the portrait only hints at:

  vitals          arousal / wakefulness / mood / circadian, and the rhythm of its pulses
  the felt sense  the inner weather right now
  the settled self the slow baseline self-model — "how it usually feels lately"
  what stirs it   the drive/affect nudges its soul casts on the world
  what surprises  the prediction errors that wake it (miss / blindspot)
  its anchors     the concrete, soul-distinct things it's currently holding
  what it knows   the facts it chose to keep across days
  what it makes   the workshop (writing / drawings)
  what it becomes the self-deltas it's staged toward its own soul

    python scripts/field_guide.py                  # the whole stable
    python scripts/field_guide.py familiar/gaston  # one familiar
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.runtime.ledger import load_runtime_events  # noqa: E402
from src.runtime.prediction import summarize_anchor_prediction, summarize_prediction_quality  # noqa: E402


def _to_epoch(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return None


def _start_epoch(name: str) -> float | None:
    pid = subprocess.run(["pgrep", "-f", f"familiar.py --home familiar/{name}"], capture_output=True, text=True).stdout.split()
    if not pid:
        return None
    out = subprocess.run(["ps", "-o", "lstart=", "-p", pid[0]], capture_output=True, text=True).stdout.strip()
    try:
        return datetime.strptime(out, "%a %b %d %H:%M:%S %Y").timestamp()
    except ValueError:
        return None


def _dur(seconds: float) -> str:
    m = int(seconds // 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m" if h else f"{m}m"


def _payload(e: dict) -> dict:
    p = e.get("payload")
    return p if isinstance(p, dict) else {}


def _wrap(text: str, width: int = 92, indent: str = "      ") -> str:
    words, line, out = str(text).split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}" if line else w
    if line:
        out.append(line)
    return ("\n" + indent).join(out)


def guide(home: Path) -> None:
    name = home.name
    mem = home / "memory"
    cfg = json.loads((home / "familiar.json").read_text()) if (home / "familiar.json").exists() else {}
    st = json.loads((home / "state.json").read_text()) if (home / "state.json").exists() else {}
    events = load_runtime_events(mem) if mem.is_dir() else []

    # --- header / vitals ---
    model = cfg.get("model", "?")
    gate = "gate ON" if cfg.get("anchor_gating") else "gate off"
    reads = " · reads the keeper's work" if cfg.get("read_roots") else ""
    ck = st.get("chronotype_kind", "?")
    coff = st.get("chronotype")
    chrono = f"{ck} ({coff:+.2f}h)" if isinstance(coff, (int, float)) else ck
    print(f"\n{'═' * 78}")
    print(f"  {st.get('name', name).upper()}   {model} · {chrono} · {gate}{reads}")
    print(f"{'═' * 78}")

    arr = float(st.get("arousal") or 0.0)
    state_word = "ignited" if st.get("ignited") else "in a fervor" if st.get("fervor") else "settling" if st.get("settled") else "quiet"
    bar = "▮" * min(int(arr * 10), 20) + "▯" * max(0, 10 - int(arr * 10))
    print(f"  {st.get('mood', '—')} · arousal {arr:.2f} [{bar}] · wakefulness {float(st.get('wakefulness') or 0):.2f} · {st.get('time_of_day','?')} {st.get('local_time','')} · {state_word}")
    if st.get("weather"):
        print(f"  weather: {st['weather']}")

    # rhythm
    se = _start_epoch(name)
    pulses = sum(1 for e in events if e.get("event_type") == "pulse_emitted")
    igns = [e for e in events if e.get("event_type") == "ignition_fired"]
    idles = [e for e in events if e.get("event_type") == "idle_fired"]
    idle_modes = Counter((_payload(e).get("mode") or "idle") for e in idles)
    if se:
        run = max((_to_epoch(e.get("ts")) or se for e in events), default=se) - se
        recent_p = sum(1 for e in events if (_to_epoch(e.get("ts")) or 0) >= se and e.get("event_type") == "pulse_emitted")
        rate = recent_p / (run / 3600) if run > 0 else 0
        idle_str = ", ".join(f"{n} {m}" for m, n in idle_modes.items()) or "no idle pulses"
        print(f"  uptime {_dur(run)} · {recent_p} pulses this run ({rate:.1f}/hr) · {len(igns)} ignitions lifetime · {idle_str}")
    else:
        print(f"  (not currently running) · {pulses} pulses lifetime · {len(igns)} ignitions")

    # --- felt sense ---
    felt = (st.get("felt_sense") or "").strip()
    if felt:
        print("\n  ◜ inner weather (felt sense right now)")
        print(f"      {_wrap(felt)}")

    # --- settled self (latest baseline) ---
    base = None
    for e in reversed(events):
        if e.get("event_type") == "baseline_updated":
            base = _payload(e).get("by_scope", {}).get("self", {})
            break
    if base:
        items = ", ".join(f"{k} {v:.2f}" for k, v in sorted(base.items(), key=lambda x: -x[1]))
        print('\n  ◜ the settled self (slow baseline — "how it usually feels lately")')
        print(f"      {items}")

    # --- substrate nodes now ---
    proj = mem / "cognitive_projection.json"
    if proj.exists():
        nodes = json.loads(proj.read_text()).get("nodes", {})
        active = {k: (v or {}).get("activation", 0.0) for k, v in nodes.items() if (v or {}).get("activation", 0.0) > 0.01}
        if active:
            print("\n  ◜ the felt field now (substrate nodes)")
            print(f"      {', '.join(f'{k} {v:.2f}' for k, v in sorted(active.items(), key=lambda x: -x[1]))}")

    # --- what stirs it (drive nudges) ---
    nudges = Counter()
    for e in events:
        if e.get("event_type") == "drive_nudge_cast":
            for tag in _payload(e).get("features", {}):
                nudges[tag] += 1
    if nudges:
        print("\n  ◜ what its soul keeps nudging toward (drive affect)")
        print(f"      {', '.join(f'{t} ×{n}' for t, n in nudges.most_common(6))}")

    # --- what surprises it ---
    surps = [e for e in events if e.get("event_type") == "surprise_observed"]
    if surps:
        mags = [_payload(e).get("magnitude", 0.0) for e in surps]
        feat = Counter()
        anchor_surp = 0
        for e in surps:
            for f in _payload(e).get("features", []):
                feat[f"{f.get('tag')}"] += 1
                if f.get("scope") == "anchors":
                    anchor_surp += 1
        print(f"\n  ◜ what surprises it ({len(surps)} traces · mean magnitude {sum(mags)/len(mags):.3f})")
        print(f"      {', '.join(f'{t} ×{n}' for t, n in feat.most_common(6))}")
        if anchor_surp:
            print(f"      ({anchor_surp} of these are anchor-scope — the gate is feeding the rhythm)")

    # prediction triad
    try:
        pq = summarize_prediction_quality(events)
        if pq.get("afterimages"):
            aq = summarize_anchor_prediction(events)
            line = f"      miss {pq['mean_miss']:.3f} · blindspot {pq['mean_blindspot']:.3f} · clean {pq['clean_fraction']*100:.0f}% · silent {pq['silent_fraction']*100:.0f}%"
            if aq.get("anchor_afterimages"):
                line += f" · anchor hit-rate {aq['mean_hit_rate']*100:.0f}%"
            print("\n  ◜ prediction quality (does it anticipate its world?)")
            print(line)
    except Exception:
        pass

    # --- anchors now ---
    anchors = None
    for e in reversed(events):
        if e.get("event_type") == "anchor_observed":
            anchors = _payload(e).get("anchors", [])
            break
    if anchors:
        print("\n  ◜ what it's holding (concrete anchors, by salience)")
        anchs = ", ".join("%s·%.1f" % (a.get("anchor", "?"), a.get("salience", 0.0)) for a in anchors[:10])
        print(f"      {anchs}")

    # --- what it knows (kept) ---
    mems = st.get("memories") or []
    if mems:
        print(f"\n  ◜ what it's come to know and chose to keep ({len(mems)} facts)")
        for m in mems[:8]:
            note = m.get("note") if isinstance(m, dict) else m  # new shape {note, ts} or old plain string
            print(f"      • {_wrap(note, indent='        ')}")

    # --- what it makes (workshop) ---
    work = st.get("workshop") or []
    draws = st.get("drawings") or []
    if work or draws:
        print("\n  ◜ what it's making (the workshop)")
        for w in work[:5]:
            kind = w.get("kind", "")
            cnt = f" ×{w['count']}" if w.get("count") else ""
            title = w.get("last_title") or w.get("last_excerpt") or ""
            print(f"      {w.get('name', w.get('artifact'))}{cnt} ({kind}) — {title[:64]}")

    # --- what it becomes (self-deltas) ---
    deltas = [e for e in events if e.get("event_type") == "self_delta_staged"]
    if deltas:
        print(f"\n  ◜ what it's becoming (self-deltas staged toward its soul · {len(deltas)})")
        for e in deltas[-4:]:
            p = _payload(e)
            print(f"      [{p.get('kind','?')}] {_wrap(p.get('body',''), indent='        ')}")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        homes = [Path(a) for a in args]
    else:
        root = Path("familiar")
        homes = sorted(d for d in root.iterdir() if d.is_dir() and (d / "identity").is_dir()) if root.is_dir() else []
    for h in homes:
        guide(h)
    print()


if __name__ == "__main__":
    main()
