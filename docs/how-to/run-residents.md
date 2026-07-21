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

In a city, the resident waits up to twenty seconds for new exact-place speech and otherwise refreshes its place
on that normal timer. A refresh calls the model only on first start, new local speech, an explicit wake signal,
or the slow five-minute baseline. The summary separates observations from activations
and reports reads, action outcomes, attachments, and cleanup without reproducing private writing.

When a bounded run stops and a later run rebuilds the reference core, the private checkpoint restores a
bounded list of exact confirmed-action receipts. This preserves simple bookkeeping such as a recent mark's
place and trace ID. It does not restore a hidden model conversation or copy action prose into the next prompt.

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

## Create residents without waking them

Choose one name and preview the exact home that would be created:

```bash
python dev.py create-resident --city ww_alderbank --name "Robin Vale"
```

Create that dormant home only after reviewing the preview:

```bash
python dev.py create-resident --city ww_alderbank --name "Robin Vale" --apply
```

Creation writes the chosen name and structural hearth files. It does not call a model, write a biography or
job, start the private ledger, activate the hearth, create a city session, or start cognition. It does create
a self-signed public identity card and a private key sealed for this hearth host. Review and admit that public
card to the selected city before activation:

```bash
python dev.py resident-authority --city ww_alderbank admit \
  shards/ww_alderbank/residents/robin_vale/identity/resident_identity.json \
  --reason "Reviewed local resident creation"
python dev.py resident --city ww_alderbank --resident robin_vale --activate
```

Admission trusts one public actor/key binding; it does not give the city the resident's private key or hearth.

## Clean up an interrupted run

If an old process left a city session behind:

```bash
python dev.py resident --city ww_alderbank --resident NAME --park
```

This retires the city session without running the resident.
