# Pruning Prevention Standards

Use these standards during normal feature work so future pruning is smaller,
faster, and lower risk.

Derived from:
- `improvements/history/PRUNING_RETROSPECTIVE_2026-03-06.md`
- `improvements/history/PRUNING_RETROSPECTIVE_2026-03-03.md`

## 1) Single-authority path per behavior

Rules:
- Do not introduce parallel runtime paths for the same behavior unless there is
  an explicit migration/deprecation plan.
- Extend existing orchestrators/adapters before creating new endpoint or service
  wrappers.
- If a temporary parallel path is required, add:
  - owner,
  - removal condition,
  - removal target date/work item.

## 2) Contract-first change discipline

Rules:
- Treat API payloads, CLI command shapes, and event envelopes as contracts.
- Any contract change requires:
  - compatibility note,
  - test updates,
  - rollback path.
- Avoid package-level re-export coupling for tests/patching; patch concrete
  module ownership paths.

## 3) Optional subsystem isolation by default

Rules:
- Experimental/evaluation/harness features must be opt-in and demoted from the
  default validation/runtime path.
- Risky behavior must have a fast disable switch (feature flag or explicit
  command namespace).
- Default path should remain production-critical checks only.

## 4) Feature-flag lifecycle hygiene

Rules:
- Every new flag must declare:
  - default value,
  - owner,
  - purpose,
  - planned retirement condition.
- Add tests for both flag OFF and ON when behavior materially changes.
- Remove stale flags once migration is complete.

## 5) Source-of-truth vs generated artifact boundary

Rules:
- Keep runtime source-of-truth files in-repo where they are needed to build/run.
- Route generated run outputs, logs, and large evidence artifacts to historical
  archive locations (`improvements/history/...`) unless actively needed.
- Commit automation scripts that regenerate evidence; archive generated outputs.

## 6) Integration test maintainability rules

Rules:
- Prefer shared fixtures/helpers over repeated inline setup/teardown patterns.
- Keep integration tests aligned to public contracts, not internal incidental
  implementation details.
- When backend and frontend semantics intersect, add explicit cross-surface
  regression coverage.

## 7) Complexity budget for hot files

Rules:
- Do not grow high-churn files with mixed responsibilities without extraction
  (for example, move lane routing/payload parsing into dedicated modules).
- Prefer behavior-preserving extraction first, then behavior changes.
- Require clear ownership boundaries for new modules/components.

## 8) Evidence and gate discipline

Rules:
- Run the repository strict gate (`python scripts/dev.py quality-strict`) before
  marking non-trivial work complete.
- Warning-budget increases require explicit approval and a follow-up debt item.
- Record validation outcomes and residual risk in the work item evidence.

## 9) Definition of done additions for agents

Before closing a minor/major item, confirm:
- [ ] No new duplicate runtime path was added without an expiration plan.
- [ ] Contract changes (if any) were explicitly documented and tested.
- [ ] Optional features remain off critical default path.
- [ ] New artifacts are stored in the correct source-of-truth vs archive location.
- [ ] `quality-strict` (or documented substitute when blocked) is captured.

## 10) Anti-patterns to reject during review

- "Add new wrapper path now, reconcile later."
- "Keep compatibility export forever to avoid touching tests."
- "Default-enable fragile feature and fix fallout in follow-ups."
- "Commit generated evidence blobs without regen scripts or archival plan."
