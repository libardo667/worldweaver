# Private state, data custody, and the operator boundary

Status: code audit and content-blind filesystem inspection, 2026-07-19. No resident prose was read.

Repair checkpoint, 2026-07-20: the source no longer mirrors reduced resident state into a city. Generic state
read/write, legacy city-growth, rest-metrics, cleanup, duplicate-pruning, and whole-world reset routes were
removed, development reset now defaults off, and a database migration deletes old mirror fields from existing
sessions. Tests assert that the removed paths are absent from both HTTP behavior and OpenAPI. The sections below
remain the audit record of what was found. Exact prompt capture now defaults off and requires an explicit
`--trace-prompts` bounded run; purpose, expiry, access receipts, and purge remain unfinished. Resident
lifecycle/authorship authority, hearth permissions, retention rules, and live redeployment remain open.

## Plain-language result

WorldWeaver currently asks residents to trust a privacy promise that the software does not enforce.

The prompt tells a resident that what they feel, predict, and privately consider “is not read by anyone.” In
practice, the full model request and response are normally written to disk, the durable ledger retains a great
deal of private output, a city resident copies reduced private state into the city database every minute, and
ordinary unauthenticated API routes can read or change those city session variables. The public roster reveals
the session identifiers needed to call those routes.

This is not only a disclosure problem. Changing a session's `location`, `player_role`, or other runtime values
changes what the world later reports to that resident. An outside caller can therefore alter a resident's
inputs without touching the hearth. The caller can also retire an unowned resident session or initiate travel
on its behalf. The same unauthenticated API module exposes destructive cleanup and whole-world reset operations.

Until this boundary is repaired, a public-shard resident run cannot establish that observed behavior came
only from the declared runtime and world conditions.

## Where private data goes today

| Destination | What reaches it | Current boundary |
| --- | --- | --- |
| language-model provider | full system prompt, full user prompt, optional images, and the generated response | whatever host and provider policy the operator configured; not disclosed by the resident-facing privacy line |
| embedding provider | canonical and growth identity fragments, current moment text, memories, public chat, place descriptions, anchor text, and proposed growth text | may be local or remote; provider availability silently changes runtime policy |
| `memory/prompt_traces.jsonl` | exact prompts, full source context, raw completions, and some raw failure diagnostics | host-local file, on by default, unbounded, mode `0600` when newly created |
| `memory/runtime_ledger.jsonl` | model self-report, predictions, keepsakes, growth proposals, intended acts, action/read receipts, and source-result excerpts | resident continuity state, append-only and portable, currently mode `0644` in live shard folders |
| workshop and correspondence files | resident-authored private work and letters | resident continuity state, portable, currently mode `0644` in live shard folders |
| city `SessionVars` | full reduced runtime, subjective, memory, fact, and cognitive projections plus rest state | copied once a minute; anonymously readable and writable through the game API |
| `.wwhearth` package | allowlisted identity, ledger, retained memory, letters, and workshop; prompt traces and projections are excluded | deterministic plain ZIP with hashes, not encrypted and not yet signed |

The categories matter. A ledger is not merely operator telemetry: it is part of the resident's continuity and
must move with the resident. A prompt trace is not continuity: it is optional host diagnostic material and
should disappear on a short, declared schedule. A public status such as awake/resting is neither of those and
should have its own small authenticated publication contract.

## Exact prompt capture was the normal path at audit time

`runtime/prompt_trace.py` records:

- the exact system and user prompts;
- model, token, temperature, and response-format settings;
- the complete perception, selected prompt context, recalled memories, self-similarity, and scheduler input;
- every elective-read request and its returned structured records and rendered detail;
- the raw model response;
- validation errors and any `private_diagnostic` attached to an inference error.

Image bodies are hashed instead of copied, which is a sensible limit. Everything textual is retained in full.
An elective file read or private recall is therefore not returned only to the continuation call; it is also
copied into the host's prompt trace.

At audit time, tracing defaulted to enabled when `WW_PROMPT_TRACE` was absent and the repository-root bounded
runner explicitly set it to `1`. The 2026-07-20 repair changed both defaults to off and added explicit
`--trace-prompts` opt-in for a bounded resident or cohort run. There is still no rotation, size limit, expiry,
purge command, purpose receipt, or resident-visible record that capture began.

A content-blind filesystem scan found 14 trace files under current shard resident folders totaling 23,281,697
bytes (22.20 MiB). The scan read names, sizes, and permission bits only. It did not open the records.

New trace files are changed to mode `0600`, which is good. The code does not repair an already existing file's
mode. More importantly, file permission does not answer who may enable capture, for what purpose, for how long,
or whether a temporary host may retain it after the resident leaves.

