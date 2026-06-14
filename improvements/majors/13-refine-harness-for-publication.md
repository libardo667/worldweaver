# Refine and publish the improvement harness methodology

## Problem

`improvements/harness/` contains 11 markdown docs and 9 templates that
describe a structured workflow for directing LLM coding agents through
non-trivial software improvements. The workflow was developed organically
while building WorldWeaver and has proven effective in practice.

The current state:
- Documentation is written for internal use only, with WorldWeaver-specific
  examples baked in
- The templates reference project-specific paths and assumptions
- There is no standalone README or "pitch" doc that explains the methodology
  to an outside reader
- Some docs are V3-era and may need updating to reflect how the process
  actually works with modern Claude (tool-use, memory, background tasks)

The user wants to refine this into something that could be published or shared
as a general-purpose methodology for working with LLM coding agents.

## Proposed Solution

1. Audit all 11 harness docs for WorldWeaver-specific content vs. generic
   methodology.
2. Extract the generic methodology into a clean, standalone
   `improvements/harness/METHODOLOGY.md` pitched to an outside reader.
3. Update the 9 templates to remove hardcoded WorldWeaver paths; use
   `<project-name>` / `<repo-root>` placeholders instead.
4. Write a `improvements/harness/PUBLICATION_NOTES.md` capturing what worked
   well and what didn't in practice — the honest retrospective.
5. Keep the worldweaver-specific harness config as an example/case study,
   clearly labelled as such.
6. Archive any docs that are fully superseded by the new METHODOLOGY.md.

## Files Affected

- `improvements/harness/README.md` — rewrite as external-facing pitch
- `improvements/harness/METHODOLOGY.md` — create (core methodology doc)
- `improvements/harness/PUBLICATION_NOTES.md` — create (retrospective)
- `improvements/harness/templates/*.md` (9 files) — de-WorldWeaver-ify
- Several existing harness docs — review, update or archive

## Acceptance Criteria

- [ ] `METHODOLOGY.md` reads cleanly to someone who has never seen WorldWeaver
- [ ] All templates use generic placeholders, not WorldWeaver-specific paths
- [ ] `README.md` functions as a project pitch / entry point
- [ ] `PUBLICATION_NOTES.md` exists with honest retrospective
- [ ] No doc in `improvements/harness/` references WorldWeaver internals
      without clearly labelling it as an example

## Risks & Rollback

Documentation only. No code impact. Rollback: `git revert`.
