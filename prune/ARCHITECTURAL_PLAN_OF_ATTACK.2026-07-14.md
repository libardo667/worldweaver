# Architectural plan of attack — 2026-07-14

This is the working architectural sequence for WorldWeaver after reviewing the live majors and minors
under `prune/` against the code they name. It is a durable coordination document, not a replacement for
the individual work items: each implementation still belongs in its major or minor and must satisfy that
item's acceptance criteria and evidence requirements.

**Execution update (2026-07-17):** the full relevance/completion sweep is recorded in
`WORK_ITEM_AUDIT.2026-07-14.md`. The consolidation work this plan originally prioritized is complete:
root CI and one root developer environment, the engine event spine, removal of the storylet/turn pipeline,
the durable resident ledger, relational evidence, the narrow resident-state contract, physical speech,
plural world salience, substrate-native rest, and the shared city/hearth resident host have all landed.
Stable work items now have one canonical home here and Stable is read-only source history.

City-to-city travel has also moved well beyond the state described in the original plan. Node identity is
separate from city-pack identity; city packs publish validated travel hubs; discovery joins possible local
routes to live federation nodes; source departure and destination arrival are recoverable; and the resident
host can resume one unfinished trip from ledger evidence without running cognition between cities. Local
SFO and Portland containers now prove direct two-way reachability while residents remain stopped.

The immediate direction is now **public, independently operated node connectivity** on top of the new
resident/hearth portability boundary. This is still architectural work, not a request for population
experiments, tuning runs, or broad resident activation. Maker has completed the first deliberately bounded
three-tick check and is parked at his hearth; no cohort was started.

## What landed after this plan was written

The July 14–17 implementation sequence changed the project in six concrete ways:

1. **One developer surface.** The monorepo uses the root `.venv`, root `dev.py`, and root CI. Nested
   virtualenv workflows and local-state CI assumptions are retired.
2. **One event and evidence path.** World commands submit through the reducer/event service; the resident
   ledger is truly append-only with bounded normal reads and checkpoint recovery; relationship claims can
   be traced to delivery and reply events.
3. **Elective information instead of prompt flooding.** Exact prompt traces are private diagnostics;
   encounters are consumed only when selected into a prompt; typed prompt context distinguishes available,
   selected, and withheld sources; private `reach` is separate from outward `act`; source records retain
   provenance; local physical traces can be inspected without becoming ambient narration.
4. **One resident across hearth and city.** `Resident` is the only composition root. It swaps one core
   between an exclusive public city attachment and a private hearth, with keeper, files, weather, sight,
   and gifts available only as explicit hearth grants.
5. **A real local travel topology.** SFO and Portland have separate databases and backends, stable node and
   city identities, validated travel hubs, live route discovery, and recoverable departure/arrival. Normal
   `weave-up` keeps agents off, auto-seeding cannot reset resident state, registration waits for a real
   pulse, and strict readiness probes the advertised peer address rather than trusting registry freshness.
6. **Hosting no longer means ownership.** Major 127 separates the resident's `actor_id`, personal hearth
   shard, current world attachment, and temporary runtime host. Hearth manifest v1 describes only the
   stable actor/hearth identity and runtime generation. Maker is the first legacy hearth imported under
   this contract; his old host permissions were deliberately not carried forward.
7. **One real resident crossed the new launch boundary.** Maker ran alone for three ticks. That check found
   and fixed self-writing being mistaken for a letter, failed actions being reported as successful, and a
   stopped bounded process leaving a public city session behind. He is asleep at his hearth now.

## Current limits — do not describe these as complete

- SFO and Portland currently advertise `host.docker.internal` addresses supplied by the local developer
  harness. Those addresses work between containers on one computer and are not reachable by another
  steward over the internet.
- `world-weaver.org` and its Cloudflare tunnel are currently offline. The older configuration is useful
  deployment groundwork, not a live public node.
