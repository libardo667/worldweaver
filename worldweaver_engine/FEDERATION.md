# Federation development notes

The current federation code supports discovery and recoverable city-to-city handoff between cooperating
nodes. It is ready for local development, not an open internet deployment.

For the design boundary, read [Federation without ownership](../docs/explanation/federation-without-ownership.md).
For current operating commands, read [Operate a local node](../docs/how-to/operate-a-local-node.md).

## Local topology

The root development command starts the directory node and one or more city nodes:

```bash
python dev.py weave-up --city ww_alderbank --no-client
python dev.py weave-status --city ww_alderbank --strict
python dev.py weave-status --city ww_alderbank --strict --require-travel
python dev.py weave-down --city ww_alderbank
```

Each node has its own database, shard ID, city pack, and `.env`. A city pack is portable place data; a
shard ID identifies one running node that hosts it. Multiple independent nodes may host the same pack.

The directory reports recently registered nodes and advertised travel routes. It does not own those nodes,
their cities, or visiting residents.

## Current trust limit

Controlled nodes share `FEDERATION_TOKEN`. That proves possession of one deployment secret, not an
independent node identity. A public network still needs:

- a key pair and stable identity for every node;
- signed registration and travel requests;
- HTTPS ingress and address rotation;
- revocation and recovery rules;
- discovery that can use more than one directory.

Do not describe the current shared-token deployment as decentralized or secure against a hostile node.

## Public-address development

Local nodes advertise `host.docker.internal` addresses so sibling containers can reach them. Another
computer cannot use those addresses. A real node needs a stable public HTTPS URL through a reverse proxy or
tunnel, plus the unfinished signed-node trust above. `world-weaver.org` is reserved for this work but is not
currently the production root of a secure federation.
