# WorldWeaver Vision (V3)

## The One-Sentence Pitch

**WorldWeaver is a narrative simulation engine where a reducer-committed world evolves turn by turn, while multi-lane AI planners continuously project plausible futures and render grounded scenes in real time.**

## Product Contract

WorldWeaver must deliver three things on every turn:

1. A coherent immediate scene that is grounded in current state, not generic atmosphere.
2. A strict canonical world history that only changes through reducer-validated commits.
3. A continuously prepared near-future frontier so the next turn is faster and more coherent.

## V3 Narrative Architecture

V3 formalizes three narrative lanes with different privileges.

| Lane | Primary role | Allowed context | Output type | Canon authority |
| --- | --- | --- | --- | --- |
| World narrator (planner/referee) | Evaluate plausibility and project near futures | World bible, constraints, scene-card summary, recent committed facts | Structured projection stubs (`allowed`, `confidence`, deltas, anchors) | None |
| Scene narrator | Render the present turn | Full scene card, selected projection seed, goal lens, recent events | Player-visible scene prose and choices | None |
| Player narrator (hint filter) | Expose limited perspective hints | Restricted scene/projection subset plus player state | Hint text and clarity labels | None |

The reducer remains the only canonical authority.

## Projection-First World Model

V3 treats speculative futures as first-class but non-canon data.

- Maintain a per-session projection tree with bounded breadth-first expansion.
- Expand only top-K candidates under strict depth, node, and time budgets.
- Keep projection data separate from canonical world history.
- Invalidate stale/conflicting projection branches after each committed turn.

### Clarity Levels

| Level | Meaning |
| --- | --- |
| `unknown` | No reliable information yet |
| `rumor` | Low-confidence hint only |
| `lead` | Structured plausible branch |
| `prepared` | Scene-ready projection seed exists |
| `committed` | Canonical fact after reducer commit |

## Turn Lifecycle (V3)

1. **Ack**: Immediate one-line confirmation.
2. **Commit**: Deterministic validation plus reducer-authoritative state mutation.
3. **Narrate**: Scene narrator renders from scene card plus selected projection seed.
4. **Hint**: Player narrator emits limited-knowledge signal (optional/additive).
5. **Weave ahead**: Background planner expands projection frontier within budgets.

## Canon Safety Rules

- Speculation is never canon until reducer commit succeeds.
- Failed commits must rollback transaction state.
- Projection IDs are trace metadata, not truth.
- Route contracts stay stable unless explicitly approved.

## Performance and Quality Goals

V3 optimization targets:

- Stable request latency under bounded planner budgets.
- Near-zero hidden harness overhead inflation.
- Reduced motif gravity and repetition while maintaining scene grounding.
- Observable projection quality via hit/waste/veto metrics.

## Non-Goals

- No unbounded tree search or full simulation of all futures.
- No speculative branch promotion to canon without player-triggered commit.
- No route-breaking API redesign in v3 rollout.

## Delivery Strategy

- Implement v3 as atomic major/minor improvements with explicit acceptance criteria.
- Keep all high-risk work behind feature flags and budget controls.
- Use sweep and smoke harnesses as mandatory quality gates for planner changes.
- Maintain single-source status in `improvements/ROADMAP.md`.
