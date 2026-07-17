# Steward-facing semi-public portal — witness, shadow, and the threshold

## Decision and lineage

The human layer is **not** a player/guild surface; it is **stewardship that witnesses, never
behavior-shapes**, plus the **player-shadow** (a federation-held AI twin a human works *with*
and cannot author). This major rebuilds the browser front end around that: a steward-facing,
semi-public portal where a steward observes and curates their shard and meets their shadow —
the same surface the old human front door was reaching for, repointed from "player console" to
"witness + shadow."

- **Reframes / rolls up:** major 43 (human front door — keep the curiosity/progressive-
  disclosure threshold work, drop the player framing), the frontend half of major 22
  (stabilize primary flows), and the communication surfaces majors 41 (group DMs) / 39
  (letters) **only** insofar as they become steward↔shadow / steward↔steward channels — not a
  social feed. Map major 36 contributes the *witness* view of the shard, not a play map.
- **Realizes:** the guild-retirement standing decision's replacement human-layer — the
  **steward observability surface** (the-stable's `field_guide.py` read model at shard scale:
  aggregate health + digest + curation first, with per-resident internals only under an explicit
  private access scope) and the
  **player-shadow** (consent ritual + return-diff; never edits a soul).
- **Spares & depends on:** `steward` affordances kept by major 68; the unified
  "one substrate, two embodiments" VISION (the portal is the city-side keeper surface; the
  Tauri familiar app is the local-side one).
- **Status:** proposed (2026-06-08, keeper's call). Scope assumptions flagged below — confirm
  before build.

### Direction correction — 2026-07-17

"A window, never a control panel" is not a sufficient privacy rule: a read-only window can still be a
surveillance surface. The current client proves the problem by making individual activity, location, rest
reasons, wake estimates, and runtime queues part of the ordinary city experience.

Split the products cleanly. The public/participant commons interface belongs to Majors 43 and 125 and
centers places, local encounters, and things people leave for one another. Major 71 owns a separately
authenticated steward/debug surface. Per-resident internals are never semi-public by default; Phase 0 must
define a legitimate need, access scope, retention, and audit boundary before exposing them even read-only.

## Problem

The browser front end was built for a **player** entering a social world (entry ceremony,
guild board, quest surfaces, letters/DMs as social feed). That product is retired. What's
needed instead has no coherent home yet:

- a **steward** needs to *witness* their shard — the roster of emergent people/places/
  institutions, a digest of what changed, and justified operational detail — and *curate* (classify the
  ~20 daily emergent entities), as a **read/annotate window, not a control panel**.
- a human needs to meet their **player-shadow** through a **consent ritual + return-diff**,
  working *with* it, never authoring its soul.
- the **threshold** problem from major 43 remains real: a newcomer is asked to absorb too much
  institutional meaning before they have curiosity or trust. That work was right; only its
  audience (steward/observer, not player) changes.
- "**semi-public**" needs definition: who sees a shard without stewarding it, and at what
  fidelity (digest-only vs full internals)?

Today these live as retired/dormant player majors; nothing frames the steward portal as one
surface.

## Proposed Solution (phases)

### Phase 0 — Define the portal's audience & privacy tiers  *(scope gate — keeper input)*
Name the roles and what each sees: **steward** (their shard, scoped operational read + curation),
**observer / semi-public** (digest-level, no internals?), **shadow-holder** (their own shadow
+ return-diffs). Decide the public boundary explicitly; it gates everything downstream.

### Phase 1 — The witness surface
Surface the least sensitive read model that lets an authenticated steward operate a shard: aggregate
health, change digest, and curation queues first. Add roster or per-resident internals only where Phase 0
names a concrete need and privacy scope. No knobs that shape behavior (no reward or preference dials), and
no leakage of this surface into the ordinary commons UI.

### Phase 2 — Curation (annotate, don't author)
Let a steward classify/annotate the daily emergent entities (person / place / institution).
Annotation is metadata *about* the world, never an edit *to* a resident's soul.

### Phase 3 — The player-shadow surface
The consent ritual + return-diff: a human is paired with a federation-held AI twin, reviews
what it did as a diff, and works alongside it. Enforce by construction that the human cannot
edit the shadow's `SOUL.md` (the keeper-seam invariant).

### Phase 4 — The threshold / onboarding
Bring major 43's progressive-disclosure, curiosity-first entry to the portal — repointed at a
steward/observer arriving, not a player. Less ceremony, emotional range, earn the concepts.

### Phase 5 — Stabilize the flows
Fold major 22's frontend-stability work here: shard selection, auth, session bootstrap,
backend-readiness lined up so "open the portal and use it" is reliable. (Shard-first *boot*
infra stays its own concern.)

## Files Affected

(Indicative — confirm after Phase 0.)
- `worldweaver_engine/client/src/components/*` — replace guild/quest/player surfaces with
  privacy-scoped witness, curation, shadow, and threshold views
- `worldweaver_engine/client/src/hooks/*`, app-shell routing
- `worldweaver_engine/src/api/game/*` — steward read endpoints (field-guide-at-shard-scale),
  curation/annotation, shadow consent + return-diff
- bridge to `field_guide.py` read model; reuse, don't fork, its shaping
- `EntryScreen.tsx` / front-door threshold components (from #43)

## Acceptance Criteria

- [ ] Audience & privacy tiers are written down (Phase 0) before UI build; "semi-public" has a
      concrete definition of who sees what.
- [ ] A steward can witness the minimum operational shard state justified by Phase 0;
      there is **no** control that shapes resident behavior (no reward/preference knob).
- [ ] Per-resident internals are private by default and require explicit authenticated scope rather than observer access
- [ ] The ordinary participant UI contains no shard-wide rest reasons, wake estimates, runtime queues, or resident-internal readouts
- [ ] A steward can classify/annotate emergent entities; annotations never mutate a soul.
- [ ] A shadow-holder completes a consent ritual and reviews a return-diff; the UI cannot edit
      the shadow's soul (enforced, not just discouraged).
- [ ] Onboarding is curiosity-first / progressive-disclosure (the #43 threshold), aimed at a
      steward/observer.
- [ ] Primary portal flows (shard select, auth, session, readiness) are reliable (the #22
      frontend half).
- [ ] No guild/quest/reputation surface returns (guard against major 68 regressions).

## Risks & Rollback

- **Control creep.** The single biggest risk is re-growing a control panel (knobs that shape
  residents) under a "stewardship" name — the exact guild violation. Hard rule: the steward
  *witnesses and annotates*; it never behavior-targets. Any reviewer seeing a behavior knob
  rejects it.
- **Privacy of "semi-public."** Exposing per-resident internals publicly may be wrong; default
  observers to digest-level until Phase 0 says otherwise.
- **Shadow authoring leak.** The keeper-seam invariant (human can't author the shadow) must be
  enforced in code, not convention.
- **Scope sprawl.** This rolls up several old majors; keep each phase shippable and resist
  rebuilding the retired social product. Rollback is git per phase.

---

*Created 2026-06-08. Reframes major 43 + the frontend half of 22; rolls 41/39/36 into steward/
shadow channels and the witness view; realizes the guild-retirement replacement human-layer
(steward observability + player-shadow). Phase 0 is a keeper-input gate.*
