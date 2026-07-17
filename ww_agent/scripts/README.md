# scripts/ — operational tooling

Operational scripts for running and maintaining residents. Research/diagnostic probes
(register checks, pen-swap harness, cost curves, …) moved to
[`../../research/probes/`](../../research/probes/README.md) in Major 83 slice 3 — this
directory is only for tools you run to *operate* the system, not to measure it.

- `live_boot.py` — boot a resident against a live shard.
- `hearth_manifest.py` — inspect one resident's stable, host-independent hearth identity; initialization
  requires the explicit `--initialize` flag.
- `hearth_package.py` — inventory one resident home, export an allowlisted deterministic `.wwhearth`
  package, or verify and atomically import one into a new path. Unknown paths and symlinks fail closed.
- `hearth_activation.py` — inspect a hearth's runtime generation, explicitly activate a new manifest, or
  retire a stopped source and activate its already imported successor.
- `pulse_familiars.py` — write a keeper whisper to a configured group of resident homes.
- `familiar.py` — compatibility command for running one resident at its hearth, including offline
  smoke mode and portrait `state.json`. It delegates identity, core, travel, and world lifecycle to
  the same `src.resident.Resident` host as the normal daemon; it is not a second agent runtime.
- `give.py` — copy a file into an explicitly enabled resident gift source. The file waits in the
  resident's workshop until they elect to inspect it; `--say` is a separate keeper whisper and rouse.
- `backfill_resident_actor_ids.py` — one-shot ops backfill of durable actor ids from the
  historical-resident archive.

(`_*.py` / `_*.sh` files are gitignored local scratch. The loop-era "planned scripts" list
that used to live here described tools that were never built — removed with Major 83.)
