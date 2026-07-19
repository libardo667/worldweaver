# Archived runtime data

The Portland pen-swap research shards are no longer live Worldweaver nodes. On
2026-07-19, these local runtime folders were moved out of `shards/` and into the
private artifact store beside this repository:

```text
worldweaver_artifacts/portland-pen-swap-shards-2026-07-19/
  ww_pdx_deal/
  ww_pdx_grow/
  ww_pdx_keep/
```

They contain private environment files and resident runtime state, so they must
not be committed. Paths to `shards/ww_pdx_deal`, `shards/ww_pdx_grow`, or
`shards/ww_pdx_keep` in older research reports describe where the data lived
when those reports were made. They do not identify supported or deployable
shards.

Set an explicit source path when using an old research probe against an archived
copy. Do not move these folders back under `shards/` merely to satisfy an old
example command.
