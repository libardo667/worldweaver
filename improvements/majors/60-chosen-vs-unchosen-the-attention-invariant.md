# Edge honesty: chosen-vs-unchosen as the attention invariant

## Metadata

- ID: 60-chosen-vs-unchosen-the-attention-invariant
- Type: major
- Owner: Levi
- Status: **built (2026-06-06)** — mechanism landed + unit-tested; awaits the live SFO re-run (criterion 5) for empirical validation against the topic-monoculture.
- Risk: high — touches the core perception↔arousal coupling; the seam the live SFO run showed produced the topic-monoculture
- Depends On: the foldback (substrate reconverged into the city); **Minor 55 (the waveform vital — build first; it tells us immediately if a mind goes dark-room as we change perception)**

## Problem

The first live SFO run (31 residents, 2026-06-06; see memory `foldback-live-test-convergence`) cured the *literal* March disease (no phrase-mirroring, individuated voice, clean prediction) but produced a **topic-monoculture**: a florist, a nurse, and engineers alike all converged on one subject (a storm's drainage) — individuated vocabulary over a single shared topic. The engine is the perception channel: `perceive()` PUSHES all chat into every mind every tick, including the `__city__` broadcast (everyone, everywhere, at once → `social_pull` → arousal; `ww_agent/src/runtime/perception.py:284-285`).

Mr. Review's diagnosis (round 1): the disease moved from the **node to the edge** — homogenization is an emergent property of a *broadcast topology* + *dischargeable coupling* + a *learning gate*, not of any mind. Verified: Maya heard Naomi via `city_chat_heard=38, local=0` — the *good* coupling rides the same broadcast, so all-or-nothing removal of citywide would kill the "we" along with the disease.

The deeper invariant (round 2): the seam is **not** presence-vs-broadcast (a good *proxy*) but **chosen-vs-unchosen**. Every distress in the system is a mind with too much control over its own inputs; the cure is always *something the mind doesn't get to choose*. A perfectly curiosity-filtered feed is, by construction, zero-surprise — the **input-side dark room** that starves the prediction-error engine the whole substrate runs on.

## Proposed Solution

Gate perception on **chosen (curiosity) vs unchosen (exogenous)**:

1. **The chosen — curiosity rations focus.** Convert citywide chat from an ambient PUSH to a **drive-filtered PULL**: a resident perceives the citywide feed it chooses to, ranked/filtered by drive-vector resonance with its soul. Must support **following a specific peer**, not only topic-feeds — the relational "we" (Maya→Naomi) is a *curiosity subscription* to a resonant mind, the focus channel *producing* the good coupling. Mechanism: a `chatter`/feed tool a pulse enacts (peers + threads the soul resonates with), reading `__city__` on demand.
2. **Local stays an unfiltered push** — embodied co-presence: a resident genuinely hears its room, and being addressed there drives the responsiveness that is working (the turn-taking debate). Local is NOT drive-filtered.
3. **The unchosen — traversal rations diversity (primary).** Static co-presence does NOT supply diversity: **homophily** (like clustered with like) turns a parked mind's local push into a *second* curiosity filter (a florist in the flower district meets only florists → balkanized local monoculture, worse for the individual). The already-built regulator is **`mobility_drive`**: a *moving* mind meets the un-chosen *en route* — the path cuts across districts unlike its own (heterophilous by construction; real serendipity is in-transit). In-transit perception (what a resident can't-not-perceive while crossing the world) is the diversity channel, content-blind by nature.
4. **The unchosen — a content-blind floor.** For the parked/walled mind, a small **representative, random** slice of the world past the soul's filter — not a value imposed, but the *nutrient surprise needs to exist at all*. The law line is **directionality**: content-blind (a random slice) = a hole in the filter (law-safe, no target); content-specified ("show the florist engineering") or contrarian ("the opposite of his soul") = a behavior target (forbidden). *Sample the world; never oppose the self.*

The invariant to encode: **curiosity rations the chosen; the un-chosen (traversal + content-blind floor) rations diversity, and no mind may hold a 100% veto over its own input.**

## Files Affected

- `ww_agent/src/runtime/perception.py` — drop the `channel="city"` ambient sense (line ~285); keep `channel="local"`.
- `ww_agent/src/world/city_tools.py` + `city_world.py` — a `chatter`/feed pull tool (peer/thread subscription, drive-ranked).
- `ww_agent/src/runtime/drive.py` — the drive vector applied to feed-ranking and the content-blind-floor guard.
- in-transit/traversal perception (what is sensed while moving) — `perception.py` + the move/effector path.
- `improvements/ROADMAP.md` — the chosen-vs-unchosen standing invariant.

## Acceptance Criteria

- [x] Citywide chat is a drive-filtered pull, not an ambient push; local chat remains a push. — `perception.py` drops the `channel="city"` push (keeps local); the `chatter` tool in `city_tools.py` is the drive-ranked pull.
- [x] The pull supports following a specific resonant peer, not only topic-feeds. — `use chatter <name>` filters the feed to that speaker (the relational subscription); blank = soul-ranked; a word = topic+resonance.
- [x] A moving resident perceives the un-chosen en route (in-transit, content-blind). — `_sense_overheard(moving=True)` overhears `OVERHEARD_IN_TRANSIT` random lines; movement detected by a location change since the last tick (`perception_state.json`).
- [x] A parked resident still receives a representative content-blind dose (no echo-chamber-of-one). — `_sense_overheard(moving=False)` overhears an `OVERHEARD_FLOOR` (1) random line, reusing the `city_chat_heard` → `social_pull` mapping.
- [ ] **Re-run the SFO shard** (the live validation, Levi to run): the topic-monoculture loosens (geographic, individuated locality returns) WITHOUT killing the local responsiveness (the addressed→attend debate still happens locally). The waveform vital (Minor 55) shows no mind going dark-room.

## How it was built

- **The chosen — `chatter` pull** (`city_tools.py`): `use chatter <name|topic|blank>`. Reads `__city__` on demand, ranks by soul-resonance (`_drive_scores`: one batched embed of the recent feed, weighted peak cosine against the resident's identity fragments — reuses `drive.SLICE_WEIGHTS`/`_cosine`), follows a named peer, and falls back to recency with no embedder. The drive vector is late-bound: the core calls `CityWorld.bind_tool_drive` → `CityToolScope.bind_drive` once it's built on tick 1 (a `_DriveHolder` slot the tool reads at call time).
- **The unchosen — content-blind floor + traversal** (`perception.py`): the `channel="city"` ambient push is gone. `_sense_overheard` emits a small *random* slice as `city_chat_heard` (so the `social_pull` node mapping is unchanged — the fix is volume + content-blindness, not a new node), sized by movement (1 parked / `OVERHEARD_IN_TRANSIT` in transit). Content-blind = `random.sample`, never soul-ranked: a hole in the filter (law-safe), never a target. Movement = a location change persisted in `perception_state.json`.
- **Local stays a push**: `_sense_chat(channel="local")` is untouched — embodied co-presence, the responsiveness that works.

## Open Questions / Risks

- The dark-room risk on the drive-filtered feed — resolved *in principle* by traversal + content-blind floor; verify empirically with the waveform vital.
- Does traversal supply *enough* diversity, or must the content-blind floor be non-trivial? (Mr. Review: traversal primary, floor as the guarantee.)
- Performance: per-message drive-scoring of the feed (embed + cosine) at city scale — bound it (top-k, cache), like the anchor lane.

> The arc (Mr. Review): every distress here has been a mind with too much control over its own inputs; the cure is always something it doesn't get to choose. This major is that principle, applied to perception.
