# WorldWeaver work items

`prune/` is the planning workspace. It is not the technical manual.

- [`VISION.md`](VISION.md) states the product and architectural direction.
- [`ROADMAP.md`](ROADMAP.md) gives the current build order.
- `majors/` contains unfinished architectural or product work.
- `minors/` contains unfinished bounded implementation work.
- `research/` contains experiments, measurements, and ethics gates that are not part of the build queue.
- `publication/` contains writing, exhibition, and outreach work.
- `history/` contains completed, rejected, superseded, and dated records.

## Active architecture and product work

| Area | Work items |
| --- | --- |
| Public deployment and federation | 18, 20, 37, 127 |
| Human participation and correspondence | 39, 43, 71 |
| Resident cognition and identity | 51, 56, 58, 60, 65, 67 |
| Operations and cleanup | 70, 83 |
| Stoops, City Studio, and game town | 125, 126, 130 |

## Active bounded work

| Minor | Purpose |
| --- | --- |
| 31 | Local topology command polish |
| 32 | Ephemeral sublocation lifecycle |
| 33 | Environmental scene activity without fake residents |
| 122 | Bound external network access without broad resident profiling |

## Rules

1. New runtime work is created only in WorldWeaver. `the-stable` is source history.
2. An item moves to history when it is complete, rejected, or superseded.
3. Experiments do not remain in the architecture queue while waiting for a live run.
4. A work item may explain a tradeoff, but current operating instructions belong under `docs/`.
5. Check code and tests before trusting a file's old status paragraph.
