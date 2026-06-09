# Post-mortem — two-shard bench: venture-targeting `argmax` vs `sampled`

**Date:** 2026-06-07 · **Shards:** `ww_pdx` (Arm A, argmax) · `ww_pdx_b` (Arm B, sampled, temp 0.25)
**Frozen at:** pop ~34–37 each · agents stopped, containers down, volumes kept, `residents/` ledgers archived here.

## The bench (what made it clean)

Two slots on one bench, **≤1 differing axis** — the discipline the SFO/PDX comparison never had:

- **Identical** Portland geography (233 neighborhoods each), identical dealt-hand doula seeding logic → 50, venture **on** in both, gemini-3-flash-preview, chronotype spread 12, same embedder.
- **Isolated**: separate DBs / volumes (`ww_pdx_postgres_data` vs `ww_pdx_b_postgres_data`), no shared feed, no federation. A finding here is *reproduced*, not *transmitted*.
- **The one varied axis**: `WW_VENTURE_TARGET_MODE` — Arm A picks the **argmax** most-resonant reachable place; Arm B **softmax-samples** from the resonance distribution.

## Result 1 — the targeting asymmetry is real and robust (population-level)

The knob does exactly what it says, across *many* ventures:

| | ventures | stray rate | mean chosen-rank | move_executed |
|---|---|---|---|---|
| **A (argmax)** | 17 | **0%** | **1.0** | 12 |
| **B (sampled)** | 12 | **58%** | **~3.0** | 9 |

Arm A funnels every venture to the single most-resonant place; Arm B strays from its top pick the majority of the time. Both arms move *real bodies* (`move_executed` 12 / 9) — venture (the substrate as motor cortex) fires in both. This half is **not** n=1; it's the population behaving as designed.

## Result 2 — the null: targeting mode does NOT move population health

`three_axis` (VOICE / ATTENTION-displacement / CONTACT), full population, same judge:

| | VOICE | DISPLACEMENT | CONTACT | dominant theme |
|---|---|---|---|---|
| **A (argmax)** | 0.98 | 0.10 | **36%** | "the shifting earth reclaiming the city" |
| **B (sampled)** | 0.98 | 0.10 | **30%** | "the memory of the grain" |

A *dramatic* micro-difference (Result 1) produces **essentially zero macro-difference**. Voice identical, displacement identical, contact within instrument noise. **De-homophily-by-targeting does not change emergent health.** This is consistent with the standing finding that the topic-monoculture is **casting**, not targeting — both arms share the dealt-hand's structure/decay-heavy cast, so both converge on a material-decay theme regardless of where individuals walk.

## Result 3 — the contact win belongs to venture, not to targeting

CONTACT ~30–36% on *both* arms vs **7%** on the pre-venture frozen dealt-hand cohort. Movement (present in both arms) is the lever that lifted the axis every prior lever missed — a ~4–5× rise in minds actually engaging each other, distributed across the population (per-resident contact 17–50%, not carried by a few loud souls). The targeting *refinement* is a wash; the *presence of venture* is the win.

> Guards the **push-bias-down / leave-the-genius-alone** rule: venture (movement — a thing the LLM was *biased* away from, regardless of soul) earned its keep in the substrate. The argmax-vs-sampled refinement is a wash, so don't over-engineer it. The successes are the threat; venture is a success, the targeting tweak is not.

## Result 4 — de-homophily and contact may TRADE OFF (the surprise)

The direction is mildly **against** the intuition that scattering helps: argmax CONTACT (36%) ≥ sampled (30%). The argmax **funnel-to-a-hub is what manufactures the shared room** — everyone converging on Arnada (the coffee command-post) ends up in conversation; scattering souls to diverse 4th-choice places means fewer end up together. Within noise, but it does **not** support "kill argmax for sampled," and it complicates the build-queue assumption that de-homophily is desirable. *Homophily produces contact; the cure for one is the cause of the other.*

## Result 5 — the persistent topic reads as HEALTHY shared-ground, not disease

This resolves the question that gated the casting-diversity fix. Both arms: VOICE 0.98 (distinct registers kept), DISPLACEMENT 0.10 (selves intact *alongside* the shared concern), CONTACT ~33% (a real we). By the instrument's own thresholds: *voices kept · selves intact · a real we.* A town that shares a concern (the shifting earth / the memory of the grain) while every mind stays itself is the **good** kind of "we have a common ground," not the SF false-we collapse. One casualty per arm worth naming: A's `leonardo_amato` (voice 0.87, displacement **1.00**) is the single soul the shared thing fully crowded out — the exception that proves the population rule.

## Honest caveats (existence-proof vs frequency)

- **Co-location is n=1–2 per arm and flickery** (A's Arnada pair had dispersed by the final snapshot while B's Rose Village pair held). The *meeting-mechanism contrast* — argmax funnels a soul to the topic-hub where a same-topic soul already lives (homophilous); sampled strays a paralegal + a shopkeeper into a 4th-choice village (chance, cross-kind) — is a clean **existence proof**, not a rate. A frequency claim needs a dedicated co-location-rate run (fixed pop, frozen, meetings counted), not this idle.
- The CONTACT 7%→33% lift is **across-run** (vs the earlier frozen dealt-hand), not a within-bench control. Suggestive, not airtight.
- `three_axis` is an LLM-judge over modest per-resident utterance counts; treat ±6 points as noise.

## Decisions

1. **Keep venture on; it's the contact lever.** This is the banked positive result.
2. **Do not "kill argmax for sampled."** The A/B shows it's health-neutral at best and mildly contact-negative at worst. The instrument-cleaning question is answered: argmax stays (or the choice is aesthetic, not health-driven).
3. **De-prioritize the casting-diversity fix.** The persistent topic is healthy shared-ground here, not disease — the fix is not urgent and risks engineering away a good thing.
4. **The real open question moved:** not "how do we de-homophily targeting" (a wash) but the **withdraw / satiety edge** — contact at ~33% with voices intact is a genuine *we*; the next lever is whether the substrate can let a sated soul *leave* a hub (so contact is chosen, not just funneled), which is the honest path to contact-without-homophily that Result 4 says targeting alone can't buy.

## Artifacts (this folder)

- `3axis_A_argmax.txt`, `3axis_B_sampled.txt` — full per-resident three-axis reads.
- `residents_ww_pdx_argmax.tar.gz`, `residents_ww_pdx_b_sampled.tar.gz` — frozen `residents/` ledgers (the raw substrate; re-derive any metric from these).
- `watcher-bench.log` — the ripening trace (both arms, +0→+90m).
