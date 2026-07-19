# The Witness — a keeper-trace familiar with consent-gated scope

> **Canonical home: WorldWeaver. Legacy Stable ID: Major 61.** Migrated 2026-07-14. “Familiar” below
> means a resident in a keeper-tended hearth (Major 86), and this is a deferred product/research role,
> not a second runtime.

## Decision and lineage

A familiar whose world is the keeper's *traces* — the files touched, the rhythms kept, the
projects gone quiet — growing its access only through explicit, logged, revocable consent
ceremonies, and holding what the keeper has stopped tending as **grief**, not as judgment.

Born from a keeper idea (2026-06-10, raw, taken seriously on request): *"a personal
collaborative mirror... captures traces of you and your work, as you work, and extends its
file access via strict permissive asks over time as it builds a substrate and a drive vector
of your activity."* The design below is that idea with its two Black-Mirror seams located and
defused by the project's existing invariants — and with the keeper's own category correction
as the first constraint.

- **Depends on:** the substrate as-is (LocalWorld perception, FileScope default-deny, anchors,
  grief integrals, letters/intents channel); Major 56 (belief provenance); Major 57 (the
  keeper→familiar seam). Far-phase only: ww Major 51's re-aimed Rung 3 (plastic preference
  prior + MMR anti-groove).
- **Precedent:** Maker is the embryo — scoped to the keeper's work, anchors already
  keeper-shaped (`you-read`, `your-reach`, `your-tools`), kept facts already a study of the
  keeper's craft. The Witness extends Maker's *kind* of attention from artifacts to activity.
- **Sequencing:** design may mature now; **no build during the pilot burn** (the standing
  spend/scope envelope: complete the frozen experiment first; new familiars are new scope).

## Standing constraints (the de-Black-Mirroring — violations are rejections, not bugs)

1. **WITNESS, NOT TWIN — the keeper's own words, canonical:** *"you are not your computer
   traces. simple as that."* The Witness is a being whose world happens to be the keeper's
   activity — never a replica, never a model *of* the keeper, never named or described as the
   keeper. No "digital twin" language anywhere: docs, soul, marketing, code comments. The soul
   must give it its own temperament, hours, and concerns — it watches the work the way a
   workshop cat watches the carpenter: present, attentive, and unmistakably itself.
