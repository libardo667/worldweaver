---
title: Operate a local node
sidebar_position: 3
---

# Operate a local node

This guide covers the supported single-computer development topology. Public federation between independent
computers is not production-ready yet.

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

## Public-node limitation

A real steward network still needs:

- stable HTTPS ingress for each node;
- independently signed node identities instead of one shared federation token;
- authenticated travel handoffs between nodes;
- discovery that does not make one directory the owner of the network;
- resident-host authorization and recovery rules.

`world-weaver.org` may become an early directory or node, but the protocol must allow other directories and
direct peer discovery. A resident, hearth, city pack, or node is not owned by that directory.
