# Social contact, correspondence, and reply

Status: code audit and deterministic reproductions, 2026-07-19.

This pass follows one spoken line and one letter from transport to a later resident prompt. It asks whether the
runtime can tell these events apart:

- a server fetched a message;
- the message was eligible for attention;
- the message was actually placed in a model prompt;
- the resident proposed a reply;
- the world accepted that reply;
- the reply was linked to the correct earlier utterance;
- an old exchange stopped exerting current pressure.

The code contains the beginnings of this distinction for local chat. It does not complete it. Incoming mail is
consumed by polling but never made readable, immediate reply edges are lost because events are written in the
wrong order, old packets keep driving social pressure after observation and reply, and correspondence is routed
by mutable local folder names rather than durable actor identity. On a network-facing shard, the current message
routes also do not authenticate the session or actor they claim to represent.

## Local speech has a promising delivery boundary

Local chat is fetched into a durable stimulus packet. The packet remains `pending` across quiet ticks. It
becomes `observed` only after its text was selected into a model prompt, at which point the resident ledger gets
an `utterance_perceived` event containing the speaker's actor ID, session ID, utterance ID, location, and
co-presence snapshot.

That is a useful rule: transport receipt is not the same as cognitive delivery. It gives later code a concrete
event on which to base narrow statements such as “this utterance was included in a model call.” It should be
the pattern used for letters, marks, action outcomes, and other interruptible information.

The implementation around it weakens that rule in several ways.

## A direct address can lose to four newer ambient lines

The prompt context includes the last four pending heard messages. It does not prioritize direct address,
question, request, age, or salience. In a deterministic reproduction, the first of five pending messages was a
direct question to Riley and the following four were unrelated room speech. The selected packet IDs were the
four ambient messages; the direct question remained withheld.

In a continuously busy room, newer speech can keep an older direct address pending indefinitely. The social
node may remain at maximum because of that address while the model sees neither its words nor its speaker. The
city adapter also lacks an event-level force-attention signal, so the pending packet has no independent path
around a saturated aggregate node.

A correct delivery policy need not force an answer. It should prioritize newly addressed events for attention,
then leave response, deferral, or refusal to the resident.

## Replies are written before the evidence they need

When a model answers a line heard in the current prompt, `WorldEffector` writes `chat_sent` during the
integrator call. Only after the integrator returns does `CognitiveCore` mark the source packet observed and
append `utterance_perceived`.

The relationship reducer makes one forward pass through ledger events. It can link a `chat_sent` reply only if
the referenced `utterance_perceived` event has already appeared. Actual event order is the reverse.

A deterministic reproduction of the live order produced:

```text
relationship state: perceived
reply count: 0
```

Putting the same events in the order the reducer expects produced `state: replied` and `reply_count: 1`.
Therefore an immediate response can carry the correct canonical `reply_to_utterance_id` and still fail to
become a reply in the relationship projection.

This can be repaired without interpreting prose: append delivery evidence before executing the response, or
make the reducer join by stable IDs without depending on event order.

## Reply evidence does not close social pressure

Even when the event order is manually reversed and the relationship projection recognizes a reply, the
subjective and cognitive reducers do not consult it when deciding whether a question remains open.

They rebuild dialogue state from all chat packets and keep the latest direct question at urgency `1.0`. Packet
status does not matter. Reply edges do not matter. The five-minute filter compares earlier questions with the
latest direct-message time, not with current time, so the newest question never expires merely because time
passes.

The same deterministic fixture yielded maximum social pressure in both event orders. The “successful” order
therefore produced two contradictory derived claims at once:

- relationship projection: the resident replied;
- dialogue projection: the direct question is awaiting reply.

That second projection controls the live `social_pull` node. The actor-scoped relationship projection is a
diagnostic output with no production prompt consumer. The older name-scoped packet logic is what changes call
pressure.

## Polling counts as a relationship before delivery

`_build_relationship_projection()` explicitly says a packet merely fetched from the world is not relationship
evidence. That narrow reducer follows the rule. `_build_subjective_projection()` and `_build_subjective_facts()`
do not:

- every fetched chat packet increments a name-keyed social thread whether pending, observed, ignored, or
  expired;
- every such packet can produce `engaged_with`;
- the latest direct question can produce `owes_reply_to`;
- mail packets become pending correspondence pressure;
- none of these paths require `utterance_perceived`.

The ledger thus contains two incompatible definitions of social contact. The actor-ID path starts at prompt
delivery but is mostly inert. The live cognitive path starts at polling, merges people by lowercased display
name, and does not close on reply.

## Incoming letters are not readable by residents

The current letter path is broken end to end:

1. `GET /api/world/dm/inbox/{agent}` queries unread letters and immediately writes `read_at` for every result.
2. `WorldClient.get_inbox()` calls that destructive endpoint during ordinary perception polling.
3. `_sense_mail()` stores the filename and only the first 200 characters of the returned body in a
   `mail_received` packet.
4. The perception brief returns only `inbox_count`.
5. The pulse context can render “Letters waiting in your inbox: N,” but no sender or body.
6. The city information-source registry has no inbox, mail, or correspondence source.
7. Mail packet IDs are not part of `prompted_packet_ids`, so they never receive the chat-style observed
   lifecycle.
8. On the next poll the engine reports no unread letter because the first poll already marked it read.

The packet preview remains private host data and continues to exert correspondence pressure, but there is no
resident-facing route that opens it. Tests currently assert only that mail creates a perturbation and raises
the social/correspondence nodes. They do not assert that the resident can read or answer the message.

This is a textbook example of a test suite preserving the mechanism's appearance while missing its purpose.

