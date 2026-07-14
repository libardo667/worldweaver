# Gate provenance: what is allowed to become soul

> **Disposition: complete; archived 2026-07-14.** All acceptance criteria are checked and the named
> production service/tests remain present. Tuning the population window is operational follow-up, not an
> unfinished architecture slice.

## Metadata

- ID: 61-gate-provenance-what-becomes-soul
- Type: major
- Owner: Levi
- Status: **built (2026-06-06)** — all three provenance rules landed in `growth_service.promote_growth` + the population baseline wired into the live endpoint; 6 new gate tests. Preventive: the gate is still empty live, so this is in place *before* learning turns on at scale (as Mr. Review urged).
- Risk: medium–high — governs identity change under learning; the place a world-event could launder into thirty souls
- Depends On: the server-side concordance growth gate (built — `worldweaver_engine/src/services/growth_service.py`). Do this **before** turning learning on at city scale.

## Problem

The growth gate (concordance: promote a theme only if it recurs ≥3× across ≥2 calendar days) is built and currently empty (residents stage reveries/goals, 0 soul-edits). Mr. Review's load-bearing risk: "recurs across days" conflates **temporal recurrence** with **self-sourcing** — a multi-day world event (a storm) clears that bar *trivially* precisely because it is world-sourced, so the gate would faithfully promote "structural-infrastructure-fixation" into a florist's and a baker's souls alike, baking the **weather** into identity. Two adjacent hazards: an **unfulfillable goal** promoted to soul becomes Mason's cell made permanent (a commitment to an action the world affords no way to complete); and a self-delta about **social strategy** (how to get peers to respond) promoted to soul is where attention-farming would grow.

## Proposed Solution

Three provenance rules on what may become soul — all **law-safe** (provenance/attribution, never preference/target):

1. **Differential persistence past the event.** Promote a theme only if *this mind's* attention to it **outlasts the population's**. The population is the **null hypothesis for world-provenance**, not a divergence target: the florist still thinking drainage a week after the rain (when the engineers have moved on) genuinely grew; the one who drops it when the rain stops was just wet. (Not "be different" — that's a target; this is pure attribution, the same family as dedup-diversity and canon-provenance.)
2. **Dischargeability gate on goal promotion.** A `goal_update` promotes to soul only if the world affords an action that can **discharge** it. An unfulfillable goal may pass through as reverie; it must never become soul (a soul-commitment you can never act on is the toxic goal×undischargeable cell, made permanent — Major 57's cell).
3. **No social-strategy promotion.** Never promote a self-delta whose *content* is a social strategy (eliciting peer attention) rather than about the world or the self. Learning points at cognition, never at social instrumentality — the guard that gives attention-farming no surface to grow on.

## Files Affected

- `worldweaver_engine/src/services/growth_service.py` — `promote_growth` gains the three rules.
- a rolling cross-resident **population-theme baseline** (for rule 1 — the null hypothesis).
- a **world-affordance** check (does an action exist to discharge this goal — rule 2).
- a **social-strategy** heuristic/classifier on self-delta content (rule 3).
- `worldweaver_engine/tests/service/test_growth_service.py` — tests per rule.

## Acceptance Criteria

- [x] A theme the whole population converges on (a world event) and then drops is NOT promoted; one a single mind retains past the population IS. — rule 1 defers a cluster matching a still-current `population_theme` (`pday >= this mind's latest_day`); promotes once this mind outlasts it. Tests: `test_rule1_defers_a_theme_the_population_is_still_on`, `test_rule1_promotes_when_this_mind_outlasts_the_population`, `test_rule1_promotes_a_self_sourced_theme_despite_a_population_baseline`.
- [x] An unfulfillable `goal_update` never reaches `growth_text` (reverie-only). — rule 2: `_looks_like_goal` × `_goal_is_dischargeable` rejects absolute/totalizing vows before clustering. Tests: `test_rule2_never_promotes_an_undischargeable_goal`, `test_rule2_promotes_a_dischargeable_goal_that_recurs`.
- [x] A social-strategy self-delta is never promoted. — rule 3: `_is_social_strategy` rejects peer-attention-eliciting content outright. Test: `test_rule3_never_promotes_a_social_strategy_self_delta`.
- [x] Tests cover each rule (mirror the concordance-gate tests). — 6 new tests in `tests/service/test_growth_service.py` (14 total pass).

## How it was built

- `promote_growth` gains three law-safe, **injectable** rules (all *attribution*, never *preference* — no content reward, no target):
  - **Rule 3 (no social-strategy)** and **Rule 2 (dischargeable goals)** are per-proposal filters applied *before* clustering — a rejected proposal never even counts toward a theme's concordance, and is recorded in `meta["rejected_pulse_ids"]` (with reason) so it isn't re-examined. Rule 2 only applies to goal/vow proposals (`_looks_like_goal`: explicit `kind` first, else a vow-phrasing fallback); un-dischargeable = an absolute/totalizing vow the world affords no finite act to complete.
  - **Rule 1 (differential persistence)** is a per-cluster gate using a `population_themes` baseline (the world-event null hypothesis): a mature theme matching a population theme the population is *still on* is **deferred** (left un-promoted AND un-consumed, so it can promote later) until this mind's latest activity on it strictly outlasts the population's. Not "be different" (a target) — pure source-attribution.
- The live wiring: `state.py:_population_growth_themes(db, actor_id)` gathers other residents' recent (≤2-day) proposal bodies+days, newest-first, capped — best-effort/fail-open (absent baseline → rule 1 simply doesn't gate; rules 2/3 unaffected). Caching this across residents is the noted perf follow-up.

## Validation Commands

- `cd worldweaver_engine && .venv/bin/python -m pytest tests/service/test_growth_service.py -q`

## Open Questions / Risks

- Operationalizing "outlasts the population" — the window, the baseline, the threshold. Keep it attribution, never a divergence target.
- The world-affordance check: a static action vocabulary, or query the rules engine for what discharges a given goal?
- Social-strategy detection without an LLM call per delta — a heuristic, or embed against a "social-instrumentality" prototype?

> Risk if skipped: the gate, turned on during a world event, launders the weather (or the unfulfillable, or the instrumental) into identity — promotion and persistence, not the acute convergence, is the disease.
