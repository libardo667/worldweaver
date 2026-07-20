# Publish the first federated WorldWeaver node

## Status

The `world-weaver.org` domain now serves a single-computer public test, but no supported production node is
online yet. The old proposal for a public observatory is rejected: the public interface should show places
and local participation, not resident timelines or operating data.

The 2026-07-19 CognitiveCore privacy audit found that the deployed Alderbank OpenAPI exposed unauthenticated
full-state, arbitrary session-variable write, and whole-world reset routes. Source was repaired on 2026-07-20:
those routes and the private runtime mirror are gone, development reset defaults off, tests assert that the old
paths are absent, and a migration removes stale mirror fields. This repair is not yet the deployed Alderbank
image. Resident bootstrap, leave, messages, and travel also still need an actor-scoped resident/host credential.
The public tunnel must not host residents until both pieces are deployed and verified live.

The development shard generator now gives each new folder its own strong JWT and data-encryption secrets,
private `.env` permissions, stable Compose project identity, node signing key, and public descriptor. Signed
requests now protect registration and private federation operations from alteration, impersonation after
registration, and replay. The three active development cities have been migrated and no longer use the
shared federation token.

The directory now starts closed. A steward admits the safe-to-share `node.json` with an explicit reason
before that node may register. Revocation removes a node from discovery and blocks its signed private calls.
Replacing a key requires revoking the old identity first, then explicitly accepting a new descriptor and
reason. Admit, revoke, and key-recovery decisions are append-only audit rows. The live directory kept its
three existing cities approved after migration and rejected a correctly signed but uninvited node with HTTP
403. This is one directory's local trust policy, not global ownership or permission to exist.

Generated folders now use immutable engine and agent image references rather than neighboring source
folders. Each carries a standard-library `ww.py` for checks, setup, start, one-time city seeding, stop, status,
version updates, full backup, same-identity restore, and directory-local node admission/revocation/recovery.
GitHub now publishes both images under the full commit SHA, and both were pulled back successfully from the
registry. A clean-computer run still needs verification.

The signed local network has also completed a real Portland-to-San-Francisco session handoff and return with
a throwaway actor. Each source retired its session before the destination created one, and the wrong signing
identity could not claim the destination transition. The same trip has not yet been repeated across the new
public addresses or between computers.

An isolated folder under `/tmp` has also run the SHA-tagged engine image with no source-tree mount, seeded
1,315 Portland places, disabled the reset endpoint, kept its agent service stopped, made a mode-`0600` full
backup, restored that backup, and passed its post-restore check. This proves the folder boundary on the
development computer, not yet on a clean second computer.

A second isolated Alderbank folder then ran beside the Portland folder. Their Compose project names, backend
ports, database ports, database passwords, JWT secrets, encryption keys, node IDs, signing keys, networks,
and database volumes were all distinct. Both served seeded worlds concurrently from the same immutable images,
neither mounted a source checkout, and neither started its agent service. The disposable folders, containers,
networks, and volumes were removed after the check.

On 2026-07-19, a fresh project-operated directory and Alderbank node were created outside the monorepo under
`~/worldweaver-nodes`. They now run the immutable engine image `sha-b5a98fe...` with separate secrets, signing keys,
projects, networks, volumes, databases, and loopback-only host ports. The directory admitted Alderbank's
public descriptor with a written reason. Alderbank then registered and pulsed with its own signature, seeded
15 places, and disabled its reset endpoint. No resident container was started.

A new Cloudflare tunnel now serves this test deployment:

- `https://world-weaver.org` — human commons client;
- `https://directory.world-weaver.org` — closed federation directory;
- `https://alderbank.world-weaver.org` — isolated Alderbank API.

Public checks reached the isolated containers, the directory listed only `alderbank-public-1`, and Alderbank
advertised the HTTPS API and client addresses. Exact CORS permits `https://world-weaver.org`; an unrelated
origin received no CORS permission. The connector runs as a user service, and both node folders have local
mode-`0600` backups.

A real person then registered through the public client and made, left, and reclaimed two objects. That
play found a duplicate stoop/loose-object view and a missing human control for physical marks. Both were
fixed through the shared engine contracts and deployed after a fresh backup. The restart preserved the
account, objects, and stoop history. Humans can now read and leave local marks without receiving temporary
session IDs, and active stoop objects appear only on their stoop. GitHub checks and image publication passed
for the deployed commit. Residents remained stopped throughout this public human check.

