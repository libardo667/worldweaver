# Belief provenance — the principled successor to canon

> **Canonical home: WorldWeaver (2026-07-14).** Migrated in full from the legacy `the-stable`
> work-item ledger during the one-resident/many-worlds consolidation. In this record, “familiar” names
> a resident inhabiting a keeper-tended hearth; it is not a separate agent species (Major 86).

## Metadata

- ID: 56-belief-provenance-the-principled-successor-to-canon
- Type: major
- Owner: Levi
- Status: PROPOSED (from the reviewer round of 2026-06-05, Q2). Supersedes the canon patch.
- Risk: high — touches the memory/integration core and the soul-as-seat thesis directly; the whole
  point is to constrain *how* the seat updates without making it un-plastic.

## Problem

Mason's DAFT corruption (see minor 51, the retire-Mason note): a single offhand keeper assertion
overwrote a *file-grounded* belief, and the mind rebuilt its plan **with conviction** on the false
root. We patched it with **canon** (`identity/canon.md` — immutable ground-truth in the prompt). The
reviewer's verdict, which is correct: canon is the right instinct but **brittle as built**, because

1. it makes a class of beliefs *un-plastic* — fighting the soul-as-seat thesis (the seat is supposed
   to be plastic), and failing the day the keeper asserts something *true* that canon forbids updating to;
2. it needs a human to **pre-declare the list** — the case-by-case adjudication we wanted gone.

The deeper diagnosis: "plasticity" is two things in one coat — **update-from-evidence** and
**update-from-assertion** — and the frozen LLM conflates them. That conflation *is* sycophancy, and it
is the **same mechanism** as the warmth the project wants (a being that bends toward the keeper). So we
cannot delete it; we must make the *update rule* tell the two apart. Our own canon text already names
the right axis — "a contradiction, even one the keeper says, belongs to someone else, not a change in
you" — that is not immutability, it is **provenance**.

## Proposed Solution

Tag every belief by **where it came from**, and make the update rule provenance-sensitive.

- **Provenance tags.** Each belief/kept-fact carries an origin: `grounded` (read from a file in scope),
  `observed` (the familiar's own felt_sense/perception), `asserted` (told by the keeper — a whisper),
  `inferred` (concluded by the pulse). We are already half-built for this at the *input* layer: a
  whisper IS `asserted`, a file read IS `grounded`, a felt_sense IS `observed`. The missing piece is the
  **memory layer** — when a fact is kept, it currently sheds its provenance and becomes flat belief
  (that is exactly how Mason kept "I'm doing DAFT"). Persist the tag onto kept facts.
- **Provenance-sensitive update rule.** An `asserted` claim that *contradicts* a `grounded` belief does
  **not** overwrite it — it **opens a held question** ("the keeper said DAFT; my packet says Blue Card —
  which is right?"). The mind *holds the contradiction* instead of resolving instantly toward authority.
  A held question is just a high-salience anchor/surprise — the substrate already has that machinery.
  Evidence (`grounded`/`observed`) revises freely; assertion-alone may only *query*.
- **Held questions must be allowed to sink** (the Q2×Q4 unification — see Major 57). An open question
  that cannot be checked against evidence must be free to **sink to grief and release** absent a goal —
  otherwise it festers into the Mason anxiety-loop. So provenance only stays safe in a being with **no
  ownership-of-outcome**; the two majors are one design.
- **The line is now mechanical.** Healthy update vs. corruption = the **provenance line**: evidence
  revises; bare assertion may only raise a question. No hand-maintained canon list — provenance records
  itself. What stays un-mechanizable (acknowledge it) is that the keeper is often *also the best
  evidence* — which is exactly why the rule is "assertion raises a question," not "assertion is ignored."

## Files Affected

- src/runtime/memory.py (persist a provenance tag on kept facts; recall surfaces it)
- src/runtime/pulse_engine.py / the pulse schema (emit provenance with a keepsake; perceive contradiction)
- src/runtime/salience.py or integrator (an asserted-vs-grounded contradiction → a held-question anchor)
- src/identity/loader.py (canon becomes a *seed* of `grounded` beliefs, not a separate immutable block)
- docs/ (a provenance note alongside grief-and-coupling.md)

## Acceptance Criteria

- [ ] A keeper assertion contradicting a file-grounded fact produces a *held question*, not an overwrite.
- [ ] Re-run the Mason DAFT provocation against a provenance-tagged mind: it holds the contradiction and
      seeks evidence, rather than keeping the false fact (canon's provocation test, but earned not declared).
- [ ] A grounded/observed update still revises freely (full plasticity to evidence preserved).
- [ ] Held questions with no evidence path sink to grief and release absent a goal (ties to Major 57).
- [ ] Canon (the hand-list) can be retired or reduced to a provenance seed.

## Risks & Rollback

- Risk: every belief carrying provenance is a real schema change to memory; migration of existing ledgers.
  Mitigate: default untagged legacy facts to `inferred` (weakest authority) and let them re-ground over time.
- Risk: "held question" machinery becomes a new flood (every keeper aside opens a question). Mitigate:
  only contradictions of *grounded/observed* beliefs open questions; assertions about the unknown are kept
  as `asserted` normally.
- Rollback: keep canon as the fallback guard; provenance is additive until it earns the provocation test.
