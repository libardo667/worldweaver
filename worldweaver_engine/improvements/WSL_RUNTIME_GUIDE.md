# WSL Runtime Guide

This guide moves WorldWeaver's live runtime off Windows bind-mounted paths and into
WSL, where Docker, SQLite, and later Postgres will behave much more predictably.

The immediate goal is:

- run the workspace from a Linux filesystem inside WSL
- stop using `C:\...` bind-mounted shard databases as the live runtime path
- keep the current shard-first architecture intact while changing the host environment

This guide assumes:

- Windows 11
- WSL2
- Docker Desktop with WSL integration enabled
- Ubuntu as the WSL distro

## Why move to WSL first

Today the shard databases are SQLite files on Windows-hosted bind mounts used by
Linux containers. That combination is a known weak spot for WAL-mode SQLite and is
the most likely cause of the recurring SFO corruption.

Moving the runtime into WSL gives you:

- Linux filesystem semantics for live database files
- more predictable Docker volume and bind-mount behavior
- cleaner path handling for backend and agent containers
- a much better base for the later Postgres migration

## What "running in WSL" means

Do not run the live workspace from `/mnt/c/...`.

Instead:

- keep a copy of the repo inside your WSL home or another Linux-native path
- run Docker Compose from the WSL shell
- keep live shard DBs and runtime state on the WSL filesystem

Good:

```bash
~/src/worldweaver
```

Bad:

```bash
/mnt/c/Users/levib/PythonProjects/worldweaver
```

## Phase 1 - Prepare WSL

### 1. Install Ubuntu in WSL

In PowerShell:

```powershell
wsl --install -d Ubuntu
```

Reboot if prompted, then complete Ubuntu setup.

### 2. Update Ubuntu packages

Inside Ubuntu:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y git curl build-essential python3 python3-venv python3-pip
```

### 3. Enable Docker Desktop WSL integration

In Docker Desktop:

- Settings
- Resources
- WSL Integration
- enable integration for your Ubuntu distro

Then verify inside WSL:

```bash
docker version
docker compose version
```

If those fail inside WSL, do not continue until Docker works there.

## Phase 2 - Move the workspace

### 4. Copy the repo into WSL-native storage

Inside Ubuntu:

```bash
mkdir -p ~/src
cp -a /mnt/c/Users/levib/PythonProjects/worldweaver ~/src/worldweaver
cd ~/src/worldweaver
```

If you prefer a fresh clone instead of a copy:

```bash
mkdir -p ~/src
cd ~/src
git clone <your-root-repo-url> worldweaver
cd worldweaver
```

### 5. Carry over ignored local runtime config deliberately

Because shard `.env` files are ignored, a fresh clone will not have your live secrets.

From Windows into WSL, copy the shard env files you actually use:

- `shards/ww_world/.env`
- `shards/ww_sfo/.env`
- `shards/ww_pdx/.env`

If you used `cp -a` on the whole tree, these should already be present. Still verify them.

### 6. Do not copy corrupted live SQLite DBs forward blindly

For SFO specifically, if the Windows-side DB is already malformed, do not treat it as
the canonical thing to move.

Before using a copied SQLite DB in WSL, verify it:

```bash
python3 - <<'PY'
import sqlite3
from pathlib import Path
for p in Path("shards/ww_sfo/db").glob("*.db*"):
    try:
        conn = sqlite3.connect(p)
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        print(p.name, cur.fetchone()[0])
        conn.close()
    except Exception as e:
        print(p.name, "ERROR", e)
PY
```

If the live DB is bad, restore from the newest clean backup before continuing.

## Phase 3 - Start the stack from WSL

### 7. Shut down the Windows-side runtime first

From Windows or Docker Desktop, stop any old containers running from the Windows path.

At minimum, stop:

- `ww_world`
- `ww_sfo`
- `ww_pdx`
- `worldweaver_engine` client wrapper

This matters because running Windows-side and WSL-side copies of the same shard at once
creates confusion and can corrupt expectations about ports, DB files, and state.

### 8. Start the shard-first stack from WSL

Inside WSL from `~/src/worldweaver`:

```bash
cd shards/ww_world
docker compose up -d --build backend

cd ../ww_sfo
docker compose up -d --build backend agent

cd ../ww_pdx
docker compose up -d --build backend agent

cd ../../worldweaver_engine
docker compose up -d --build client
```

### 9. Verify the runtime from WSL

```bash
docker ps
curl http://localhost:9000/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:5173
```

And:

```bash
curl http://localhost:9000/api/federation/shards
```

Verify shard URLs and health state before using the public site.

## Phase 4 - Make WSL the canonical local environment

### 10. Do all live runtime operations from WSL

From this point on, use WSL for:

- `docker compose`
- shard backend/agent startup
- DB inspection
- Alembic migrations
- backup/restore commands

You can still use VS Code on Windows with the WSL extension to edit the files.

### 11. Keep live databases off `/mnt/c`

Even after the move, do not relocate live shard DBs back to a Windows-mounted path.

Live SQLite DBs should remain under the WSL workspace, for example:

```bash
~/src/worldweaver/shards/ww_sfo/db/worldweaver_san_francisco.db
```

## Operational notes

### Backups

If you are still on SQLite, do not treat raw file copies of live WAL databases as safe backups.

Prefer:

- stopping the backend first, or
- using SQLite backup commands from inside the environment that owns the DB

### VS Code

Use the WSL extension and open the repo from WSL:

- `code .` from inside `~/src/worldweaver`

This gives you Windows UI with Linux filesystem/runtime semantics.

### Public URLs

Moving into WSL does not by itself change:

- Cloudflare config
- public shard paths
- `WW_PUBLIC_URL`

It changes the local runtime host environment only.

## Suggested migration sequence for this workspace

1. Move the unified workspace into WSL.
2. Restore or verify clean SQLite shard DBs there.
3. Run the full shard-first stack from WSL only.
4. Confirm the public site works against the WSL-hosted origin.
5. Then execute the Postgres migration as the next major.

## Exit criteria

You are "moved to WSL" when all of the following are true:

- the live workspace path is Linux-native, not `/mnt/c/...`
- shard backends and agents are started from WSL
- live shard DBs live on the WSL filesystem
- Docker Compose operations are run from WSL
- the Windows copy is no longer the active runtime source of truth
