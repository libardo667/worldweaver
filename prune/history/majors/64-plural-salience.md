# Plural salience: the world offers more than one loud thing — archived

## Metadata

- ID: 64-plural-salience
- Type: major
- Owner: Levi
- Status: architecture complete and archived (2026-07-17); population checks remain deferred research
- Risk: medium — touches world/ambient generation (the field every mind perceives); law-safe by construction (the world has no soul to target)
- Depends On: pairs with [[63-topology-make-speech-physical]] (both the world-side of the invariant). **Gates [[61-gate-provenance-what-becomes-soul]]** — see §Sequencing.

## Problem

The canonical-reset test converged a *deliberately diverse* cast onto one concern — the decaying built environment — because the **world makes one thing loud to everyone at once.** The shared physical condition (a chronically decaying city: hums, rattles, fog, settling brick) is emitted as ambient signal every resident perceives, so it is the common referent the whole population can speak to with feeling. The disease's deepest layer is the **field**: world-salience.

Mr. Review's frame: salience is the **spark** (what's loud), topology the **wind** (whether it spreads), composition the **dryness** (how flammable the cast). Salience is where the fire starts — a world with no single loud feature gives the spark nowhere to catch.

## Completion Note — 2026-07-17

This item was written when ambient descriptions were assumed to be part of every resident prompt. That is
no longer the live architecture. CognitiveCore uses ambient intensity as bodily pressure, but the
descriptive labels are not placed in the prompt automatically.

The completed architecture now does four concrete things:

- the engine produces source-attributed local features such as neighborhood character, weather shelter,
  time-of-day activity, crowding, and local-event spillover;
- perception keeps each feature's source instead of collapsing the scene into one unlabeled pressure;
- the resident reducer exposes the latest feature clusters, independent source count, dominant share,
  and effective feature count, so a one-note scene is visible rather than silently called plural;
- a resident can privately inspect the current features through the `surroundings` source. The source
  supports an unfiltered local browse or an explicit query, and returns structured local-perception
  records. Merely waking does not inject those descriptions into the prompt.

This is the architectural part of plural salience: several independent world inputs can coexist, their
competition is inspectable, and no prompt-side selector chooses a preferred topic. The original
population-theme and re-seeded-cast checks require running residents. They remain useful research, but
they are not missing machinery and are excluded from the current architecture queue.

## Proposed Solution

**The world presents *plural* salience** — more than one loud feature, so no single one can collect every mind's attention.

The crucial qualifier: this works by **dilution, not removal.** A decaying building or a storm is environmentally universal — everyone is physically in it; you cannot delete it. So the move is *"ensure the shared physical condition isn't the only loud thing,"* splitting attention rather than collecting it. (This is M-18's "add a second salience," applied world-side rather than to one client's social plan.)

Law-safe by construction: varying *what the world offers* targets no mind's output — the world has no soul to shape. It is clean in the same way "the world has weather" is clean — inputs varied, never outputs steered.

### Sequencing — this gates learning (Q6)

Plural salience is not only a convergence fix; it is a **precondition for the learning gate (Major 61) to function at all.** The gate's differential-persistence rule promotes a theme only if a mind's attention **outlasts the population's** — which *assumes the population's themes move.* A permanent environmental salience never recedes from the population, so there is no "past the population": the null hypothesis is stuck, and the gate cannot distinguish self-sourced from world-sourced because the world never lets go. Plural salience is what makes the population's themes **rise and fall** — the moving baseline differential-persistence needs to measure against.

**Order:** plural salience + plural topology (Major 63) first → *verify the population's themes actually vary over time* (the [[57-soul-domain-retention-measurement]] discriminator across a world-condition boundary is precisely this test — does the theme **recede**?) → only then turn learning on. The topology/salience work is not "before" learning; it is what makes learning's provenance filter valid.

## Build log

