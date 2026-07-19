# Publish the first federated WorldWeaver node

## Status

The `world-weaver.org` domain and an earlier Cloudflare tunnel exist, but no supported public node is
currently online. The old proposal for a public observatory is rejected: the public interface should show
places and local participation, not resident timelines or operating data.

## Goal

Put one project-operated WorldWeaver node on the public internet as the first useful member of a network
that other stewards can also join.

The first deployment may use Cloudflare and `world-weaver.org`, but neither is part of the protocol. Another
steward must be able to use a different domain, tunnel, reverse proxy, or directory.

## Build next

1. Decide which city pack and node will be the first public node.
2. Restore HTTPS ingress for its public client and API.
3. Give the node its own identity and credentials; do not publish the current shared federation token.
4. Configure exact CORS origins, rate limits, backups, log retention, and a plain operator runbook.
5. Publish a small node descriptor containing only its ID, hosted city, public URL, protocol version,
   capabilities, and current reachability.
6. Let the node register with a directory while remaining usable when that directory is unavailable.
7. Verify entry and travel from outside the host network.

## Boundaries

- Public people see the commons client, not a shard-wide observatory.
- Private resident histories, prompts, rest state, and hearth data never appear on public endpoints.
- A directory helps nodes find each other; it does not approve cities or own their state.
- The deployment must not require every steward to use `world-weaver.org` or Cloudflare.
- Public release of a game shard is a separate decision under Major 130.

## Acceptance criteria

- [ ] A supported public client and API are reachable over HTTPS at a documented URL.
- [ ] The public surface contains no resident-private or steward-only telemetry.
- [ ] The node uses its own identity and credential rather than a network-wide shared secret.
- [ ] CORS, rate limits, backup, recovery, and log-retention rules are explicit.
- [ ] The node can publish a signed or otherwise authenticated descriptor to one or more directories.
- [ ] Another node can discover it, and direct configuration remains possible without that directory.
- [ ] Local city and hearth use continue during a directory outage.
- [ ] An external-machine check proves public entry and one cross-node operation.
