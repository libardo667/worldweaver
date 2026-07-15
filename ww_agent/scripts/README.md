# scripts/ — operational tooling

Operational scripts for running and maintaining residents. Research/diagnostic probes
(register checks, pen-swap harness, cost curves, …) moved to
[`../../research/probes/`](../../research/probes/README.md) in Major 83 slice 3 — this
directory is only for tools you run to *operate* the system, not to measure it.

- `live_boot.py` — boot a resident against a live shard.
- `pulse_familiars.py` — pulse the local `familiar/` residents.
- `familiar.py` — standalone familiar entry point (LocalWorld/FileScope pilot mode; any retained
  behavior must be reconciled directly into WorldWeaver).
- `backfill_resident_actor_ids.py` — one-shot ops backfill of durable actor ids from the
  historical-resident archive.

(`_*.py` / `_*.sh` files are gitignored local scratch. The loop-era "planned scripts" list
that used to live here described tools that were never built — removed with Major 83.)
