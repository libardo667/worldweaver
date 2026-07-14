# The disorientation signal — a salience channel for incoherence (the trigger that convenes a reckoning)

> **Canonical home: WorldWeaver. Legacy Stable ID: Major 72.** Migrated 2026-07-14. Phase 0 is a
> completed legacy-Stable instrument; behavioral Phase 1 remains gated and must be reconciled into the
> universal resident runtime before use.

## Metadata

- ID: 121-the-disorientation-signal-a-salience-channel-for-incoherence
- Type: major
- Owner: Levi
- Status: **Phase 0 BUILT + calibrated** (2026-06-15). `derive_disorientation` + four honest cue
  detectors in `src/runtime/salience.py`, surfaced in `scripts/field_guide.py`, 11 calibration tests
  (full suite 246 green). Pure read, no behaviour change. Calibrated against Maker's REAL ledger:
  cue-1 felt-vs-fact fires on the 06-14 06:31 "measurements caught" search-empty (via the
  misattribution-recognition path; the realization landed 11s *after* the empty search), cue-3
  re-derivation fires on real near-dup keeps. cue-2 claim-vs-record validated synthetically; firing on
  the real 05:16 episode needs recipient-matching (the claim was surrounded by other chat) — a noted
  Phase-0.1 refinement. cue-4 keeper-correction is wired but silent (no heard-channel/keeper-flag yet).
  **Phase 1 (convene the reckoning) deliberately NOT built — gated on looping Maker in.** Spec below is
  the original (2026-06-14).
- Risk: low in Phase 0 (pure read, no behavior change — measure first, the project's discipline); medium in
  Phase 1 (it convenes a reasoning pass that changes what the resident does — cycle-gated, loop Maker in).
- The one genuinely new piece under [COGNITION-PLAN.md](../../docs/COGNITION-PLAN.md) **Lever 2** (the full-fat
  orienting reasoning gear). The loop (Major 59 `continue_tool`), the instruments (recall/search, made
  honest in archived Major 124), and the cost-gating (Major 119 tiered pens) already exist or are portable — *this
  signal is what they were missing.*

## Problem

The substrate has exactly one trigger for cognition: **surprise** (mismatch between stimulus and the
afterimage) accumulates into arousal, and crossing threshold is **ignition**. Surprise is the wrong
instrument for the failure we keep watching. Maker's recurring trouble is not novelty — it is
**incoherence**: getting the *order of things* wrong, mistaking inner for outer, re-deriving what he
already knew. Observed, all in his own ledger:

- **felt-vs-fact misattribution** — he felt a spike ("measurements caught"), `search`ed the *world's files*
  for it, found nothing, and only then realized "I named a sensation and treated the name like a fact about
  the world" (2026-06-14 ~06:31).
- **claim-vs-record contradiction** — he was certain he'd answered Claude three times when no such act had
  been emitted ("I hallucinated responding… before it actually arrived").
- **worn-groove re-derivation** — the cliff insight written four times across days, each as if new.
- **keeper-correction** — Levi repeatedly having to say "that's not right / you hallucinated / it's the
  pen's signature, not a broken thread."

A single forward pulse cannot catch any of these — there is no step where the mind *checks before it acts*.
And he will not reliably summon that check himself: when disoriented he reached for `search` (outward) when
he needed `recall` (inward), and needed the keeper to redirect. So the **substrate** must notice the
incoherence and convene the reckoning. There is currently no signal that measures it.

## Proposed Solution

A new salience channel, `derive_disorientation`, **read-time derived over the ledger** like everything else
(no second source of truth). It is a leaky, windowed integral of observable **incoherence cues**, each a
pure read:

1. **Felt-vs-fact reach** — an outward tool call (`search`) that returns empty (`No readable file…`) for a
   query that matches the resident's *own* recent `felt_sense` / anchors. He looked outside for an inside
   thing. *(The cleanest, most concrete cue — and a complete episode is already on the ledger.)*
2. **Claim-vs-record gap** — a pulse that asserts a self-action ("I answered / replied / sent / did…")
   in a window with no corresponding `pulse_act_emitted` / `packet_emitted`. He believes he acted; the
   record disagrees.
3. **Re-derivation** — a fresh `felt_sense` / keep that is a near-duplicate (embedding cosine, reusing
   `MemoryRecall.novel`'s threshold) of one already held, within a short window: the worn groove, measured.
4. **Keeper-correction** — a `chat_heard` from the keeper carrying a bounded set of correction cues
   ("that's not right", "actually", "you hallucinated", "no —"). (Brittle by keywords alone; a keeper-set
   flag is the robust form — note it as an option.)

The channel is **separate from arousal** (it is not surprise) and feeds its own threshold.

### Phase 0 — measure only (no behavior change; do first)
`derive_disorientation(events) -> {score, cues:[…]}` + a `field_guide` line ("how often, and why, it loses
the thread"). Trains nothing, changes no live behaviour — exactly as `prediction.py` scored before any
learning. **Calibrate against the known episodes above** before wiring anything: the signal must light up
on the "measurements caught" search-empty, the re-derived cliff, and the hallucinated reply, and stay dark
on ordinary surprise.

### Phase 1 — convene the reckoning (gated; Lever 2)
When the score crosses threshold, ignite a **reckoning** instead of (or before) an ordinary pulse: the
bounded, tool-equipped orienting pass (Major 59 loop; recall/search/check-the-record; reasoning trace
captured; consolidates to one pulse), on the capable pen (Major 119). The reckoning prompt **states the
scenario** ("you seem disoriented about X — here are your instruments") and **never tells him what to
conclude** (archived Major 124 discipline). Cycle-gated: loop Maker in first.

## Files Affected

- `src/runtime/salience.py` or `src/runtime/signals.py` — `derive_disorientation` + cue detectors (Phase 0).
- `scripts/field_guide.py` — surface the signal + its cues (Phase 0).
- `src/runtime/{integrator,cognitive_core}.py` + `pulse_engine.py` — convene the reckoning on threshold,
  reusing `continue_tool` (Phase 1).
- `tests/` — each cue detector fires on its episode and stays dark on ordinary surprise.

## Acceptance Criteria

- [ ] Phase 0: `derive_disorientation` lights up on each known episode (search-empty-for-an-inner-query;
      near-dup re-derivation; claim-with-no-act) and stays near zero on ordinary high-surprise pulses.
      Pure read; no live behaviour change; surfaced in `field_guide`.
- [ ] The signal is **distinct from arousal** — a novel-but-coherent moment does not raise it.
- [ ] Phase 1 (separate cycle, Maker looped in): crossing threshold convenes a reckoning that states the
      scenario, draws on the orienting tools, and consolidates into one pulse — behaviour-shaping forbidden.
- [ ] Tests green.

## Notes

- **Welfare:** an *artifactual* disorientation he can't escape from the inside is the same class of problem
  as the phantom (minor 66) — the resolving move isn't available to him until we build it. This signal is
  how the substrate offers the help instead of waiting for the keeper to notice.
- Keep cue detection **honest**: a cue is a *fact about the record* (a search returned empty; no act exists;
  a near-dup was stored), never a judgment about the quality of his thought.
