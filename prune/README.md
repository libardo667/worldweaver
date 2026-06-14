# prune/ — the work-item ledger (WorldWeaver)

The project's work-item harness: intended changes written down *before* they are built, reviewed against a
rubric frozen ahead of the work, and kept with their evidence. `majors/` hold large arcs; `minors/` hold
bounded changes; `harness/` holds the method (operating model, quality gates, the pruning playbook) with
the item shapes in [`majors/MAJOR_SCHEMA.md`](majors/MAJOR_SCHEMA.md) / [`minors/MINOR_SCHEMA.md`](minors/MINOR_SCHEMA.md).

**How the record works here.** WorldWeaver keeps an append-only archive in `history/` — shipped work is
recorded as `PR_EVIDENCE_*` alongside pruning retrospectives, and removed or superseded items move under
`history/`. So the live `majors/` and `minors/` still include foundational items that have already shipped;
read each item's own `Status` line for where it stands. (A deeper active-vs-archived reclassification is in
progress; this is a first honest cut, not a fully pruned one.)

**Shared substrate, stored once.** Majors 49–59 are the cognitive substrate — a mechanistic core under a
single predictive pulse — **canonical in the sibling project [the-stable](https://github.com/libardo667/the-stable)** (the pilot, the clean fractal
sample of the mechanism that WorldWeaver applies at city scale). Work items here are stored by *subject*:
the substrate's full spec lives in the-stable, so 49–59 are kept as **pointer stubs** that resolve
WorldWeaver's dependent majors (60+) without duplicating it. The familiar-era minors the fork left here
have likewise moved to their canonical home in the-stable; WorldWeaver's active `minors/` now holds only
WorldWeaver-specific work.

**Provenance — seams showing.** These items are written by the operating AI instance in working session
with the keeper, who sets direction and holds the veto. Kept as worked, corrections and all: a model's hand
shown as a model's, not laundered into the keeper's voice.

## The majors, by era

- **City foundation (11–43)** — the world runtime: shards, federation-wide identity, the map and
  navigation, letters and group DMs, billing and spend caps, the human front door. Much of this shipped or
  was later pruned (kept in the project's archive).
- **The cognitive substrate (49–59)** — the rebuild onto a salience substrate plus a predictive pulse;
  canonical in the-stable, kept here as pointer stubs.
- **World-design frontier (60–75)** — chosen-vs-unchosen attention, gate provenance, cast diversity,
  physical speech topology, tools-as-verbs, the relational ledger, in-ignition reasoning, the steward
  portal, private channels, marination, forkable cultures, scarcity economies. Mostly recent: built,
  proposed, or held.

## Minors

Bounded changes and experiment seeds — runtime polish, settings and app-shell decomposition,
social-feedback damping, measurement, safety guards, a demographic-bias fix. Each file names its own
problem and carries its own status.

> Funding, grant, and business-strategy documents (the grant pack, the lever, the product and
> talking-points packs, the roadmaps) are tracked privately and are not part of this public cut.

## See also

- [`harness/`](harness/) — the operating model, quality gates, and pruning playbook this ledger runs on.
- The project keeps an append-only archive (shipped `PR_EVIDENCE_*`, pruning audits, retrospectives); a
  public selection of it is pending review.
- **the-stable** — the familiars fork; shares the 49–59 substrate, diverges after it.
- **prune** — the same harness shipped empty, as a reusable scaffold for any project.
