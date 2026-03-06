# Audit archived improvements against acceptance criteria and reopen leaky closures

## Problem

Archived majors/minors represent completion claims, but there is no lightweight,
repeatable audit loop validating that acceptance criteria remain true in current
runtime behavior.

## Proposed Solution

Run a bounded archive audit and convert findings into follow-up work:

1. Randomly sample 5 archived improvements (mixed major/minor).
2. Verify each sampled item's acceptance criteria with tests or manual repro.
3. Publish an audit report with evidence and pass/fail outcomes.
4. Create follow-up minor docs for any failed or partially met criteria.

## Files Affected

- `improvements/majors/archive/*` (read-only audit inputs)
- `improvements/minors/archive/*` (read-only audit inputs)
- `improvements/archive-audit/2026-03-sample-01.md` (new)
- `improvements/ROADMAP.md`

## Acceptance Criteria

- [ ] Audit report exists with exactly 5 sampled archived items and evidence for
      each verdict.
- [ ] Any failed/partial archived items have linked follow-up improvements.
- [ ] Roadmap references the audit report and resulting follow-up work.

