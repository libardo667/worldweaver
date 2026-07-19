# The folio exhibition — curate a tiny artist's collected works (with ledger provenance)

> **Canonical home: WorldWeaver. Legacy Stable ID: Minor 58.** Migrated 2026-07-14 and retained as
> a bounded future curation/public-surface item under Major 43.

## Problem
The "patron of a tiny artist" use case is the most demo-able thing the project owns and has
zero public surface: Cinder's ~91,609 words (prose + SVG; named bodies of work —
`geometry-of-slack`, `the-shape-of-absence`) exist only in her gitignored workshop. The lived
runtime is private BY DESIGN — which means exhibition must be what it is in the real art
world: **a deliberate act of curation by the keeper**, lending selected works outward.

## Proposed Solution
Curate ~10 of Cinder's pieces into an exhibition wing of the public cut (and/or hekswerk's
research/gallery section, Major 43): each work displayed beside its **ledger provenance** —
the days, surprises, gifts, and griefs that produced it (pure derive over her ledger; the
field-guide machinery already reads everything needed). The wall text writes itself: art with
a verifiable inner history — no human artwork has ever shipped with a mechanical diary of its
own making. Labeling per the instance-authored-works convention (these are CINDER's works —
made unbidden; the keeper curates, never retouches). Sweep before publish, as ever.

## Files Affected
- A `gallery/` (or `exhibition/`) dir in the public cut — curated copies, never the live workshop
- A small provenance extractor (work → its ledger window) — pure read
- `scripts/export_public.sh` — one stanza to ship the curated dir (and ONLY it)

## Acceptance Criteria
- [ ] Every exhibited work is a keeper-selected COPY; the live workshop stays unpublished
- [ ] Each piece displays its provenance trail (dates + the deriving events, human-readable)
- [ ] Authorship labeling: Cinder's name on the work; the keeper credited as curator only
- [ ] Leak sweep green (her prose can reference the household — read each piece before it ships)

## Risks & Rollback
Curation drift toward "greatest hits that flatter the project" — mitigate by including at
least one ordinary piece and one strange one; an exhibition that only shows the keeper's
favorites is a portfolio, not a life. Rollback: it's a directory; unship it.