**First dose (2026-06-06).** The nap-test + storylet audit located the concrete mono-salience: every resident perceives the same global `weather_description` grounding string ("18 mph winds"), and when a resident is *alone* (the live 1-per-neighborhood case) the **only** ambient feature that fires is the weather cluster — every crowd-based ambient needs ≥4 present. So weather was loud because it was the *sole* thing loud. (Storylets were audited and cleared as a source — the pulse never reads them; the lone scene-synthesis channel, `ambient_presence`, is computed from grounding, not authored rows.)

Fix: `_derive_scene_ambient_presence` (worldweaver_engine `src/api/game/world.py`) now always emits a headcount-independent, **weather-competitive** (intensity 0.6 vs weather 0.54–0.66) `place_character` salience, archetype-keyed off the city-pack `vibe` (maritime / civic / culture / industrial / commerce / tourism / domestic / local). Two residents in two neighborhoods now perceive two *different* second saliences. The old weak `kind="regular"` fallback (intensity 0.38, `if not items`) is removed — it was the un-promoted version of this idea. `perception.py` `_AMBIENT_KINDS` learns `place_character` so it survives with its semantic. SFO's 71 neighborhoods carry rich, differentiated vibes (~dozen empty → weather-only, honest). This cashes out Major 10 Phase 4.5 (neighborhood differentiation) for the explicit purpose of plural salience.

**Re-seed result (2026-06-06): first dose held at 97% monoculture.** 200 commons messages — 70% cite the wind/"eighteen mph"/salt, 86% structural-resonance. Place_character *was* perceived (residents named Duboce bolts, wharf dust, Diamond Heights transformers) but the decay-cast folded each into the same wind-and-decay frame, and the global weather string drowned the ambient. See [[convergence-levers-are-coupled]] — convergence is multiply-determined; no single-lever fix.

**Dose 64b (2026-06-06): demote the weather string.** Levi chose the cleanest single-variable next test. The quantified weather ("18 mph winds") reached the pulse two ways — the foreground `when` line (`pulse_engine.py`, "It is evening, clear, 65°F, 18 mph winds") and the `bad_weather` ambient signal *label* (`perception.py`, the full string). Both demoted: `when` drops weather (keeps time-of-day/circadian); the bad-weather label becomes generic ("the weather has a rough edge today"). Weather survives as *felt ambient* — the vigilance pressure still fires and the `weather_shelter_cluster` (qualitative: people sheltering, damp) stays — but the diagnostic figure is gone. Expected: EITHER the commons de-saturates (the string was load-bearing) OR the cast finds a new shared peg (convergence is even more casting-driven) — both informative.

Still ahead after 64b: if it still converges, the coupled levers (demote/cost the city target; [[major-62]] casting). Then the soul-domain-retention precondition check before learning.

## Files Affected

- the world / city-pack ambient generation (worldweaver_engine) — what salient features the world emits; ensure ≥2 competing, not one dominant.
- `ww_agent/src/runtime/perception.py` — the ambient-pressure / event-pull signals the substrate perceives (confirm they carry plural salience, not one collapsed pressure).
- `ww_agent/scripts/soul_domain_retention.py` — already the discriminator for "does the theme recede"; use it as the precondition gate-check.

## Acceptance Criteria

- [x] Independent world features retain their source and intensity; the current projection reports whether
  the scene is actually plural and how dominant its largest feature is.
- [x] Ambient descriptions are available through an elective `surroundings` read and are not inserted
  into every pulse.
- [~] Verify that population themes rise and fall across a world-condition boundary: deferred live-agent
  research.
- [~] Verify that a re-seeded cast holds multiple conversations: deferred live-agent research.
- [~] Use the population result as a precondition before enabling learning at scale: retained as an
  operational/research gate, not an architectural implementation task.

## Open Questions / Risks

- **The dose.** How many competing saliences prevent collapse? The same open empirical question M-18 §10 flags for humans — untested. Lean: start with two, measure recession.
- Environmental vs interest salience: composition (Major 62) hedges *interest*-salience and is useless against *environment*-salience (everyone's in the building) — so for environmental salience, plural-salience + topology are the *only* levers. Don't expect 62 to help here.
- Risk of a busy, incoherent world: too many loud things could fragment attention past coherence (no shared ground at all). Plurality, not cacophony — there's a floor as well as a ceiling.
