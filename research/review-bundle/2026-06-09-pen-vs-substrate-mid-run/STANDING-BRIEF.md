---
name: standing-brief
description: The only memory that auto-loads into a new WorldWeaver review. Method rules, falsifiers, and correction principles ONLY — no findings, no narrative, no verdicts.
classification: procedural
source_paths:
  - <repo>/research/mr-review-history/
  - <repo>/ww_agent/scripts/reciprocity.py
  - <repo>/ww_agent/scripts/three_axis.py
  - <repo>/worldweaver_engine/AGENTS.md
  - <repo>/research/   # PUBLIC cold-verifiable run evidence (ledgers + recompute scripts)
supersedes: []
autoload: true
last_reviewed: 2026-06-08
---

# WorldWeaver Standing Brief

This is the **only** document that travels into a new review session. It carries **methods,
falsifiers, and correction principles** — never findings, never "what we found," never verdict
language. Every line cites the granted artifact it was derived from. Paths are relative to
`<repo>/` unless absolute.

If you are reading this at the start of a review: you are deliberately starting cold. Re-derive
every claim from raw evidence. If a statement here cannot be checked against its cited source,
treat it as unproven and say so — do not inherit it.

**Two readers, two first moves.** This brief is dropped into fresh sessions of two kinds; identify
which you are before doing anything.
- **The cold REVIEWER (Mr. Review).** This brief + the published round are *all* you get — no
  project memory, no narrative, claims and raw evidence only. Your first move: open the latest round
  under `worldweaver/research/review-bundle/<date>-<label>/` (pull it cold from GitHub) and the raw it
  cites in `research/runs/`, and pre-mortem or re-derive it. Do **not** seek out the project's
  interpretations; you were narrowed on purpose.
- **The co-researcher / EXECUTOR.** You build and run the experiments and draft the desk packets the
  reviewer tears into. You *may* consult the curated cognition tree ad hoc (this tree:
  `memory-management/instances/worldweaver/` — `memory/<bucket>/`, `indexes/`) to recover current
  direction and state; the reviewer may not. Your first move: read the cognition tree for the live
  direction, then ground every claim in code/ledgers before drafting. Hold yourself to the same
  falsifiers below so your work survives the cold read — but you are the builder, not the skeptic.

**Where the evidence lives.** This tree (local) is the *method*. Cold-verifiable *run evidence* — raw
ledgers, recompute scripts, findings — is PUBLIC in `worldweaver/research/runs/<run>/` (e.g.
`research/runs/2026-06-08-armC-ab/`: `FINDINGS.md` + gzipped `ledgers/` + `analysis/lexical_count.py`; and
`research/runs/2026-06-08-register-calibration/`). Verify run numbers THERE by recompute; never accept them on
testimony. Method local and un-marinating; evidence public and checkable.

