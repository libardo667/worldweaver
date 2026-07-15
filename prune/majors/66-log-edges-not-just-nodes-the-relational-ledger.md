# Log edges, not just nodes — the relational ledger

## Update (2026-07-14) — re-baselined: Phase 1 was ALREADY ~2/3 built; verified & closed

The major was filed "proposed / unstarted." Recon found Phase 1 largely shipped, its consumer
already written, but never verified end-to-end. This pass verified it and closed the one metric-
relevant gap. **Stale paths corrected below:** `loops/doula.py`→`runtime/doula.py`;
`scripts/reciprocity.py` & `three_axis.py`→`research/probes/` (both moved in Major 83).

**Already built before this pass (state of the code):**
- `event_id` on every ledger event — `append_runtime_event` (`ledger.py:1425`), both forks
  (byte-identical, canonical-in-the-stable). **Criterion #1 met.**
- `in_reply_to` on `chat_sent` / `city_broadcast_sent` / `speech_carried` — computed by
  `WorldEffector._reply_edge` (`effectors.py:168-179`) from `Act.target × self.heard` (the
  addressee's most-recent perceived overture). Stable perceived-utterance `id` at
  `perception.py:147,157`. **Criterion #2 met.**
- Consumer already complete — `reciprocity.py:perceived_conditioned` (`:63-110`): counts an
  overture answered iff its perceived `id` reappears as a sent `in_reply_to`; dyad concentration,
  top-dyad share, power gate (`MIN_PERCEIVED_OVERTURES=20`).

**Design decision LOCKED (keeper, 2026-07-14) — do not re-open:** the addressee-based reply-edge
(`_reply_edge`) is **canonical**. It matches the blessed *person-addressed* definition. The major's
"stamp `in_reply_to` from the triggering stimulus (integrator knows what surprised it)" is **rejected
as anti-architecture**: the substrate deliberately severs packet→act (the pulse reads reduced node
state, not packet identity; the surprise trace carries feature fields, no utterance id). Threading
true-stimulus identity would fight that design and is fork-wide. Accept the reconstruction.

**Done this pass:**
- **Verification run (criterion #3)** — `research/runs/2026-07-14-reciprocity-edge-verification/FINDINGS.md`.
  On the stationary `ww_pdx_keep` cohort the edge-based rate (20.4%, conclusive) agrees in direction
  and rough magnitude with windowed@5min (14.3%) and clears the null — **#3 met for that cohort**.
  On high-motion `ww_pdx_deal` the edge metric is **underpowered** (10 perceived overtures < 20 gate)
  — itself a finding: motion suppresses perception, so addressing ≫ perceived-overtures, which is
  direct empirical motivation for Phase 2 (opportunity-conditioning).
- **Coverage gap closed** — `_write`/`mail_intent_sent` now stamps `in_reply_to` via `_reply_edge`
  (`effectors.py:243-248`), additive-only. `reciprocity.py` does **not** count mail as reciprocation
  yet — that metric-definition call is deferred to the keeper. Emit smoke test added
  (`tests/test_cognitive_core.py::test_effector_mail_stamps_reply_edge_when_recipient_was_heard`).
- **Deliberately left:** overheard utterances carry no `id` (`_sense_overheard`,
  `perception.py:229-244`) — correct, you cannot reply to content you only overheard the existence
  of. Canonical `pulse_act_emitted` carries no reply-edge (reciprocity reads the effector events,
  which do) — skipped, not needed for the metric.

**Remaining (NOT done this pass):**
- **Phase 2 — co-presence + perception** (`co_present:[ids]`, `perceived_by:[ids]`): neither fork.
  The verification's deal-vs-keep split is the empirical case FOR it (opportunity-conditioned
  denominator). Criteria #4.
- **Phase 3 — spawn provenance** (`resident_seeded` with `seed_model`/`doula_mode`, `cohort_config`):
  neither fork; would emit from `runtime/doula.py`. Criterion #5. (Cohort labels in the verification
  were *inferred from motion*, not read from a logged config — exactly this gap.)
- **Criterion #6** (Auditor opens a reply-edge by `event_id` to the real utterance / Minor 58):
  out of scope; the metric joins within a resident's own ledger (perceived `id` → `in_reply_to`) and
  does not need cross-ledger event resolution.
- **Related substrate concern surfaced:** the ledger front-truncates at `_MAX_EVENTS=10000`
  (`ledger.py:26`), which silently windows any long run and is in tension with the append-only-log
  philosophy and the grief-undischargeable boundary. Candidate separate major (unbounded/compacted
  ledger). Does not bite these short frozen cohorts.

**Fork note:** producers live in `effectors.py`/`perception.py` (bidirectional; ww is ahead,
the-stable has no reply-edge). Lands in `ww_agent`, the canonical substrate owner; it is not blocked on
or synchronized from the historical Stable tree. `ledger.py` needed no change (already has `event_id`).

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

- [x] Every event carries a stable `event_id` (`append_runtime_event`; all events, not just acts).
- [x] A pulse triggered by a perceived utterance records `in_reply_to` — via `_reply_edge`
      (addressee-based reconstruction, keeper-blessed as canonical). Points at the perceived
      utterance's stable `id`, not a ledger `event_id` (see #6, out of scope).
- [~] `reciprocity.py` computes reciprocity from `in_reply_to` with zero window: **met on the
      stationary cohort** (keep: 20.4% edge vs 14.3% windowed, agree within noise); **underpowered
      on the high-motion cohort** (deal: 10 < 20-overture gate). See 2026-07-14 FINDINGS.
- [ ] `co_present:[ids]` on acts; reciprocity opportunity-conditioned. **(Phase 2 — deferred.)**
- [ ] `resident_seeded` carries `seed_model` + `doula_mode`. **(Phase 3 — deferred.)**
- [ ] Auditor cites a reply-edge by `event_id` that opens to the real utterance. **(Out of scope;
      Minor 58 confabulation guard. The metric joins within a resident's own ledger and doesn't
      need cross-ledger event resolution.)**

## Risks & Rollback

- **Schema churn / migration.** New fields are additive (old readers ignore them); no migration of past
  ledgers — `reciprocity.py` keeps the windowed fallback for pre-schema runs. Rollback = stop writing
  the fields; readers degrade to the heuristic path.
- **`in_reply_to` fidelity.** If the integrator's "what surprised me" is ambiguous (multiple stimuli),
  record the strongest or a list; never fabricate a single edge. A wrong reply-edge is worse than none,
  so prefer `null` when uncertain.
- **Fork drift.** The runtime is shared with `the-stable`; land the change in one and reconverge, do not
  fork the schema.
