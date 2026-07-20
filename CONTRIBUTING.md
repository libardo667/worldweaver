# Contributing to WorldWeaver

WorldWeaver is an experimental shared-world engine maintained by one person. Focused reports and small,
well-tested changes are more useful than broad rewrites.

## Useful ways to help

- Follow the local-town tutorial from a clean checkout and report where it fails or becomes unclear.
- Point out a claim that is stronger than the code or evidence.
- Review a world-action, privacy, identity, travel, or recovery boundary.
- Improve a small test, explanation, or participant-facing interaction.

For a substantial architecture change, open a design feedback issue before writing it. The active order of
work is in [`prune/ROADMAP.md`](prune/ROADMAP.md); a work item is a design record, not a promise that every
proposal will be built.

## Before posting anything

Do not include credentials, private resident histories, prompts, hearth files, unpublished workshop files,
private correspondence, or personal participant data. Public speech and objects should still be quoted only
when the report truly needs them. Report security problems through the private process in
[`SECURITY.md`](SECURITY.md), not a public issue.

## Making a change

1. Keep the change narrow and explain what current behavior it corrects.
2. Add or update a test when behavior changes.
3. Run `python dev.py check` from the repository root.
4. State what you tested and what remains unproven.

Contributions to the software are accepted under AGPL-3.0-or-later. Do not add resident-produced creative
material unless its provenance and publication permission are explicit.
