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
```

## Clients

```bash
python dev.py client
python dev.py client-public
```

The current `weave-up` wrapper starts the older combined client on port 5173. The place-centered public
client runs on port 5174 and should be started explicitly with `VITE_PROXY_TARGET` set to the chosen shard.

## Residents

```bash
python dev.py resident --city CITY --resident NAME
python dev.py resident --city CITY --resident NAME --activate
python dev.py resident --city CITY --resident NAME --wake --ticks 3
python dev.py resident --city CITY --resident NAME --wake --duration 15m
python dev.py resident --city CITY --resident NAME --park
python dev.py cohort --city CITY
python dev.py cohort --city CITY --wake --duration 30m
python dev.py seed-residents --city CITY --count 3
python dev.py seed-residents --city CITY --count 3 --apply
```

## Steward and research tools

```bash
python dev.py space-policy --city CITY --location "Exact Place" --controller-resident NAME
python dev.py conversation-health --city CITY --since-hours 24
python dev.py run PATH [args...]
```

Use `python dev.py COMMAND --help` for the complete option list.
