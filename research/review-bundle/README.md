# research/review-bundle/ — review rounds for the cold reviewer

This is where each **Mr. Review round** is published, as plain browsable files, so a
structurally-separated reviewer can pull it **cold from GitHub** and re-derive it from raw
evidence — never from the project's own story of itself.

## What's here

Each round is a dated directory: `YYYY-MM-DD-<label>/`. A round typically holds:

- a `REVIEW-PROMPT-*.md` (or `REVIEW-FOLLOWUP-*.md`) — what this round asks,
- a `DRAFT-preregistration-*.md` or pre-registration — metric roles, verdict rule, confound
  controls locked **before** the data exists,
- any lightweight evidence or pointers needed to tell *this* round's story.

Heavy evidence (raw ledgers, recompute scripts) lives in [`../runs/`](../runs/), not here —
the bundle prose points at it so this directory stays light and readable.

## How a round gets here (operator workflow)

1. The round is built locally in the gitignored workspace `review-bundle/` at the repo root.
2. `./research/archive.sh <label>` copies it here as plain files, commits, and pushes,
   then clears the local workspace so the next round starts fresh.
3. The reviewer reads the round cold off GitHub and recomputes from `../runs/`.

## For the reviewer

You start cold on purpose. Re-derive every number by recompute against `../runs/`; never accept
a figure on testimony. The method you hold yourself to is the **standing brief** (dropped into
your session separately — it is not in this repo). Claims and raw evidence only; the project's
interpretations are kept off your desk deliberately.