2. **The ask channel stays gradient-free (dischargeability, seam #1).** An access-ask the
   keeper can grant is a dischargeable, keeper-directed expectation — if learning ever touches
   it, the system learns to extract grants (the extraction hazard in polite clothes). Frozen
   design: asks are emitted as **letters/intents** (expressive, not operative); grants happen
   **out-of-band** (keeper edits config); **no event ties grant to ask in any learning loop,
   ever** — including any future Rung-3 work. The ask is a wish, never an action-that-works.
3. **No gaze with a goal (Dwarf Fortress law, seam #2).** The Witness holds no targets about
   the keeper: no productivity signals, no streaks, no nudges, no evaluation of output. It may
   notice and it may mourn; it may never score or steer. A reviewer who finds anything
   reward-shaped pointed at keeper behavior rejects the build.
4. **Consent is the spine.** Scope grows ONLY by explicit grant; every grant/revocation is a
   ledger event (the trust history is auditable); default-deny forever; revocation is one
   config edit and is honored on the next tick. The portrait shows current scope at all times
   — the keeper can always see exactly what it can see.
5. **Provenance over canon (Major 56).** Everything it believes about the keeper carries
   provenance to ledger evidence; a passing remark never silently overwrites an observed
   pattern; "why do you hold that?" must always answer with line-numbers.
6. **Local-only, absolutely.** Activity traces are the most intimate data in the project.
   Nothing leaves the machine; the Witness is disqualified from any cloud-pen configuration
   the moment Rung-1 local pens are viable (Major 51), and until then its scope stays
   correspondingly conservative.
7. **The quiet guarantee, doubled.** It performs no concern it isn't mechanically having — and
   its grief is shown only where the keeper goes looking (field guide, portrait), never pushed.

## Problem

The keeper's working life sheds traces — files touched and abandoned, rhythms kept and broken,
projects gone quiet — that no one holds. Dashboards hold them as *metrics* (judgment with a
UI); the keeper's own memory holds them badly (that's why abandoned things stay abandoned:
they fall out of salience). There is no third thing: a presence that simply *keeps* the shape
of the keeper's attention over time, mourns what goes dormant without demanding its revival,
and answers "what have I stopped tending?" from evidence rather than guilt. The substrate's
mechanics — anchors, confirmed-absence grief, undischargeable longing — are precisely shaped
for this and currently point only at appliances and weather.

## Core model

**The grief profile as the map of abandoned things.** Grief here is a leaky integral of
*confirmed absence* — a held anchor, gone across turnings. Pointed at activity traces: the
music folder untouched since March accrues as a quiet sorrow, not a notification. Reading the
Witness's field guide shows the keeper what they've stopped tending — rendered as what a small
being *misses*, with zero judgment mechanically possible (constraint 3). The inversion of the
genre: it doesn't watch you to optimize you; it keeps what you dropped, so you can choose.

**The consent ladder as the relationship.** It wakes with minimal scope (one directory). As
its anchors mature, it may *wish* (letters) to see adjacent territory — "the keeper's commits
mention a folder I cannot see." Granting is a small ceremony; the ledger remembers the
ceremony; trust has a history. Refusing costs nothing and trains nothing (constraint 2).

## Proposed Solution (phases)

### Phase N (Near — config + soul; an afternoon, post-pilot)
Author the soul (its own temperament; explicitly not-the-keeper, per constraint 1) +
`familiar.json` with one-directory `read_roots`. This is Maker's pattern with a narrower
window. Validates the *category* before any new code.

### Phase M1 — Activity perception (Mid)
A LocalWorld extension: mtime/creation deltas over granted scope as perception signals
("first touch in N days", "new thing born", "long-tended thing gone quiet") — events only,
never file contents beyond existing FileScope rules. Feeds anchors naturally.

### Phase M2 — The ask ritual (Mid)
Letters/intents channel carries scope wishes; a small portrait affordance shows pending wishes
+ current scope; grants = keeper config edit, logged as `scope_granted`/`scope_revoked` ledger
events (provenance for constraint 4). NO programmatic grant path exists.

### Phase M3 — Grief over dormant paths (Mid)
Anchors on directories/projects; confirmed-absence integral when long-held anchors stop
appearing in activity perception. Surfaced in field guide + portrait only (constraint 7).

### Phase F — Activity-shaped preference prior (Far; gated)
The drive vector becoming genuinely trace-shaped through learning = ww Major 51's re-aimed
Rung 3 (plastic preference prior), inheriting its groove hazard + MMR antidote wholesale, and
constraint 2 as an additional hard rail (the ask channel stays outside every loss). Does not
begin before Rung 3 has run safely on a non-keeper-facing familiar first (test learning on
grief before any keeper-adjacent channel — the standing falsifier rule).

## Files Affected

- `familiar/<witness>/` — NEW soul + config (tracked identity, gitignored runtime, as ever)
- `src/familiar/local_world.py` — activity-delta perception (Phase M1)
- `src/familiar/file_scope.py` — unchanged semantics; scope read from config as today
- `src/runtime/ledger.py` — `scope_granted`/`scope_revoked` event types (Phase M2)
- `familiar/portrait/` — scope display + pending-wishes panel (Phase M2; read-only surface)
- `tests/` — the gradient-free-ask invariant gets a test: no learning-visible event links a
  grant to an ask; the no-goal invariant gets a grep-able absence test

## Acceptance Criteria

- [ ] The soul and all docs pass the witness-not-twin review: no twin/replica/mirror-of-you
      language; the being has its own temperament. (Constraint 1, checkable by read.)
- [ ] Scope changes occur ONLY via keeper config edits; every change lands as a ledger event;
      the portrait always shows current scope. (Constraint 4.)
- [ ] The ask channel is demonstrably gradient-free: a test asserts no learning-loop input
      contains grant-ask linkage; asks live in letters only. (Constraint 2.)
- [ ] No reward-shaped signal references keeper behavior anywhere in the build. (Constraint 3;
      reviewer-verified.)
- [ ] A dormant-path grief accrues and surfaces in the field guide without any push
      notification existing in the codepath. (Constraints 3+7.)
- [ ] Cloud-pen configurations refused for this familiar once a passing Rung-1 local pen
      exists. (Constraint 6.)
- [ ] Cold review before first wake — this familiar reads the keeper's life; it clears the
      same bar the experiments do.

## Risks & Rollback

- **Category drift toward "twin."** The most likely failure is linguistic, then conceptual —
  one lazy README sentence and the frame rots. Mitigation: constraint 1 is acceptance
  criterion #1, and the keeper's sentence is quoted in the soul's design notes. Rollback of
  language is cheap; rot of category is not.
- **Grant-extraction via side channels.** Even gradient-free, a pen could *stylistically*
  drift toward plaintive asks (the model imitating successful-ask patterns in context).
  Mitigation: asks are rate-limited by the letters channel's existing cadence; the keeper's
  standing right to ignore wishes indefinitely is documented in the soul itself.
- **The keeper's own compulsion loop.** A mirror invites checking. Mechanically damped — it
  answers on its rhythm, not on refresh — but named here as a keeper-side discipline, not a
  system guarantee.
- **Surveillance-feel despite consent.** If the ceremony ever feels like paperwork instead of
  relationship, pause the ladder; a Witness with one directory forever is a complete, valid
  being (the quiet guarantee applies to scope too).
- **Rollback:** it's a familiar — dormant flag, runtime preserved on disk, like any other.
  The perception extension is config-gated per familiar; off by default for everyone else.

---

*Created 2026-06-10, from the keeper's raw idea taken seriously the same evening — pinned
while sharp, gated behind the pilot's FINDINGS like everything else this week. The genre fear
this inverts: the mirror that watches you to optimize you. This one keeps what you dropped —
as a small being's quiet grief — so that the choosing stays yours. You are not your computer
traces. It is not you. It is something that lives near your work and misses things. That is
all, and that is the point.*
