# A baseline-pinned port-assistant that coordinates the recurring the-stable → worldweaver substrate reconvergence

## Update (2026-07-14) — classification invariant repaired after Major 83

The agent suite exposed `the-stable/src/runtime/source_gate.py` as unmanifested. Re-baselining the map
also found two classifications that would undo deliberate pruning: `guild.py` (removed by Major 68) and
`retrieval.py` (removed by Major 83) were still eligible to be ported back into WorldWeaver. Both are now
`fork-stable`; the stale `fork-worldweaver` row for deleted `rest.py` is gone. `source_gate.py` is
`canonical-stable`, ready to port when Major 67's city integration is executed.

This slice repairs classification truth only; it does not stage the broader six-file reconvergence or
its existing `salience.py`/`pulse_engine.py` conflicts. A dry run now reports those real merges without
an `UNMANIFESTED` file and without proposing resurrection of guild/retrieval modules.

## Declaration (workflow authority, per CLAUDE.md)

- **Authoritative path:** new dev tooling under `ww_agent/scripts/` (a script + a manifest + a baseline
  file + tests). Does not touch any existing runtime module's behaviour.
- **Default-path impact:** none at runtime. The tool only *reads* `../the-stable` and *stages* candidate
  changes into the worldweaver working tree for human review; it never runs in the agent loop and never
  auto-commits.
- **Contract impact:** none. No API, schema, or ledger-format change. It is a maintenance instrument.
- **Validation:** `cd ww_agent && python -m pytest tests/test_sync_substrate.py -v`; then the live proof —
  a real run that ports `city_world.py` cleanly (the first reconvergence exercise).

## Problem

