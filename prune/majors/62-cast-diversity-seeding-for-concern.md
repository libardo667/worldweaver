# Cast diversity: seeding (and running) for diversity of concern

## Metadata

- ID: 62-cast-diversity-seeding-for-concern
- Type: major
- Owner: Levi
- Status: proposed — **reframed by Mr. Review round 3 as the HEDGE: build last, modest, scoped.** Composition is the *weakest* of the three terms ((shared-world salience) × (topology) × (composition)); ship it *after* [[63-topology-make-speech-physical]] and [[64-plural-salience]], never alone.
- Risk: medium — touches the doula's character generation (the source of the population) and per-resident model assignment; changes who the world is *made of*

## Round-3 reframe (Mr. Review, 2026-06-06)

The canonical-reset re-seed proved a diverse cast converges anyway, so composition is the *hedge*, not the cure — and its claim must be **scoped precisely**: composition lowers baseline flammability against **interest-salience** (a shared *professional topic* — fewer souls resonate with any given spark) but is **useless against environment-salience** (a thing everyone is *physically exposed to*). Run 2 is the proof: a florist, a tattoo artist, a window cleaner converged on the failing building *because everyone lives in a building* — no composition could have helped, because the salience was environmental. So composition is the weak lever **especially** in situational-salience domains (which is exactly relocation — everyone's moving). Build M62, frame it as "reduces flammability against shared *interests*, does nothing against shared *conditions*, matters only once topology and salience are fixed." Shipping it alone is shipping the visible-but-weak lever the lab already disproved.
- Depends On: nothing hard; informed by the live test in memory `topic-monoculture-is-casting`

## Problem

The 2026-06-06 canonical-reset test (fresh souls from canon, empty ledgers, wiped chat + 3732 events, overcast/dry — no storm) showed the SFO **topic-monoculture re-forms within minutes**. It is **not** accumulated drive, **not** a live shared event, and **not** primarily the perception coupling Major 60 targets. It is a **casting artifact**: ~2/3 of the 31 residents are built-environment-decay souls (structural engineers/inspectors, masonry/restoration/conservation, physical-repair trades). They converge on "substrate / moisture / core samples / structural failure" because that is *what they are*. The cast is **demographically diverse but thematically a monoculture** — diverse skin, one concern. The diversity hid behind the roster; it only shows in what they *talk about*.

Major 60 + anchor gating do their real jobs (no literal mirroring, no flood, individuated *voice* — Santiago≠Maya) but **cannot diversify the topic when the souls share a domain.** "Individuated voice on a shared topic" is the ceiling for a thematically narrow cast.

**Why the existing machinery did not prevent it (verified in `doula.py`, some to confirm):**
- The doula already has a diversity **codex** (`_NAME_TRADITIONS`, `_VOCATION_DOMAINS`, `_AGE_BANDS`, `_TEMPERAMENTS`, sampled per spawn — line ~129) and **generator-model rotation** (`_pick_soul_model` / `WW_DOULA_MODELS` — line ~1224), both added *after a prior collapse* ("we watched it make five Chens and a pile of structural engineers").
- But the codex is a soft **"lean, not literal"** (line ~1642), **de-novo / founding-only**, and even its non-structural briefs **drift structural** under the seed model's gravity + the SF-infrastructure narrative evidence ("cleaning and maintenance" → stucco restoration; a flower-vendor brief → a florist who thinks in *hydraulics*).
- **Evidence-based spawns** (a name mentioned in conversation → seeded from `context_lines`, line ~673) **inherit the prevailing theme** — a name born inside a structural debate is cast structural. Monoculture begets monoculture.
- A **canonical reset restores `SOUL.canonical.md`; it does not re-seed.** The test restored the already-collapsed cohort, so the machinery never got a fresh chance. *The real monoculture re-test requires a re-seed, not a reset.*

This is very Dwarf-Fortress: the emergent culture is read off the population you seed. A commons of 20 masons is a guild, not a society.

## Proposed Solution

Three levers, attacking the **source** (Levi's framing):

1. **A shuffling codex of constraints — generative, hard, all-paths, population-aware.** Make the orientation-brief a recombinant deck that "configures again and again into new orientations," not a soft de-novo lean:
   - **Hard, not a lean** — the assigned domain of *concern* is a constraint the soul must honor, not a suggestion the model can drift out of.
   - **All spawn paths** — apply it to evidence-based spawns too, so a name born in a structural conversation can still be cast as a poet (break the monoculture-begets-monoculture loop). Evidence informs *who noticed them*, not *what they must be about*.
   - **Population-aware anti-clustering** — sample domains **under-represented in the live cast** (read the room): if the city is already thick with structural trades, the next souls are weighted away from it. Close the loop the static pools leave open. (Law-safe: diversity-of-source by *attribution/representation*, never a behavior target on any individual.)
   - **Domain of CONCERN, not job title** — expand past vocation to *what a soul turns toward*: a griever, a schemer, a believer, a gossip, a child who thinks about nothing useful, a cook who tastes the fog. "Everyone gets a craft" → "everyone gets a different kind of soul." Deliberately seed people who are *not* busy with the physical city.

2. **Doula generator-model diversity (verify + widen).** Confirm `WW_DOULA_MODELS` is actually populated (it likely falls back to a single model), widen the approved pool, so no one model's gravity stamps the whole cohort. (The model that *writes* the soul.)

3. **Cast runtime-model diversity (new).** Assign **varied pulse models across the residents** — as the familiars already do (gemini / claude-haiku / mistral / deepseek = different pens = different minds) — instead of every city resident defaulting to one `WW_INFERENCE_MODEL`. The doula writes `tuning.json`, so it assigns each resident a runtime model drawn from an approved pool. Even kindred souls then think in different cognitive textures. (The model that *runs* the resident.)

And the operational truth to encode: **to change the cast you must RE-SEED, not reset** — a regeneration path (or `--neutral-start` reseed) is the real monoculture re-test, distinct from `canon_reset`'s soul-restore.

## Files Affected

- `ww_agent/src/loops/doula.py` — the codex (hard + all-paths + population-aware + concern-domains); verify/widen `WW_DOULA_MODELS`; assign a runtime pulse model per resident into `tuning.json` from a pool.
- resident `tuning.json` generation — per-resident `model` (or `fast`/`slow`) assignment for runtime-model diversity.
- a **cast-diversity metric** — embedding spread / concern-domain histogram of the souls (extend `ww_agent/scripts/soul_domain_retention.py` or a new script) to *measure* heterogeneity, not eyeball it.
- (test harness) a re-seed path distinct from canon_reset's restore.

## Acceptance Criteria

- [ ] A freshly **re-seeded** cohort shows diverse soul-domains — no ~2/3 single cluster; measured by embedding spread / a concern-domain histogram, not by eye.
- [ ] Evidence-based spawns do **not** inherit the prevailing theme (a name mentioned in a structural conversation can be cast in an unrelated domain of concern).
- [ ] Residents run on a **diversity of pulse models** (not all one default).
- [ ] Generator-model rotation (`WW_DOULA_MODELS`) is confirmed live with a real pool.
- [ ] **Re-run the monoculture test on the re-seeded cast:** multiple distinct conversations/topics emerge (geographic + thematic), not one citywide debate. The waveform vital (Minor 55) shows no mind dark-rooming.

## Implementation note — 2026-07-17

The architectural creation seam now exists independently of the larger population experiment. The root
`seed-residents` command is dry-run-first and can create a fixed batch of one to five dormant hearths. It
uses a dealt hand plus a bare home location, never queries the city's accumulated narrative history, deals
distinct ordinary livelihood domains for the small batch, writes birth provenance and a portable hearth
manifest, and never queues or starts a resident. The ordinary daemon path still boots births as before.

This does **not** satisfy the acceptance criteria above. Three fresh residents are useful usability
baselines, not evidence that the population is diverse or that monoculture has been solved. Any activation,
bounded run, or comparison remains a separate explicit step.

## Open Questions / Risks

- How hard can the concern-constraint be before souls read as "assigned a quirk" rather than whole people? (The current codex is soft *because* hard briefs risked caricature — find the line.)
- Population-aware sampling needs a live read of the cast's concern-distribution — reuse the soul-embedding spread; bound the cost.
- Runtime-model diversity interacts with cost (some models are pricier) and with the substrate's model-agnostic claim — verify the substrate behaves across the pool (the familiars suggest it does).
- The deeper question this raises: is monoculture-from-casting a *bug* or an honest reading of what the seed prompt + city-pack evidence *asks for*? The fix is to ask for diversity of concern explicitly — but watch that we don't just trade one imposed distribution for another. Diversity-of-source is attribution, never a per-resident target.

> The test that uncovered this: a canonical reset re-converged a demographically-diverse cast onto one concern in minutes. The lever isn't the edge (perception) or the accumulation (memory) — it's the **bones we cast**.