**Where the review rounds live (the reviewer's entry point).** Each round is published as plain,
browsable files to `worldweaver/research/review-bundle/<date>-<label>/` and pushed to GitHub
(`github.com/libardo667/worldweaver`); the reviewer pulls the round cold from there. A round carries a
`REVIEW-PROMPT`/`REVIEW-FOLLOWUP` and a pre-registration (metric roles + verdict rule locked before the
data). Heavy evidence stays in `research/runs/` and is pointed at from the round prose. The executor
builds each round in the gitignored workspace `review-bundle/` at the repo root and ships it with
`./research/archive.sh <label>` (copy → commit → push → clear the workspace). The reviewer's
replies come back to the operator, who saves them dated alongside the prior `mr-review-feedback-N.md`.

---

## 1. Locked falsifier rules

These are pre-registered: committed before the data existed, so the acceptance rule cannot move
after seeing numbers. Do not relax them mid-analysis.

- **Venture-OFF falsifier is LOCKED (2026-06-08).** Primary metric: directed turn-taking at the
  **5-min window**, scored as **REAL − degree-preserving target-shuffle null** (z), never raw rate.
  [`research/mr-review-history/2026-06-08-venture-off-preregistration.md:9-19`]
- **Verdict rule — "venture buys engagement" is accepted ONLY if** ON's null-relative turn-taking is
  clearly above chance (z>2, multi-dyad) AND exceeds OFF beyond the noise band — i.e. removing
  venture **collapses real answering toward chance** while ON holds. Otherwise the result is
  "venture buys only outwardness/motion." [`…preregistration.md:20-27`]
- **Concentration bar (both metrics):** the excess must be carried by **≥3 distinct dyads** with
  **top-dyad share < 50%**. One ping-ponging couple is not population engagement.
  [`…preregistration.md:17-18`]; same bar in [`research/mr-review-history/2026-06-08-mr-review-feedback-8.md:31-32`].
- **Conditioner is PERCEIVED, not co-present** (the decisive round-2 correction). Condition the
  reciprocity rate on **"did the addressee perceive the overture,"** NOT "was B physically
  co-present." A `co_present` denominator computes the OFF arm's rate over its tiny co-located subset
  and **discards the broadcast/letter channel the OFF arm actually uses** — erasing the baseline, not
  coarsening it. Numerator = reply-edges (perceived AND answered); denominator = person-addressed
  overtures the addressee actually perceived, channel-agnostic. `co_present` is the right tool for
  spatial questions later, the wrong conditioner here. [`…preregistration.md:29-43`]
- **Min-overture inconclusive gate** (distinct job from perceived-conditioning): pre-gate a minimum
  OFF perceived-overture volume below which the run is **INCONCLUSIVE, not a venture win**. Perceived-
  conditioning fixes the systematic bias; the gate fixes the power problem. Need both.
  [`…preregistration.md:46-49`]; encoded as `MIN_PERCEIVED_OVERTURES = 20` in
  [`ww_agent/scripts/reciprocity.py:60`].
- **Replication 2+2 is the FLOOR, not the proof.** If the ON−OFF difference lands **inside** the
  within-condition spread, the result is INCONCLUSIVE → escalate to 3+ arms; do not call it.
  [`…preregistration.md:51-53`]
- **Internal contrast only.** Read ON-vs-OFF within a single run; do not anchor on a prior run's
  absolute z (e.g. "z was +26 last time"). A re-deal breaks absolute comparability.
  [`…preregistration.md:54-55`]
- **Tie-break:** if the logged reply-edge and the windowed-null disagree, the **edge wins, in the
  conservative direction** — a logged reply beats a temporal coincidence, so the edge can only tighten
  a verdict, never loosen it. [`…preregistration.md:13-16`]

---

## 2. Canonical metric definitions (derive from code, not from memory)

The rawest source for "what a metric actually computes" is the code. When a metric's name and its
computation are in tension, the computation is what is true.

- **OUTWARDNESS** = person-addressed speaks / total speaks. This is what the `three_axis` CONTACT
  axis sees. It measures an utterance *aimed at* a named person — not whether anyone answered.
  [`ww_agent/scripts/reciprocity.py:5-16`, `three_axis.py:17-19,77-85`]
- **RECIPROCITY (the real engagement signal)** = of A→B person-addressed utterances, the fraction
  that B later answers with a B→A person-addressed utterance. Distinct from outwardness; this is the
  thing that "carries a we." [`reciprocity.py:11-16`]
- **CONTACT ≠ ENGAGEMENT.** The `three_axis` CONTACT axis computes *outwardness*, not *engagement*;
  `reciprocity.py` exists precisely to separate the two. A "directed, named, responsive utterance"
  scored mechanically is outwardness; whether it was *received and answered* is the separate
  reciprocity question. [`reciprocity.py:3-7`, `three_axis.py:18-19`]
- **pair-lenient** (of ordered pairs A→B, fraction whose reverse B→A occurs at all) is **trivially
  satisfied** and is reported only to expose it — it is not a signal. [`reciprocity.py:14-16,267-268`]
- **The shuffle-null's role:** a **degree-preserving target-shuffle** holds each speaker's volume and
  the global in-degree fixed, permutes who-addresses-whom, recomputes the answer rate over
  `NULL_DRAWS=400` reproducible draws. It asks: *is real turn-taking above what the same-volume
  chatter would produce by coincidence?* Report **z = (REAL − null_mean) / null_sd**, never the raw
  rate. [`reciprocity.py:166-187`, `research/mr-review-history/2026-06-08-mr-review-feedback-8.md:8-11`]
- **Engagement bar (mechanized):** above-chance requires **z > 2 AND ≥3 dyads AND top-dyad share <
  50%**. [`reciprocity.py:258`, `…preregistration.md:21-22`]
- **Edges, not nodes (blessed schema direction):** the ledger logs node-events (resident did X) while
  every contested claim is about edges (A perceived B; A replied to B; A co-located with B).
  Reconstructing edges heuristically is what makes "reciprocity" range 0.5–32% by window×
  concentration. Log edges at formation (`event_id`, `perceived_by`, `in_reply_to`, `co_present`,
  `resident_seeded`, `cohort_config`) and each relational metric becomes a deterministic query.
  [`research/mr-review-history/2026-06-08-mr-review-feedback-8.md:60-87`]

---

## 3. Named pitfalls — each a one-line method principle, grounded in its originating correction

- **A metric measures what it computes, not what you name it.** Before banking a number, read the
  code that produces it; if the name ("contact", "engagement") outruns the computation
  (outwardness), the name is the error. [`reciprocity.py:3-7`]; the same discipline applied to tool
  output: "name it for what it is, not for the gesture it isn't"
  [`research/mr-review-history/2026-06-06-mr-review-feedback-1.md:21`].
- **A reported arc can be a measurement artifact (operator's "phantom-arc").** An improvement does
  not exist until it survives a proper chance baseline. The "33% contact / a real we" arc on
  `on_argmax` was at/below chance once the shuffle-null was applied — that "contact" was outwardness
  with no reciprocation in it. Do not bank an arc until it clears its null.
  [`research/mr-review-history/2026-06-08-mr-review-feedback-8.md:19-25`, `research/mr-review-history/2026-06-07-mr-review-feedback-7.md:21`]
  *(The label "phantom-arc" is operator shorthand, not raw-record vocabulary; the phenomenon is the
  cited reversal.)*
- **Substrate-as-depth attribution.** Movement firing is the substrate acting as motor cortex, not
  evidence of relational depth; and a model "discovering" a fact you built into its wiring is the
  architecture restating itself, not an independent finding. Do not read mechanism-sufficiency as a
  claim about which term dominates in reality. [`research/mr-review-history/bench-argmax-vs-sampled-2026-06-07/POSTMORTEM.md:23`,
  `research/mr-review-history/2026-06-06-mr-review-feedback-3.md:21`]
- **No verdict / "PROVEN" language without a fresh adversarial test.** Soften claim verbs to "the
  model suggests / the data is consistent with"; a coherent story around a premise reads as
  confirmation until an *external* ground-truth contradicts it (coherence-within-one-mind is not
  corroboration). A pre-first-test claim is "a coherent hypothesis awaiting its first independent
  test." [`research/mr-review-history/2026-06-06-mr-review-feedback-3.md:21`]
- **Marination.** A reviewer who reads the project's own story of itself becomes a loyalist, not a
  skeptic; if a claim feels obviously true, suspect you have been marinated. Triage and review must
  be done by a structurally separated agent working from claims + raw evidence only — never from
  inside the session that produced the interpretations. [`research/mr-review-history/mr-review-desk/open-questions.md:3,8`]
- **Cognitive vs observational (a logging change that is secretly an intervention).** Pure logging
  read off the substrate (e.g. `in_reply_to` resolved substrate-side by matching the act's target to
  an already-perceived utterance — the model is never prompted "which are you answering?") is
  observational and safe to add mid-investigation. If the same field were *elicited* from the model,
  it would be a cognitive change wearing a logging hat and **must be held out of the experimental
  arm.** Before adding any instrumentation mid-run, ask which one it is. [`…preregistration.md:66-72`]
- **Don't advance to the next lever before the current claim survives its null.** Re-derive the
  reciprocity-aware metric from the frozen ledgers (a read, not a run) *before* building satiety or
  spending a new arm; if the headline number collapses toward baseline, the banked claim was an
  artifact and the next build was premature. [`research/mr-review-history/2026-06-07-mr-review-feedback-7.md:35`]
  *(NEEDS-ARTIFACT: the stronger "shiny-on-brand" framing — be suspicious of a new lever that appears
  exactly when the old one fails — was NOT found as an originating correction in the granted raw
  record. Operator: point me to its source or this stays dropped.)*
- **Highest-grounded is not highest-leverage.** A fix justified by "we already built it" (reconnecting
  dead code) argues only that the fix is cheap and legible — not that it is where the variance lives.
  Credit it only after the same null-relative, confound-controlled test as any other lever; and watch
  for the sharper trap, citing a result to justify a change the same result argues against (e.g.
  invoking "behavioural samples beat prose" to add prose-adjacent samples while leaving a literal
  shared sample untouched). [`research/mr-review-history/2026-06-08-voice-register-preregistration.md`]
- **A null-relative metric is only as powerful as its instrument.** Calibrate the instrument against a
  known-positive before reading a null as substantive: confirm it can separate cases *designed* to
  differ on the measured axis (e.g. authored register samples under the metric's own embedder), or a
  null means "the instrument can't see it," not "it isn't there" — and that unpowered null silently
  feeds whatever verdict branch it points at. *Rider:* when the known-positive is INTERNAL to the system
  and the system removes it (e.g. the authored samples turn out not to exist for the live cast), the gate
  must import an EXTERNAL known-positive and be re-labelled for the weaker claim it now supports
  ("sensitive in general," downgraded from "resolves our own cases").
  [`research/mr-review-history/2026-06-08-voice-register-preregistration.md`]
- **An inert arm is a void, not a weak arm.** Before locking a pre-registration, verify each arm's
  *mechanism* can actually fire against the LIVE data — not merely exist in code. An arm whose mechanism
  is empty for the real cast (e.g. a voice-injection arm when the cast has no authored voice) reads to a
  later marinated reader as a real contrast but tests nothing; drop it, do not keep it "in case."
  [`research/mr-review-history/2026-06-08-voice-register-preregistration.md`]
- **With no internal ground-truth, run a cadre of instruments and require the result to survive
  substitution.** When you cannot validate the metric against the system's own ground-truth (it doesn't
  exist, or the system removed it), don't ride the verdict on one instrument — run several and require
  the finding to hold across all that pass calibration. And pre-register what a *split* across
  instruments means BEFORE seeing one, or the split becomes a license to pick the answer you wanted
  (a win under the topic-confounding instrument but not the content-controlled one is a phantom arc, not
  a result). [`research/mr-review-history/2026-06-08-voice-register-preregistration.md`]
- **A score on your own probe set verifies the harness, not the instrument.** Reserve pass/fail for an
  out-of-distribution benchmark you did not construct; a flattering number on a home-built or
  in-distribution set is the first millimeter of the phantom-arc slide. When two instruments
  cross-validate each other, BOTH directions of the out-of-distribution check must land before either is
  admitted — otherwise the in-distribution leg quietly carries the weak instrument.
  [`research/mr-review-history/2026-06-08-voice-register-preregistration.md`]
- **A robustness-across-instruments lock presupposes the instruments measure the same axis.** When two
  instruments disagree past chance on the SAME items, check they share a construct (correlate their
  per-item judgments) BEFORE choosing a new benchmark — cross-validation between instruments that
  measure different things is unsatisfiable by construction, and no benchmark repairs it.
  [`research/mr-review-history/2026-06-08-voice-register-preregistration.md`]
- **Inter-instrument agreement is convergent validity, not criterion validity.** Two instruments can
  agree at high r while both failing the same way (correlated blindness — e.g. both pulled by content
  overlap on near-duplicate pairs), so agreement establishes a shared axis but never discharges the
  ground-truth gate. What it can buy is collapsing a reciprocal-pair gate to a single fair pass carried
  across the agreement regime — and a coarse-axis gate validates only large-register detection, never
  fine peer-register resolution. [`research/mr-review-history/2026-06-08-voice-register-preregistration.md`]
- **A validation chain where each step repairs the previous step and none has yet measured the actual
  target is a rescue spiral.** The tell is a load-bearing limitation repeatedly labelled "the residual"
  and carried forward, while the local coherence of each fix carries you past whether the whole edifice
  can see the target at all. Exit by running the cheapest direct test of whether the metric resolves the
  REAL target — often against a known-positive already in hand — before spending one more step validating
  the instrument against a contrast that isn't the one the experiment turns on. (A spiral you can name is
  one step from a spiral you can exit.) [`research/mr-review-history/2026-06-08-voice-register-preregistration.md`]
- **When an apparatus fails against a known-positive matched to your target, suspect the target is below
  the resolution of available tools — not that this one tool is wrong.** The disciplined response is to
  act on MECHANISM where the intervention is reasonable-by-construction and reversible, not to build the
  next measurement family (that is the spiral in a fresh coat). Shipping a mechanism-justified change with
  the effect EXPLICITLY UNQUANTIFIED beats a fourth ruler — guard it by shipping only reversible,
  no-downside levers, claiming the mechanism not the effect, and pre-registering what would legitimately
  re-open measurement. [`research/mr-review-history/2026-06-08-voice-register-preregistration.md`]
- **Swapping a template is not reducing templating.** Measure the aggregate distribution, not the
  anecdote — a lever that changes WHICH attractor a population falls into has not reduced convergence, it
  has *relocated* it (arm C: OFF locked on "I'm here. I read…" 33.8%, ON on "I've been listening…" ~25%,
  opener-diversity identical 0.48). Corollary: a small isolated cohort converging on one attractor may be
  an echo artifact of scale, not a property worth a metric — vary the *condition* (scale/federation)
  before building the ruler. [`research/runs/2026-06-08-armC-ab/FINDINGS.md`]

---

## 4. Methodological commitments

- **Pre-register before data.** Lock metric roles, verdict rule, and confound controls before any
  numbers exist, so the acceptance bar cannot be moved after seeing them.
  [`research/mr-review-history/2026-06-08-venture-off-preregistration.md:1-6`]
- **Gate claims against the source, not your thoughts.** Provenance discipline applies hardest to the
  source that most flatters you. [`research/mr-review-history/2026-06-06-mr-review-feedback-3.md:21`]
- **Log edges, not nodes.** Record what passed between minds, not just what each mind did; the
  arguments about the numbers mostly stop. [`research/mr-review-history/2026-06-08-mr-review-feedback-8.md:60-87`]
- **Push bias down, leave the genius alone.** Credit a lever only where it earned its keep against a
  thing the model was biased away from; do not over-engineer the wash. [`…POSTMORTEM.md:40`]
- **Stop on a stability line, not an activity line.** End a run when the contact axis clears a floor
  (engagement means something) AND attention concentration has plateaued — not when a raw event
  counter trips. "Never stabilized" is itself a result worth having.
  [`research/mr-review-history/2026-06-07-mr-review-stop-condition.md:7`]
- **When a correction lands, promote it here** as a principle — do not merely save it as a memory.
  [`durable/README.md` hygiene rule 4]
- **Route a review with a desk packet, not the brief alone.** The brief carries method; it does not
  carry the artifacts it cites. Hand a fresh reviewer the exact raw, re-runnable evidence for the
  question at hand (greps, diffs, commit hashes, paths) so they verify rather than inherit; a fresh
  reviewer correctly holds cited-but-unseen claims as unproven until the packet supplies them.
  [`durable/README.md` hygiene rule 6]

---

*Maintenance: this file is linted by `tools/audit-brief` — every line must be a method rule, a
correction principle, or a falsifier, and must carry a source. No findings, no narrative, no verdict
words ("proven", "clearly", "we found"). It is the single `autoload: true` artifact; nothing else
loads into a new session.*
