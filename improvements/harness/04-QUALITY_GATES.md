# Quality Gates

Quality gates prevent fast delivery from degrading reliability.

## Gate categories

## Gate 1: Contract integrity

Checks:

- API routes and payload shapes remain stable unless approved.
- Event schemas and response envelopes remain compatible.

Evidence:

- contract tests
- snapshot/schema checks

## Gate 2: Correctness

Checks:

- unit tests pass for touched modules
- integration tests pass for touched workflows
- critical path smoke tests pass
- pytest warning count stays at or below budget artifact threshold

Evidence:

- test command output summaries
- failed test list with disposition if any are quarantined

## Gate 3: Build and static health

Checks:

- project builds successfully
- lint/type/static analysis checks pass

Evidence:

- command + result summary

## Gate 4: Runtime behavior

Checks:

- no regressions in key latency paths
- error rate does not exceed budget
- memory/cache growth remains bounded

Evidence:

- baseline vs after metrics

## Gate 5: Operational safety

Checks:

- rollback path documented
- feature flag or safe disable path for risky changes
- migration rollback strategy documented for stateful changes

Evidence:

- rollback notes in item or PR evidence doc

## Merge policy by risk level

Low risk:

- Gate 1 + Gate 2 + Gate 3 required.

Medium risk:

- All low-risk gates plus Gate 4.

High risk:

- All gates required, plus staged rollout plan.

## Suggested baseline commands

Project strict command path:

- `python scripts/dev.py quality-strict`

Project baseline commands:

- backend tests
- frontend tests/build
- contract tests
- lint/type checks
- smoke scripts

## Failure handling

If any required gate fails:

- do not mark item done,
- either fix immediately,
- or split remaining work into a follow-up item and keep current item in
  `verify` or `blocked`.
