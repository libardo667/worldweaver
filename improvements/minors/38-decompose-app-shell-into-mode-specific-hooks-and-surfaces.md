# Decompose App shell into mode-specific hooks and surfaces

## Problem

[`worldweaver_engine/client/src/App.tsx`](worldweaver_engine/client/src/App.tsx)
currently carries too many cross-cutting responsibilities at once, including:

- shard/session recovery
- auth recovery
- observer state
- guild board state
- quest state
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

- `useShardSession`
- `useAuthRecovery`
- `useObserverMode`
- `useGuildState`
- `useChatState`
- `useQuestState`

Then clarify the app surface into distinct modes:

- threshold mode
- world mode
- guild/admin mode

This is not a full redesign. It is a structural cleanup that makes the product
shape legible and lowers the cost of future UI work.

## Files Affected

- `worldweaver_engine/client/src/App.tsx`
- `worldweaver_engine/client/src/hooks/useShardSession.ts`
- `worldweaver_engine/client/src/hooks/useAuthRecovery.ts`
- `worldweaver_engine/client/src/hooks/useObserverMode.ts`
- `worldweaver_engine/client/src/hooks/useGuildState.ts`
- `worldweaver_engine/client/src/hooks/useChatState.ts`
- `worldweaver_engine/client/src/hooks/useQuestState.ts`
- `worldweaver_engine/client/src/components/GuildBoard.tsx`
- `worldweaver_engine/client/src/components/GuildQuestPanel.tsx`
- `worldweaver_engine/client/src/components/PresencePanel.tsx`

## Acceptance Criteria

- [ ] `App.tsx` is materially smaller and no longer owns all onboarding, observer, guild, chat, and diagnostics state directly
- [ ] Session/auth, observer, guild, chat, and quest concerns each have a clearer state boundary
- [ ] Threshold mode, world mode, and guild/admin mode become easier to reason about separately
- [ ] The refactor does not regress existing world participation, observer, or guild-board behavior