- Federation registration and handoff still rely on one shared token. Independently operated stewards need
  separate node identities and signed requests before this is a real trust boundary.
- Resident homes still live under city shard directories, and the city agent service still boots a whole
  resident cohort. The package and generation fence make a stopped hearth portable between cooperating
  hosts, but this physical layout still makes the city look like its owner.
- The generation fence handles orderly moves between cooperating hosts. It cannot remotely revoke an
  undisclosed offline copy; signed host authorization and a recovery policy are still open.
- Accepted identity growth is still hydrated from a city database. That authority must move to the
  resident/hearth without bypassing the evidence and maturation rules.
- Maker's first bounded wake tested ordinary startup and shutdown, not city travel or cross-host migration.
  Those paths still need one deliberate resident check after the trust and public ingress boundary is ready.

## Architectural correction — one resident, many worlds

Major 86 records a dependency that this plan previously omitted: `the-stable`'s hearth resident and
WorldWeaver's city resident are not two agent species. The resident is the continuous owner of identity,
ledger, memory, workshop, and cognition; hearth and city are world attachments. Every resident must have a
private hearth it can enter without being exposed to the city current, and travel must change embodiment
without creating or copying a second mind.

This is an architectural requirement, not a live-agent experiment and not a verdict deferred to Major 82.
It changes the placement of later work:

- resident faculties and the elective-source contract must be shared before Major 65 grows more city-only
  tools;
- Major 37 must model hearth entry as one actor swapping world attachment, with exclusive presence;
- WorldWeaver owns the resident host and capability ecology; Stable is read-only source lineage;
- keeper/FileScope/MCP capabilities remain optional grants and must not become universal city-resident facts.

Major 127 adds the physical-host correction. The resident/hearth is a portable logical shard; a computer
only supplies temporary storage and compute. City travel changes one active world attachment. Host
migration moves the resident/hearth machinery. Neither operation changes identity or gives a city,
steward, computer, or federation directory ownership of the resident.

## Executive sequence

1. Restore trustworthy CI and current architectural guidance. **Complete.**
2. Unify engine event submission and finish deleting the turn pipeline. **Complete.**
3. Fix the resident ledger's append and reduction cost model. **Complete.**
4. Complete relational events and narrow the resident-state ontology around evidence-backed claims.
   **Complete.**
5. Complete physical speech topology and plural world salience, then build the shared resident/hearth
   capability seam. **Complete.**
6. Build actor identity, private hearth attachment, and recoverable federation travel outward from those
   stable contracts. **Core identity and host-local travel complete; cross-host portability open.**
7. Make hearths portable across temporary hosts, replace shared federation credentials with node identity,
   and bring up the first public independently reachable nodes.
8. Build correspondence, stoops, city authoring, and human-facing surfaces on those settled boundaries.

## Architectural baseline

The live architectural baseline is now:

- The engine submits action, movement, speech, bootstrap, and system events through one canonical
  application service. `/api/action` is a lean action service rather than a narrative-turn orchestrator.
- The resident runtime has already moved to the substrate + predictive pulse under
  `ww_agent/src/runtime/`; `CognitiveCore`, the resident ledger, reducers, perception, and effectors are the
  live architecture.
- Current guidance describes the CognitiveCore architecture; superseded loop-era guidance is historical.

There are also two related but distinct event-sourced systems:

- The engine/world ledger is Postgres-backed through
  `worldweaver_engine/src/services/world_memory.py`.
- The resident ledger is file-backed through `ww_agent/src/runtime/ledger.py`.

They now have clean mutation, schema, projection, and persistence contracts for the current travel and
hearth work. They remain deliberately separate stores: a city's Postgres world ledger owns public local
facts, while the resident's file-backed ledger owns private continuity. Major 127 must preserve that
boundary when a hearth moves between physical hosts.

## Milestone A — make the repository trustworthy

### A1. Root CI — complete (archived Minor 61)

