# Security policy

WorldWeaver is active experimental software. The current public deployment is a supervised, single-computer
test topology, not a production service or a proven secure decentralized network.

## Report a vulnerability privately

Use [GitHub's private vulnerability report](https://github.com/libardo667/worldweaver/security/advisories/new).
Do not open a public issue for a suspected vulnerability.

Include the affected commit or version, the smallest safe reproduction you can provide, likely impact, and
whether you believe the public test deployment is affected. Do not send working credentials or copy private
resident or participant material into the report. Describe how the maintainer can reproduce the issue with
synthetic data instead.

Only the current `main` branch is supported. There is no promised response deadline, but reports will be
acknowledged and assessed as maintainer capacity permits. Please allow time for a fix before public disclosure.

## Especially relevant boundaries

- account authentication, recovery, and participant data;
- private resident ledgers, prompts, hearth files, and correspondence;
- node identities, signed federation calls, admission, and replay protection;
- object ownership, travel handoffs, generation fencing, backups, and restore;
- operator commands that could expose a service or delete state.

If the concern is a design criticism rather than an exploitable vulnerability, use the public design feedback
issue form instead.
