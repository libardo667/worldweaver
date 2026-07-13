# research/ — public, cold-verifiable run records & artifacts

This tree exists so the review process can **verify instead of trust**. For most of the voice-register
arc, Mr. Review had to accept run numbers as `[OPERATOR-OBSERVED]` because the data lived only in
gitignored `shards/` on one machine. That's the gap this box closes: run data, the exact commands that
produced it, and recompute scripts live here, tracked and public, so any reviewer can re-derive the
result.

## THE ONE RULE: no secrets, ever
This is a **public** repo. `shards/*/.env` carry live keys (OpenRouter, JWT, encryption, Resend,
federation token, DB password) and **stay gitignored** — we never un-ignore `shards/`. This box is
populated by **deliberately copying secret-free data in** (ledgers, identities, manifests, analysis),
never by tracking a secret-bearing tree. Nothing with a key shape goes here. (`research/**/.env` is also
explicitly gitignored as a backstop.)

## Layout
```
artifacts/
  historical-residents/   the hand-authored resident souls (Voice: blocks), moved out of ww_agent/
                          because they're DATA, not runtime. The peer-register known-positive baseline.
probes/                   research/diagnostic instrumentation (pen-swap harness, register probes,
                          cost curves), moved out of ww_agent/scripts/ because they MEASURE the
                          runtime rather than operate it (Major 83). See probes/README.md.
runs/<YYYY-MM-DD-name>/
  FINDINGS.md             the claim/result, the cast, the method, the re-open trigger — the durable record
  cast/<soul>/IDENTITY.md who was in the run
  ledgers/<arm>/*.jsonl.gz the raw evidence (gzipped), per resident
  analysis/*.py           recompute scripts — run them over the ledgers to cold-verify FINDINGS
```

## Convention (the regimented part)
Each run records, deliberately and next to each other: the **exact commands + config** that produced it
(no secrets), the **raw ledgers**, and a **recompute script** that reproduces the headline numbers. A
result you can't recompute from this box isn't banked — it's a story.

## Retention
Ledgers are gzipped. A 2-arm 15-soul run is ~2 MB; large/long runs should be sampled or moved to git-LFS
rather than committed raw, so a public repo doesn't bloat.

## Relationship to the cognition tree (local)
`../memory-management/worldweaver-cognition/` is **local** — it holds the *method*: the standing brief,
falsifier rules, desk-packets, the "how we review." This `research/` box is **public** — it holds the
*what we found*: the run data and the recompute path. Method stays local and un-marinating; evidence goes
public and verifiable.
