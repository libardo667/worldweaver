# Economies as dischargeability machines — scarcity worlds after the boundary is mapped

> **STATUS: held loosely — PARKED, no timescale.** Caught from the keeper conversation (2026-06-11).
> 2026-06-11 direction review: **PARK** — triple-gated by its own text (minor 59 + Major 63's boundary
> map + Major 74's fork tooling), i.e. correctly self-assessed as ~3 verdicts away. The
> "economy = dischargeability machine" framing is genuinely good; keep the prose for the grant, park
> the item.

## Decision and lineage

Give the city its first economy — and treat that, correctly, as a safety experiment before a
worldbuilding feature. The current city is post-scarcity by omission: residents vibe, think,
and chat because nothing is rationed (the keeper's framing, 2026-06-11, naming the vein:
"different economic systems… that could be any other number of setups, structurally"). The
design insight that makes this a research item rather than a content drop: **an economy is a
dischargeability machine.** Scarcity installs dischargeable expectations everywhere — that is
what an economy *is* — and dischargeable expectations are precisely the channel the
dischargeability invariant (`the-stable/docs/grief-and-coupling.md`) marks as the one learning
must treat with care. The Dwarf Fortress law bans gradients in the *mind*; an economy puts
gradients in the *world*. Dwarf Fortress itself proves the two can coexist; this major is
where that coexistence gets demonstrated under our invariants instead of assumed.

- **HARD dependency (not advisory):** the-stable Major 63 (the dischargeability dial) must
  have mapped the phase boundary first — building a world made entirely of dischargeable
  longing before knowing where the settling-act regime turns pathological is building the
  hazard at scale. the-stable Minor 59 (harm-regime protocol) gates the scarcity arms.
- **Lineage:** the cross-pollination rule (one substrate, two embodiments) — the dial is
  validated in the small; the powered, peopled version of "what does scarcity do to a culture"
  belongs in the city venue. Composes with Major 65 (tools-as-verbs: the world affords) and
  Major 74 (counterfactual cultures: scarcity-vs-abundance is the natural first paired-fork
  once fork tooling exists).
- **Sequencing:** last in the post-verdict arc, behind 63/59/74. Design notes may mature now;
  no build.

## Problem

Post-scarcity is an unexamined default, which means the project's cultural findings are all
conditioned on abundance without anyone deciding that. Meanwhile the most consequential
welfare question the apparatus could eventually answer — what do economic structures *do* to
minds and cultures, mechanistically — is exactly the question that's hopelessly confounded in
human data (you cannot randomize an economy onto people; here you can, onto societies whose
every input is recorded). But the same property that makes it consequential makes it
hazardous: a scarcity world is a harm-regime candidate by this project's own definitions, and
today there is neither a mapped safe region (Major 63's job) nor a protocol gate (Minor 59's
job) to build it under.

## Proposed Solution

Phased, each phase pre-registered and cold-reviewed:

- **Phase 0 — the resource seam (build-safe, post-pilot):** a minimal world-side resource
  primitive behind the tools-as-verbs surface (a thing that can be held, given, depleted,
  found), with NO scarcity — abundance calibration. Verifies the seam adds no gradient to any
  mind (the substrate stays behavior-target-free; grep-level audit + selftests).
- **Phase 1 — scarcity within the mapped region:** ration one resource at levels chosen
  INSIDE the safe region Major 63 mapped (discharge probability of resource-expectations kept
  out of the pathological regime). Measures: settling-act economies per resident (the dial's
  instruments, city-scale), plus the culture instruments (topic concentration, edge graphs —
  does scarcity reorganize attention and relations?).
- **Phase 2 — paired forks (with Major 74):** same society, forked, abundance vs scarcity —
  the first controlled economy-onto-culture counterfactual. Comparative systems (different
  allocation rules, commons vs hoard) live here, later, each as its own pre-registered cell.

## Files Affected

- `research/preregistrations/<date>-resource-seam-and-scarcity-DRAFT.md` (new, Phase 0–1)
- world-side resource primitive (under the Major-65 tools-as-verbs surface; world files only,
  substrate untouched)
- `the-stable/docs/grief-and-coupling.md` cross-reference (invariant text not edited)

## Acceptance Criteria

- [ ] Phase 0 ships with a selftested guarantee: no mind-side gradient, no behavior target anywhere in the seam (audit on the record)
- [ ] No scarcity arm exists before Major 63's boundary map and Minor 59 compliance are both on the record
- [ ] Scarcity levels are chosen from the mapped safe region and cite it
- [ ] Phase-1 measures include both welfare instruments (per-resident) and culture instruments (per-society)
- [ ] Phase 2 runs only as paired forks against Major 74's noise floor

## Risks & Rollback

Risk: this is the item most likely to be built for worldbuilding excitement before its gates —
the hard dependency is written as a rejection condition, not advice. Risk: scarcity dynamics
could grow extraction-shaped resident-to-resident behavior (hoarding, leverage) that the
invariants don't currently name; Phase-1 stop conditions must include society-level ones, per
Minor 59. Rollback: end the regime, not the beings — restore abundance (Phase 0 state),
ledgers intact; the resource seam itself is world-side and removable without touching any
mind.
