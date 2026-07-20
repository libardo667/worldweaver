# Demote loops to mechanism under a salience substrate and a predictive pulse

> **Canonical home: WorldWeaver (2026-07-14).** Migrated in full from the legacy `the-stable`
> work-item ledger during the one-resident/many-worlds consolidation. In this record, “familiar” names
> a resident inhabiting a keeper-tended hearth; it is not a separate agent species (Major 86).

> **Disposition: complete; archived 2026-07-14.** The live `CognitiveCore`, typed `Pulse`, ledger-derived
> substrate, afterimage/surprise/ignition cycle, constitution-weighted drive, and deterministic loop-closure
> tests satisfy this rebuild. The old cognitive loop package is absent. Later majors refine the substrate;
> they do not leave this foundational migration open.

> **Audit correction (2026-07-19):** This remains the historical record of the loop-to-pulse migration, but
> its stronger completion claims do not match the current runtime. `felt_sense` is read back through anchors;
> drive nudges, trace verdicts, and graph-like node fields have no live consumer; surprise valence and the
> semantic constitution check are not wired by `CognitiveCore`; reveries are not supplied to the drive build.
> See `research/audits/cognitive-core/` and active Major 136. Do not treat the checked acceptance list below as
> present-tense verification of those cognitive claims.

## Decision and lineage

This major collapses the resident's multi-tempo LLM loops into a **mechanistic substrate plus a single predictive integration pulse**. It is the connective layer that closes the architecture Majors 34 / 35 / 40 / 42 / 46 / 47 / 48 were already building toward.

**Decision (2026-06, made post-rest with intent to resect rather than accrete):** the resident mind is a mechanistic substrate (Major 46's ledger-derived cognitive nodes, perturbed per Major 47, grounded in world-graph truth per Major 48) plus a single ignition-triggered LLM pulse (governed by Major 42's immutable-canon-and-matured-growth identity model). The fast / slow / mail / ground / wander loops are **demoted to pure sensorimotor mechanism**: they translate world events into perturbations and execute intents. They no longer call the LLM.

- **Depends on:** 46 (node substrate), 47 (perturbation vocabulary), 48 (world-graph coupling), 42 (soul governance). 34/35/40 are upstream framing.
- **Supersedes the loop-era guidance:** `CLAUDE.md`, `GEMINI.md`, `ww_agent/AGENTS.md`, `ww_agent/src/loops/README.md`. They describe the fast/slow/mail-as-mind model this major retires. Mark them superseded; do not let a fresh agent trust them as current architecture.
- **Starting posture: cold rebuild, not live migration.** The server is not running and no resident is accumulating experience. There is no runtime behavior to preserve, which frees the hand. The bundles in `worldweaver_artifacts/legacy_git_bundles/` plus normal git history are the safety net. Old loops are removed, not kept as a parallel rail.

## Problem

The resident carries its mind as per-cycle LLM calls inside the loops (the fast-loop classifier, the slow-loop reflection). Majors 46 and 47 both diagnose the resulting behavior as "too prompt-shaped." Worse, coordination runs on three overlapping rails accreted across sprints:

1. shared in-memory store objects passed to every loop,
2. sentinel files (`introspect_signal`, `active_route.json`, `letters/intents/*.md`),
3. a half-migrated packet/intent layer in `runtime/signals.py` whose queues are internally inconsistent: `emit()`/`_load()` go through the event log (`append_runtime_event` / `derive_*`) while `_save()` writes a json file that `_load()` never reads. The helper is literally named `sync_runtime_compatibility_projections`; it is a migration that was started and not finished.

Major 46 already mandates the fix ("the resident ledger remains canonical; the substrate is a derived projection; do not create a second source of truth"). The code has not finished getting there. And the substrate majors build the bottom-up node dynamics but leave the LLM inside the loops and never close the top-down predictive loop.

## Core model (what we are building)

- **Salience = prediction error = the grain.** With-the-grain (low-surprise) cognition flows cheaply through the mechanistic substrate and leaves decaying traces. Against-the-grain (high-surprise) accumulates as arousal/pressure; crossing threshold is **ignition**.
- **The pulse** is the single LLM call, fired only on ignition. It reads the igniting traces plus current self-state and emits a **typed** output (never prose-as-control). The output is projected back into the substrate as a **decaying afterimage**: the top-down prediction the substrate is then surprised against. As the afterimage decays, the world drifts from it and surprise re-accumulates on its own, firing the next pulse. The rhythm is self-generating.
- **The substrate** is Major 46's nodes (leaky `activation`, `stability`, `refractory_until`, `sticky_until`, `evidence_refs`, `neighbor_bias`), perturbed via Major 47's vocabulary, biased by Major 48's exact world-graph truth. It is a derived projection of the one canonical ledger.
- **The constitution anchor.** Plasticity is everywhere (Hebbian `neighbor_bias` strengthening, habituation, afterimage decay, drive drift) and it all rotates around one immutable fixed point: Major 42's canonical soul. The **drive vector** that gives affect meaning is read from the embedding space of the identity docs in three rigidity slices: constitution (hard, dominant, immutable) + soul / matured-growth (stable) + reveries (transient, decaying). `valence = weighted cosine alignment`, constitution weighted to dominate. Cheap, no per-tick LLM.
- **The Dwarf Fortress law (standing constraint):** never script behaviors. Build general mechanisms over the shared substrate and let behavior emerge. Any reviewer who sees an outcome being hard-coded should reject it.

### The pulse output contract (typed)