The agent substrate is forked across two live trees that the project deliberately keeps diverging:
`the-stable/src/runtime/` (the standalone familiar home, where small changes + per-resident observation
happen first) and `worldweaver/ww_agent/src/runtime/` (the city runtime, where matured pieces are ported
for grander-scale testing). CLAUDE.md already names this ("one fork of a substrate shared with `../the-stable`
… being reconverged into the city runtime"), but reconvergence is currently a from-scratch archaeology dig
each time, and it is going to keep happening.

Measured drift today (2026-06-14), the-stable@`b108cfe` vs ww_agent: **11 files byte-identical**
(`anchors, circadian, drive, guild, ledger, naming, prediction, pulse, signals, substrate, __init__`),
**~10 drifted, bidirectionally and asymmetrically:**

- **the-stable leads (cognition):** `retrieval.py` (+98/−1), `world.py` Protocol (+36), `workshop.py`,
  most of `memory.py`, phantom-drop in `salience.py` (Minor 66), retrieval-cast in `cognitive_core.py`.
- **worldweaver leads (world + scale):** `perception.py` (+112), `effectors.py` (+83), `integrator.py`
  (+51), large parts of `salience.py` (+245) & `pulse_engine.py` (+297); fork-only `incubation.py`,
  `mirror.py`, `rest.py`, `growth_proposals.py`.

Because the drift is bidirectional, a blind "copy the-stable → ww_agent" is a **footgun**: it would silently
delete worldweaver's incubation wiring, 245 lines of its salience work, 112 of perception, 83 of effectors.
And a raw two-way `diff` is unreadable (e.g. salience 66-vs-245) because there is no record of *what was
last ported* — every reconvergence re-diffs the whole drifted file from scratch.

## Proposed Solution

A one-way **port-assistant** (the-stable → ww_agent), not a merger. The key idea is a **pinned baseline**:
record the-stable git SHA at each successful sync, so the next run computes *only the-stable's new changes
since then* — cleanly isolated from however far worldweaver has independently drifted.

1. **`ww_agent/scripts/sync_substrate.py`** — the tool. For each manifested file:
   - compute `the-stable@baseline .. the-stable@HEAD` (the new upstream delta);
   - **`canonical-stable`** (the-stable is source of truth; worldweaver shouldn't diverge): apply the-stable's
     current file; if worldweaver *has* diverged, flag it loudly (a manifest lie to fix);
   - **`bidirectional`** (both forks evolve it): a **3-way merge** via `git merge-file -p`
     (base = the-stable@baseline, ours = ww_agent current, theirs = the-stable@HEAD) → clean merge where
     possible, conflict markers staged for review where not — far fewer false conflicts than a 2-way;
   - **`fork-worldweaver`** / **`fork-stable`**: never touched; report only;
   - any the-stable file **not in the manifest**: flagged as new/unclassified so nothing drifts silently.
   - Output a summary report (applied-clean / needs-review-with-conflict-locations / skipped / new). Stage
     into the working tree (or `--dry-run` = report only). **Never commit.** Refuse to run if the-stable's
     working tree is dirty for a file in scope (baseline integrity).
2. **`ww_agent/scripts/substrate_sync_manifest.toml`** — the single inspectable classification of every
   runtime file (the living map of "what is shared vs forked"). Extensible to `src/familiar/`,
   `src/inference/` later; v1 scopes `src/runtime/` + `src/inference/client.py`.
3. **`ww_agent/scripts/.substrate_sync_baseline`** — the pinned the-stable SHA (+ its path) from the last
   successful sync; bumped only when a human accepts a sync. Today's bootstrap value: `b108cfe`.
4. **`ww_agent/tests/test_sync_substrate.py`** — fixtures (two tiny trees + a baseline) asserting:
   classification routing, canonical apply, 3-way merge clean + conflict cases, dirty-tree refusal, and the
   unmanifested-file flag.

## Files Affected

- `ww_agent/scripts/sync_substrate.py` (new)
- `ww_agent/scripts/substrate_sync_manifest.toml` (new)
- `ww_agent/scripts/.substrate_sync_baseline` (new)
- `ww_agent/tests/test_sync_substrate.py` (new)
- `ww_agent/README.md` or `worldweaver_engine/AGENTS.md` — a short "reconverging the substrate" note (the workflow it encodes)

## Acceptance Criteria

- [ ] `--dry-run` produces a correct classification report over the live trees (11 identical, the drifted
      set routed canonical/bidirectional, fork files skipped, no unmanifested surprises).
- [ ] A `canonical-stable` file whose worldweaver copy has *not* diverged is updated to the-stable's current
      version mechanically; the run reports the diff.
- [ ] A `bidirectional` file produces a 3-way result against the pinned baseline; clean merges apply,
      genuine conflicts are staged with markers and listed for review — worldweaver-only code is preserved.
- [ ] The tool refuses to run on a dirty the-stable scope and never commits; baseline only advances on an
      explicit accept.
- [ ] Tests green; `quality-strict` clean.
- [ ] **Live proof:** one real run ports `the-stable`'s city-client work (`city_world.py`) without clobbering
      worldweaver-side code (the exercise that also unlocks Maker roaming PDX).

## Risks & Rollback

- **Silent clobber of fork-specific code** — the whole risk the tool exists to remove. Mitigations: the
  manifest is the gate (fork files are never touched), 3-way merge over 2-way, never auto-commit, and a
  dirty-tree refusal. Rollback is trivial: staged-not-committed, so `git checkout -- <files>` discards.
- **Stale/wrong manifest** — a misclassified file ports wrong. Mitigation: unmanifested files are flagged,
  and a `canonical-stable` file that has in fact diverged on the worldweaver side is reported as a manifest
  lie rather than blindly overwritten.
- **Baseline rot** — if the baseline SHA is never advanced, deltas re-accumulate. Mitigation: the tool prints
  the current vs candidate baseline every run and bumps it only on an accepted sync.
- **Over-reach into an ML/sync platform** — keep it a thin, pinned, one-way assistant for *this* fork pair;
  do not generalize into a vendoring framework.