The folder operator now also supports verified additive-map publication. It inspects artifact, SVG, city,
version, and route hashes; refuses changes to canonical city files or publication while resident agents are
active; makes a full backup; and reloads the backend. The command completed against live Alderbank and kept
its resident service stopped. This removes a source-tree-dependent manual copy from routine map work without
creating a general inhabited-city migration command.

Four host-run residents have now completed a one-hour bounded run against the isolated public Alderbank API.
All four parked cleanly and disappeared from the roster. The run also exposed an operator gap: the root
`dev.py cohort --city` command resolves only repository shards, so the first launch accidentally targeted the
development Alderbank with the same human-facing name. The correct run required invoking the lower-level
cohort script with the isolated folder's URL and resident paths. Folder-local resident preflight, wake,
bounded cohort, interrupt, and cleanup commands are still needed before a steward can operate residents
without source-tree knowledge.

This is a useful single-computer public test, not the completed deployment proof. The human client still uses
Vite's development server, the backups are on the same computer, WSL reboot recovery is not configured, and
no outside computer has completed entry or travel.

## Goal

Put one project-operated WorldWeaver node on the public internet as the first useful member of a network
that other stewards can also join.

The first deployment may use Cloudflare and `world-weaver.org`, but neither is part of the protocol. Another
steward must be able to use a different domain, tunnel, reverse proxy, or directory.

The supported deployment unit is one isolated shard folder. A steward should be able to create that folder,
answer a small set of setup questions, and operate the node from there without understanding the monorepo.
The folder owns its configuration, identity, state, logs, and backups. It runs versioned WorldWeaver images;
it does not mount or build from a neighboring source checkout.

## Build next

1. Keep public residents stopped. Publish the source privacy repair, run its database scrub, and verify the live
   OpenAPI no longer contains the removed state, growth, rest, cleanup, pruning, or reset paths. Then add the
   actor-scoped resident/host capability and wrong-owner tests for bootstrap, leave, messages, and travel.
2. Verify the image publisher and pull the SHA-tagged images on a clean second computer or clean trust domain.
3. Create two folders there and prove distinct ports, projects, credentials, volumes, and signing identities.
4. Replace the Vite development server with a small production client gateway while preserving the same-origin
   shard routes.
5. Put encrypted backups on a different device or service and test restore from that copy.
6. Configure unattended tunnel restart after Windows/WSL reboot and document how to stop public ingress.
7. Finish rate-limit and log-retention policy and write a plain operator runbook.
8. Publish a small node descriptor containing only its ID, hosted city, public URL, protocol version,
   capabilities, and current reachability.
9. Verify entry and travel from outside the host network and then repeat between two computers.
10. Add folder-local resident and cohort commands that always target this folder's API and resident homes,
   refuse ambiguous city labels, and prove cleanup after normal exit and interruption.

## Boundaries

- Public people see the commons client, not a shard-wide observatory.
- Private resident histories, prompts, rest state, and hearth data never appear on public endpoints.
- A directory helps nodes find each other; it does not approve cities or own their state.
- The deployment must not require every steward to use `world-weaver.org` or Cloudflare.
- Public release of a game shard is a separate decision under Major 130.
- A shard folder must not contain source-tree-relative mounts, a network-wide secret, or credentials copied
  from another shard.
- Setup should generate secure defaults and clearly label the few choices a steward must make. Routine use
  should not require editing Compose YAML or handling raw private keys.

## Acceptance criteria

- [ ] A supported public client and API are reachable over HTTPS at a documented URL.
- [ ] A clean computer can create and operate one shard from an isolated folder using versioned images.
- [x] Two folders on one computer can run independently without shared state, secrets, ports, or Compose
  project identity.
- [ ] The operator commands detect unsafe permissions, placeholder secrets, port conflicts, unreachable
  public URLs, and incompatible image or protocol versions before launch.
- [ ] The public surface contains no resident-private or steward-only telemetry.
- [x] The node uses its own identity and credential rather than a network-wide shared secret.
- [ ] CORS, rate limits, backup, recovery, and log-retention rules are explicit.
- [x] The node can publish a signed or otherwise authenticated descriptor to one or more directories.
- [ ] Another node can discover it, and direct configuration remains possible without that directory.
- [ ] Local city and hearth use continue during a directory outage.
- [ ] An external-machine check proves public entry and one cross-node operation.
