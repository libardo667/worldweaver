# Retrospective

## Window

- Start: 2026-03-03
- End: 2026-03-03
- Scope: Pruning cycle `001` (lanes 1-4), integrated via `improvements/PRUNING_INTEGRATION_EVIDENCE.md`

## Outcomes

- What shipped:
  - Integrated lane outputs in planned order (Lane 2 -> Lane 3 -> Lane 1 -> Lane 4 -> final gate).
  - Produced integration evidence with conflict decisions, validations, and follow-up actions.
  - Restored minimal compatibility exports needed by active contract tests while keeping broader legacy cleanup.
- What was stabilized:
  - Spatial movement contract behavior (`403` blocked semantics and traversable-only direction affordances).
  - Full regression gate execution (`python -m pytest -q`, client build) after merge conflict resolution.
  - Dev verification command surface (`python scripts/dev.py verify`) as a reliable integration gate.
- What was pruned (successfully deleted/merged/demoted):
  - Deleted:
    - `save_storylets_with_postprocessing()` compatibility alias in ingest service.
    - Broad refactor-transition re-export surfaces in `src/api/game/__init__.py` and `src/api/author/__init__.py` (except minimal required symbols).
  - Merged:
    - Spatial navigator legacy choice parsing (`set`/`set_vars`) into a single helper path.
    - Compass/client behavior reconciled to one authoritative traversability signal (`directions`) instead of dual semantics.
  - Demoted:
    - Story smoothing / spatial auto-fixer to explicit opt-in (`WW_ENABLE_STORY_SMOOTHING` default off).
    - Repo-wide lint gate to non-blocking debt track (while preserving visibility via explicit commands/docs).

## What Worked

- Contract-first conflict resolution prevented payload drift while still allowing aggressive pruning.
- Lane-order validation caught regressions early before full-suite execution.
- Small, targeted merge edits resolved the highest-risk conflicts without reopening lane scopes.

## What Did Not Work

- Coordination failed on compatibility assumptions:
  - Lane 3 removed `src.api.author` symbols still referenced by contract tests (`patch("src.api.author.SessionVars")`), breaking `scripts/dev.py verify`.
- Coordination failed on UI/backend semantics:
  - Lane 1 temporarily reintroduced attempt-any-direction controls, conflicting with Lane 2 traversability guarantees.
- Lane 4 static gate expectations remained misaligned with current repository debt; lint/format gates stayed red and cannot yet be treated as release blockers.

## Bottlenecks Observed

- Cross-lane compatibility visibility gap (Class A: contract ownership ambiguity).
- Repo-wide static debt volume blocking strict Gate 3 enforcement (Class B: structural hygiene debt).
- Missing focused client tests for compass affordance semantics (Class C: validation coverage gap).

## Process Changes

- Keep:
  - Contract-first arbitration order (`Contract stability -> Correctness -> Simplicity -> Performance -> Style`).
  - Lane-ordered integration with per-lane command gates before full-suite run.
- Change:
  - Add explicit "patch/import contract inventory" to each lane evidence doc so compatibility deletions are pre-negotiated.
  - Require one cross-lane handshake checkpoint between Lane 1 and Lane 2 before UI movement semantics merge.
  - Record lint baseline counts at lane start/end so debt movement is measurable.
- Stop:
  - Implicitly assuming deleted compatibility exports are unused because lane-local tests pass.
  - Treating red repo-wide lint as a surprise at integration time instead of a tracked expected failure class.

## Lane Boundary Changes For Next Cycle

- Lane 1 (Client Navigation):
  - Keep current files.
  - Add ownership of client movement behavior tests (new test files) to prevent UI/back-end semantic drift.
- Lane 2 (Spatial/Prefetch Backend):
  - Keep current files.
  - Add ownership of a compact "navigation contract snapshot" doc artifact consumed by Lane 1.
- Lane 3 (Legacy/Runtime Pruning):
  - Keep current files.
  - Remove authority to delete package-level exports unless paired with explicit import migration edits in all affected tests/docs.
- Lane 4 (Tooling/Gates):
  - Keep current files.
  - Split into:
    - Lane 4A: command/docs/wrapper updates,
    - Lane 4B: lint debt remediation batches,
    to avoid coupling command-surface progress with full lint closure.

## Next Batch Inputs

- Candidate majors:
  - `50-establish-full-project-lint-baseline-and-ci-gates` (resume as staged debt burn-down with enforceable checkpoints).
- Candidate minors:
  - Decouple `/author/debug` and related tests from package-level model patch targets.
  - Add client compass traversability + keyboard parity regression tests.
  - Add lane contract snapshot artifact for spatial navigation payload semantics.
- Required hardening:
  - Convert static debt into tracked buckets (auto-fixable vs manual) and define merge policy thresholds per bucket.

## Top 3 Next Pruning Candidates

1. Package-level patch/import coupling in author debug path
   - Why next: already caused integration failure; high leverage, low blast radius.
2. Repo-wide lint/format debt (major 50 continuation)
   - Why next: blocks strict static gating and adds recurring integration noise.
3. Compass/client movement semantic test coverage gap
   - Why next: recent cross-lane conflict showed behavior can regress without fast detection.
