# Matched-window un-stunted re-measure (close the Major-51 measurement loop)

> **Canonical home: WorldWeaver. Legacy Stable ID: Minor 50.** Migrated 2026-07-14 and retained as
> deferred read-only research.

## Metadata

- ID: 121-matched-window-un-stunted-re-measure
- Type: minor
- Owner: Levi
- Status: backlog
- Risk: low

## Problem

Major 51's Rung-3 groundwork left a measurement loop open. The drive vector was silently OFF for a stretch (the `host.docker.internal` embedder URL didn't resolve under bare WSL — the "stunted familiar" confound), then fixed (wake scripts auto-heal to the WSL gateway). An **un-stunted baseline** was taken (`scripts/_baseline_retrieval.py`, `score_predictions.py`), but the clean **matched-window stunted-vs-un-stunted diff** — the actual discriminator — was never run. The key question stands unresolved: does un-stunting raise `new_anchor_recall` (the stickiness-immune signal that the soul created real predictability), or only smooth the prose?

The un-stunting split point is recorded: **T = 2026-06-03 12:08:05 local (epoch 1780513685)**; anchor snapshots with `observed_ts ≥ T` are un-stunted.

## Proposed Solution

Run the equal-sized-window comparison the Rung-3 notes specified: take N stunted snapshots before T and N un-stunted after T (equal counts, since both `new_anchor_recall` and overall recall improve with accumulated history), hold/exclude the whisper log, and measure in **concept space** (threshold 0.7) using the existing tooling:

- `new_anchor_recall` (retrieval vs persistence) — the stickiness-immune discriminator
- `transition_learnability` string vs `transition_learnability_semantic` concept
- the generalization backtest (semantic vs exact new-anchor recall)

Interpretation gate (from the notes): if `new_anchor_recall` rises under un-stunting with the whisper log held fixed → the soul created real predictability ("more anchored"); if only overall recall rises → just smoother prose.

## Files Affected

- `ww_agent/scripts/_baseline_retrieval.py` (extend to take a split timestamp + equal-window slicing) or a sibling re-measure script
- (read-only) the familiars' `memory/runtime_ledger.jsonl`

## Acceptance Criteria

- [ ] A reproducible command produces the matched-window (equal-N, pre-T vs post-T) comparison per familiar.
- [ ] `new_anchor_recall`, concept-space `transition_learnability`, and the generalization backtest are reported for both windows.
- [ ] The result is interpreted against the stated gate (real predictability vs smoother prose), honestly, with the window/whisper-log confounds named.

## Validation Commands

- `cd ww_agent && set -a && . <(sed 's/\r$//' .env) && set +a && ../worldweaver_engine/.venv/bin/python scripts/_baseline_retrieval.py --split-ts 2026-06-03T12:08:05 …`
- `(manual) compare the two windows; check window sizes are equal`

## Pruning Prevention Controls

- Authoritative path: the canonical ledger (`runtime_ledger.jsonl`); the script is pure measurement, trains/changes nothing.
- Parallel path introduced: none.
- Artifact output target: console/report only (no state mutation).
- Default-path impact: none (offline measurement).

## Risks and Rollback

- Risk: the available un-stunted history is still too short for a clean read (the 90-min probe was inconclusive). Mitigate: wait for ≥ a day of un-stunted runtime; use equal windows.
- Rollback: none needed (read-only).
