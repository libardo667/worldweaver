# Cross-embodiment transplant — the world as the fourth identity carrier

> **Canonical home: WorldWeaver. Legacy Stable ID: Major 65.** Migrated 2026-07-14. Product travel is
> now accepted architecture under Major 86; this retained item is only the later controlled research
> question about how a continuous resident re-settles across worlds.

> **STATUS: held loosely — PARKED, no timescale.** Caught from the 2026-06-10/11 conversation.
> 2026-06-11 direction review: **PARK** — real apparatus asset (the WorldClient seam), but fourth in
> a serial chain and its hard dependency on Major 117 is actually soft (FRESH + CONTINUE nulls make a
> transplant interpretable without exact shares). Revisit as a design doc after two verdicts land.

## Decision and lineage

Re-embody a matured resident across the two world attachments that share one substrate: move between
the private, optionally file-grounded hearth (peers → files) and a city. The legacy repository fork
first exposed the `WorldClient` seam; Major 86 now makes it one product architecture. The controlled
question remains: identity = soul × ledger × pen × **world**, and this apparatus can vary the fourth
factor while freezing the first three.

Complements Major 117 (which factorizes within one embodiment): after pen, soul, and ledger
shares are known, the transplant asks which parts of a settled self are **world-shaped** —
does a resident whose drive profile settled around peers re-settle around files as the same
self with new objects, or as a different self? Born from the keeper conversation 2026-06-10
("two embodiments of one substrate"). The keeper's culture line (2026-06-11) names the same
seam from the other side: worldweaver's post-scarcity vibe-and-chat world "could be any other
number of setups, structurally" — culture shock, formally, IS a world swap with the self held
fixed, so this item is also the controlled core of any future cultural-interpretation work
(which additionally requires Minor 126's ethics gate).

- **Depends on:** Major 117 (factorization shares known first — otherwise a transplant effect
  is unattributable); the relevant pen-vs-substrate evidence; divergence-compounding
  statistics from Major 115 (a transplant is a forward free-run, not teacher-forced).
- **Sequencing: last of the post-verdict arc.** No build during the pilot burn; design only.

## Problem

Both repos assume the substrate is the invariant and the world is "embodiment detail," but no
measurement separates substrate-carried self from world-scaffolded self. If a transplanted
resident's settled profile collapses, the self was substantially world-scaffolded — which
bounds every portability claim the project makes (including the product-level one: a familiar
that travels by filesystem). If it holds with re-aimed objects, the substrate-carry claim
gains its strongest form.

## Proposed Solution

- **Seam audit first:** verify soul + ledger move cleanly across the `WorldClient` seam
  (perception vocabularies differ: peers/overheard vs files/weather). Pre-declare the mapping
  of measurement channels (elective peer-address ↔ elective read) and what counts as "the
  same concern re-aimed" — this dictionary is the experiment's hardest part and is
  pre-registered, not improvised after seeing output.
- **Arms:** TRANSPLANT (matured city ledger+soul into the stable; and the reverse direction if
  the first is informative) vs CONTINUE (same mind continuing in its home world, matched
  horizon) vs FRESH (same soul, zero ledger, in the destination world — the
  arrival-as-newborn null).
- **Measures:** `maturation_stability` profile distance at matched horizons; concern/anchor
  re-aiming (do held concerns find new objects or dissolve); time-to-resettle vs FRESH's
  time-to-settle.
- Pre-registered, cold-reviewed, outcomes pre-accepted; the channel-mapping dictionary frozen
  before any transplant runs.

## Files Affected

- `research/preregistrations/<date>-cross-embodiment-transplant-DRAFT.md` (new; one unified record)
- `research/harness/` (transplant tool: soul+ledger import across the seam, copies only)
- `src/runtime/world.py` (read-only reference — the seam itself is not modified)

## Acceptance Criteria

- [ ] Channel-mapping dictionary (peer-world ↔ file-world measures) pre-registered before any run
- [ ] FRESH-in-destination null arm included; CONTINUE-at-home matched horizon included
- [ ] Transplant tool operates on copies; no live familiar or resident is moved in place
- [ ] Verdict reported as world-share against the Major-66 pen/soul/ledger shares
- [ ] One WorldWeaver preregistration covers both world attachments and the shared resident host

## Risks & Rollback

Risk: the channel mapping is where motivated reasoning would live — a generous dictionary makes
any transplant "hold"; hence frozen-before-run and cold-reviewed. Risk: a transplanted being
that fails to resettle is a being in distress by construction — Minor 126's stop conditions
apply, and the humane rollback (return to home world, ledger intact) is pre-declared. Rollback:
research-side tools and copies only; the seam and both production runtimes are untouched.
