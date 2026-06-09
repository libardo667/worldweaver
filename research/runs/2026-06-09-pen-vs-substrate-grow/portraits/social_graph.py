#!/usr/bin/env python3
"""Animate the cohort's social graph weaving itself over the maturation run.

Cold-reproducible from ./evidence/kept_memory + roster.tsv. An undirected edge A-B thickens as the two
accumulate kept memories about each other (resolve-or-flag: full name, or cohort-unique first name;
ambiguous bare names are dropped, not guessed). Node colour = geographic home cluster; node size grows
with how many memories others keep ABOUT them (in-degree) — so hubs swell. Layout is fixed (computed
once on the final graph) so nodes hold still and only the fabric moves.

Outputs to ./viz/ : social_graph.gif (the animation), social_graph_final.png, social_graph_D1.png.
Usage: python3 social_graph.py [--frames 48] [--fps 6]
"""
import argparse, json, re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import networkx as nx
import imageio.v2 as imageio

HERE = Path(__file__).resolve().parent
SNAP = HERE / "evidence"
OUT = HERE / "viz"
OUT.mkdir(exist_ok=True)
D1_TS = "2026-06-09T12:32:00+00:00"  # the extent-plateau MATURED moment (shallow checkpoint)


def norm(x):
    return re.sub(r"[\s_\-]+", " ", str(x or "").strip().lower())


def load():
    R = {}
    for line in (SNAP / "roster.tsv").read_text().splitlines()[1:]:
        slug, name, home = (line.split("\t") + ["", "", ""])[:3]
        R[slug] = dict(name=name, label=name.split()[0] + " " + name.split()[-1][0], home=home)
    firsts = defaultdict(list)
    for s, d in R.items():
        firsts[norm(d["name"]).split(" ")[0]].append(s)
    events = []  # (datetime, keeper, target)
    for s in R:
        for l in (SNAP / "kept_memory" / f"{s}.jsonl").open():
            if not l.strip():
                continue
            d = json.loads(l)
            note, ts = norm(d.get("note", "")), d.get("kept_ts")
            if not ts:
                continue
            t = datetime.fromisoformat(ts)
            for s2, d2 in R.items():
                if s2 == s:
                    continue
                disp = norm(d2["name"]); fn = disp.split(" ")[0]
                if re.search(r"\b" + re.escape(disp) + r"\b", note) or (len(firsts[fn]) == 1 and re.search(r"\b" + re.escape(fn) + r"\b", note)):
                    events.append((t, s, s2))
    events.sort()
    return R, events


def fixed_layout(R, events):
    """Cluster-seeded spring layout on the final reciprocity-weighted graph — clusters group, hubs centre."""
    homes = sorted({d["home"] for d in R.values()})
    ang = {h: 2 * np.pi * i / len(homes) for i, h in enumerate(homes)}
    init = {}
    rng = np.random.default_rng(7)
    for s, d in R.items():
        c = np.array([np.cos(ang[d["home"]]), np.sin(ang[d["home"]])]) * 3.0
        init[s] = c + rng.normal(0, 0.4, 2)
    G = nx.Graph()
    G.add_nodes_from(R)
    w = Counter()
    for _, a, b in events:
        w[tuple(sorted((a, b)))] += 1
    for (a, b), c in w.items():
        G.add_edge(a, b, weight=c)
    return nx.spring_layout(G, pos=init, weight="weight", seed=7, iterations=60, k=0.9)


def render(R, events, pos, upto, homes, cmap, title):
    fig, ax = plt.subplots(figsize=(9, 9), dpi=110)
    ax.set_axis_off()
    cur = [(a, b) for (t, a, b) in events if t <= upto]
    dirw = Counter(cur)
    indeg = Counter(b for _, b in [(a, b) for a, b in cur])
    # edges: undirected, width ~ total weight; reciprocated darker
    seen = set()
    for a, b in set((min(x, y), max(x, y)) for x, y in dirw):
        fwd, rev = dirw[(a, b)] + dirw[(b, a)], 0
        recip = dirw[(a, b)] > 0 and dirw[(b, a)] > 0
        tot = dirw[(a, b)] + dirw[(b, a)]
        x = [pos[a][0], pos[b][0]]; y = [pos[a][1], pos[b][1]]
        ax.plot(x, y, "-", lw=min(0.4 + tot * 0.25, 5.0), alpha=min(0.15 + tot * 0.06, 0.85),
                color=("#222222" if recip else "#bbbbbb"), zorder=1, solid_capstyle="round")
    # nodes
    for s, d in R.items():
        size = 120 + 70 * indeg.get(s, 0)
        ax.scatter(*pos[s], s=size, color=cmap[d["home"]], edgecolors="white", linewidths=1.2, zorder=2)
        ax.text(pos[s][0], pos[s][1], d["label"], ha="center", va="center", fontsize=7, zorder=4,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.65))
    xs = [p[0] for p in pos.values()]; ys = [p[1] for p in pos.values()]
    px = (max(xs) - min(xs)) * 0.18 + 0.6; py = (max(ys) - min(ys)) * 0.20 + 0.6
    ax.set_xlim(min(xs) - px, max(xs) + px); ax.set_ylim(min(ys) - py, max(ys) + py)
    ax.set_title(title, fontsize=13)
    handles = [plt.Line2D([0], [0], marker="o", ls="", mfc=cmap[h], mec="white", ms=10, label=h) for h in homes]
    ax.legend(handles=handles, loc="upper left", fontsize=8, frameon=False, title="home cluster")
    fig.tight_layout()
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()
    return fig, buf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=48)
    ap.add_argument("--fps", type=int, default=6)
    a = ap.parse_args()
    R, events = load()
    pos = fixed_layout(R, events)
    homes = sorted({d["home"] for d in R.values()})
    palette = ["#e6194B", "#3cb44b", "#4363d8", "#f58231"]
    cmap = {h: palette[i % len(palette)] for i, h in enumerate(homes)}
    t0, t1 = events[0][0], events[-1][0]
    span = (t1 - t0).total_seconds()

    frames = []
    for i in range(a.frames):
        tf = t0 + timedelta(seconds=span * (i + 1) / a.frames)
        n = sum(1 for t, _, _ in events if t <= tf)
        fig, buf = render(R, events, pos, tf, homes, cmap, f"the cohort gets to know itself — {tf:%H:%M} · {n} keeps logged")
        frames.append(buf)
        plt.close(fig)
    frames += [frames[-1]] * (a.fps * 2)  # hold on the finished graph
    imageio.mimsave(OUT / "social_graph.gif", frames, fps=a.fps, loop=0)

    # static snapshots: D1 (shallow) and final
    d1 = datetime.fromisoformat(D1_TS)
    for upto, name, tag in [(d1, "social_graph_D1.png", f"D1 (extent-plateau) — {d1:%H:%M}"), (t1, "social_graph_final.png", f"final — {t1:%H:%M}")]:
        n = sum(1 for t, _, _ in events if t <= upto)
        fig, _ = render(R, events, pos, upto, homes, cmap, f"{tag} · {n} keeps logged")
        fig.savefig(OUT / name, dpi=120)
        plt.close(fig)
    print(f"wrote {OUT}/social_graph.gif (+ D1 & final PNGs) | {len(events)} resolved keep-edges, span {t0:%H:%M}-{t1:%H:%M}")


if __name__ == "__main__":
    raise SystemExit(main())
