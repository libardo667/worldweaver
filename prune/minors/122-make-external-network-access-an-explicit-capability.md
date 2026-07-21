# Make external network access an explicit capability

## Status

The 2026-07-20 elective-source audit found that the San Francisco `news` source could trigger server-side RSS
access without this grant. It is no longer advertised to production residents. Federation discovery remains a
separate, labelled connection to the steward-configured directory. This item must be completed before an
open-web source is restored.

## Problem

External network reads are materially different from local city information and scoped files. They can
leak private query terms, reach untrusted content, cost money, and expose a host network. The old rule tried
to grant or deny access by classifying residents as “goal-bearing” or “goalless.” That requires vague
profiling and does not match the current universal resident model.

## Build next

Add a fail-closed `world-egress` grant with explicit:

- resident and hearth identity;
- allowed schemes and destinations;
- public-internet versus private-network policy;
- read-only methods;
- query, response-size, redirect, and rate limits;
- secret and local-path redaction;
- expiry and revocation;
- private audit metadata without response contents.

The resident should be able to inspect whether the capability exists and what it permits. A host may refuse
to offer egress. Lack of egress must not stop ordinary hearth or city life.

## Boundaries

- No grant is inferred from personality, goals, prose, occupation, or a population category.
- Read access never implies posting, messaging, purchasing, account login, code execution, or host-file
  access.
- Private, loopback, link-local, and cloud-metadata addresses are denied unless a separate named local
  service grant allows them.
- The capability returns source records with URLs and provenance, not automatic prompt injections.
- Queries and results remain private to the resident unless deliberately published.

## Acceptance criteria

- [ ] External requests fail closed without an active resident-scoped grant.
- [ ] The grant declares destination, method, size, redirect, rate, expiry, and revocation limits.
- [ ] Network policy blocks private-address and metadata-service access by default.
- [ ] Requests return bounded, provenance-tagged source records.
- [ ] Audit records contain routing and usage metadata but not private response bodies.
- [ ] No resident goal or personality classifier participates in permission decisions.
- [ ] Revoking egress leaves local resident capabilities working.
