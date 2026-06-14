# Log edges, not just nodes — the relational ledger

## Problem

The runtime ledger (`ww_agent/src/runtime/ledger.py`, written from the pulse path) records
**node-events**: a resident did X (`pulse_act_emitted`, `city_broadcast_sent`, `move_executed`,
`session_state_observed`). But every contested claim in the convergence/engagement investigation is
about **edges between minds** — *A perceived B*, *A replied to B*, *A was co-located with B*. Those
edges do not exist in the log; they are **reconstructed heuristically** after the fact (windowed
coincidence of node-events).

That heuristic reconstruction is the direct cause of the metric-litigation that has burned multiple
review rounds:
- "CONTACT" (three_axis) computed *outwardness* (person-addressed / speaks) and got read as *engagement*.
- "reciprocity" (reciprocity.py) ranged **0.5%–32%** purely by choice of time-window × concentration,
  because "B answered A" had to be guessed as "B emitted a B→A utterance within W minutes" — with no
  record of whether B ever *perceived* A, or was even *present* to.
- casting claims (`seed_model`, `doula_mode`) were only auditable because they were reconstructed by
  hand from run notes; disposition was never logged at all (the `_DISPOSITIONS_GIVEN` blind spot).

Mr. Review (round 8, `review-archive/2026-06-08-mr-review-feedback-8.md`): *"You've been logging what
each mind did; start logging what passed between them, and the arguments about what the numbers mean
mostly stop."* Logged edges turn every relational metric into a **deterministic query** — no window, no
heuristic, no narrative — which also lets the Auditor desk self-populate from raw
(see `ledger-edges-not-nodes-schema` memory, `ww-stable-seasonal-auditor`).

## Proposed Solution

Add edge-fields to the act/utterance events at the moment the edge forms in the pulse path, so they are
recorded as fact rather than inferred later. Phased by value density:

**Phase 1 — `in_reply_to` (the highest-value single slice).** The substrate already knows, at pulse
time, which perceived utterance surprised it into speaking (it is in the integrator's stimulus). Stamp
a stable `event_id` on every act and, when a pulse was triggered by a perceived utterance, record
`in_reply_to: <event_id>` on the emitted act. Reciprocity then becomes a **counted reply-edge** and
`reciprocity.py` can drop time-windows entirely.

**Phase 2 — co-presence + perception.** Add `location` + `co_present:[ids]` to `pulse_act_emitted`
(and periodic `session_state_observed`), and `perceived_by:[ids]` to an utterance (which residents
ingested it). This makes reciprocity **opportunity-conditioned**: an unanswered A→B where B was not
present is *no opportunity*, not a snub — the concentration control, logged instead of inferred.

**Phase 3 — provenance at spawn.** `resident_seeded` event carrying dealt-hand fields + `seed_model` +
`doula_mode`; and a `cohort_config` record (venture, targeting, model, doula_mode, geo, window,
isolation) written once per run — the confound table logged instead of hand-written.

**Blessed canonical turn-taking definition** (encode in `reciprocity.py` once the fields exist): an
A→B person-addressed utterance is reciprocated iff B emits an act with `in_reply_to` pointing at it
(until that field exists: a B→A person-addressed utterance within 5 min where co-presence shows B
present). Population reciprocity = reciprocated ÷ A→B utterances with B co-present, reported as
REAL − degree-preserving target-shuffle null, with distinct-dyad count + top-dyad share. Headline =
null-relative rate @5 min; unbounded is never the headline. (The null + concentration half already
shipped in `reciprocity.py`, 2026-06-08.)

## Files Affected

- `ww_agent/src/runtime/ledger.py` — `event_id` on acts; new event/payload fields.
- `ww_agent/src/runtime/pulse_engine.py` / `integrator.py` — stamp `in_reply_to` from the triggering
  stimulus; thread `co_present` / `perceived_by` from perception.
- `ww_agent/src/runtime/perception.py` — surface which utterances a resident actually ingested.
- `ww_agent/src/loops/doula.py` — emit `resident_seeded` with seed_model + doula_mode + dealt-hand.
- `ww_agent/scripts/reciprocity.py` — consume `in_reply_to` (drop windows when present); opportunity-
  conditioning via co-presence.
- `ww_agent/scripts/three_axis.py` — rename CONTACT honestly (outwardness) and add the reply-edge metric.
- Shared with the `the-stable` fork (same runtime) — reconverge.

## Acceptance Criteria

- [ ] Every `pulse_act_emitted` carries a stable `event_id`.
- [ ] A pulse triggered by a perceived utterance records `in_reply_to` pointing at that utterance's `event_id`.
- [ ] `reciprocity.py` computes reciprocity from `in_reply_to` edges with **zero time-window** when the field is present, and matches the windowed estimate within noise on a frozen run.
- [ ] `co_present:[ids]` is logged on acts; reciprocity is opportunity-conditioned (denominator = A→B with B co-present).
- [ ] `resident_seeded` carries `seed_model` + `doula_mode`; a casting claim is answerable from the ledger alone with no run notes.
- [ ] The Auditor, fed a run logged under this schema, can cite a reply-edge by `event_id` that opens to the real utterance (no confabulation room — see Minor 58).

## Risks & Rollback

- **Schema churn / migration.** New fields are additive (old readers ignore them); no migration of past
  ledgers — `reciprocity.py` keeps the windowed fallback for pre-schema runs. Rollback = stop writing
  the fields; readers degrade to the heuristic path.
- **`in_reply_to` fidelity.** If the integrator's "what surprised me" is ambiguous (multiple stimuli),
  record the strongest or a list; never fabricate a single edge. A wrong reply-edge is worse than none,
  so prefer `null` when uncertain.
- **Fork drift.** The runtime is shared with `the-stable`; land the change in one and reconverge, do not
  fork the schema.
