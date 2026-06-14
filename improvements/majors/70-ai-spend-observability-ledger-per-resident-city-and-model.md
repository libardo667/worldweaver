# AI-spend observability ledger — per resident, city, and model

## Decision and lineage

User-facing billing is **not** the target; **observability of our own AI spend** is. The
keeper wants to see, at a glance, where inference money goes — overall, and broken down by
resident, by city/shard, by region, and by model — to learn which models and which residents
burn the most, and on which models. This is instrumentation for *our* spend, not a product
billing feature.

- **Reframes / absorbs:** major 26 (isolate-actor-billing) and major 27 (actor-usage-ledger
  and spend-caps). Those built a per-call ledger schema (`model_id`, `prompt_tokens`,
  `completion_tokens`, `estimated_cost_usd`, `trace_id`) for **player BYOK** narration spend
  and **explicitly excluded `agent_runtime` calls**. This major **reuses that schema and
  inverts the scope** — it is *about* the agent-runtime calls #27 excluded. The retired pieces
  (player budget caps, observer-mode lockout) do **not** come along.
- **Threads onto:** major 66 (log edges, not nodes) — spend is another fact to log at
  formation. A pulse's cost is logged where the pulse happens, attributable, not reconstructed.
- **Status:** proposed (2026-06-08, keeper's call).

## Problem

The data exists in pieces but cannot be joined into the question that matters.

- `ww_agent/src/inference/client.py` already tracks `last_usage` and running
  `total_prompt_tokens` / `total_completion_tokens` per client, and logs
  `inference: model=… tokens=…+…` per call — but this is **in-memory per client**, not a
  persisted, attributable record.
- `ww_agent/scripts/cost_curve.py` turns usage into a **projected** cost-per-resident-hour
  under synthetic calm/busy worlds — a forecasting harness, not a ledger of **actual live spend**.
- `openrouter-activity-*.csv` has real dollars (`Usage`, `Requests`, `Prompt/Completion/
  Reasoning Tokens`) but **only per-model-per-day** — no resident, no city.

So today there is **no way to answer**: which residents cost the most? on which models? which
city/shard dominates spend? where would a cheaper model save real money? The attribution axis
(resident × city × model) is missing, and the per-pulse cost is never durably logged.

## Proposed Solution (phases)

### Phase 1 — Log a spend fact at every pulse
At each ignition, the `InferenceClient` already holds `model` + `last_usage`. Emit a
`pulse_cost` event into the resident's runtime ledger (write-after, off the critical path)
carrying: `resident`, `shard` (city), `region` (bioregion if set), `model_id`, `operation`,
`prompt_tokens`, `completion_tokens`, `reasoning_tokens`, `estimated_cost_usd`, `ts`,
`trace_id`. Spend becomes a first-class logged, attributable fact.

### Phase 2 — Cost estimation
A small model→price table (input/output/reasoning $ per token) yields `estimated_cost_usd`
per pulse. Keep the table in one place, versioned; default to the provider's published prices.

### Phase 3 — The spend reader (the deliverable the keeper asked for)
`ww_agent/scripts/spend.py` — a ledger reader in the `reciprocity.py` family that aggregates
the logged `pulse_cost` facts and prints:
- **overall** spend + token totals (window-selectable: today / 7d / all)
- **per resident** (top spenders)
- **per city/shard** and **per region**
- **per model**
- the **resident × model cross-tab** ("which residents on which models cost most") — the
  headline question
- cheapest-swap hints: per-resident spend if its model were swapped down a tier (uses the
  Phase 2 price table).

### Phase 4 — Reconcile against the OpenRouter actuals
Cross-check the summed per-model estimate against `openrouter-activity-*.csv` (the real
per-model-per-day dollars). Report drift; if estimates diverge beyond a threshold, the price
table is stale. The CSV is the external ground truth; our per-pulse log is the attribution.

### Phase 5 (later, optional) — soft budget visibility
Per-resident / per-shard spend **alerts** (a number crossing a line surfaces to the steward).
**Visibility only** — NOT the retired player lockout/observer-fallback enforcement.

## Files Affected

- `ww_agent/src/inference/client.py` — expose per-call `(model, usage)` for logging
- `ww_agent/src/runtime/` (pulse engine / ledger) — emit the `pulse_cost` event at ignition
- `ww_agent/src/runtime/` ledger reducers — a `derive_spend` view if read-time aggregation fits
- `ww_agent/scripts/spend.py` — NEW reader (overall / resident / city / region / model / cross-tab)
- a model→price table (e.g. `ww_agent/src/inference/pricing.py` or a small data file)
- reconciliation helper reading `openrouter-activity-*.csv`
- reuse, do not rebuild, major 27's per-call field set

## Acceptance Criteria

- [ ] Every LLM pulse logs a `pulse_cost` fact attributable to resident + shard + model, with
      token counts and an estimated cost; logging is off the pulse critical path.
- [ ] `spend.py` reports overall, per-resident, per-city/shard, per-region, per-model, AND the
      resident × model cross-tab, over a selectable time window.
- [ ] The summed per-model estimate reconciles against the OpenRouter CSV within a stated
      tolerance; drift beyond it flags a stale price table.
- [ ] No player-BYOK billing, budget cap, or observer-mode lockout is (re)introduced — this is
      observability of agent-runtime spend only.
- [ ] `python scripts/dev.py quality-strict` green; a small fixture-ledger test for the reader.

## Risks & Rollback

- **Estimate drift.** Published prices change; estimates are approximate. Phase 4 reconciliation
  against the real OpenRouter dollars is the guardrail — treat the CSV as truth, the per-pulse
  log as attribution, and report the gap rather than hiding it.
- **Logging overhead on the pulse path.** Write the cost fact after the act is emitted
  (observational, like `in_reply_to`); never let accounting reorder or delay cognition.
- **Scope creep back into billing.** The retired player-billing/caps machinery must NOT ride
  back in under this banner. Visibility and (optional) alerts only.
- **Rollback** is git; the `pulse_cost` event is additive and ignorable by every other reader.

---

*Created 2026-06-08. Reframes majors 26/27 from player billing to agent-spend observability;
reuses #27's per-call schema; threads onto #66 (log facts at formation); reconciles against the
OpenRouter activity export.*
