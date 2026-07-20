# Audit WorldWeaver for public readiness

## Problem

WorldWeaver is public source code, but that does not mean it is ready for useful outside attention. The
repository currently gives little help to a stranger deciding what the project is, what is real, what remains
experimental, whether it is safe to run, or how to offer useful feedback. Public code, a public demonstration,
and a production public service are three different levels of readiness and must not be confused.

Repository clone counts do not establish human interest. The useful baseline is whether a person with no prior
project context can understand the claim, inspect its limits, run the supported demonstration, and identify a
small way to participate.

## Proposed work

1. Inspect the GitHub landing page, README, documentation site, local-town tutorial, repository metadata,
   licenses, public issue surfaces, and the existing `hekswerk-site` deployment.
2. Record concrete gaps under four questions:
   - Can a stranger understand why WorldWeaver exists?
   - Can they see or run one truthful example?
   - Can they distinguish working code, active research, and unbuilt plans?
   - Can they report a problem or offer a bounded contribution safely?
3. Audit for accidental secrets, private resident material, machine-local paths, unsafe default exposure, and
   claims stronger than the implementation warrants.
4. Recommend the smallest useful public surface. Do not add corporate-style process merely for appearance.
5. Separate blockers for outside review from blockers for operating an open public node.

## Expected files

- `README.md`
- `docs/`
- `.github/`
- repository description, topics, and homepage metadata
- `/mnt/c/Hub/Projects/hekswerk-site/`
- a dated audit report under `research/audits/public-readiness/`

## Acceptance criteria

- [ ] A dated audit records evidence, severity, and a proposed disposition for each finding.
- [ ] The audit separately rates readiness for source review, a local demonstration, an invited playtest, and
  an unattended public service.
- [ ] Public documentation makes no unsupported security, scientific, or resident-continuity claims.
- [ ] Private resident data, credentials, local secrets, and machine-specific operator material are absent
  from the intended public surface.
- [ ] The next implementation slices are small enough to review and commit independently.

## Risks and rollback

The main risk is turning public readiness into branding work that conceals unfinished engineering. Every
recommendation must be supported by current code or clearly labeled as a proposal. Repository metadata and
documentation changes are reversible; no live public service or resident should be started by this audit.
