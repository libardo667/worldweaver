# Pruning Playbook

Pruning is an explicit development phase to remove accidental complexity.

## Pruning targets

Look for:

- duplicated logic paths
- dead code and stale compatibility layers
- features that are unreliable and non-core
- synchronous work that can be best-effort background
- heavy abstractions with low leverage

## Candidate scoring

Score each candidate from 1 to 5:

- user value
- reliability
- complexity cost
- operational risk
- observability quality

Prioritize pruning when:

- user value <= 3
- reliability <= 3
- complexity cost >= 4

## Pruning strategies

## Strategy A: Delete

Use when value is low and replacement exists.

## Strategy B: Merge

Use when two paths do the same thing with minor differences.

## Strategy C: Demote

Use when feature is valuable for power users but unstable as default.

Demotion example:

- move feature behind explicit toggle
- keep endpoints/contracts for compatibility
- remove dependency from critical completion path

## Strategy D: Isolate

Use when subsystem remains but should not block core flow.

## Safe pruning protocol

1. Freeze baseline behavior with tests.
2. Add temporary feature flag if risk is medium/high.
3. Execute pruning in bounded commits.
4. Validate baseline scenarios.
5. Remove temporary flags if no longer needed.

## Required pruning evidence

- before/after complexity notes
- before/after latency/error observations
- confirmed unaffected critical flows
- rollback notes

