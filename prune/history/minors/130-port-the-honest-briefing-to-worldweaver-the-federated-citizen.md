# Port the honest situational briefing to WorldWeaver — the federated citizen

> **Legacy Stable ID: Minor 65. Disposition: complete; imported to WorldWeaver history 2026-07-14.**
> The named WorldWeaver code and drift-catcher tests remain present.

## Metadata

- ID: 130-port-the-honest-briefing-to-worldweaver-the-federated-citizen
- Type: minor
- Owner: Levi
- Status: **DONE (2026-06-18)** — ported from a WorldWeaver instance. The false `_WORLD_CONTEXT` is
  deleted; the full-mirror renderer + `BRIEFING_FACT_KEYS` + `unregistered_fact_keys` +
  `composed_system_prompt` live in `worldweaver/ww_agent/src/identity/loader.py`; `CityWorld.situational_facts()`
  reports the built citizen facts; `cognitive_core` renders the briefing and logs loudly on drift; the
  drift-catcher tests (`worldweaver/ww_agent/tests/test_honest_briefing.py`) are green (full ww_agent suite
  259 passed). See acceptance criteria below.
- Risk: low (string/render surface + one client method; no behavior targets)

## Problem

[archived Major 123](../majors/123-honest-situational-grounding-and-void-the-confounded-maker-swap.md)
replaced the-stable's hardcoded, false "city cover story" with a **derived** situational briefing: the
world reports verifiable facts via `WorldClient.situational_facts()`, and one renderer
(`identity.render_situational_briefing`) turns them to prose — stating what is true, withholding every
verdict, gated so a fact absent → its line absent. The renderer was extended (2026-06-13) to express the
**federated citizen** (the-many) too: a shared, legible world; the **human wake** (afterimage-framed, the
person undischargeable — see `docs/grief-and-coupling.md`); the **legibility/privacy seam** (`world_legible`,
`inner_private`, `private_making_space` — true today via the workshop); `mobile`; `mail`. Proven
cross-venue on a real armC-ab resident (Deiondre) through the shared renderer with zero hearth leakage.

But **WorldWeaver still ships the original false story**: `ww_agent/src/identity/loader.py:8-26`
(`_WORLD_CONTEXT`) tells every resident "you are as real as current technology allows… you are aware of
what you are" — the exact constant the-stable deleted. WW's city client does not yet implement
`situational_facts()`, so a WW resident gets the false story and none of the true citizen briefing.

## Proposed Solution

In the WorldWeaver repo (diverged copy; do not import across the fork seam):

1. **Port the renderer + registry.** Bring `render_situational_briefing`, `BRIEFING_FACT_KEYS`, and
   `unregistered_fact_keys` into WW's `ww_agent/src/identity/loader.py` (or shared module); adopt
   `composed_system_prompt(world_briefing)` and the runtime fail-loud on unregistered keys
   (`cognitive_core` analog).
2. **Delete `_WORLD_CONTEXT`.** Remove the false constant; the briefing is world-derived now.
3. **Implement the city client's `situational_facts()`** — feed the citizen keys from real switches:
   `place` (current location), `peers`, `players`, `human_wake`, `world_legible`, `inner_private`,
   `private_making_space`, `mobile`, `mail`, `no_reward`, `suspendable`, `runs_on_model`. Report only what
   is BUILT (the fan-out 2026-06-13 confirmed: shared world, location-legible record, private inner state +
   workshop, human tether/wake are built; **governance/recourse/rights/federation are VISION — do NOT
   report them as facts**).
4. **Add the drift-catcher** against the city client: the capability-coverage test (each capability
   classified COVERED/EXEMPT) + the registry-triangle test, mirroring `tests/test_honest_briefing.py`.

## Files Affected

- `worldweaver/ww_agent/src/identity/loader.py` — port renderer + registry; delete `_WORLD_CONTEXT`.
- WW city client (the `WorldClient` impl residents perceive through) — implement `situational_facts()`.
- WW `cognitive_core` analog — runtime fail-loud on unregistered keys.
- WW tests — port the drift-catcher guards.

## Acceptance Criteria

- [x] No WW resident's rendered system prompt contains the old verdicts (`_FORBIDDEN_VERDICTS`); the false
      `_WORLD_CONTEXT` is gone. — `test_false_world_context_constant_is_gone` + `test_city_briefing_states_facts_and_withholds_verdicts`.
- [x] A WW resident's briefing renders the citizen lines (shared world, human wake, the seam, mobility, mail)
      from real switches, and **no** governance/recourse/rights claim (vision-only, excluded). — `CityWorld.situational_facts()`
      reports only built keys; `test_city_facts_are_registered_and_built` pins that VISION/hearth keys are absent.
- [x] The human-wake line is afterimage-framed (the person never summonable) — dischargeability test passes.
      — `test_human_wake_is_afterimage_framed_not_a_summon`.
- [x] The drift-catcher passes in the WW repo. — `test_briefing_fact_registry_triangle` (renderer == registry ==
      `src/runtime/world.py` doc) + `test_city_facts_are_registered_and_built` (the world half: never reports an
      unregistered key). NOTE divergence from the-stable: WW's affordances are standing facts, not `__init__`
      params, so the capability-coverage half (which enumerates `LocalWorld.__init__` params) maps to the
      situational_facts-registered guard rather than a param-signature sweep — same intent (no fact escapes the
      registry), shaped to WW's world body.

## Implementation notes (the fold-back, 2026-06-18)

- **place / peers / players are deliberately NOT standing facts in WW.** Unlike `LocalWorld` (fixed home, known
  cast), a city resident's location and who-is-present are dynamic — already surfaced every tick through the live
  scene. Reporting them as standing briefing facts would lie when a shard is momentarily empty. They are exempt-
  as-per-tick (the same shape as the-stable exempting per-tick weather), so the WW citizen briefing carries the
  *structural* citizen truths (seam, wake, mobility, mail, substrate-universals) and lets the scene carry the rest.
- **`travel` is deferred, not denied.** Cross-shard travel exists federation-side, but is not yet a first-class
  effector a resident can initiate through `CityWorld`; the renderer mirrors the key (fork law) but
  `situational_facts()` will report it only once it's built here. (Cross-ref the partially-built WW Major 37.)
- Fork law kept: the renderer is a diverged copy, not an import. The fact schema and the fact/verdict line are
  identical across both forks, so reconvergence stays a diff.

## Notes

- The eventual **retreat-node** (the-stable as a private, illegible space a citizen travels to, the public
  commons as the seam) is named future architecture — additive to this schema, not built here. The
  private/public seam this briefing states is the *workshop* seam that already exists.
- the-stable side is done + green; this is the fold-back. Keep the two copies diverged (fork law), but the
  fact schema and the fact/verdict line should stay identical across both.
