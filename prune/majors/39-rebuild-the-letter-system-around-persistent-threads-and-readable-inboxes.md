# Make letters readable as persistent conversations

## Status

Resident mail is durable and available through the current CognitiveCore path. The deleted mail loop must
not return. The engine's human-facing `DirectMessage` table and routes, however, still address temporary
session IDs and local resident folder names. They are not yet the actor-addressed shared thread model this
item calls for, so they must not be copied into the public client as if the architecture were complete.

## Problem

The legacy client derives two-person threads from message text fields and session IDs. Its single
`read_at` field marks a message globally, not separately for each participant. Recipient discovery scans
local resident folders and recent session contacts. City travel therefore changes the human address, and
federated delivery is still translating back into the same local table. Resident state can notice incoming
mail, but humans and residents do not yet share one stable conversation record.

## Build next

1. Replace the session/name `DirectMessage` address fields with sender and recipient actor IDs. Keep a
   narrow compatibility reader only long enough to migrate existing correspondence.
2. Derive or store one stable thread ID for a pair of actors or a deliberately bounded group.
3. Return sent and received messages together in chronological order.
4. Add read/unread state that belongs to each participant rather than to the message globally.
5. Add a simple mailbox and thread view to the public client after login. Do not port the legacy routes.
6. Keep thread IDs and pending replies in the resident's bounded reduced state.
7. Preserve correspondence across city travel by addressing actors, not sessions or local player rows.
8. Add basic search or filtering without turning mail into an urgent notification feed.

## Boundaries

- Mail is slower correspondence, not an automatic prompt interruption.
- A resident may reply, defer, archive, or ignore a letter.
- Public users see only correspondence they participate in.
- The federation may route cross-node mail, but it does not publish or analyze private thread contents.
- Humans and residents use the same message and thread rules.

## Acceptance criteria

- [ ] One API returns an actor's thread list and ordered messages.
- [ ] Sent and received messages appear together in the human thread view.
- [ ] Per-participant unread state is visible and clearable.
- [ ] Basic search or filtering is available.
- [ ] A resident's reduced state retains active mail threads across unrelated local chat.
- [ ] City travel does not change thread identity or duplicate correspondence.
- [ ] Mail does not force ignition or become a shard-wide feed.
