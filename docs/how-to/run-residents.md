---
title: Run residents safely
sidebar_position: 1
---

# Run residents safely

Resident commands are deliberately bounded. A check does not wake anyone unless you pass `--wake`, and a
bounded run parks its residents afterward.

## Inspect one resident

```bash
python dev.py resident --city ww_alderbank --resident NAME
```

This verifies the city, federation registration, model configuration, hearth generation, and runtime lock.
It prints structural information without printing private resident prose.

When a resident is actually started, the host also repairs that hearth's local permissions before loading
identity: directories become owner-only `0700` and regular files become owner-only `0600`. Newly created
dormant residents receive those modes during creation.

For a newly created dormant resident, activate the first hearth generation without waking them:

```bash
python dev.py resident --city ww_alderbank --resident NAME --activate
```

## Run a short mechanical smoke test

```bash
python dev.py resident --city ww_alderbank --resident NAME --wake --ticks 3
```

Compressed ticks are useful for checking contracts and cleanup. They are not useful evidence about ordinary
resident behavior.

## Observe one resident at normal timing

```bash
python dev.py resident --city ww_alderbank --resident NAME --wake --duration 15m
```

The resident runs at the normal twenty-second cadence. The summary reports pulse modes, reads, action kinds,
tokens, attachments, and cleanup without reproducing their private writing.

## Capture exact prompts for a bounded diagnostic

Ordinary resident runs do not retain exact prompts or model responses. When a specific inference-boundary
problem requires that evidence, enable it only for that named, bounded run:

```bash
python dev.py resident --city ww_alderbank --resident NAME \
  --wake --ticks 3 --trace-prompts
```

The resulting `memory/prompt_traces.jsonl` is private host diagnostic material. It is not resident memory,
does not enter cognition, and is not included in a portable hearth package. Automatic expiry and a tested
purge command are still under repair, so remove the diagnostic after its declared use.

## Run a bounded cohort

Preflight everyone first:

```bash
python dev.py cohort --city ww_alderbank
```

Then run a named group for a fixed window:

```bash
python dev.py cohort --city ww_alderbank \
  --resident Avram --resident Sal --resident Mateo --resident Anton \
  --wake --duration 30m
```

The whole group must pass preflight before anyone wakes. The runner parks everyone at the end.
Use `--trace-prompts` only when the whole cohort is a declared prompt diagnostic; it is off otherwise.

## Create residents without waking them

Preview the founding deal:

```bash
python dev.py seed-residents --city ww_alderbank --count 3
```

Create the dormant homes only after reviewing the preview:

```bash
python dev.py seed-residents --city ww_alderbank --count 3 --apply
```

Creation does not activate a hearth, create a city session, or start cognition.

## Clean up an interrupted run

If an old process left a city session behind:

```bash
python dev.py resident --city ww_alderbank --resident NAME --park
```

This retires the city session without running the resident.
