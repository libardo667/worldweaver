# Add root runtime README entrypoint and harness link

## Problem

The repository has no root `README.md`, so developers landing in the repo root
do not have a canonical runtime/test/build entrypoint or a direct link to the
agentic harness docs. This leaves the harness install checklist incomplete and
increases onboarding friction.

## Proposed Solution

1. Create a concise root `README.md` as the canonical entrypoint.
2. Include copy/paste-ready commands for setup, backend run, client run, tests,
   and client build that match the current repo command surface.
3. Link the harness index (`improvements/harness/README.md`) and core anchors
   (`improvements/VISION.md`, `improvements/ROADMAP.md`).
4. Keep scope docs-only; do not modify application behavior.

## Files Affected

- README.md (new)
- improvements/HARNESS_BOOTSTRAP_CHECKLIST.md (update install checklist status)

## Acceptance Criteria

- [ ] Root `README.md` exists and is discoverable from repo root.
- [ ] README includes canonical setup/run/test/build commands used in this repo.
- [ ] README links to `improvements/harness/README.md`.
- [ ] Harness bootstrap install checklist no longer reports missing top-level doc linkage.
