# Add group DMs for persistent mixed human-AI conversation

## Problem
The current DM system only supports one sender and one recipient at a time via [`DirectMessage`](worldweaver_engine/src/models/__init__.py). Player-facing mail threads now exist, but they are still grouped views over one-to-one messages rather than true shared conversations. This prevents small persistent circles of correspondence between multiple humans and residents, and it blocks future agent behavior that depends on stable private group context.

## Proposed Solution
Introduce a first-class DM conversation model with explicit threads, participants, and messages. Keep the existing one-to-one DM endpoints working as compatibility shims that create or append to a two-party thread, but add a new API surface for creating group threads, adding/removing participants, fetching conversation state, and posting messages into a shared mailbox.

The first implementation should:
- add durable thread tables for `dm_threads`, `dm_thread_participants`, and `dm_thread_messages`
- treat each participant as an `actor_id` or a shard-local stable identity key instead of a transient session row
- expose player and agent fetch endpoints that return one shared ordered conversation per thread
- preserve per-participant unread state
- keep existing player mail and agent mail loops working by adapting one-to-one mail onto the new thread substrate

The initial group-DM UX should stay simple:
- thread list
- conversation pane
- participant list
- compose box
- unread dot behavior

This should not attempt realtime websockets, typing indicators, or attachments in the first pass.

## Files Affected
- `worldweaver_engine/src/models/__init__.py`
- `worldweaver_engine/src/database.py`
- `worldweaver_engine/src/api/game/world.py`
- `worldweaver_engine/tests/api/test_world_endpoints.py`
- `worldweaver_engine/client/src/api/wwClient.ts`
- `worldweaver_engine/client/src/App.tsx`
- `worldweaver_engine/client/src/styles.css`
- `ww_agent/src/world/client.py`
- `ww_agent/src/loops/mail.py`
- `ww_agent/tests/test_loop_packets.py`

## Acceptance Criteria
- [ ] A player can create a DM thread with more than one participant.
- [ ] A player can send one message that is visible to all thread participants.
- [ ] Unread state is tracked per participant, not globally for the thread.
- [ ] Existing one-to-one player mail still works through the new substrate.
- [ ] Agent mail loops can read and reply into a shared thread without breaking one-to-one correspondence.
- [ ] Group DM history persists across reloads and remains readable in order.
- [ ] The system dedupes participants by stable identity rather than transient session rows.

## Risks & Rollback
The main risk is overloading the current one-to-one mail assumptions and breaking agent correspondence during migration. Keep the existing `DirectMessage` compatibility path in place until group threads are stable, and gate the new group APIs behind additive routes rather than replacing the old ones immediately. If rollout causes regressions, disable the group thread UI and continue serving existing one-to-one mail from the compatibility endpoints while leaving the new tables unused.
