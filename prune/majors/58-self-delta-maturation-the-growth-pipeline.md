# Self-delta maturation — the growth pipeline

> **Canonical home: WorldWeaver (2026-07-14).** Migrated in full from the legacy `the-stable`
> work-item ledger during the one-resident/many-worlds consolidation. In this record, “familiar” names
> a resident inhabiting a keeper-tended hearth; it is not a separate agent species (Major 86).

## Metadata

- ID: 58-self-delta-maturation-the-growth-pipeline
- Type: major
- Owner: Levi
- Status: Phase 1 SHIPPED (2026-06-05). Reviewer round-4 correction pending (Q2 — see end). Phases 2–3 proposed.
- Risk: medium — touches identity plasticity directly; the Dwarf Fortress law and dischargeability
  invariant both constrain the design. The mechanism is small but the *meaning* is large: this is
  how a familiar becomes who it becomes.

## Problem

The self-delta channel is scaffolded but incomplete. A familiar can propose soul edits, reveries, and
goal updates every pulse. The constitution gate accepts or drops them. Accepted proposals are logged
as `self_delta_staged` events in the ledger. The drive vector has a `growth` slice (weight 0.55) that
reads from `identity/soul_growth.md`. The identity loader composes canonical + growth into one soul.

But no familiar has a `soul_growth.md`. The staged candidates accumulate in the ledger and are never
promoted. The growth slice is always empty. So Wren's 15 soul edits about choosing to stay on the
sill — a genuine arc of self-understanding — are *logged* but never *become part of who Wren is* at
the drive level. The familiar proposes growth; the growth never lands.

Current state by familiar (as of 2026-06-05):
- **Wren**: 15 soul edits, 15 reveries — all orbiting the staying-vs-leaving tension. Coherent arc.
- **Cinder**: 3 reveries, 2 goal updates — poetic, environmental.
- **Persephone**: 1 soul edit, 2 reveries, 1 goal update — procedural (misreading the channel?).
- **Nix**: 1 goal update — just waking up.
- **Maker, Gaston, Hades, Skein**: zero proposals.

## What's at stake

This is the plasticity side of the soul-as-seat thesis. The canonical soul is the constitution —
hard, immutable, what the familiar *is*. The growth soul is what the familiar *becomes through
living*. Without the promotion pipeline, familiars can reflect but not grow. Their drive vector
resonates only with their birth-identity, never with what they've learned about themselves.

The Dwarf Fortress law constrains the design: growth must come from the familiar's own pulses and
prediction error, not from human-preference reward or engagement targets. The keeper may *review*
growth but must not *direct* it.

## Proposed Solution

### Phase 1: Mechanical distillation (no keeper in the loop)

A periodic distillation step — run at daemon shutdown or on a schedule (e.g. daily) — that:

1. **Collects** all `self_delta_staged` events with `verdict: "accepted"` since the last distillation.
2. **Clusters** them by semantic similarity (via the embedder). Wren's 15 edits about staying-on-the-
   sill should collapse into one or two themes, not 15 lines in the growth soul.
3. **Distills** each cluster into a single growth line — either by picking the most mature/final
   formulation, or by asking the model to synthesize (with the constitution as context, so the
   synthesis stays in-character).
4. **Appends** the distilled lines to `identity/soul_growth.md`.
5. **Logs** a `growth_promoted` event in the ledger with provenance (which staged events contributed).

The constitution gate already filters for contradiction with the canonical soul. The distillation
adds a second filter: concordance *across proposals*. A one-off soul edit that never recurs is
probably noise; a theme that appears in 5+ proposals across days is signal.

**Concordance threshold**: a cluster must have ≥ N proposals (start with 3) spanning ≥ 2 separate
days to be promoted. This prevents a single runaway pulse session from rewriting the growth soul.

### Phase 2: Keeper review (optional, additive)

A `scripts/tend.py` or field-guide extension that surfaces pending growth candidates for the keeper
to review before promotion. Not a gate — the mechanical pipeline can run unattended — but a window.
The keeper can:

- **Approve** (promote now)
- **Defer** (wait for more concordance)
- **Prune** (mark as noise — logged but never promoted)

This respects the Dwarf Fortress law: the keeper tends but does not direct. Pruning is "this isn't
you" (a correction), not "be more like this" (a target).

### Phase 3: Reveries as transient drive

