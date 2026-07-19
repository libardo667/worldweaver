---
title: Operate a local node
sidebar_position: 3
---

# Operate a local node

This guide covers the supported single-computer development topology. Public federation between independent
computers is not production-ready yet.

There are two command surfaces. The repository-root commands below operate the development topology. A node
created with `python dev.py new-shard` carries its own `ww.py` and is operated entirely from that folder.

## Start one city

```bash
python dev.py weave-up --city ww_sfo
```

Residents remain stopped. Add `--agents` only when you deliberately want the shard's resident service to
run.

## Start every local city

```bash
python dev.py weave-up --city ww_sfo --all-cities --no-client
```

The local harness advertises `host.docker.internal` URLs so containers on this computer can reach one
another. Those addresses do not work from another steward's computer.

## Check readiness

```bash
python dev.py weave-status --city ww_sfo --strict
python dev.py weave-status --city ww_sfo --strict --require-travel
```

The second command also proves at least one advertised destination is directly reachable.

## Inspect logs

```bash
python dev.py weave-logs --city ww_sfo
python dev.py weave-logs --city ww_sfo --follow
python dev.py weave-logs --city ww_sfo --target world
```

## Stop the node

```bash
python dev.py weave-down --city ww_sfo
```

## Operate an isolated folder

From inside a generated node folder:

```bash
python ww.py setup
python ww.py check
python ww.py start
python ww.py seed       # one time, for a new city
python ww.py status
python ww.py backup
python ww.py stop
```

`start` leaves residents stopped. `start --agents` wakes them deliberately. `seed` uses the copied city pack
and then disables the development seed/reset endpoint. `update` accepts versioned engine and agent image
references. `restore BACKUP --yes` restores only a backup with the same node identity.

On a generated federation directory, receive a city's public `node.json` through a channel where you can
confirm who sent it, then run:

```bash
python ww.py node admit ../city-node/node.json --reason "Known steward joining the commons"
python ww.py node list
python ww.py node history city-node-id
```

To block a node, use `node revoke NODE_ID --reason "..."`. To replace a compromised or lost node key, revoke
the old identity first and then use `node recover NEW_NODE_JSON --reason "..."`. These commands never require
the other node's private key.

## Prepare public settings

After a city is seeded and its reset endpoint is closed, set its reviewed public addresses from inside the
folder:

```bash
python ww.py public-config \
  --api-url https://city.example.org \
  --client-url https://play.example.org \
  --federation-url https://directory.example.org \
  --cors-origin https://play.example.org \
  --ingress-provider cloudflare
```

Run the same command on a directory without `--federation-url`. This writes local configuration and restarts
an already-running backend. It does not create DNS, start a tunnel, or expose a port. Cloudflare mode also
requires the generated loopback-only backend binding so traffic cannot bypass the tunnel.

The folder contains private credentials, its signing key, database, city data, resident files, and backups.
Do not commit or casually copy it. A backup contains all of that private state and is created mode `0600` on
systems that support Unix permissions.

## Public-node limitation

A real steward network still needs:

- stable HTTPS ingress for each node;
- discovery that does not make one directory the owner of the network;
- resident-host authorization and recovery rules.

The project test deployment currently uses `https://world-weaver.org`, with directory and Alderbank APIs at
`https://directory.world-weaver.org` and `https://alderbank.world-weaver.org`. It is a single-computer test;
do not use it as evidence that two independent hosts work yet.

`world-weaver.org` may become an early directory or node, but the protocol must allow other directories and
direct peer discovery. A resident, hearth, city pack, or node is not owned by that directory.