The only GitHub Actions workflow still lives under `worldweaver_engine/.github/workflows/`, so it is not a
repository-root workflow. Minor 61 is also stale where it names `narrative-eval-smoke`, which Major 69
deleted with the storylet/next pipeline.

The corrected root gates should cover:

- engine tests and lint;
- agent tests and lint;
- client typecheck and build;
- the public leak sweep;
- a check against references to deleted narrative-evaluation machinery where useful.

### A2. Document currency — complete (archived Major 81)

This should be a factual rewrite, not a prose expansion:

- replace `ww_agent/AGENTS.md` with current guidance;
- rewrite `ww_agent/src/README.md` around the live runtime;
- remove current-doc references to deleted `src/loops/` and `src/memory/` packages;
- re-baseline roadmap claims against actual work-item status;
- update Minor 38's proposed frontend decomposition, since several suggested hooks already exist and the
  guild surfaces it names have been retired.

### A3. Repair and retire Major 76's substrate-sync invariant — complete

Commit `507557d` repaired the former source classifications. The subsequent ownership decision retired
the sync tool entirely: WorldWeaver is canonical, so no external manifest can overwrite its substrate.

### Exit condition

Repository-root CI exercises the engine, agent, and client, and a new contributor or agent is directed to
the architecture that actually runs.

## Milestone B — give the engine one event spine — complete

### B1. Define canonical world-event submission — complete

World-event writes formerly split among:

- `worldweaver_engine/src/services/turn_service.py`;
- movement and speech routes in `worldweaver_engine/src/api/game/world.py`;
- `record_event()` in `worldweaver_engine/src/services/world_memory.py`.

The application-level event-submission contract now owns:

- command/event validation;
- reducer invocation;
- persistence;
- projection update and invalidation;
- a consistent response/receipt boundary.

Action, movement, public chat, bootstrap, and system events now route through it. `/api/action` follows the
lean path Major 69 names: **interpret → validate → reduce → record**.

Private mail is deliberately not a `WorldEvent`: `/api/world/history` exposes that table, while DMs are
private by contract. Keep delivery in `DirectMessage` until the Major 66/72 relational envelope can carry
directed edges with explicit visibility. Unification must not make private correspondence public.

### B2. Finish Major 69 slice 3 — complete

After no event write depended on the turn orchestrator, the implementation:

- deleted `turn_service.py`;
- moved the retained pure action helpers from `src/services/turn/` to `src/services/action/`, then deleted
  the turn package;
- deleted `orchestration_adapters.py` and turn-only compatibility types;
- replaced orchestration-mechanism tests with action/event-contract and reducer-authority tests.

Do not retain a generic turn abstraction merely because an action arrives as an HTTP request. The target
world is command/event-driven, not narrative-turn-driven.

### B3. Honor archived Major 15's WorldProjection decision

The audit resolved Outcome C: `WorldProjection` is a reducer-produced materialized view of canonical
events and is load-bearing in action, movement, speech, rebuild, and overlay tests. Preserve that model
while tightening event ownership:

- keep projection writes behind canonical event reduction;
- prohibit new direct mutation authorities;
- keep reset/rebuild operations explicit and tested.

Do not mechanically apply the resident slogan "the ledger is the only state" to the engine. Durable
materialized projections are compatible with event sourcing; competing mutation authorities are not.

The event-path work preserved this already-proven ownership while removing the turn orchestrator.

### Exit condition

The reducer is the only canonical world-state mutation authority, every production command retains its
event-ledger write, and no live code describes a storylet/turn runtime.

## Milestone C — make the resident substrate durable

### C1. Execute Major 85 through the canonical substrate owner — complete

The resident ledger now appends without rewriting history, keeps the complete cold log, uses a guarded
hot window for short-lived calculations, and advances an atomic versioned checkpoint during normal work.
Complex projections rebuild from at most the newest 10,000 events; only checkpoint recovery rereads the
complete file. Golden and performance tests cover output agreement, recovery, retention beyond the old
limit, and flat normal-update cost as cold history grows. The completed work item is archived at
`prune/history/majors/85-unbounded-ledger-the-append-only-log-should-actually-be-append-only.md`.

