# Topology runtime polish after Major 30

## Problem

Major 30's highest-value runtime gap is closed: `weave-up` now waits for health,
auto-seeds empty city shards, registers them with the federation root, and
`weave-status` makes shard readiness visible.

What remains is useful, but it is no longer a major-blocker class of work:

- naming and flag consistency still reflect the incremental path (`--all-cities`
  instead of a clearer topology-wide surface such as `--all-shards`)
- `SHARD_DEPTH` is only partially honored and not yet treated as a documented
  operator contract
- city agents are still started through the same compose project boot path rather
  than a clearly staged backend-then-agent tier
- there is no stricter "ready means healthy + seeded + registered" mode for CI
  or operator confidence checks
- topology reporting is useful but still thin on inclusion/exclusion reasons and
  tier summaries

These are worth finishing, but they are now developer-experience polish rather
than a blocker to Postgres-backed multi-city operation.

## Proposed Solution

Do a narrow cleanup pass on the shard-first runtime without reopening Major 30 as
the next primary architecture track.

- normalize the public flag surface:
  - decide whether `--all-cities` stays or becomes `--all-shards`
  - document focused mode vs fan-out mode explicitly
- harden topology metadata:
  - document `SHARD_DEPTH`
  - add validation warnings for shards missing explicit depth once that contract
    matters
- improve startup/shutdown staging:
  - if needed, split compose operations so agents are brought up only after local
    backend readiness instead of piggybacking on the same city compose boot
- add a strict readiness contract:
  - `weave-status --strict`
  - or `weave-up --strict-ready`
  - require health + seeded state + federation registration for success
- improve topology diagnostics:
  - show startup/shutdown tiers
  - explain what fan-out included
  - explain what focused mode intentionally left running

## Files Affected

- `worldweaver_engine/scripts/dev.py`
- `worldweaver_engine/README.md`
- `worldweaver_engine/FEDERATION.md`
- `shards/*/.env`

## Acceptance Criteria

- [ ] The runtime flag surface uses one clear fan-out name and one clear focused name
- [ ] `SHARD_DEPTH` is documented and validated where topology ordering depends on it
- [ ] Operators can run a strict readiness check that fails when a shard is unhealthy, unseeded, or unregistered
- [ ] `weave-status` reports tier ordering and inclusion/exclusion reasons in human-readable form
- [ ] If agent startup remains separate from backend readiness, that behavior is explicit in docs and output
