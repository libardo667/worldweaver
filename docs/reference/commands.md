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
python dev.py demo-init
python dev.py weave-up --city CITY
python dev.py weave-up --city CITY --no-client
python dev.py weave-up --city CITY --agents
python dev.py weave-status --city CITY --strict
python dev.py weave-status --city CITY --strict --require-travel
python dev.py weave-logs --city CITY --follow
python dev.py weave-down --city CITY
python dev.py new-shard CITY_ID [options]
```

`demo-init` creates the ignored local secrets, identities, and Alderbank pack needed by the tutorial. It does
not start Docker or residents, and it refuses to replace unmarked existing state.

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
python dev.py resident --city CITY --resident NAME --park
python dev.py cohort --city CITY
python dev.py cohort --city CITY --wake --duration 30m
python dev.py create-resident --city CITY --name "DISPLAY NAME"
python dev.py create-resident --city CITY --name "DISPLAY NAME" --apply
```

`--ticks` counts local polls, not model calls. The reference loop activates when its slow baseline or a chosen
return is due, eligible local speech arrives, or an explicit wake is supplied. A recent activation time
survives a core rebuild. Each activation permits at most one elective read.
Creation is dry-run-first and makes one dormant, empty-ledger resident at a time. The deprecated
`seed-residents` command can inspect its old batch plan but can no longer create model-written residents.

## Steward and research tools

```bash
python dev.py gym
python dev.py space-policy --city CITY --location "Exact Place" --controller-resident NAME
python dev.py resident-authority --city CITY list
python dev.py resident-authority --city CITY admit RESIDENT_IDENTITY.json --reason "REVIEW"
python dev.py conversation-health --city CITY --since-hours 24
python dev.py run PATH [args...]
```

`gym` runs the first deterministic production-rule episode without a model or live shard. It prints a factual
timeline and writes a self-contained visual report under `.runs/gym/`.

Use `python dev.py COMMAND --help` for the complete option list.