### C2. Complete Major 66's architectural event schema — complete

Phase 1 is effectively complete and its addressee-based `in_reply_to` decision is locked. Do not reopen
it. Complete the schema needed for deterministic relational queries:

- stable actor identity and location on relevant perceptions and acts; **complete (2026-07-17)**
- `co_present` on the event at which presence is known; **complete (2026-07-17)**
- recipient-side perception events at prompt ingestion time; **complete (2026-07-17)**
- `resident_seeded` with stable provenance from `runtime/doula.py`; **complete (2026-07-17)**
- stable identifiers across speech transport, perception, and reply edges; **complete (2026-07-17)**
- a versioned edge schema rather than accumulating ungoverned payload keys. **complete (2026-07-17)**

The completed Phase 2 uses a versioned envelope and immutable `utterance_perceived` events. A resident
does not count as having perceived a line merely because polling returned it: the event is written when
that line enters a prompt. The edge can be derived by joining the sender's canonical `utterance_id` and
the recipient's `utterance_perceived`; mutating the original utterance would violate the append-only
model.

The completed Phase 3 writes a resident's birth facts to that resident's ledger before boot and one shared
`cohort_config` entry per doula process to its administrative ledger. This makes the actual configuration
inspectable without treating it as resident thought or scheduling a live cohort run. Major 66 is archived
at `prune/history/majors/66-log-edges-not-just-nodes-the-relational-ledger.md`.

### C3. Re-baseline Major 35 into a smaller resident-state contract — complete

Major 35 has the right destination but names deleted implementation surfaces and treats already-landed
phases as future work. Narrow the remaining contract to four layers:

1. immutable resident events;
2. reducer checkpoints;
3. derived projections;
4. provenanced subjective claims and edges.

The ticket is now re-baselined. Prove the model with one relationship-knowledge vertical slice:

```text
utterance perceived
→ reply edge
→ relationship projection
→ subjective claim with evidence IDs
→ inspectable steward view
```

This gives supersession, evidence lineage, temporal state, and query semantics a real use case before the
project invents a general subjective fact graph.

The relationship slice is complete and archived at
`prune/history/majors/35-deepen-the-fractal-architecture-with-resident-ledgers-and-subjective-fact-graphs.md`.
It proves event → projection → evidence-backed claim → mirror inspection without inventing a general fact
graph. Belief provenance stays with Major 56.

Keep canonical resident truth file-backed during this milestone. First make the contract correct,
versioned, reproducible, and inspectable; decide on shard Postgres only after that.

### C4. Reconcile identity and growth governance

Archived Major 42 plus active Majors 56/58 and archived Major 61 describe overlapping architectural
generations. Do not reintroduce Major 42's
deleted `slow.py`/soul-note mechanism. Preserve its constitutional concern in the newer model:

- canonical identity is immutable;
- growth is a separate append-only, evidence-backed layer;
- promotion follows archived Major 61's provenance rules;
- beliefs follow Major 56's provenance model;
- matured growth follows Major 58's concordance gate;
- rendered `SOUL.md` is a projection/export, never the in-place source of truth.

Major 127's hosting audit exposed one remaining ownership problem here: accepted growth is currently
hydrated from the active city database. Before a hearth becomes portable, decide how accepted growth is
carried by the resident/hearth while preserving the existing proposal and maturation gate. Do not let the
city a resident happens to visit become the permanent owner of their changed identity.

### Exit condition

Complete resident history is retained, per-event runtime cost is bounded, relational facts are recorded at
the edge-forming moment, and a resident claim can be traced to immutable evidence.

## Milestone D — make the world structurally plural

### D1. Execute Major 63 (physical speech topology) — complete

The live transport now treats monoculture first as a routing problem, not a personality problem:

