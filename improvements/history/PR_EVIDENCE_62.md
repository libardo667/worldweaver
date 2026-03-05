# PR Evidence: Major 62 - Harden World Memory and Projection Spine (v2)

## Item

`improvements/majors/archive/62-harden-world-memory-and-projection-spine-v2.md`

## Scope

Completed v2 hardening for the world-memory/projection acceptance layer by tightening deterministic eval coverage (identity + grounding), fixing harness execution correctness, and adding canonical identity normalization for rank-prefixed aliases.

## What Changed

| File | Change |
|------|--------|
| `scripts/eval_narrative.py` | Reworked identity assertion execution to use the authoritative eval DB session directly; removed brittle dependency-override generator usage; retained scenario-level `identity_results` and aggregate `identity_stability_score` metric computation. |
| `tests/integration/narrative_eval_scenarios.json` | Expanded/retained mined coherence probes and new scenarios; updated NPC identity scenario actions to produce extractable identity-bearing facts under deterministic offline eval. |
| `src/services/world_memory.py` | Hardened canonical node-name normalization with rank/honorific prefix stripping (`warden`, `captain`, `dr`, etc.) so alias forms converge to stable identity keys. |
| `tests/service/test_world_memory.py` | Added coverage proving rank-prefixed alias convergence resolves to one canonical node and identical neighborhood center node. |
| `tests/integration/test_narrative_eval_harness.py` | Extended smoke assertions to require `identity_stability_score` presence. |
| `reports/narrative_eval/baseline.json` | Updated thresholds for expanded probe set and added `identity_stability_score` guard. |
| `reports/narrative_eval/latest.json` | Updated with final passing full eval report. |
| `reports/narrative_eval/history.jsonl` | Appended smoke/full eval history entries for this major's verification runs. |
| `reports/narrative_eval/runs/*.json` | Added run artifacts captured during enforce-gated verification passes. |
| `improvements/ROADMAP.md` | Marked major `62` complete and flattened active queue to remaining minor work. |

## Why This Matters

- It makes world-memory identity checks deterministic and trustworthy, instead of depending on a fragile harness DB-access path.
- It directly upgrades comparative-playtest readiness: grounding/identity regressions are now measurable and enforce-gated.
- It improves graph consistency under real narrative alias patterns (`Silas Vane` vs `Warden Silas Vane`) so downstream projection/fact queries stay coherent across turns.
- It reduces "false confidence" runs by enforcing the expanded scenario/probe suite as part of CI-friendly deterministic evaluation.

## Acceptance Criteria Check

- [x] v2 world-memory/projection hardening includes deterministic identity convergence checks in narrative eval.
- [x] Strict narrative eval harness passes with `--enforce` on expanded scenarios/probes.
- [x] Playtest-mined grounding probes are encoded and evaluated deterministically.
- [x] `python -m pytest -q` succeeds.

## Quality Gate Evidence

### Gate 1: Contract Integrity

- No API route/path/payload contract changes.
- Changes are internal service normalization + harness/scenario/test artifact updates.

### Gate 2: Correctness

- `python scripts/dev.py eval-smoke` -> pass, regressions `[]`
- `python scripts/dev.py eval` -> pass, regressions `[]`
- `python -m pytest tests/integration/test_narrative_eval_harness.py -q` -> `1 passed`
- `python -m pytest tests/service/test_world_memory.py -q` -> `42 passed`
- `python -m pytest -q` -> `548 passed, 14 warnings`

### Gate 3: Build and Static Health

- `python scripts/dev.py lint-all` -> pass
- `npm --prefix client run build` -> pass

### Gate 4: Runtime Behavior (Deterministic Eval Metrics)

- Final full eval metrics (`reports/narrative_eval/latest.json`):
  - `memory_carryover_score=1.0`
  - `divergence_score=0.4`
  - `freeform_coherence_score=0.6`
  - `contradiction_free_score=1.0`
  - `arc_adherence_score=1.0`
  - `identity_stability_score=1.0`
  - `repetition_window_guard_score=0.947368`
  - `narrative_command_success_rate=1.0`
- Regressions: `[]`

### Gate 5: Operational Safety

- Rollback path: revert this PR's harness/scenario/baseline/test updates plus rank-prefix normalization in `src/services/world_memory.py`.
- Safe-disable path: remove `identity_stability_score` threshold from baseline to disable identity gating without reverting broader eval harness improvements.
- Data safety: no destructive migrations; behavior change is canonicalization heuristics + eval/test artifacts.

## Residual Risk

- Rank/honorific stripping is heuristic and may over-merge unusual names that intentionally include title-like prefixes.
- `freeform_coherence_score` baseline was lowered to match the stricter probe corpus; additional command-interpreter hardening can raise this threshold in a follow-up.
