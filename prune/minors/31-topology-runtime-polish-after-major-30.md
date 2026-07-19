# Make topology commands use clear shard language

## Status

Root commands already start backends before optional agents, seed empty cities without resetting them,
register nodes, and provide strict readiness and travel checks. The remaining work is naming and diagnostic
polish, not an architecture blocker.

## Build next

- Replace or alias the old `--all-cities` fan-out wording with consistent shard/node wording.
- Document focused single-node mode and topology-wide fan-out mode in one place.
- Either make `SHARD_DEPTH` an enforced startup-order contract or remove it.
- Show which nodes were included, excluded, already running, or stopped, and why.
- Keep agents opt-in and start them only after backend, seed, federation, inference, and route checks pass.

## Acceptance criteria

- [ ] Root commands use one consistent vocabulary for nodes, hosted cities, and fan-out.
- [ ] `SHARD_DEPTH` is enforced and documented or deleted.
- [x] Strict readiness fails for unhealthy, unseeded, or unregistered nodes.
- [x] Resident startup is explicit and follows infrastructure readiness.
- [ ] Status output explains topology order and inclusion decisions in plain language.