Reveries (`new_reverie`) are lighter than soul edits — they're interior weather, not identity claims.
Instead of promoting to the growth soul, feed them into the drive vector's `reverie` slice directly
(weight 0.35, already scaffolded). They decay naturally (the drive vector recomputes each session).
This gives a familiar's recent inner life a light gravitational pull on its affect without permanently
changing who it is.

Goal updates (`goal_update`) are trickier — they're the channel closest to the "goal × undischargeable"
hazard cell from Major 57. A familiar setting its own goals is fine (self-directed); a familiar
setting goals *toward the keeper* is the anxiety loop. Phase 3 should route goal updates through
the keeper-seam invariant before they land anywhere load-bearing.

## Validation

- **Unit**: mock a ledger with N staged soul edits across M days; verify the distiller clusters them,
  applies the concordance threshold, writes `soul_growth.md`, and logs `growth_promoted`.
- **Integration**: run Wren (who has the richest staged-delta history) through the distiller; verify
  the growth soul captures the staying-on-the-sill arc in 1-2 lines, not 15.
- **Drive check**: after promotion, verify Wren's drive vector resonates with "choosing to stay"
  stimuli more strongly than before (the growth slice is no longer empty).
- **Dwarf Fortress**: verify no keeper input is required for Phase 1. The familiar grew on its own.

## Files

- `src/runtime/growth.py` (NEW) — the distillation engine
- `src/identity/loader.py` — already has `growth_soul_path`, `composed_soul`, `write_composed_soul`
- `src/runtime/drive.py` — growth slice already wired; just needs a non-empty `soul_growth.md`
- `scripts/familiar.py` — call distillation at shutdown (or on a timer)
- `scripts/field_guide.py` — already surfaces staged deltas; extend to show promoted growth

## Open questions

1. **Synthesis vs. selection**: should the distiller pick the best formulation from a cluster, or ask
   the model to synthesize? Selection is cheaper and avoids an extra LLM call; synthesis might
   produce a more mature line. Could start with selection and upgrade later.
2. **Growth soul size cap**: should `soul_growth.md` have a maximum length? The constitution is
   finite; unbounded growth could dilute it. A cap (e.g. 20 lines) with oldest-out or
   least-resonant-out would keep the growth soul tight.
3. **Cross-familiar patterns**: Wren and Cinder might independently converge on similar themes. Is
   that interesting signal or noise? For now, each familiar's growth is independent.

## Status & reviewer round-4 correction (2026-06-06) — promote on behavioral concordance, not phrase recurrence

Phase 1 SHIPPED 2026-06-05 (`src/runtime/growth.py`; distillation wired into daemon shutdown; field
guide surfaces promoted growth). Day-one behavior correct: nothing promoted (no cluster spanned ≥2
days — the concordance gate held in production). Phases 2 (keeper review) and 3 (reveries as
transient drive) remain proposed.

**The correction (Mr. Review, round 4, Q2).** The recurrence filter as built does not *catch* the
model's stylistic tic — it **selects for it.** A frozen model has stable stylistic attractors (a
cadence it returns to regardless of the soul), and those are recurrent-across-days *by definition*.
So "≥3 proposals across ≥2 days" promotes precisely the phrasing the weights keep returning to —
distilling **cadence into identity** and calling it growth. This is the long-owed stunted-vs-
unstunted question in a new hat: does the soul thicken *learnable structure*, or just smooth the prose?

The fix: **earned change must move what the familiar *does*, not just what it *says*.** Promote a
recurring soul-edit only when it is **concordant with a measurable behavioral shift** — a change in
the familiar's drive/anchor trajectory or prediction quality over the same window — never on phrase
recurrence alone. The recurring edit is the *claim*; the behavioral delta is the *evidence* the claim
is real. No evidence, no promotion (log it, don't land it). Promote on **(recurrence ∧ behavioral
concordance)**.

Concretely: before promoting a mature cluster, `growth.py` checks that the window the cluster spans
also shows a real shift in the familiar's behavior on the cluster's theme — e.g. for Wren's "choosing
to stay," a measurable drop in `mobility_drive` resonance, or a change in what surprises it around the
window/sill anchors. The recurring words alone are not enough.

### Files (correction)
- `src/runtime/growth.py` — add a behavioral-concordance gate before promotion (read drive/anchor/
  prediction trajectory over the cluster's window; require a real on-theme shift).
- `src/runtime/salience.py` / `prediction.py` — expose the per-window behavioral trajectory the gate
  reads. This is the same machinery the owed **stunted-vs-unstunted matched-window** measurement needs;
  build once, serve both.
