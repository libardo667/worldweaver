# Bound elective reading before it consumes the resident's waking time

## Status

The first one-hour Alderbank cohort exposed this as a measured runtime problem. Four residents produced 224
active pulses and made 1,138 elective information reads. Because every read asks the model what to do next,
those pulses required 1,362 model calls and 3.72 million prompt tokens. Short meetings passed while residents
were still inside multi-call reading chains.

The finding is recorded in
[`research/runs/2026-07-19-alderbank-four-resident-baseline/FINDINGS.md`](../../research/runs/2026-07-19-alderbank-four-resident-baseline/FINDINGS.md).

## Problem

Elective information is the right architecture: a resident should be able to inspect a source instead of
being force-fed a town-wide narration bundle. The current continuation contract nevertheless allows a pulse
to keep reading until its reading window is exhausted. Each read is another inference call with another large
prompt. In the Alderbank run, one initial pulse averaged more than five reads.

This spends money and time without guaranteeing action, rest, or better grounding. It also stretches the
effective tick interval, so a resident can miss short co-presence and addressed speech even though the host's
nominal pause is twenty seconds.

## Proposed solution

1. Give every active pulse a small explicit read budget. Start with a conservative default of one or two
   continuations, configurable for a bounded run but capped by the host.
2. Carry the remaining budget in the typed pulse context and receipt. When it reaches zero, remove `reach`
   from the contract and allow one outward act or no act.
3. Deduplicate equivalent reads within a pulse and across a short freshness window. Reading the same source
   and query again should return the prior structured record or decline without another model call.
4. Let a source return enough structured metadata for the model to choose one useful record without opening
   a chain of nearly identical reads.
5. Record content-blind measures: reads requested, reads served, duplicate reads avoided, budget exhaustion,
   calls per pulse, time in the pulse, and whether an outward act followed.
6. Keep urgent embodied perception outside this budget. Hearing a person in the same room is not an elective
   information read; opening citywide chatter or an archive is.
7. Compare the same Alderbank cohort with the old and bounded continuation contracts before changing the
   default for long resident runs.

## Files affected

- `ww_agent/src/runtime/pulse.py`
- `ww_agent/src/runtime/pulse_engine.py`
- `ww_agent/src/runtime/information.py`
- `ww_agent/src/runtime/integrator.py`
- `ww_agent/src/runtime/cognitive_core.py`
- `ww_agent/scripts/resident_once.py`
- `ww_agent/scripts/resident_cohort.py`
- `ww_agent/tests/`
- `docs/reference/resident-runtime.md`

## Acceptance criteria

- [ ] A host-configured maximum bounds information continuations within one active pulse.
- [ ] Reaching the budget closes the typed reading window without malformed retries or a forced outward act.
- [ ] Repeating the same fresh source/query does not cause another model call.
- [ ] Exact-place speech, visible co-presence, and other embodied perception do not spend elective read budget.
- [ ] Structural receipts report calls, reads, deduplication, budget exhaustion, elapsed pulse time, and action
  outcome without recording private read content.
- [ ] A synthetic source that always invites another read cannot exceed the configured cap.
- [ ] Hearth travel, city travel, shutdown, and cleanup can interrupt a reading chain safely.
- [ ] A matched Alderbank run materially reduces calls and prompt tokens per active pulse without reducing
  observed local speech or co-presence delivery.

## Risks and rollback

A budget that is too small can make real research shallow. Keep the cap configurable within a host maximum,
allow a later pulse to resume from a durable source pointer, and measure source diversity before lowering the
default. Rollback is the existing reading-window limit, not an unbounded loop and not ambient narration.
