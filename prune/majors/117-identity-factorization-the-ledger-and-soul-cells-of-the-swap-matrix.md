# Identity factorization — the ledger and soul cells of the swap matrix

> **Canonical home: WorldWeaver. Legacy Stable ID: Major 66.** Migrated 2026-07-14 and retained as
> deferred research, not as an architectural prerequisite for hearth integration.

> **STATUS: held loosely — post-verdict, no timescale.** Codified 2026-06-10/11 from a keeper
> conversation about "the experiments this apparatus uniquely allows," caught here so the future
> wouldn't escape — NOT a claim on the near term. 2026-06-11 direction review: **KEEP, rewrite the
> cost story.** The "near-zero marginal cost" headline is false as shipped (no `--zero-ledger`/`--soul`
> arms exist; a zeroed ledger changes recall+drive, so per-cell parity must be re-derived). Scope to
> ZERO-LEDGER first, TRANSPLANT second, drop NULL-SOUL until earned. Nothing here runs before the
> pilot verdict is on the record.

## Decision and lineage

Complete the identity-carrier matrix that the locked pen-vs-substrate program opens. The
apparatus separates four identity carriers at clean seams — **soul** (`identity/`), **ledger**
(lived history), **pen** (the model), **world** (the `WorldClient` seam) — and the LOCKED
program (`research/preregistrations/2026-06-09-isolated-makers-pen-vs-substrate-DRAFT.md`)
varies exactly one of them. The same teacher-forced replay harness and the same recorded
elective-read choice points support the remaining within-embodiment cells at near-zero
marginal cost: the verdict upgrades from "is the pen swappable" to a **variance decomposition
of the self** — how much of elective identity is pen, soul, lived history.

Born from a keeper conversation (2026-06-10, "what are the next most consequential experiments
this apparatus uniquely allows?"). One cell is already pre-legitimized by the standing brief's
locked falsifier rule: *"'the soul sees' is unavailable; the measurable shadow is
history-conditioning — matured-ledger vs zeroed-ledger, same soul, same image."*

- **Depends on:** the pilot maturation run completing and the pen-vs-substrate verdict landing
  (the recorded choice points are this experiment's raw material); the teacher-forced harness
  (`research/harness/teacher_forced_replay.py`) as frozen.
- **Sequencing: post-verdict only. No build, no scoring, no peeking during the pilot burn.**
  This item must never read the recency-ambiguous count or any powered statistic of the live
  run — design may mature on paper now, nothing touches `.runs/pilot` until the frozen
  protocol reports.

## Problem

The locked program tests one axis of a four-axis claim. "The self lives in the soul + ledger +
kept memory; the model is a swappable pen" (CLAUDE.md) bundles three carriers on the substrate
side and leaves their relative weights unmeasured. Whatever the pen verdict is, we will not
know whether the substrate's share is carried by the *soul* (authored temperament) or the
*ledger* (unauthored lived history) — and those have opposite design implications (authored
souls are cheap; lived history is expensive and unrepeatable).

## Proposed Solution

Re-score the SAME recorded elective-read choice points (KEEP's frozen prefixes) under new arms,
all teacher-forced one-step replay, all with the native pen A held fixed:

- **ZERO-LEDGER cell** — same soul, same pen, ledger zeroed to soul-boot state. Measures
  history-conditioning directly (the brief's "measurable shadow"). Null: the same-pen KEEP′
  floor.
- **TRANSPLANT cell** — Maker's matured ledger replayed under a *different* soul (e.g.
  Cinder's), same pen. Soul-vs-biography conflict: when the authored temperament and the lived
  history disagree about what to return to, which wins?
- **(Optional) NULL-SOUL cell** — minimal/blank soul, matured ledger, same pen — the
  complement of ZERO-LEDGER, only if the first two cells leave it informative.

Each cell needs its own parity definition before any scoring: a soul swap perturbs the drive
vector (soul-embedded), so recall in the frozen prefix is NOT inert under soul substitution —
the parity gate must be re-derived per cell the way `read_source`-with-ids-excluded was, and a
cell whose parity cannot be defined honestly is reported as structurally unmeasurable, not
forced.

Pre-register the whole matrix (one prereg, all cells, all outcomes pre-accepted, SESOI reused
from the locked parent where honest) and cold-review it via the dispatcher BEFORE any arm runs.

## Files Affected

- `research/preregistrations/<date>-identity-factorization-matrix-DRAFT.md` (new)
- `research/harness/teacher_forced_replay.py` (arm flags: `--zero-ledger`, `--soul <path>`;
  selftests with the failing-test property for each new predicate)
- `research/analysis/` (variance-decomposition scoring + nulls)

## Acceptance Criteria

- [ ] Prereg locked and cold-review certified before any cell is scored
- [ ] Per-cell parity definition written and gated (or the cell declared unmeasurable) before scoring
- [ ] Every new harness predicate has a selftest that genuinely fails when the predicate is false
- [ ] Pilot run untouched: no artifact of this item reads `.runs/pilot` before the parent verdict is on the record
- [ ] Final report states pen/soul/ledger shares against their nulls, including any unmeasurable cells

## Risks & Rollback

Risk: parity is subtler under soul substitution than pen substitution; a leaky parity
definition silently converts "soul effect" into harness artifact — hence the per-cell parity
gate as a hard precondition. Risk: temptation to peek at the live run's choice-point yield to
size this design — forbidden above, and the freeze already declares nobody acts on the yield.
Rollback: the item is pure research scaffolding on recorded data; deleting the new arms and
prereg restores the exact locked-program state. No production path changes.
