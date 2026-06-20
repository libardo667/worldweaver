#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""prune_pick.py — an egalitarian work-item picker across the prune ledgers.

Recency bias quietly turns the backlog into a monoculture: whatever is loudest and
most recent gets attended to, and the long tail rots. This is the same dynamics the
project studies in its residents, pointed at the keeper's own attention. So: pool the
*actionable* work items from worldweaver/prune and the-stable/prune, weight the draw by
staleness (the longest-neglected item gets the best odds — a refugia mechanism for
forgotten work), and nominate a shortlist. Draw N, you pick one (or reroll).

Pooling both repos tilts naturally toward worldweaver, the larger backlog; --repo narrows.

    python3 scripts/prune_pick.py                      # 3 nominations across both repos
    python3 scripts/prune_pick.py -n 5                 # a bigger shortlist
    python3 scripts/prune_pick.py --repo the-stable    # one repo only
    python3 scripts/prune_pick.py --kind minor         # bounded items only
    python3 scripts/prune_pick.py --list               # show the whole eligible pool, stalest first
    python3 scripts/prune_pick.py --all                # ignore the eligibility filter
    python3 scripts/prune_pick.py --seed 7             # reproducible draw

Eligibility (skipped unless --all): pointer-stubs (canonical elsewhere), parked /
revisit-later / parked-behind-a-dependency, and done / graduated-into-VISION items. The
shortlist prints each item's staleness, status line, and any "Depends On" so you can veto
a blocked draw at a glance — the draw is a nomination, never a mandate.
"""
import argparse
import os
import random
import re
import subprocess
import time
from dataclasses import dataclass, field
from os.path import abspath, basename, dirname, isdir, join, relpath

HERE = dirname(abspath(__file__))          # worldweaver/scripts
WW_ROOT = dirname(HERE)                     # worldweaver
PARENT = dirname(WW_ROOT)                   # personal-projects (the-stable's home)
# "overarching" pools PARENT/prune — the cross-project work-item ledger (funding, roadmap, north-star),
# kept one level up so each project's prune stays about that project. Its root is PARENT itself, so
# join(root, "prune") lands on personal-projects/prune; PARENT is not a git repo, so git_last_touched
# returns nothing and those items fall back to file mtime (the picker already does this). NOTE: the
# PUBLIC harness/template is a different dir — PARENT/prune-public — and is deliberately NOT pooled.
REPOS = {"worldweaver": WW_ROOT, "the-stable": join(PARENT, "the-stable"), "overarching": PARENT}

# --- eligibility heuristics (tuned to the real banners; see --all to bypass) ---
STUB = re.compile(r"canonical in .{0,4}the-stable|Shared cognitive substrate|Full spec\s*[-=]*>", re.I)
PARKED = re.compile(r"\bPARKED\b|REVISIT-LATER|REVISIT \(parked|held loosely.{0,40}\bPARK\b|parked behind|parked \d{4}|⏳", re.I)
DONE = re.compile(r"graduated into VISION|superseded by|\bSTATUS:?\s*\**\s*(DONE|COMPLETE|RESOLVED|SHIPPED|ARCHIVED)\b|✅", re.I)
# --- extraction ---
TITLE = re.compile(r"^#\s+(.+)")
STATUS = re.compile(r"^\s*[>\-*]*\s*\**\s*(?:STATUS|Status)\b\W*(.+)", re.M)
BANNER = re.compile(r"^\s*>\s*(?:⏳\s*)?\**\s*(.+)", re.M)
DEPENDS = re.compile(r"Depends[- ]On\W*(.+)", re.I)


@dataclass
class Item:
    repo: str
    kind: str          # "major" | "minor"
    num: int
    slug: str
    path: str
    title: str
    status: str
    depends: str
    ts: int            # last-commit epoch (staleness)
    eligible: bool = True
    reason: str = "active"

    @property
    def tag(self):
        return f"{self.repo} {'M' if self.kind == 'major' else 'm'}{self.num}"

    @property
    def days(self):
        return max(0, int((time.time() - self.ts) / 86400))


def read_head(path, n=30):
    try:
        with open(path, encoding="utf-8") as f:
            return "".join(f.readline() for _ in range(n))
    except OSError:
        return ""


def first(rx, text, default="—"):
    m = rx.search(text)
    if not m:
        return default
    s = re.sub(r"[*_`]", "", m.group(1))      # drop markdown emphasis / code marks
    return re.sub(r"\s+", " ", s).strip(" -:.")


def git_last_touched(root):
    """Map {relpath: newest-commit-epoch} for the prune ledgers, in one git call."""
    out = {}
    try:
        raw = subprocess.run(
            ["git", "-C", root, "log", "--format=@%ct", "--name-only", "--", "prune/majors", "prune/minors"],
            capture_output=True, text=True, timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return out
    cur = None
    for line in raw.splitlines():
        if line.startswith("@"):
            cur = int(line[1:])
        elif line.strip() and cur and line not in out:
            out[line] = cur          # log is newest-first; first sighting wins
    return out


def classify(head):
    if STUB.search(head):
        return False, "pointer-stub"
    if PARKED.search(head):
        return False, "parked/blocked"
    if DONE.search(head):
        return False, "done/graduated"
    return True, "active"


def load_repo(name, root, kinds):
    items = []
    pruned = join(root, "prune")
    if not isdir(pruned):
        return items
    last = git_last_touched(root)
    for kind in kinds:
        d = join(pruned, kind + "s")
        if not isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            m = re.match(r"(\d+)-(.+)\.md$", fn)
            if not m:
                continue
            path = join(d, fn)
            head = read_head(path)
            ok, why = classify(head)
            status = first(STATUS, head, first(BANNER, head, "—"))
            items.append(Item(
                repo=name, kind=kind, num=int(m.group(1)), slug=m.group(2), path=path,
                title=first(TITLE, head, m.group(2).replace("-", " ")),
                status=status[:90], depends=first(DEPENDS, head, ""),
                ts=last.get(relpath(path, root), int(os.path.getmtime(path))),
                eligible=ok, reason=why,
            ))
    return items


def wsample(items, k):
    """Weighted sample WITHOUT replacement; weight = staleness in days (+1)."""
    items = list(items)
    weights = [it.days + 1 for it in items]
    out = []
    for _ in range(min(k, len(items))):
        i = random.choices(range(len(items)), weights=weights, k=1)[0]
        out.append(items.pop(i))
        weights.pop(i)
    return out


def show(it, idx=None):
    head = f"  [{idx}] " if idx else "  → "
    print(f"{head}{it.tag:<16} {it.title[:60]:<60} · {it.days}d idle")
    line = f"        {it.reason if it.reason != 'active' else 'status'}: {it.status[:70]}"
    if it.depends:
        line += f"   ⚠ depends: {it.depends[:50]}"
    print(line)


def main():
    ap = argparse.ArgumentParser(description="Egalitarian, staleness-weighted picker for the prune backlog.")
    ap.add_argument("-n", "--num", type=int, default=3, help="shortlist size (default 3)")
    ap.add_argument("--repo", choices=list(REPOS), help="restrict to one repo (default: pool both)")
    ap.add_argument("--kind", choices=["major", "minor", "both"], default="both", help="default both")
    ap.add_argument("--all", action="store_true", help="ignore the eligibility filter (include parked/stubs/done)")
    ap.add_argument("--list", action="store_true", help="just list the eligible pool, stalest first")
    ap.add_argument("--seed", type=int, help="reproducible draw")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
    kinds = ["major", "minor"] if args.kind == "both" else [args.kind]
    repos = [args.repo] if args.repo else list(REPOS)

    items = []
    for name in repos:
        items += load_repo(name, REPOS[name], kinds)

    pool = items if args.all else [it for it in items if it.eligible]
    by_repo = {r: sum(1 for it in pool if it.repo == r) for r in repos}
    counts = " · ".join(f"{r} {n}" for r, n in by_repo.items())

    if not pool:
        print("nothing in the pool — try --all, or check that the-stable is a sibling repo.")
        return

    if args.list:
        print(f"\n📋  eligible pool — {len(pool)} items ({counts}), stalest first\n")
        for it in sorted(pool, key=lambda x: -x.days):
            show(it)
        return

    shortlist = wsample(pool, args.num)
    pick = random.choices(shortlist, weights=[it.days + 1 for it in shortlist], k=1)[0]
    print(f"\n🎲  prune-pick — drew {len(shortlist)} of {len(pool)} eligible ({counts})\n")
    for i, it in enumerate(shortlist, 1):
        show(it, i)
    print()
    show(pick)
    print(f"      {relpath(pick.path, PARENT)}\n")


if __name__ == "__main__":
    main()
