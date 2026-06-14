# Observability and Bottleneck Triage

Without instrumentation, pruning decisions become guesswork.

## Minimum telemetry model

Track these per request/job:

- route or operation name
- trace or correlation id
- total duration
- phase timings (selection, generation, persistence, render prep)
- model/provider used (if LLM call)
- token/cost data (if available)
- status (`ok`, `error`, `timeout`, `fallback`)

## Three bottleneck classes

## Class A: Remote model latency

Signals:

- high chat/embedding duration
- retries/timeouts dominate total request time

Typical actions:

- reduce call count in hot paths
- parallelize safe phases
- cache reusable context vectors
- move optional calls to background lane

## Class B: Local compute/data latency

Signals:

- DB queries dominate
- serialization/scoring phases dominate
- cache miss rates are high

Typical actions:

- index and query tuning
- data shape normalization
- cache strategy and TTL tuning
- avoid repeated full scans

## Class C: Correctness-induced latency

Signals:

- retries from invalid states
- UI waits on non-critical subsystems
- fallback loops from unstable integrations

Typical actions:

- decouple optional subsystems
- fail fast with best-effort degradation
- tighten contracts and data invariants

## Triage cadence

Per week:

1. Capture top 3 slowest user-facing operations.
2. Classify each into A/B/C.
3. Create one improvement item per top bottleneck.
4. Record before/after metrics in PR evidence.

## Decision rule

Do not remove subsystems based on complexity alone.

Remove or demote when:

- measured impact is low on core outcomes,
- maintenance risk is high,
- and the same user value can be delivered more simply.