```
Pulse  (one ignition produces this: LLM returns JSON, validated, then routed)
  felt_sense:   str          # prose READOUT only; logged to the chronicle; never routed as control.
                             # the self-image accrues here pulse over pulse.
  act:          Act | null    # one outward move; { kind: speak|move|do|write, body, target? }
  expectations: [             # THE AFTERIMAGE. becomes the substrate's predict().
    { features: {tag: intensity}, scope: here|self|<character>, confidence, half_life } ]
  drive_nudges: [ { features: {tag: intensity}, half_life } ]   # transient reverie pulls
  self_delta:   { soul_edit?, new_reverie?, goal_update? }      # slow plasticity; constitution-GATED
  trace_verdicts: [ { trace_id, verdict: consolidate|release|watch } ]
```

The **back-prop routing layer is pure mechanism**: it fans each field to its region. `expectations`/`drive_nudges` are stored as decaying modulations (afterimages). `self_delta` passes the Major 42 constitution gate before it can touch soul/growth (anything contradicting an immutable direction is clamped or dropped, enforced in code, not asked of the prompt). `act` is the only path to the world. `felt_sense` goes only to the chronicle and is never read back as control.

## Proposed Solution (phases)

### Phase 0 — Clean the incision (complete Major 46's single-ledger truth)
Make `StimulusPacketQueue`/`IntentQueue` pure views over the ledger event log. Remove the `_save`-to-json path that `_load` ignores; route status changes through `append_runtime_event`. Retire the sentinel-file rails. One canonical substrate must exist before any loop is demoted.

### Phase 1 — The pulse contract and afterimage
Implement the typed `Pulse` schema and the back-prop routing layer. The afterimage is a decaying top-down modulation stored in the substrate; it is what the substrate's `predict()` returns.

### Phase 2 — Salience as prediction error, and ignition
A salience/affect node measures `surprise = mismatch(stimulus, afterimage)`, tags affect via the drive vector, accumulates a leaky arousal level, and raises ignition when it crosses threshold. (Warp already designed; see memory and conversation handoff.)

### Phase 3 — Demote the loops to mechanism
Resect the fast-loop classifier and every in-loop LLM call. Loops become perception→perturbation emitters and intent executors only. Keep the world client, ledger, identity loader, perception/effector plumbing.

### Phase 4 — Drive vector from the doc embedding space
Build the constitution/soul/reveries embedding slices per Major 42; affect reads alignment from them. Plastic because reveries decay and the pulse rewrites soul/reveries through the constitution gate.

### Phase 5 — Make plasticity explicit
Hebbian `neighbor_bias` strengthening on co-activation, habituation (prediction catching up), and decay constants, all inspectable. Add the Dwarf Fortress law to the review checklist.

### Phase 6 — Cold validation and clean start
Seed a small deterministic world. Boot one resident on substrate+pulse from its canonical soul. Assert the loop closes: perturbation in → node transition → ignition → pulse → afterimage out → surprise re-accumulates. `canon_reset` restores canonical-soul-only per Major 42; old loop-era memory/ledger is not migrated (different representation; not worth carrying).

## Files Affected

- `ww_agent/src/runtime/signals.py`, `ledger.py`, `mirror.py`, `rest.py`
- `ww_agent/src/runtime/` new pulse/integrator + substrate-predict modules
- `ww_agent/src/loops/fast.py`, `slow.py`, `mail.py`, `ground.py`, `wander.py` (LLM removed; reduced to mechanism)
- `ww_agent/src/resident.py` (wires substrate + pulse instead of LLM loops)
- `ww_agent/src/identity/loader.py` (canonical/growth/reverie slices for the drive vector)
- `ww_agent/src/world/client.py` (exact graph queries per Major 48)
- `ww_agent/tests/*` (cold-boot loop-closure smoke; substrate reduction; constitution gate)
- Superseded docs to mark/retire: `CLAUDE.md`, `GEMINI.md`, `ww_agent/AGENTS.md`, `ww_agent/src/loops/README.md`

## Acceptance Criteria

- [x] One canonical ledger; packet/intent queues are pure views; the sentinel-file and json-shadow rails are gone (Phase 0).
- [x] A typed `Pulse` is the only LLM output shape, validated and mechanically routed; no loop calls the LLM.
- [x] The afterimage is a decaying top-down prediction that the salience node measures surprise against; ignition fires the pulse; the rhythm self-generates.
- [x] Loops are mechanism only: perception emits perturbations, effectors execute intents.
- [x] The drive vector is read from canonical/soul/reverie embeddings; `self_delta` cannot cross the Major 42 constitution gate.
- [x] A cold-booted resident closes the full loop against a seeded world in a deterministic test.
- [x] The loop-era guidance docs are marked superseded by this major.

## Validation

- `cd ww_agent && pytest -q tests/ -k "pulse or substrate or salience or loop_closure or constitution_gate"`
- Cold-boot smoke: seed deterministic world, boot one resident, assert one full perturbation→pulse→afterimage cycle with provenance.
- `cd worldweaver_engine && python scripts/dev.py quality-strict`

## Risks & Rollback

- **The substrate can't carry behavior without per-loop LLM.** If mechanistic cognition feels too thin between pulses, tune the ignition threshold and add cheap mechanistic reflexes; do **not** re-add LLM calls to the loops. Rollback is the git bundle, not a restored loop-mind.
- **Resprawl.** Building fast with nothing running reintroduces parallel rails. Hold Phase 0's single-ledger discipline as a hard gate before Phases 3+.
- **Pulse too sparse or too frequent.** Ignition threshold and afterimage half-life are the dials; calibrate against the cold-validation harness, not vibes.
- **Constitution gate too rigid or too loose.** Per Major 42: expose steward-visible tuning; rigid freezes the resident, loose lets drift become canon.

---

*Created 2026-06. Threads onto 42/46/47/48; supersedes the loop-era agent docs. Drafted from a design conversation (society-of-mind reframe → predictive pulse → salience-as-grain → constitution anchor) captured in the collaborator's notes.*
