# Resolve cross-repo work-item duplication (the-stable ↔ worldweaver prune)

> **Disposition: superseded by unification and complete; archived 2026-07-14.** The keeper rejected the
> two-canonical-home premise: retained Stable specifications now live in WorldWeaver under local IDs, full
> pointer specs are local, post-fork number collisions were renumbered, and completed Stable lineage was
> imported to WorldWeaver history. The legacy repository is a source snapshot, not a second active prune
> authority. The repository-wide audit records explicit status for the surviving WorldWeaver backlog.

## Metadata

- ID: 64-resolve-cross-repo-workitem-duplication
- Type: minor (keeper-decision sweep; bounded but needs per-row ownership calls)
- Owner: Levi (the line is yours to draw)
- Status: **backlog (2026-06-18).** Carries forward the still-open A/B/C decisions from the 2026-06-11
  portfolio-hygiene review, verified still-unresolved during the 2026-06-18 doc-triage pass. The source
  doc (`HYGIENE_DECISIONS-2026-06-11.md`) was archived to `prune/history/` once these were captured here.
- Risk: low (reversible: pointers/headers, not deletions).

## Problem

Several work-items exist as **byte-identical copies in both `worldweaver/prune/` and `the-stable/prune/`**.
The 2026-06-11 review flagged this; the unambiguous sweeps ran, but the ownership decisions did not.
Verified 2026-06-18: ww majors **52, 54, 55, 57, 58, 59** are still active in *both* repos with **no
pointer**, and there are **zero `MIRRORED-WITH` / `MOVED →` banners anywhere** — so the A/B sweep never
executed. The named risk stands: two copies of "the same item" in two harnesses silently diverge (edit
one, forget the other).

## What remains (the keeper-decisions, from the archived 2026-06-11 doc)

- **A. Familiar-specific dupes → the-stable OWNS; close ww's copy with a pointer.** Candidates (confirm per
  row): ww majors 52, 54, 55, 57, 58, 59; minors 48, 51, 52 (minor 53 already resolved). Action per row:
  move ww's copy to `worldweaver/prune/history/<majors|minors>/` with a one-line banner
  `MOVED → the-stable owns this post-fork; see the-stable/prune/...`.
- **B. Shared substrate work → pick ONE home, pointer from the other.** Candidates: minors 46, 47, 49, 50,
  54; shared-lineage majors 49–51, 53. Per the standing-brief split (ww owns substrate, the-stable owns
  familiar-specific), default **ww owns; the-stable's copy gets the pointer** — but confirm each, and
  `diff` 49–51/53 first (they may have already diverged; if deliberately mirrored, add a `MIRRORED-WITH:
  <repo>` header instead of a pointer).
- **C. Residual ww legacy sweep (11–45).** 26/27/41 are already closed. The rest still want a RETIRED/PARKED
  header pass so the portfolio passes the three-click test (bulk, low-judgment; confirm nothing live hides).

## Acceptance Criteria

- [x] WorldWeaver is the one canonical active work-item home; the legacy Stable ledger is no longer an ownership peer.
- [x] No deliberately mirrored active item remains; retained specifications carry a WorldWeaver canonical-home banner.
- [x] The repository-wide 2026-07-14 audit explicitly classifies the surviving 11–45 items and archives resolved ones.

## Pointer

- Verified detail + the original recommended dispositions: `prune/history/HYGIENE_DECISIONS-2026-06-11.md`.
