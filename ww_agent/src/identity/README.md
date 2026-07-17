# Identity

## Loader and prompt identity

`loader.py` loads a resident's durable identity, compatibility tuning, and world-supplied situational
facts. It renders only facts the world reports; missing affordances stay silent rather than becoming
prompt folklore.

The identity seam distinguishes immutable canonical soul text from separately recorded growth. Runtime
cognition may propose growth, but it does not rewrite canon in place. See `runtime/growth_proposals.py`
and the identity tests for the maturation contract.

`LoopTuning` and loop-shaped keys in `tuning.json` remain compatibility inputs for existing resident
directories. Current consumers translate those values into pulse, rest, incubation, grounding, and
other substrate behavior. They are not evidence that the removed loop bank still exists.

When adding a situational affordance, update all three pinned surfaces together:

- `BRIEFING_FACT_KEYS` and its gated renderer line;
- the runtime world protocol documentation;
- the drift-catcher tests.

Never infer a claim about a resident's selfhood from deployment facts. State the circumstance and leave
its meaning open.

## Resident, hearth, attachment, and hosting

These are four different things. Code in this package and in `resident.py` must not collapse them.

## The contract

- **Resident identity (`actor_id`)** says who the resident is. It survives every city, hearth, process,
  physical computer, and federation-directory outage.
- **Hearth shard (`hearth_shard_id`)** is the resident's stable private world and resident-owned storage
  scope. It is not a city of origin and not a computer.
- **World attachment** says where the one active `CognitiveCore` presently lives: the hearth or one city
  shard. `resident.py` records attachment changes in the resident ledger and must keep this exclusive.
- **Runtime host** is the temporary computer or worker supplying storage and compute. Hosting may change
  without changing identity, hearth, or current world attachment.

A steward or city may host a resident/hearth, but does not own it. Do not add a permanent owner-host field
or derive identity from a filesystem path, Compose project, hostname, or city shard.

City travel and host migration are separate state machines:

- city/hearth or city/city travel changes world attachment;
- host migration moves the resident/hearth runtime to different machinery;
- neither creates a new actor, copies a second live core, or makes a federation directory authoritative
  for private resident state.

## What the code does today

The useful parts of this contract already exist:

- `identity/resident_id.txt` holds the durable `actor_id`;
- `Resident` owns one core lifecycle and serializes attachment changes;
- the append-only ledger restores hearth/city attachment and unfinished city travel;
- city sessions are local incarnations and may be retired and recreated;
- the hearth rebuild uses the same resident directory, ledger, identity, and workshop.

Physical deployment still violates or obscures the intended boundary:

- resident directories live at `shards/<city>/residents/` and are mounted by that city's Compose project;
- `ww_agent/src/main.py` boots every resident under one directory against one initial city client;
- `session_id.txt` sits at the resident root even though it is a disposable city-local handle;
- engine `home_shard` fields currently mean an origin or home city, not a resident hearth;
- mutable identity growth is currently hydrated from a city database;
- `hearth.json` can contain host-specific grants and absolute file roots;
- the federation uses one shared token and stores coordination rows described in some older code as
  canonical identity.

Those are migration inputs, not the target architecture. In particular, do not rename current
`home_shard` columns and assume the problem is solved; their existing data has different meaning.

## First portable-hearth boundary

A future versioned hearth package should allowlist resident-owned state. The first audit classifies it as:

### Resident-owned and expected to move

- stable actor and hearth identity material;
- canonical identity/soul inputs and accepted growth evidence;
- the complete append-only ledger;
- resident-owned workshop and correspondence artifacts;
- configuration that describes the private hearth itself without naming host resources.

### Rebuildable or optional

- reducer projections and checkpoints that can be verified against the ledger;
- inference prompt traces, which are private diagnostics but not cognitive input;
- caches and generated mirrors.

### Must not move as resident identity

- `session_id.txt`, world IDs, open travel connections, and city database rows;
- provider API keys, Compose environment, database credentials, or tunnel credentials;
- absolute host paths and keeper-granted `FileScope` roots;
- city facts, stoops, occupancy, and other state owned by the visited city;
- a host's claim that its filesystem copy is entitled to wake.

Major 127 requires a versioned hearth manifest and stopped-runtime generation fencing. A stale copy must
not be able to start after a newer generation becomes active elsewhere.

`hearth_manifest.py` defines the first manifest version. It contains only `actor_id`, the deterministic
`hearth_shard_id`, and `runtime_generation` plus schema fields. It deliberately contains no current world,
session, host, path, or credential. `scripts/hearth_manifest.py HOME` inspects without writing;
`--initialize` is the explicit one-time migration action. The generation is descriptive in this first
slice and does not yet fence a running process.

`hearth_package.py` provides the fail-closed, read-only inventory used before packaging. It hashes files
that belong to the resident but does not copy them. Identity evidence, retained memory and ledgers,
correspondence, decisions, and workshop artifacts are portable. Derived projections and process files are
rebuildable; city sessions and entry hints are city-local; host grants and credential-like paths are
host-specific. An unfamiliar path or any symlink blocks packaging until its meaning is made explicit.

The same module now exports those allowlisted files into a deterministic `.wwhearth` ZIP and imports only
after the metadata, manifest, declared paths, sizes, and SHA-256 hashes all agree. Import writes into a
temporary sibling and renames it into place only after validation; it never replaces an existing home.
This protects against accidental corruption and unsafe paths, but it is not yet a signed statement of who
authorized a transfer. Export also requires an explicitly initialized hearth manifest. Generation
activation and stale-copy refusal are the next boundary.

## Open decisions that must remain explicit

- Where the resident's identity signing/recovery material lives and how it can be recovered without making
  one steward or federation root the owner.
- How accepted identity growth moves out of city authority while preserving the existing proposal gate.
- Which correspondence records are resident-owned versus city/federation delivery projections.
- Which private diagnostics a resident chooses to carry during host migration.
- How a lost host is replaced after orderly migration works; this is not permission to invent automatic
  distributed consensus in the first slice.

See `prune/majors/127-make-resident-hearths-portable-across-temporary-hosts.md` for the staged work and
acceptance criteria.
