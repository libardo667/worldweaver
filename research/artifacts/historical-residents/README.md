# historical-residents — hand-authored resident souls (ARTIFACT, not runtime)

These are the **hand-authored-era** resident souls (`darnell`, `elias`, `fei_fei`, `ingrid`, `kwame`,
`meiying`, `ray`, `rosario`, `sun_li`, `zhang`, + `_template`). They were moved here out of `ww_agent/`
because they are **data artifacts, not runtime code** — `ww_agent/` is the resident daemon; these souls
don't belong in it.

## Why they matter (load-bearing twice)
Unlike the live doula-seeded cast (which has **no** authored `Voice:` field), each of these carries an
authored `Voice:` block — a deliberately distinct register per soul. That makes them:
1. The **peer-register known-positive** — the only data we have built to differ at peer-register
   granularity, used to test whether a metric/instrument can resolve peer-level voice
   (`ww_agent/scripts/peer_register_check.py`).
2. The **only authored-voice baseline** that could re-validate a future measurement attempt.

A machine-independent snapshot of just the `Voice:` lines also lives at
`ww_agent/scripts/fixtures/peer_register_known_positive.jsonl` (so the check survives even this move).

## Not the live cast
The live residents run inside each shard's own `residents/` dir (gitignored, with secrets in `.env`).
These historical souls are reference artifacts only — they are not booted by any running shard.
