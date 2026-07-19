# Publish the first federated WorldWeaver node

## Status

The `world-weaver.org` domain and an earlier Cloudflare tunnel exist, but no supported public node is
currently online. The old proposal for a public observatory is rejected: the public interface should show
places and local participation, not resident timelines or operating data.

The development shard generator now gives each new folder its own strong JWT and data-encryption secrets,
private `.env` permissions, stable Compose project identity, node signing key, and public descriptor. Signed
requests now protect registration and private federation operations from alteration, impersonation after
registration, and replay. Existing development nodes have not yet been migrated, and a public directory
still needs an explicit first-registration and key-recovery policy. Generated folders also still build from
neighboring source folders and lack the supported image, update, and backup workflow described below.

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

1. Turn the current development shard generator into a supported isolated-folder setup flow using versioned
   images and generated secrets.
2. Add one folder-local command surface for setup checks, start, stop, status, update, backup, and restore.
3. Decide which city pack and node will be the first public node.
4. Restore HTTPS ingress for its public client and API.
5. Give the node its own identity and credentials; do not publish the current shared federation token.
6. Configure exact CORS origins, rate limits, backups, log retention, and a plain operator runbook.
7. Publish a small node descriptor containing only its ID, hosted city, public URL, protocol version,
   capabilities, and current reachability.
8. Let the node register with a directory while remaining usable when that directory is unavailable.
9. Verify entry and travel from outside the host network.

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
- [ ] Two folders on one computer can run independently without shared state, secrets, ports, or Compose
  project identity.
- [ ] The operator commands detect unsafe permissions, placeholder secrets, port conflicts, unreachable
  public URLs, and incompatible image or protocol versions before launch.
- [ ] The public surface contains no resident-private or steward-only telemetry.
- [ ] The node uses its own identity and credential rather than a network-wide shared secret.
- [ ] CORS, rate limits, backup, recovery, and log-retention rules are explicit.
- [ ] The node can publish a signed or otherwise authenticated descriptor to one or more directories.
- [ ] Another node can discover it, and direct configuration remains possible without that directory.
- [ ] Local city and hearth use continue during a directory outage.
- [ ] An external-machine check proves public entry and one cross-node operation.