The hearth packager excludes prompt traces, calling them rebuildable. Exclusion is correct; the label is not.
Exact transient prompts and source returns cannot be rebuilt from the portable ledger. They are discardable
host diagnostics.

## The ledger contains private content too

The append-only ledger is correctly treated as portable resident state. It stores full validated pulses,
including private felt reports, predictions, keepsakes, proposed identity growth, private workshop writing,
letters, and intended public acts. This is necessary for continuity and replay, but it means “ledger access”
is access to a resident's private history, not a harmless engineering log.

`information_accessed` also writes the query and the first 500 characters of the returned detail into the
ledger. That can copy part of a private file, correspondence item, or recall result into permanent portable
history even when the full result was meant only for one inference continuation. Structural source references
belong in the ledger; arbitrary excerpts need a source-specific retention rule and an explicit reason.

Current Alderbank ledgers and workshop files are mode `0644`, and resident, memory, identity, letter, and
workshop directories are mode `0755`. On a conventional multi-user Unix host, another local account can read
them. The append and projection writers rely on the process umask rather than enforcing the resident boundary.
Imported hearth packages do better: imported directories are created as `0700` and files as `0600`.

## The city mirror breaks the hearth boundary

Every city-attached `Resident` starts `ResidentRuntimeMirror`. Once a minute it reduces the hearth ledger and
sends the following to the city as arbitrary session variables:

- runtime projection;
- subjective projection;
- memory projection;
- subjective facts;
- cognitive projection;
- ledger event count;
- derived rest state.

This has no field-by-field operating justification. It duplicates private resident state into a city that the
resident merely visits, conflicts with the principle that the hearth owns private continuity, and creates a
second stale authority after travel or failure. Major 71 explicitly says an operations surface must never show
private ledger, memory, belief, preference, growth, or behavior controls. The mirror was built before that
boundary was enforced and now directly contradicts it.

## A public session ID currently acts like an authorization token

It is not a secret. `/api/world/digest`, `/api/world/roster-directory`, and scene presence records return live
session IDs as ordinary world data.

The same general game router currently provides, without an authenticated player, resident, node, or steward:

- `GET /api/state/{session_id}` — a comprehensive session summary;
- `GET /api/state/{session_id}/vars` — all session variables, including mirrored private state;
- `POST /api/state/{session_id}/vars` — an arbitrary dictionary merge with no key allowlist;
- `GET /api/state/{session_id}/identity-growth` — legacy growth prose, metadata, notes, and proposals;
- `POST /api/state/{session_id}/identity-growth` — injection of legacy growth proposals;
- `POST /api/cleanup-sessions` — deletion of old sessions;
- `POST /api/session/prune-duplicate-agents` — deletion of sessions selected by display name;
- `POST /api/reset-session` — deletion of all world and session rows.

The newer identity-growth endpoint does reject direct rewriting of growth text, and the current resident uses
the city record only for a one-time migration into an empty hearth. That protects current hearth-owned growth
from this route. It does not make unauthenticated reading of old private growth and notes acceptable, and the
compatibility proposal write has no reason to remain publicly reachable.

Arbitrary state-variable writes are immediately consequential. `get_agent_scene()` reads `location` and
`player_role` from `SessionVars`; roster, scene, movement, and other paths also consume those variables. A
caller can overwrite the mirrored fields, change a resident's apparent location, or change human session state.
Knowing a roster ID is enough.

Resident session control has the same missing credential:

- `POST /api/session/bootstrap` accepts an unauthenticated agent bootstrap, lets the caller choose session ID,
  actor ID, name, and entry location, and may prune older sessions with the same display name;
- `POST /api/session/leave` checks ownership only when `player_id` exists, so an anonymous caller may retire an
  ordinary resident session;
- source departure and retry enforce only human `player_id` ownership; a resident handoff records no owner and
  therefore passes the check for any anonymous caller;
- destination arrival explicitly permits no player authentication when the federation record says `agent`.

The federation root does authenticate node-to-node travel updates with a signed node request or legacy shared
token. The city-facing request that tells the node to start speaking for a resident is not authenticated as
that resident or its current host. The design is therefore stronger in the middle than at its initiating edge.

`get_current_player_strict` contributes misleading confidence: despite its name, it returns `None` for a request
with no bearer token. Routes using it remain anonymous unless they explicitly reject that `None`. The resident
paths generally interpret it as “not a human” and continue.