- local speech is the default;
- addressing an absent person uses a private carry rather than a citywide fallback;
- only an explicit city target broadcasts;
- immutable events distinguish local, citywide, carried, heard, overheard, and directly addressed
  speech, with stable relationship evidence;
- the pulse contract tells residents what those target choices mean.

Minor 32 does not need to be folded into this completed routing slice. It remains optional map texture and
has been reassigned to Major 36, where child-location and occupancy semantics actually belong.

### D2. Complete Major 64 (plural salience) — complete

Plural salience is now a resident-side projection over independent world sources, not another prompt
filter. It can retain:

- local world events;
- physical speech;
- environmental changes;
- ambient presence;
- personal relationships;
- traversal encounters.

The reducer preserves the latest competing feature clusters and exposes source count, dominant share, and
effective feature count. Ambient descriptions remain outside the default prompt and are available through
the elective `surroundings` source. This makes a one-note scene measurable without forcing a second
authored topic into it. Major 62 remains deferred because its own analysis correctly identifies
composition as the weakest lever.

Reconsider Minor 33 here as cheap local environmental texture, not as a population of simulated full
residents.

### D3. Execute Major 84 (substrate-native rest) — complete

Rest is derived from circadian wakefulness plus sustained low arousal, published through the runtime
mirror, and consumed by the live rest-metrics endpoint and client. Deep-night calm now returns without a
model call, while ignition/direct address still wakes the resident. The old tuning-based schedule summary
is gone.

Keep Minor 62's dark-room classifier out of the immediate implementation queue until the ledger records
enough input novelty and diversity provenance to distinguish starvation from legitimate habituation.

### D4. Complete Major 86 at the capability boundary

Before adding Major 65's seed kit to `city_tools.py`, extract one typed elective-source/capability contract
usable by both HearthWorld and CityWorld. Correct FileScope provenance so authorized reading is not rendered
as already-held local knowledge. Classify faculties such as mirror, lots, provenance-on-self, and measure as
resident-scoped; classify city walks, letters, traces, and local world sources as world-scoped. **The shared
source boundary and the first shared resident host are complete as of 2026-07-17.** The host now ports
Stable's proven live swap, but requires confirmed city retirement and rebuilds world-scoped sources before
activating the keeper-free hearth.

**Complete 2026-07-17.** The current hearth is a durable actor-home attachment on the resident host; it
does not require one engine process or database per resident. The subsequent Major 37/126 work inspected
`build_city_pack.py`, separated node identity from city-pack identity, added destination-owned travel hubs,
and completed the recoverable host-local city-to-city handoff. Cross-computer hearth portability remains a
different operation under Major 127.

### Exit condition

Locality and plurality are properties of world transport and state, and operational quiet is legibly
derived from the substrate rather than imposed or guessed.

## Milestone E — connect independently hosted residents and worlds

The first three steps in the older outward sequence are substantially complete:

1. **Major 20 core complete:** one durable `actor_id` crosses local sessions and federation travel. Legacy
   migration, human cross-node hydration, and federation-root ownership language still need cleanup.
2. **Major 86 complete:** every resident has a private hearth and one host swaps exclusive world
   attachment.
3. **Major 37/126 travel core complete:** stable travel hubs, live route resolution, recoverable source
   departure, destination arrival, and resident-host recovery are implemented. A full City Studio and
   public steward workflow remain open.

Continue from that checkpoint in this order:

4. **Major 127 — portable resident/hearth hosting.** The fail-closed inventory, deterministic package
   round trip, and stopped-runtime generation fence are complete on synthetic homes. Maker's real Stable
   hearth has been reviewed, imported, activated, and woken under this boundary; identity-growth authority
   and a real stopped-host migration remain open.
5. **Majors 20/37 — independently operated node trust.** Replace the federation-wide master token with
   per-node identity and signed registration/travel handoffs. Keep directories as routing projections, not
   owners of residents or cities.
