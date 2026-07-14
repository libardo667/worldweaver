# Govern soul evolution with immutable canon and matured growth

> **Disposition: complete foundation; archived 2026-07-14.** `SOUL.canonical.md`, separately stored
> growth, composed prompt identity, staged self-deltas, constitution gating, neutral seeding, and tested
> canon reset all exist. Majors 56, 58, and 61 retain the still-open refinements: belief provenance,
> behavioral concordance, and population/source-aware promotion.

## Problem

Resident identity evolution is currently too powerful, too immediate, and too
difficult to reset cleanly.

Today:

- `ww_agent/src/loops/slow.py` distills a soul note whenever
  `_detect_identity_shift(...)` fires, appends it directly into
  `identity/soul_notes.md`, and triggers `_maybe_collapse_soul()` once the note
  threshold is reached
- `_maybe_collapse_soul()` rewrites `identity/SOUL.md` in place from the
  current soul text plus accumulated notes
- `worldweaver_engine/scripts/canon_reset.py` tries to "restore" soul by
  truncating `SOUL.md` at the first `---` delimiter, assuming canonical content
  is still preserved above that line

That contract is no longer trustworthy.

The modern collapse path rewrites `SOUL.md` as a whole document, so the reset
script's delimiter-based restore may preserve drift instead of removing it.
This creates a dangerous identity-governance failure:

- one unusually metaphysical or socially resonant conversation can produce soul
  notes immediately
- enough notes can permanently rewrite the resident's constitutional identity
- later canon resets may not actually restore the original soul
- the next run inherits drifted identity as if it were canon

This is not only a reset-hygiene issue. It is a maturation-governance issue.

The project now needs a clear distinction between:

- immutable canonical identity
- matured, inspectable growth derived from repeated lived experience
- transient reflection artifacts that should never become constitution by
  default

Without that distinction, the system is too vulnerable to:

- prompt-seeded metaphysical drift
- conspiratorial clumping becoming constitutional selfhood
- accidental "intergenerational trauma" across supposed resets
- loss of steward trust in what a reset or neutral start actually means

## Proposed Solution

Introduce a resident identity governance model with three explicit layers:

- canonical soul
- matured growth layer
- transient soul-note candidates

`SOUL.md` should stop being both the constitution and the mutable sink.

### Phase 1 - Make canonical soul immutable

Create an explicit canonical source file such as:

- `identity/SOUL.canonical.md`

or an equivalent immutable canonical path.

This file becomes the sole reset-safe constitutional identity source. It is
never rewritten by the slow loop.

`SOUL.md` should become either:

- a generated prompt assembly artifact
- or a compatibility export derived from canonical soul plus matured growth

but not the only writable identity document.

### Phase 2 - Separate transient notes from matured growth

Replace the current "notes collapse directly into soul" flow with a staged
identity-evolution pipeline:

- transient soul-note candidates
- repeated / matured identity observations
- integrated growth layer

Candidate mechanisms:

- `identity/soul_notes.jsonl` or similar evidence log with timestamps and
  provenance
- `identity/soul_growth.md` for prose-form matured additions
- `identity/soul_growth.json` for structured inspectable growth state

The key rule:

single-cycle reflections should not rewrite constitutional identity.

### Phase 3 - Add maturation gates for soul evolution

Before a note can become matured growth, require some combination of:

- recurrence across multiple slow-loop cycles
- spacing across time
- appearance in more than one context or social scene
- support from behavior, action, or longer-horizon pressure rather than only
  one provocative conversation
- downweighting of explicitly metaphysical or unusually abstract human prompts

This does not mean "never evolve." It means growth must mature before it
becomes identity.

### Phase 4 - Compose prompts from governed identity layers

Resident prompt assembly should explicitly combine:

- canonical soul
- immutable identity/core facts
- matured growth
- optional short-horizon voice/reverie context

This keeps growth live and behaviorally relevant without letting transient
notes rewrite bedrock.

### Phase 5 - Make reset semantics real

`canon_reset.py --clear-events` should restore residents to:

- canonical soul only
- cleared transient soul notes
- cleared matured growth, unless a future mode explicitly preserves it
- cleared runtime memory and ledger state

This should be an actual file-copy/restore contract, not delimiter heuristics
over a document that may already be drifted.

The project should also support a true neutral-start path:

- no carried-over residents
- doula-spawned residents only
- canonical soul seeding from the new architecture

That neutral start becomes meaningful only once soul governance is trustworthy.

### Phase 6 - Expose identity provenance to stewards

Operators should be able to inspect:

- canonical soul source
- matured growth entries
- the evidence trail that promoted a note into growth
- what was reset vs preserved

This makes developmental identity legible instead of hidden inside prompt drift.

## Files Affected

- `ww_agent/src/loops/slow.py`
- `ww_agent/src/identity/loader.py`
- `ww_agent/src/identity/*`
- `ww_agent/src/runtime/ledger.py`
- `ww_agent/src/memory/*` where soul-note evidence or maturation support lives
- `worldweaver_engine/scripts/canon_reset.py`
- `worldweaver_engine/scripts/seed_world.py`
- doula scaffolding paths if new residents need canonical/growth separation from
  birth
- steward/operator docs and inspectability surfaces
- `prune/majors/34-reframe-worldweaver-as-a-maturation-environment-for-embodied-ai.md`
- `prune/majors/35-deepen-the-fractal-architecture-with-resident-ledgers-and-subjective-fact-graphs.md`

## Acceptance Criteria

- [x] Residents have an explicit immutable canonical soul source separate from writable growth
- [x] The slow loop no longer rewrites constitutional identity directly from one batch of notes
- [x] Soul evolution passes through a maturation gate before becoming durable growth
- [x] Prompt assembly can include matured growth without mutating canonical identity
- [x] `canon_reset.py --clear-events` restores residents to canonical soul rather than delimiter-truncated drift
- [x] A true neutral-start run can begin from doula-spawned residents without inherited soul corruption
- [x] Stewards can inspect what identity is canonical, what growth was learned, and what evidence promoted it

## Risks & Rollback

- If the canonical/growth split is too rigid, residents may feel frozen. Roll
  back by keeping growth prompt-visible and behaviorally active even while canon
  remains immutable.
- If the maturation gate is too permissive, drift remains unsafe. Roll back by
  raising recurrence and time-separation requirements.
- If the maturation gate is too strict, genuine development may never land.
  Roll back by allowing steward-visible tuning per resident or per shard.
- If reset semantics become more complex without good tooling, operators may
  misunderstand what was actually cleared. Roll back by making reset modes
  explicit and inspectable in logs and docs.