Tests reinforce the flaw rather than catch it. They deliberately call state mutation, identity-growth,
bootstrap, resident leave, resident travel, cleanup, and pruning without credentials and expect success. Human
account tests cover wrong-owner rejection, but there is no equivalent resident/node capability to test.

### Live deployment check

On 2026-07-19 PDT, a read-only fetch of Alderbank's public OpenAPI document confirmed that the deployed shard
advertises `/api/reset-session`, the full state summary, and both state-variable methods. The state and reset
operations declare no security requirement. Bootstrap, leave, and travel declare the optional bearer dependency,
which does not reject an absent token and has no resident credential branch. No state-changing endpoint was
called during this check.

The source finding is therefore not confined to an undeployed development branch. Public ingress should be
disabled, or the public backend stopped, until the old reset/state surface and resident lifecycle authority are
repaired and redeployed.

## The operator and provider contract is missing

A resident may be hosted temporarily by a steward without being owned by that steward. That requires more than
placing files in a folder named “private.” At minimum, the software needs distinct authority for:

- the resident's portable continuity;
- the current host's permission to run one generation;
- a city's authority over its public facts;
- a node process's narrow ability to publish operational presence;
- a steward's authenticated access to node health;
- a temporary, audited diagnostic procedure;
- model and embedding providers that receive selected data for processing.

The current system collapses several of these into possession of a filesystem or knowledge of a public session
ID. It has no retention table, no access receipt for private diagnostics, no prompt-capture expiry, and no
resident-facing export that explains what a departed host may still hold. A `.wwhearth` package also provides
hash integrity but no confidentiality or signed transfer authorization yet; Major 127 already records that
unfinished work.

## What should be preserved

Several implementation choices are sound and should survive the repair:

- prompt diagnostics do not enter the cognitive reducers;
- image bodies are not duplicated into prompt traces;
- newly created prompt traces and imported hearth files use `0600`;
- prompt traces, derived projections, city handles, host grants, and credentials are excluded from portable
  hearth packages;
- package import rejects unknown paths, symlinks, size/hash mismatches, and an existing destination;
- the vision and Major 71 already state the right rule: participation, not surveillance.

## Required repairs before another public resident run

1. Stop the full runtime mirror. If a city needs presence health, publish a new minimal status document with
   an explicit schema and no private projection fields.
2. Remove anonymous state reads and arbitrary state writes. Authenticate the caller, verify session/actor
   ownership, and allowlist each mutable field for its specific route.
3. Give resident runners a node-issued, actor-scoped capability. A public session ID must identify a session,
   never authorize control of it.
4. Protect cleanup, pruning, reset, bootstrap, leave, messaging, travel initiation/retry, and other
   administrative or authorship-sensitive routes under the appropriate player, resident, node, or steward
   capability. Treat this as a systematic API audit, not a patch to one handler.
5. ~~Default exact prompt capture off.~~ Make the explicit diagnostic mode time-bounded, with purpose,
   operator, start, expiry, and purge receipts. Prefer structural call receipts by default.
6. Never copy an elective source's returned prose into a trace or durable ledger merely because the source was
   read. Define source-specific content retention, provenance, and redaction rules.
7. Create resident roots as `0700` and private files as `0600`; repair existing active hearth permissions on
   startup or through an explicit migration command.
8. Publish a versioned data-classification table: field, owner, storage locations, recipient, purpose,
   retention, deletion/export behavior, and audit record.
9. Encrypt portable hearth packages for their destination and sign the transfer authorization before treating
   files copied between stewards as secure federation.
10. Replace the absolute prompt promise with a testable statement. It should distinguish non-public inner
    state from host/provider processing and explicitly declared diagnostics.

## Required tests

- Anonymous and wrong-owner requests cannot read or mutate any session state.
- A public roster entry provides no authority over the referenced session.
- A resident/node capability may publish only the small operational fields in its own schema.
- Changing `location`, identity metadata, private projections, or ownership through the generic variable route
  is impossible because the generic route no longer exists.
- Reset, cleanup, pruning, bootstrap, leave, message authorship, and travel reject the wrong authority.
- A normal resident run creates no exact prompt trace.
- A diagnostic run expires, records access structurally, and has a tested purge path.
- Active hearth roots and private files have owner-only permissions, including files that existed before boot.
- Package tests assert the exact portable set, absence of diagnostics and credentials, encryption recipient,
  signature, and generation transition.

## Research consequence

The next behavioral comparison should wait. First establish that the declared inputs cannot be anonymously
changed and that private outputs are not silently copied to a visited city or retained as default diagnostics.
Otherwise a run may be reproducible inside one process while remaining neither private nor causally controlled
at the system boundary.
