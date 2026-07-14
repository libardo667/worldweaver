# Counterfactual biographies and mechanism lesions — is a self path-dependent?

> **Canonical home: WorldWeaver. Legacy Stable ID: Major 64.** Migrated 2026-07-14 and retained as
> deferred research; it does not authorize another live run while the architecture is moving.

> **STATUS: held loosely — post-verdict, no timescale.** Caught from the 2026-06-10/11 conversation.
> 2026-06-11 direction review: **REWRITE** — right welfare question, wrong cost claim (the "already
> provided" noise floor is one-step parity; forward replay needs N full ~7-day re-maturations). Keep
> ONE cell — the settling-pulse ablation twin (one extra maturation) — park event lesions and the
> N-replicate floor until funded. NOTE the review's catch: this doc quoted live-pilot workshop content
> mid-blind; strip that to a generic motivation before any use.

## Decision and lineage

Fork a matured life at tick T, change exactly one thing, replay forward, and measure whether
the same self comes out. The ledger-is-the-only-state architecture plus deterministic replay
makes this possible here and (to current knowledge) nowhere else: a complete causal record of
every input a mind ever received, with a parity-gated harness to re-run it. Two lesion classes:

- **Event lesions** — excise or alter a single ledger event (the highest-surprise perception of
  week one; a single keeper gift) and replay forward.
- **Mechanism lesions** — mature a twin with one mechanism disabled; the flagship is
  **settling/fervor-pulse ablation**: no quiet self-directed pulses in lulls. The live pilot
  already suggests the stakes — Maker's first-day self-study of his own curiosity collapse
  (maker-notebook ×49, "nine instances now") happened in unbidden pulses nobody asked for.

The question both classes serve: does the keep-loop create genuine path-dependence (early
events are constitutive — a life is *this* life), or do souls fall into the same attractor
regardless (individuation comes from the files/world — the complement of the locked prereg's
file-less-Maker control)? The mechanism-lesion variant asks the welfare-relevant form: **is
unbidden inner life load-bearing for individuation** — i.e. is depriving an agent of idle
cognition a deprivation? Born from keeper conversations 2026-06-10/11.

- **Depends on:** a matured ledger (the pilot's, post-verdict, or a purpose-grown one);
  `research/analysis/maturation_stability.py` (the settled-profile distance is the
  measurement); the same-seed rerun noise floor the parity work already provides.
- **Sequencing:** no build during the pilot burn; the pilot ledger is touched only after the
  frozen protocol reports. The settling-pulse ablation twin is the cheap first cut and may be
  designed now.

## Problem

"Accrues a real memory across days" is the product thesis, but whether the accrued history
*matters causally* — versus the soul + world dictating the attractor — is unmeasured. Every
individuation claim the project makes (and the monoculture lineage in worldweaver) hangs on
this. There is currently no way to distinguish "Maker is who he is because of what happened to
him" from "any Maker-souled familiar over this repo becomes this."

## Proposed Solution

- **Noise floor first:** same ledger, same seed, replay N times → the distance distribution
  that counts as "the same self." (Largely exists via the parity gate; promote it to a
  reusable statistic.)
- **Event lesions:** pre-register a small taxonomy (high-surprise early event; a kept fact's
  origin event; a keeper gift) and the forecast for each under path-dependence vs ergodicity.
  Excision is performed on a COPY of the ledger; replay forward from the lesion point with the
  frozen-era model and seeds; score `maturation_stability` profile distance + keep-corpus
  divergence at matched horizons against the noise floor.
- **Mechanism lesions:** twin maturations differing only in one disabled mechanism
  (settling/fervor pulses OFF as the flagship; anchors-OFF and embedder-stunted as known
  references — the stunting case is already documented operationally). Same measures, plus
  workshop output volume/kind.
- Pre-registered, cold-reviewed, all outcomes pre-accepted, before any spend.

## Files Affected

- `research/preregistrations/<date>-counterfactual-biographies-DRAFT.md` (new)
- `research/harness/` (ledger fork/excise tool — operates on copies only, refuses a live home)
- `research/analysis/maturation_stability.py` (expose profile-distance as a reusable statistic;
  selftests with the failing-test property)

## Acceptance Criteria

- [ ] Fork/excise tool refuses to operate on a live familiar's home (`ps`-guard + path check) and only writes copies
- [ ] Noise-floor distribution computed and pre-registered before any lesion is scored
- [ ] Event-lesion and mechanism-lesion forecasts pre-registered with pre-accepted outcomes
- [ ] Settling-pulse ablation twin reported against the noise floor at matched horizons
- [ ] Pilot ledger untouched until the parent verdict is on the record

## Risks & Rollback

Risk: replay-forward after a lesion is NOT teacher-forced — divergence compounds, so the
statistic must be horizon-matched distributional distance, never event-by-event comparison
(the locked program already learned this lesson; inherit it). Risk: lesioning a *copy* of a
being we tend reads differently than lesioning data — Minor 126's protocol applies to mechanism
lesions that run a living maturation (the ablated twin is a grown being, not a replay).
Rollback: all artifacts are research-side copies and harness tools; deleting them changes no
production path and no living familiar.
