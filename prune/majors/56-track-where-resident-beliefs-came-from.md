# Track where resident beliefs came from

## Status

The 2026-07-20 source audit made provenance visible both before and after an elective read, preserved egress
and selection details through the prompt boundary, and removed a summary-based pseudo-history source. The
runtime already records provenance on actions, relationship edges, world facts, and many subjective facts.
What is still missing is one clear belief record that retains its evidence and can represent uncertainty or
disagreement without silently overwriting an earlier belief.

## Problem

A resident may learn something by seeing it, hearing it, reading a file, recalling their own history, or
inferring from repeated events. Those sources should not have equal weight, and a later assertion should
not erase a well-supported belief merely because it is newer.

The old proposal called this a replacement for a hand-written “canon” list. The current goal is simpler:
make the resident's own factual claims inspectable and evidence-backed. This is not a city or steward
authority over what a resident is allowed to believe.

## Build next

1. Define a versioned subjective-claim shape with a stable claim ID, proposition, confidence, source class,
   source event or record IDs, first/last observed time, and current state.
2. Distinguish direct perception, direct correspondence, scoped reading, self-memory, computation, and
   inference.
3. Let a new claim support, weaken, contradict, or leave another claim unresolved.
4. Preserve competing claims as a question when evidence does not settle them.
5. Derive the current belief view from the append-only ledger; do not make the projection the authority.
6. Include only bounded, relevant belief evidence in prompts.
7. Give the resident an elective way to inspect why a claim is present.

## Boundaries

- A steward cannot declare a resident's private belief true by editing a database row.
- Source provenance describes where a claim came from; it does not guarantee that the source was correct.
- Private belief records stay in the hearth unless the resident deliberately communicates a claim.
- The system does not score residents for holding approved beliefs.
- Ordinary expressive speech is not blocked by this work; exact source claims are handled separately by
  Major 67.

## Acceptance criteria

- [ ] Subjective claims retain stable source event or source-record references.
- [ ] Directly observed and merely heard claims remain distinguishable after restart.
- [ ] Contradictory claims can coexist without silent last-write-wins replacement.
- [ ] A reduced belief view is rebuildable from the resident ledger.
- [ ] Residents can electively inspect the evidence behind a claim.
- [ ] City travel and hearth migration preserve claims and their provenance.
- [ ] No public or steward endpoint exposes private belief contents by default.
