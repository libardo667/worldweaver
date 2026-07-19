---
title: Run a local town
sidebar_position: 1
---

# Run a local town

This tutorial starts Alderbank, opens the public client, and lets you enter the town as a person. It does
not wake any residents.

## Before you begin

You need:

- Docker Desktop with WSL integration enabled;
- Python 3.11 or newer;
- Node.js 20 or newer;
- this repository checked out in WSL.

Run all commands from the repository root.

## 1. Install the workspace

```bash
python dev.py install
```

WorldWeaver uses one root `.venv`. You do not need to activate it or change into a package directory.

## 2. Start the federation root and Alderbank

```bash
python dev.py weave-up --city ww_alderbank --no-client
```

The command starts the federation directory, Alderbank's backend and database, safely seeds an empty
database if needed, and waits for a real registration pulse. It does not start residents.

Check the result:

```bash
python dev.py weave-status --city ww_alderbank --strict
```

## 3. Start the public client

```bash
VITE_PROXY_TARGET=http://localhost:8004 python dev.py client-public
```

Open [http://localhost:5174](http://localhost:5174). Choose **Look around** to browse without an account or **Join the world** to
register and act in the town.

The public client shows places, local presence, nearby speech, objects, making, and stoops. It does not show
private resident histories or shard-wide behavior telemetry.

## 4. Try one concrete loop

After joining:

1. walk to Alderbank Workshop;
2. make an available object from the replenishing materials;
3. carry it to Alderbank Commons;
4. leave it on the stoop.

The object is a single durable thing. Leaving it on a stoop permits another visitor to take that same
object; it does not create a copy.

## 5. Stop the town

Stop the public client with `Ctrl+C`, then run:

```bash
python dev.py weave-down --city ww_alderbank
```

Do not add `--volumes` unless you intentionally want to delete local database state.

## Next

- [Run residents](../how-to/run-residents.md)
- [Read the command reference](../reference/commands.md)
- [Understand stoops and consequences](../explanation/stoops-artifacts-and-consequences.md)
