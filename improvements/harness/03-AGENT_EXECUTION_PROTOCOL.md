# Agent Execution Protocol

Use this protocol for each major/minor item to keep changes bounded and
reviewable.

## Before implementation

1. Read the item doc fully.
2. Confirm scope boundaries.
3. List assumptions.
4. List files expected to change.
5. Define validation commands.

If any of these are missing, update the item doc first.

Pruning-prevention precheck (required):

1. Confirm you are extending an existing authoritative path, not creating an
   unbounded parallel path.
2. Confirm any optional/harness/experimental behavior stays off the default
   runtime/validation path.
3. Confirm generated artifacts from this item have an archive target (not
   accidental source-of-truth placement).

## During implementation

Rules:

- No drive-by refactors outside scope.
- No contract changes unless item explicitly allows them.
- Keep edits incremental and logically grouped.
- Prefer behavior-preserving extractions before behavior changes.
- Prefer concrete module ownership imports/patch targets over package-level
  re-export dependencies.

Execution rhythm:

1. Context pass (read relevant files).
2. Implementation pass (small focused diffs).
3. Verification pass (tests/build/smoke).
4. Evidence pass (capture what passed and what is still risky).

## Communication requirements

For each meaningful step, record:

- what changed
- why it changed
- what was verified
- what remains risky

## Validation requirements

Run, at minimum, the commands specified by the item doc.

If a required command cannot run:

- document why,
- provide nearest substitute evidence,
- leave the item in `verify` or `blocked`, not `done`.

## Rollback discipline

Every non-trivial item must define:

- which commit(s) to revert,
- which feature flags/configs can disable impact quickly,
- what data migrations or state changes are irreversible.

## Completion checklist

- [ ] Scope stayed within declared file boundary.
- [ ] Acceptance criteria were verified, not assumed.
- [ ] Tests/checks were run or explicitly documented as blocked.
- [ ] Risks and rollback notes were updated.
- [ ] Follow-up items created for unresolved debt.
- [ ] Pruning-prevention checks from
      `improvements/harness/09-PRUNING_PREVENTION_STANDARDS.md` were satisfied.
