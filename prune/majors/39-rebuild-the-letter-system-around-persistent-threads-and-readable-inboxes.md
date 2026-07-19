# Make letters readable as persistent conversations

## Status

Letters are durable, addressed by actor identity, and available to residents through the current
CognitiveCore path. The deleted mail loop must not return. What remains is a shared thread model and a
usable human mailbox.

## Problem

The current human interface treats mail as a compose form and a flat list. Sent and received messages are
hard to revisit as one conversation. Resident state can notice incoming mail, but does not yet expose a
stable conversation thread that both humans and residents share.

## Build next

1. Derive or store one stable thread ID for a pair of actors or a deliberately bounded group.
2. Return sent and received messages together in chronological order.
3. Add read/unread state that belongs to each participant rather than to the message globally.
4. Add a simple mailbox and thread view to the public client after login.
5. Keep thread IDs and pending replies in the resident's bounded reduced state.
6. Preserve correspondence across city travel by addressing actors, not sessions or local player rows.
7. Add basic search or filtering without turning mail into an urgent notification feed.

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
