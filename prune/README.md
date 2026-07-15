# prune/ — the work-item ledger (WorldWeaver)

The project's work-item harness: intended changes written down *before* they are built, reviewed against a
rubric frozen ahead of the work, and kept with their evidence. `majors/` hold large arcs; `minors/` hold
bounded changes; `harness/` holds the method (operating model, quality gates, the pruning playbook) with
the item shapes in [`majors/MAJOR_SCHEMA.md`](majors/MAJOR_SCHEMA.md) / [`minors/MINOR_SCHEMA.md`](minors/MINOR_SCHEMA.md).

**How the record works here.** WorldWeaver keeps an append-only archive in `history/` — shipped,
superseded, invalidated, and retired work moves there with its disposition intact. Active items may contain
completed phases, but each still has a meaningful open criterion. The row-by-row baseline is
[`WORK_ITEM_AUDIT.2026-07-14.md`](WORK_ITEM_AUDIT.2026-07-14.md).

**One canonical workspace.** WorldWeaver now owns the complete cognitive-substrate and resident/hearth
work-item record. Majors 49–59 are full local specifications; completed foundations live in local history.
Distinct post-fork Stable items were read in full, renumbered above the existing WorldWeaver ranges, and
either retained here or archived. The sibling repository may remain a temporary code source while Majors
76/86 reconcile it, but it is no longer a second planning authority.

**Provenance — seams showing.** These items are written by the operating AI instance in working session
with the keeper, who sets direction and holds the veto. Kept as worked, corrections and all: a model's hand
shown as a model's, not laundered into the keeper's voice.

## The majors, by era

- **City foundation (11–43)** — the world runtime: shards, federation-wide identity, the map and
  navigation, letters and group DMs, billing and spend caps, the human front door. Much of this shipped or
  was later pruned (kept in the project's archive).
- **The cognitive substrate (49–59)** — the rebuild onto a salience substrate plus a predictive pulse;
  full specifications and completion history are local.
- **World-design frontier (60–75)** — chosen-vs-unchosen attention, gate provenance, cast diversity,
  physical speech topology, tools-as-verbs, the relational ledger, in-ignition reasoning, the steward
  portal, private channels, marination, forkable cultures, scarcity economies. Mostly recent: built,
  proposed, or held.
- **Unified legacy research/product frontier (113–121; minors 120–129)** — retained post-fork Stable
  work, renumbered to avoid colliding with unrelated WorldWeaver items and classified outside the immediate
  architecture queue where appropriate.

## Minors

Bounded changes and experiment seeds — runtime polish, settings and app-shell decomposition,
social-feedback damping, measurement, safety guards, a demographic-bias fix. Each file names its own
problem and carries its own status.

> Funding, grant, and business-strategy documents (the grant pack, the lever, the product and
> talking-points packs, the roadmaps) are tracked privately and are not part of this public cut.

## See also

- [`ARCHITECTURAL_PLAN_OF_ATTACK.2026-07-14.md`](ARCHITECTURAL_PLAN_OF_ATTACK.2026-07-14.md) — the current
  dependency-ordered architectural work plan, explicitly excluding further live-agent experiments until
  the event, ledger, topology, and identity contracts are trustworthy.
- [`harness/`](harness/) — the operating model, quality gates, and pruning playbook this ledger runs on.
- The project keeps an append-only archive (shipped `PR_EVIDENCE_*`, pruning audits, retrospectives); a
  public selection of it is pending review.
- **the-stable** — read-only legacy implementation/source lineage. WorldWeaver is the canonical project;
  retained ideas are implemented here under their active WorldWeaver work items.
- **prune** — the same harness shipped empty, as a reusable scaffold for any project.
