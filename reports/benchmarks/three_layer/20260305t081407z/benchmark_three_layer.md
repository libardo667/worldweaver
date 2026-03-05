# 3-Layer Latency Benchmark

- Timestamp UTC: `2026-03-05T08:32:38.758788+00:00`
- Commit: `42d4040`
- Model: `openai/gpt-4o-mini`
- Turns Requested (per mode): `20`
- Storylet Count: `5`

## Modes

- Baseline: `strict_off` (strict=False)
- Candidate: `strict_on` (strict=True)

## Bootstrap

- Baseline: `22618.671 ms`
- Candidate: `43004.199 ms`
- Delta: `20385.528 ms` (`90.127%`)

## /next Turn Latency

- Avg delta: `1339.273 ms` (`5.323%`)
- P50 delta: `-2677.749 ms` (`-57.057%`)
- P95 delta: `1477.088 ms` (`2.72%`)

## Throughput

- Baseline turns/sec: `0.0397`
- Candidate turns/sec: `0.0377`
