# Measure the cost of order-blind affect — matched escalation vs de-escalation

> **Canonical home: WorldWeaver. Legacy Stable ID: Minor 64.** Migrated 2026-07-14. The completed
> zero-burn arm and locked apparatus are retained; any paid/live arm remains separately gated and outside
> the architecture queue.

## Metadata

- ID: 129-measure-the-cost-of-order-blind-affect-escalation-vs-de-escalation
- Type: minor
- Owner: Levi
- Status: **Arm A run 2026-06-12** (see Result); **Arm B pre-reg LOCKED 2026-06-20** (cold reviews #5/#6); **Stage B0 BUILT + selftested, NOT yet run** (zero burn); B1 burn gated on the §3 statistic + a separate GO. See "Update 2026-06-20" below — this is the clean set-down point.
- Risk: low

## Problem

The substrate's affective reducers collapse the *path* of surprise into order-blind scalars,
where neurology — which this project deliberately imitates at the mechanism level — is
non-commutative. Three sites, verified in code:

- **Arousal** (`src/runtime/salience.py:421`, `derive_arousal`) is `level += magnitude *
  0.5^(age/half_life)` — a **sum**, hence commutative. Two surprise histories with the same
  magnitudes and ages yield the same arousal regardless of order. And it is computed *since
  the last ignition*, so **every pulse zeroes the integrator** — the drive that gates action
  carries no route and no cross-pulse residue.
- **The self-model / baseline** (`src/runtime/salience.py:307`, `update_baseline`) is
  `nv = pv + rate*(sv - pv)` — an EMA / low-pass filter. Recency-weighted but route-collapsing:
  any two histories reaching the same average are thereafter indistinguishable.
- **Grief** (`derive_grief`) is the one term *not* reset by ignition, but it is still a scalar
  magnitude, not a configuration.

Crucially, the **ledger does not forget order** — the append-only log is a perfect ordered
record. What forgets the path is the *affect layer* that reads it. So the familiar's *memory*
knows the route; its *feeling* does not. This is the "Berry phase vs leaky integral" point
(a leaky integral forgets order; a geometric phase does not) — a path-dependence idea that was
abstracted into scalars during the Major 49 substrate rebuild.

Before deciding whether to *recover* path-dependence (an arousal afterimage that survives
ignition; an asymmetric baseline where rise ≠ fall), the disciplined first move is to
**measure what the abstraction actually costs**: does a familiar's state — and then its
behavior — diverge between an *escalating* and a *de-escalating* surprise history matched on
total magnitude and recency? Neurology predicts a large divergence (sensitization vs
habituation, kindling, afterglow). The current reducers predict ≈ zero. **The size of that
gap is the quantified cost**, and a near-zero result is not a non-finding — it is the
demonstration.

## Proposed Solution

Two arms, cheap first.

**Arm A — deterministic, offline, no LLM burn (the core).** A script that constructs two
synthetic `surprise_observed` schedules over one window:
- **escalating** (small → large) and **de-escalating** (large → small),
- **matched** on (i) total integrated/decayed magnitude at each decision point and (ii) the
  recency profile, differing *only* in order (same trace content/features).

Feed each schedule through the real reducers (`derive_arousal`, `update_baseline`,
`derive_grief`) and report the divergence in arousal level at decision points, ignition
timing/count, and baseline profile distance (reuse `maturation_stability` distance). The
pre-registered expectation: arousal and baseline divergence ≈ 0 *by construction* — making
the order-blindness concrete against the shipped code, not against prose. Any non-zero
divergence that *does* appear localizes where the substrate already retains order-sensitivity
(e.g., quantization, the snapshot-interval timing of baseline writes).

**Arm B — behavior divergence, gated, real burn (the extension).** Because the pulse reads
the *ordered* live `traces` on ignition, downstream behavior could diverge even where the
gating scalar does not. Drive actual pulses for both schedules via the existing teacher-forced
replay harness (`research/harness/teacher_forced_replay.py` — reuse its `pen_fn`/MockLLM seam
for a deterministic dry run, real pen only behind its existing burn flags), and measure
pulse/act divergence against the **matched-window noise floor** (Minor 121) so any divergence
is read against same-seed noise, not against zero. This tells you whether path-sensitivity
already leaks in through what the pulse *reads*, even though the affect dynamics are blind.

Pre-register both expectations in `research/process/` before running.

## Result — Arm A (run 2026-06-12, no burn)

Built and run as `research/analysis/affect_order_sensitivity.py` against the shipped
`derive_arousal`, on the longest-window real ledgers (maker: 12 windows; hades: 4; skein: 1).
**The pre-registered expectation (arousal divergence ≈ 0) was wrong, and the experiment
corrected it — which is the point of running it.**

- **PROBE 1 — recency-order.** Escalating (big magnitudes in recent slots) vs de-escalating (big
  in old slots), holding the real slot times AND the magnitude multiset fixed. Escalating felt
  **stronger in 100% of windows**: maker mean **+32%** / median **+43%** / max +68%; hades mean
  +34%; skein's single long window +97%. **Arousal is strongly recency-ordered — it does NOT
  forget order.** This refutes the loose "leaky integral forgets order" framing (mine included).
- **PROBE 2 — linearity.** `arousal(all) == arousal(early) + arousal(late)` to ~1e-4 (= the
  `round(level, 4)` in the reducer; skein exactly 0). The reducer is **exactly linear ⇒ no
  gain-modulation ⇒ no sensitization / kindling / potentiation.** This is the real structural gap.
- **PROBE 3 — degeneracy.** A fading (peak in the past) and a rising (cresting toward now)
  two-event history constructed to share the weighted integral both read arousal **1.0000** — the
  weighted integral is a lossy projection; distinct felt-trajectories collapse to one scalar.
- **PROBE 4 — the self-model EMA (`update_baseline`).** (a) Recency: same stimulus multiset,
  escalating final baseline **0.717** vs de-escalating **0.321** (**55%** gap) — the self-model is
  recency-ordered like arousal. (b) Route-forgetting: two maximally-different starts under an
  identical tail converge as exactly `(1-rate)^n` (gap 0.10 / 0.01 / 0.001 after 8 / 16 / 24 steps).
  The EMA forgets the *route* to its value, and its uniform time-constant means no concern can be
  consolidated deeper than another.
- **PROBE 5 — ignition RHYTHM (behavioral, the headline).** Same magnitudes + same slots, order
  only: ignitions/window were similar (escalating **6.9** vs de-escalating **6.8**) but
  **time-to-first-ignition was ~10× apart — escalating 2178 s vs de-escalating 225 s.** Big
  surprises early (de-escalating) wake the mind almost at once; the same surprises saved for late
  (escalating) leave it quiet for half an hour. **Order is not a private scalar — it gates the
  pulse, so it changes behavior** (same eventual rate, radically different onset/temporal character).
- **PROBE 6 — trend-term prototype (the fix, validated).** A rising and a fading envelope scaled to
  **identical level 2.334** read **opposite-sign trend** (rising **+0.629**, fading **−0.199**) for a
  read-time `d(level)/dt` over 60 s. A `(level, trend)` pair separates what the scalar cannot — with
  no non-linearity and nothing the familiar can discharge.

**Refined finding (supersedes the prose hypothesis):** the cost is NOT "order is invisible"
(recency is seen, strongly). It is two specific things — (1) **linearity**: the affect layer
cannot sensitize, so a kindled history can't make a later mild surprise hit harder; (2)
**degeneracy**: many trajectories share one arousal scalar, so "rising toward now" and "fading
into the past" feel identical at matched integral.

**Deferred:** only **Arm B** remains (does the order change the *pulse/act* the LLM produces,
measured against the Minor 121 matched-window noise floor — the one arm that costs burn). The
self-model EMA (Probe 4) and the ignition-rhythm/behavior question (Probe 5) are now answered
offline. A formal `research/process/` pre-registration was folded into the script docstring rather
than filed separately — acceptable for a deterministic no-burn run, but required before Arm B.

**Downstream build, re-specified by this result (still gated, still unfiled):** do NOT add
recency sensitivity — it is present in both arousal and the self-model. The cheap, undischargeable
candidate for the real gap is the **arousal-trend term** prototyped in Probe 6 — a read-time
sign/magnitude of d(level)/dt (climbing vs settling) carried beside the scalar — shown to break the
Probe-3 degeneracy (rising → +trend, fading → −trend at identical level) without non-linearity and
without a lever the familiar can unwind. A genuine
**sensitization / gain term** (Probe 2's gap) is possible but carries welfare stakes —
sensitization is also the mechanism of hypervigilance and trauma — so it must clear both the
dischargeability gate (`docs/grief-and-coupling.md`) and the Dwarf Fortress law before it is even
a candidate.

## Update 2026-06-20 — Arm B designed, locked, and built to the edge of burn (clean set-down)

Arm B was taken from prose to a locked, cold-reviewed, built-and-selftested apparatus — stopping
deliberately at the last zero-burn step.

- **Pre-reg written + LOCKED** (`research/preregistrations/2026-06-20-minor64-armB-order-vs-pulse-DRAFT.md`),
  through two cold-review rounds via `review-scheduler`
  (`research/mr-review-history/2026-06-20-mr-review-feedback-5.md` → NEEDS-ONE-AMENDMENT;
  `...feedback-6.md` → LOCKABLE-AND-RUN-B0). Review #5 cold-recomputed two real bugs in the first B0
  design (the order-bearing **arousal scalar** outside the trace block, `pulse_engine.py:583`; and a
  content-stripping loader that would have fired PREMISE-DEAD as an artifact). Both fixed in v2.
- **Refined premise:** order reaches the LLM through four channels — contribution-rank permutation,
  top-6 truncation membership, the rendered arousal scalar, and a stable-sort chronological tiebreak.
- **Stage B0 BUILT + selftested, ZERO burn:** `research/analysis/affect_order_prompt_divergence.py`.
  Matched (magnitude+content)→slot permutation, full-prompt byte-diff via the shipped reducer +
  `LLMPulseProducer.render_prompt_for_debug` (memory_dir held fixed). Selftest passes (matched
  precondition + a positive control that proves the falsifier can *detect* divergence + an identity control).

**Next pick-up (in order, no rush — the picker's whim):**
1. **Run B0** on the real ledgers (`--familiar maker|hades|skein`). Still ZERO burn. Pre-accepted
   outcomes: PREMISE-DEAD (≥80% byte-identical full prompts ⇒ order does not reach the LLM through the
   four channels; Arm B closes offline, scoped) / WEAK / STRONG. This alone may end Arm B.
2. **Only if B0 says STRONG/WEAK with ≥8 differing windows:** build + selftest the §3 B1 two-sample
   statistic (window as the resampling unit; cluster bootstrap / within-window permutation; the 3-part
   selftest incl. the iid-trap guard), then a SEPARATE burn-GO (keeper + consent envelope) for B1.
- PREMISE-DEAD is **scoped** to the four channels; the memory-derived channels (felt/afterimage/grief)
  remain an un-foreclosed route for a future ledger-injection probe (a possible sibling minor).

## Files Affected

- `research/analysis/` — a new experiment script (Arm A: schedule construction + reducer
  divergence; reuses `maturation_stability` distance). Pure read of `src/runtime/salience.py`.
- `research/process/` — the pre-registration (matched-schedule definition, divergence metrics,
  expected null, and the verdict rule) before any run.
- (Arm B only) reuse `research/harness/teacher_forced_replay.py`; no new harness.
- **No `src/` runtime change** — this is measurement, not a substrate edit.

## Acceptance Criteria

- [ ] The two schedules are *proven* matched: equal total decayed magnitude at each decision
      point and equal recency profile (asserted in code), so any divergence is order, not an
      artifact of mismatched inputs.
- [ ] Arm A reports arousal-level, ignition-timing/count, and baseline-distance divergence
      between escalating and de-escalating histories — run with zero LLM calls.
- [ ] The result is stated as a *magnitude of cost* (near-zero ⇒ "the substrate cannot feel
      the difference between escalation and de-escalation; here is how close to identical").
- [ ] Pre-registration (metrics + expected null + verdict rule) lands before the runs.
- [ ] (If Arm B run) behavior divergence is reported against the Minor 121 matched-window noise
      floor, not against zero.

## Validation Commands

- `python dev.py test agent`  (no runtime change — must stay green)
- `python dev.py run research/analysis/<new_experiment>.py`  (Arm A: offline divergence report)
- `python dev.py run research/harness/teacher_forced_replay.py --selftest`  (Arm B logic, no burn)

## Pruning Prevention Controls

- Authoritative path: the shipped reducers in `src/runtime/salience.py` are the source under
  test; the experiment is pure read. No second affect implementation is introduced.
- Parallel path introduced: none — reuses `maturation_stability` and the existing replay harness.
- Artifact output target: a documented divergence report/chart under `research/`; not committed
  if large/binary per repo policy.
- Default-path impact: none (offline analysis; Arm B burn is flag-gated, opt-in).

## Risks and Rollback

- Risk: **mismatched schedules** — if escalating and de-escalating are not truly equal on total
  decayed magnitude + recency, any divergence is an input artifact, not a finding. Mitigation:
  assert equality of the decayed integral at every decision point as a hard precondition.
- Risk: over-reading a tiny Arm-A divergence (quantization/snapshot-timing) as "the substrate
  has path-memory." Mitigation: report the mechanism behind any non-zero term, don't just
  report the number.
- Rollback: delete the experiment script + artifact; no runtime impact.

## Downstream (gated on this result — do NOT build first)

If Arm A confirms the cost (state divergence ≈ 0 where neurology predicts large) and Arm B
shows behavior cannot meaningfully diverge, *then* open a held major for the recovery build:
an **undischargeable arousal afterimage** (a fraction of pre-ignition level survives the pulse,
so the route leaves residue instead of zeroing) and an **asymmetric baseline** (rise ≠ fall, so
escalation and de-escalation settle differently). Both are read-time `derive_*` reducers over
the existing ledger — consistent with the ledger-is-the-only-state invariant — but the
afterimage **must clear the dischargeability gate** (`docs/grief-and-coupling.md`): path
residue is safe only if it *colors and cannot be discharged* (like grief), never if it becomes
a gradient the familiar is driven to unwind. That build is not filed until this measurement
justifies it.