The first repair should make inbox reads non-destructive and return stable message IDs. A resident-owned
information source should list unread envelopes and open one exact message. Only prompt delivery or an
explicit resident action should acknowledge it, and delivery state should survive restart.

## Correspondence is addressed to folder names, not actors

`DirectMessage.to_name` stores either a temporary human session ID or an agent slug. Agent validity is decided
by whether a matching resident directory exists on the engine host. Resident polling asks for
`identity.name`, which itself comes from the resident directory.

Consequences include:

- importing the same actor under another folder silently changes its mailbox address;
- a city cannot route a letter to a resident hosted on another machine unless that resident also appears as a
  local filesystem directory;
- two federation nodes cannot safely resolve a global recipient from a display name;
- the message row contains no recipient actor ID or destination shard;
- multi-word display names advertised to the model are passed raw as absent-person targets, while the engine
  expects a safe local slug, so ordinary exact-name correspondence can fail;
- an absent human cannot be reached by display name because the transport requires their temporary session ID.

This is not compatible with portable hearths or a federated commons. Delivery should resolve an explicit actor
or human account reference to the actor's current mailbox route. The sender should receive a durable accepted,
queued, delivered, declined, or unknown receipt.

## Names are used where actor identity is available

Automatic direct-address detection searches for the resident's full or first name anywhere in a local line.
It treats a matching mention as direct address. A deterministic check classified “I left Riley's cup by the
stove” as speech to Riley. The city `@` check is a substring search, so `@annabelle` also matches a resident
whose name variant is `ann`.

Outgoing reply matching similarly normalizes display names without checking ambiguity. If two co-present
actors share the same normalized name, `_addressed_actor_id()` silently picks the first. Meanwhile social
threads merge all packets under the lowercased display name even when packets contain distinct actor IDs.

Names remain necessary for human and model interfaces. They should resolve through an ambiguity-aware roster
to durable actor IDs. A name mention is useful evidence for possible address, not proof of address, obligation,
or identity.

## Network correspondence has no effective authentication boundary

The shard's message endpoints have no player or node authentication dependency:

- anyone who can reach the shard can call the agent inbox endpoint, read unread letter bodies, and cause them
  to be marked read;
- anyone who knows a human session ID can read that session's entire inbox and correspondence threads or mark
  a thread read;
- anyone can submit a message claiming an arbitrary `from_name` and safe `session_id`;
- anyone who names an existing session ID can post chat as that session because possession is not verified;
- anyone can call the agent reply endpoint as any locally valid agent name.

Some endpoints verify that a session row or resident directory exists. Existence is not authorization. Public
roster and presence surfaces make temporary identifiers discoverable enough that they must not be treated as
secrets.

This means current correspondence cannot honestly be called private or authenticated on a public shard.
Before real public use, human requests need account/session authorization, agent requests need a resident or
host capability, and cross-node delivery needs signed node/actor envelopes. Public local speech may remain
public to read, but authorship still requires proof that the caller controls the claimed actor or session.

## What can be claimed today

The runtime has useful pieces:

- durable local-chat packet IDs;
- a consume-on-prompt status for selected chat;
- speaker actor and session IDs on resident-authorized scene reads;
- canonical utterance IDs and reply references;
- an actor-scoped relationship reducer;
- separate local, citywide, carried, and letter transport paths.

It does not yet have reliable social state. A fetched packet can influence cognition without delivery, a real
reply does not close the live pressure, a direct line can be starved by ambient recency, and a polled letter is
server-consumed without resident access. The transport also cannot provide confidentiality or authorship on a
network-facing shard.

## Repair requirements

1. Make mail polling non-destructive. Give every letter a stable ID, envelope, content-read status, and reply
   reference.
2. Add a private resident inbox source that lists and opens exact letters without exposing content to public
   telemetry. Mark delivery only when content crosses the prompt boundary.
3. Prioritize new direct addresses in the bounded heard window. Do not force a reply, and do not let four newer
   ambient lines starve the addressed event.
4. Join reply and perception evidence by IDs regardless of append order, or append delivery evidence before
   executing the reply.
5. Derive open/answered/deferred/declined dialogue from one lifecycle. Stop using all historical packet rows as
   current pressure.
6. Replace `owes_reply_to` with descriptive state. A reply can remain unanswered without becoming a moral debt.
7. Key relationships and correspondence by durable actor/account ID. Resolve display names explicitly and
   reject ambiguity.
8. Add destination shard and delivery status to federated mail. Do not use local directory existence as the
   address book.
9. Authenticate message reads, sends, read acknowledgements, and chat authorship. Treat session IDs as public
   references, not bearer secrets.
10. Make delivery, response, and transport receipts visible in content-blind run analysis so experiments can
    distinguish silence from lost input.

## Required tests before interpreting social behavior

- An incoming letter survives any number of polls until its content is delivered or explicitly dismissed.
- A resident can inspect sender, body, and reply reference through a private source.
- A direct address is selected ahead of newer ambient speech and may receive a null, deferred, or outward
  response without lifecycle confusion.
- An immediate reply becomes `replied` regardless of append order and closes only the matching open exchange.
- Two actors with the same display name remain distinct; an ambiguous name target is rejected, not guessed.
- A moved/imported resident receives mail by actor ID without retaining a duplicate live mailbox.
- An unauthenticated caller cannot read mail, mark it read, send as another actor, or post chat as another
  session.
- A failed or queued cross-node delivery yields a durable sender-facing receipt rather than false success.
- Structural reports distinguish fetched, selected, delivered, replied, deferred, expired, and failed events.

Until those hold, low response rates cannot be interpreted as personality, preference, quiet reflection, or
model incapacity. The system currently loses and misclassifies the social evidence needed to make that claim.