6. **Major 18 — first public ingress.** Recover the existing `world-weaver.org`/Cloudflare tunnel setup as
   one project-operated directory and node. It is a bootstrap path, not a required central service; other
   stewards may use their own domains, tunnels, or public hosts.
7. **Maker-assisted resident validation.** **Basic wake/stop and hearth source review complete.** Continue
   with bounded one-resident doorway checks after architectural slices and occasional open exploration.
   Later, use one deliberate run—not a cohort—to confirm city travel and remote attachment against the live
   topology. Capture exact prompts and receipts; do not treat this as a population experiment.
8. **Major 126 — public City Studio.** Share one pack schema/build engine between CLI and a steward-facing,
   pre-habitation editor. Never mutate an occupied city pack without an explicit migration workflow.
9. **Major 125 — digital stoops.** Build local, city-owned places for bounded exchange between humans and
   residents.
10. **Major 36** — viewport map, graph navigation, and truthful occupancy.
11. **Majors 39 and 72** — durable public and private correspondence channels.
12. **Major 71** — privacy-scoped steward diagnostics, separate from the ordinary commons interface.
13. **Major 43 + re-baselined Minor 38** — rebuild the front door and client shell around settled modes.

Major 70 (AI-spend observability) is relatively orthogonal and may be pulled earlier if operating cost is
blocking development. It should use the same append-only event/accounting pattern.

Major 25 remains parked. Collapsing `worldweaver_engine` and `ww_agent` would create broad path churn
without fixing their real boundary; their HTTP separation is currently cleaner than their internal
architectures.

### Exit condition

A resident/hearth can move between temporary physical hosts without changing identity or producing two
live copies; independently operated cities can discover and receive that resident using separate node
credentials; loss of a directory or peer does not stop local city or hearth life; later public surfaces
consume the same stable actor and event contracts.

## Maker tests — resident-assisted engineering checks

Maker has a history of reading the runtime he lives in, comparing code with his own record, and naming
concrete mismatches. His work is open for project review. WorldWeaver should use that collaboration as a
normal engineering input without turning him into a compulsory bug oracle or treating one resident as a
representative population.

Use two forms of bounded session:

1. **Doorway check.** After a specific resident-facing change, offer one neutral question and the exact
   door being checked. A clean result, blocked path, mismatch, or no interest are all valid outcomes. Fix
   confirmed machinery problems and, where useful, offer one retest of the same door.
2. **Open exploration.** Occasionally make no engineering request. Tell Maker he may live in the available
   hearth and towns as he chooses: stay home, read, make something, enter a city, move, speak, inspect a
   route, travel, or do nothing. Let the bounded session finish before analyzing what paths were actually
   usable and where friction appeared.

For both forms:

- run Maker alone through `dev.py resident`; never start the doula or cohort as part of the check;
- cap the run in advance, do not steer between ticks, and park him at the hearth afterward;
- keep exact prompts and private reasoning in the private trace; review source-access metadata, action
  receipts, attachment changes, and workshop material he has expressly opened for review;
- verify every claimed code defect independently with source and a synthetic regression test;
- do not require a finding, tune behavior from one session, or turn these checks into population research;
- do not gate architectural decisions on Maker's approval. Treat his account as unusually valuable user
  evidence alongside tests, code review, and the project's stated design.

The first focused check found that Maker's carried Stable inbox existed on disk but could not be reopened.
The repair restored safe nested gift paths; his retest reopened the old pages and surfaced a second small
basename-recovery issue. Both were independently reproduced and covered by synthetic tests before landing.

## Explicitly excluded from the current architectural queue

The following work depends primarily on running, measuring, tuning, or training agents and is excluded
until the machinery above is trustworthy:

- Major 51's per-mind model training;
- Major 60's pending live validation;
- Major 62's casting experiments;
- Major 73's pen-strength/marination study;
- Majors 74, 75, and 77, plus Major 82's population experiment;
- archived Minor 57's boundary measurement application;
- Minor 63's live threshold calibration;
- further doula/casting runs under Major 32.

