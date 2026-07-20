---
title: Command reference
sidebar_position: 2
---

# Command reference

Run commands from the repository root.

## Setup and validation

```bash
python dev.py install
python dev.py test
python dev.py test engine
python dev.py test agent
python dev.py check
```

## Local shards

```bash
python dev.py weave-up --city CITY
python dev.py weave-up --city CITY --no-client
python dev.py weave-up --city CITY --agents
python dev.py weave-status --city CITY --strict
python dev.py weave-status --city CITY --strict --require-travel
python dev.py weave-logs --city CITY --follow
python dev.py weave-down --city CITY
python dev.py new-shard CITY_ID [options]
```

Inside a generated, source-independent node folder:

```bash
python ww.py setup
python ww.py check
python ww.py start [--agents]
python ww.py seed
python ww.py status
python ww.py update [--engine-image IMAGE] [--agent-image IMAGE]
python ww.py map inspect BUILT_CITY_PACK
python ww.py map publish BUILT_CITY_PACK --yes
python ww.py resident-authority list
python ww.py resident-authority admit RESIDENT_IDENTITY.json --reason "REVIEW"
python ww.py backup [--output DIRECTORY]
python ww.py restore BACKUP --yes
python ww.py stop
```

## Clients

```bash
python dev.py client
python dev.py client-public
python dev.py client-legacy
```

`client` and `client-public` both start the supported place-centered client on port 5174. `weave-up` starts
the same client and points it at the selected city automatically. `client-legacy` is the retired combined
interface on port 5173; use it only for local migration or debugging while its remaining useful functions
are separated.

## Residents

```bash
python dev.py resident --city CITY --resident NAME
python dev.py resident --city CITY --resident NAME --activate
python dev.py resident --city CITY --resident NAME --wake --ticks 3
python dev.py resident --city CITY --resident NAME --wake --duration 15m
python dev.py resident --city CITY --resident NAME --wake --duration 15m --reach-continuations 1
python dev.py resident --city CITY --resident NAME --park
python dev.py cohort --city CITY
python dev.py cohort --city CITY --wake --duration 30m
python dev.py cohort --city CITY --wake --duration 30m --reach-continuations 2
python dev.py seed-residents --city CITY --count 3
python dev.py seed-residents --city CITY --count 3 --apply
```

`--reach-continuations` requests a per-pulse private-read limit from zero through eight. The resident
host may lower it with `WW_REACH_CONTINUATION_MAX`; the default host maximum is two.

## Steward and research tools

```bash
python dev.py space-policy --city CITY --location "Exact Place" --controller-resident NAME
python dev.py resident-authority --city CITY list
python dev.py resident-authority --city CITY admit RESIDENT_IDENTITY.json --reason "REVIEW"
python dev.py conversation-health --city CITY --since-hours 24
python dev.py run PATH [args...]
```

Use `python dev.py COMMAND --help` for the complete option list.
