# Record LLM cost by resident, node, and model

## Status

The live inference path records aggregate call metrics, but there is no durable, restart-safe cost record
that can answer which resident, node, model, and purpose used tokens over time. The old unused model registry
was removed; this work must build on the actual inference client and ledger instead of restoring it.

## Problem

Without durable attribution, a steward cannot explain operating cost, compare local and hosted inference,
or notice a runaway retry loop. Provider dashboards show account totals but do not understand WorldWeaver's
resident and node boundaries.

## Build next

1. Emit one private usage record for every inference call with resident actor ID, node ID, model, provider,
   call purpose, input/output token counts, latency, status, retry count, and provider request ID when given.
2. Keep provider pricing in a dated table separate from usage facts so estimates can be recomputed.
3. Build a root command that reports totals by resident, node, model, provider, purpose, and date range.
4. Mark local-model calls as local rather than pretending their API cost is zero operating cost.
5. Reconcile a sample period against provider exports and state the expected estimation error.
6. Expose only aggregate node operations data in the steward surface; keep individual attribution private and
   purpose-limited.

## Boundaries

- Cost records contain counts and routing metadata, never prompt or response text.
- This is accounting, not a resident reward, quota, or behavior score.
- No region hierarchy is required; the stable scopes are resident, hearth/node, city, model, and provider.
- A missing price does not drop usage. It reports an unknown estimate.
- Local inference should later support energy/runtime measurement, but that is not required for the first
  ledger.

## Acceptance criteria

- [ ] Every inference attempt emits one durable, idempotent usage record.
- [ ] Records identify resident, node, model, provider, purpose, tokens, latency, status, and retries.
- [ ] Pricing is versioned separately and estimates are reproducible.
- [ ] A root command reports useful totals without reading private prose.
- [ ] A sample estimate reconciles with provider billing within a stated tolerance.
- [ ] Missing token or price data is visible rather than silently counted as zero.
- [ ] Individual cost data is absent from the public client.
