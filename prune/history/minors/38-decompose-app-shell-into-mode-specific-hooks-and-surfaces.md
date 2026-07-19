# Decompose App shell into mode-specific hooks and surfaces

## Update (2026-07-14) — re-baselined after guild removal and partial extraction

The original proposal is stale. `useShardSession`, `useObserverMode`, and `useChatState` already exist;
the guild board, guild quest panel, and their state were removed. `App.tsx` is still 1,556 lines, so the
decomposition need is real, but the remaining work is auth/entry orchestration, map/navigation state,
settings/diagnostics, and thinning the world-mode composition. Do not recreate guild or quest surfaces.

## Problem

[`worldweaver_engine/client/src/App.tsx`](worldweaver_engine/client/src/App.tsx)
currently carries too many cross-cutting responsibilities at once, including:

- shard/session recovery
- auth recovery
- observer state
- chat and DM state
- map and routing state
- diagnostics and settings state
- mobile layout state

That makes the app hard to reason about as a product. It is trying to be the
threshold, the world shell, the guild shell, and the operator console all at
the same time.

## Proposed Solution

Decompose `App.tsx` into mode-specific hooks and thinner surface components.

Suggested extraction path:

- `useAuthRecovery`
- `useMapNavigation`
- `useWorldParticipation`
- a settings/diagnostics boundary where the state warrants one

Then clarify the app surface into distinct modes:

- threshold mode
- world mode
- operator/settings surfaces inside the appropriate threshold or world mode

This is not a full redesign. It is a structural cleanup that makes the product
shape legible and lowers the cost of future UI work.

## Files Affected

- `worldweaver_engine/client/src/App.tsx`
- `worldweaver_engine/client/src/hooks/useAuthRecovery.ts`
- `worldweaver_engine/client/src/hooks/useMapNavigation.ts`
- `worldweaver_engine/client/src/hooks/useWorldParticipation.ts`
- `worldweaver_engine/client/src/components/PresencePanel.tsx`

## Acceptance Criteria

- [ ] `App.tsx` is materially smaller and no longer owns entry, map, participation, and diagnostics state directly
- [x] Shard/session, observer, and chat concerns have dedicated hooks
- [ ] Auth/entry, map/navigation, and world-participation concerns have clear state boundaries
- [ ] Threshold and world modes become easier to reason about separately
- [ ] The refactor does not regress existing entry, world participation, observer, chat, or map behavior
