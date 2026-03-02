# Add a “What changed” receipts strip using client-side diffs

## Problem
Players need immediate consequence legibility. Without a “what changed” surface, outcomes feel like prose-only drift and the world’s persistence is harder to feel.

## Proposed Solution
Add a collapsible “What changed” strip that summarizes:
- changes between previous vars and new vars,
- state_changes returned from `/api/action`,
- choice-set deltas applied by the client.

Heuristic rules (v1):
- show up to 5 changes,
- prefer non-underscore keys and human-labeled keys (e.g., `pref.*` grouped),
- provide “expand” to show full diff.

## Files Affected
- client/src/components/WhatChangedStrip.tsx
- client/src/utils/diffVars.ts (new)
- client/src/state/sessionStore.ts

## Acceptance Criteria
- After a choice or action, the strip shows at least one readable change when vars differ.
- Strip is collapsible and does not disrupt the reading flow.
- No backend changes required.
