# Make Place panel refresh best-effort after turn render

## Problem
Turn handlers currently refresh spatial navigation in the same completion path as scene/history updates. When spatial refresh is slow or fails, players experience delayed completion or noisy error feedback for what should be a secondary assistive panel.

## Proposed Solution
Convert Place panel refresh to best-effort post-render behavior.

1. Keep scene text, choices, and state-change receipts as first-class turn completion signals.
2. Trigger spatial refresh after core render settles, without blocking turn completion.
3. Downgrade spatial refresh failures to concise non-blocking feedback.
4. Preserve existing movement endpoint behavior and API contracts.

## Scope Boundaries
- Keep action/choice/move endpoint contracts unchanged.
- Do not alter core scene/choice render order for turn completion.
- Limit behavior changes to Place panel refresh timing and messaging.

## Assumptions
- Place panel refresh is assistive and can safely be non-blocking.
- Memory/history refresh behavior remains separate from Place refresh scope.
- Info-level feedback is sufficient for transient Place refresh failures.

## Files Affected
- `client/src/App.tsx`
- `client/src/components/PlacePanel.tsx` (if loading/notice state needs minor UX updates)
- `client/src/types.ts` (if response typing needs narrow alignment only)

## Acceptance Criteria
- [ ] Choice/action turns complete and render core narrative state even when spatial refresh fails.
- [ ] Spatial refresh runs as a best-effort follow-up and does not gate turn completion.
- [ ] Error feedback for Place refresh is reduced to non-blocking informational messaging.
- [ ] Existing movement interactions continue to function when explicitly invoked by the user.

## Validation Commands
- `python -m pytest -q`
- `npm --prefix client run build`

## Rollback Plan
- Revert the branch commit(s) that introduce deferred Place refresh scheduling.
- No feature flag is added; operational rollback is commit revert.
- No irreversible data or migration changes are introduced.