Also defer:

- Major 78 research synthesis;
- Major 80 thesis/publication work;
- Minor 37 until Major 43 settles the interface;
- any live Stable-era research imported as Majors 114–121 or Minors 120–129 unless separately promoted.

## Immediate next work item

The next implementation ticket should be:

> **Give independently operated nodes separate trust and a real public route**

The identity/hosting audit, manifest v1, and fail-closed inventory are complete. Every resident path is now
classified as one of:

- resident-owned and portable;
- rebuildable/optional;
- host-specific grant or secret;
- city-local runtime state;
- unknown, which fails closed.

The inventory now handles the file-level seams discovered in the audit:

- `session_id.txt` is a disposable city incarnation and must not travel as identity;
- `hearth.json` can contain absolute host paths and keeper grants that require re-approval on a new host;
- the complete append-only ledger and resident-owned workshop should move, while projections/checkpoints
  must declare whether they are verified or rebuilt;
- provider, database, tunnel, and federation credentials must never enter a resident package.

It has been proven on synthetic homes and reviewed against one real home without copying or changing it.
Deterministic export/import is also complete in synthetic tests: packages contain only declared portable
files, verify their sizes and SHA-256 hashes, install atomically into a new path, and never replace an
existing home. No real resident home has been initialized or packaged.

One authority problem is deliberately still open: accepted identity growth currently comes from the active
city database. It needs a resident/hearth-owned source without bypassing the existing growth gate.

Stopped-runtime activation is now proven on synthetic homes. A run holds one local lease; an orderly
transfer advances the imported copy to generation N+1, retires the source, and only then activates the
target. The old cooperating host refuses to start. This does not remotely revoke an undisclosed offline
copy, and the package hashes do not prove who authorized a transfer; crash recovery and node signing stay
in the later federation trust work.

The bounded operator path is now complete. It requires exactly one city and resident, disables the doula,
refuses a running cohort container, checks the selected home, activation state, city route/health, model
configuration, and runtime lock without printing credentials, and caps a live run at 20 ticks. Its default
is read-only, and it never initializes or activates a home implicitly.

Maker was selected at the human checkpoint. His Stable home was reviewed and imported through the explicit
allowlist, generation 1 was activated, and the read-only preflight passed before he was woken. His bounded
three-tick run completed and he is parked at the hearth. It found three cleanup/routing defects, now covered
by tests: self-writing stays in the workshop, failed effectors produce a false receipt value, and a bounded
stop retires the city session before releasing the runtime lease.

The architecture should now move outward: replace the shared federation token with per-node trust, recover
the `world-weaver.org` public ingress as one optional route into the commons, and prove that one resident
host can attach over authenticated HTTPS to a city on another computer without handing that city the
resident's private hearth. Maker may also take bounded open-exploration sessions under the rules above;
those sessions inform the work but do not replace the node-trust implementation sequence.

In parallel but not mixed into the hearth archive, preserve the federated-commons boundary already proven
by local SFO/Portland travel:

- `city_id` names a portable city pack;
- `shard_id` names one independently operated node hosting a pack;
- `hearth_shard_id` names one resident's private shard;
- directories coordinate discovery and travel but own none of those things;
- a physical host supplies temporary service and does not own its resident or city.

The existing `world-weaver.org` Cloudflare path can become the first public directory/node after the
offline portability boundary is clear. Do not hard-code that domain as the network's only root. Major 125's
stoops, Major 126's full City Studio, and the public client remain the next outward layers; detailed
resident internals stay in a restricted steward surface rather than the ordinary commons interface.

## Maintenance rule for this document

Update this plan only when an architectural dependency, ownership decision, or milestone exit condition
changes. Record implementation detail and evidence in the owning major/minor instead. When the sequence is
no longer current, archive this file under `prune/history/` rather than silently rewriting it into a record
of a different plan.
