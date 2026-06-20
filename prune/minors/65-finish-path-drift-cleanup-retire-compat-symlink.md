# Finish the personal_projects -> personal-projects path-drift cleanup (retire the compat symlink)

## Metadata

- ID: 65-finish-path-drift-cleanup-retire-compat-symlink
- Type: minor
- Owner: Levi
- Status: backlog -- URGENT (a hidden single point of failure; see Why urgent)
- Risk: medium (silent breakage of live resident startup if the symlink is lost)

> Tracked here in worldweaver/prune (git-tracked + pushed, so it cannot get lost) even though most of
> the affected files live in the-stable / the-mews / memory-management; the-stable's own prune is
> gitignored and its repo has no remote, so an urgent item there would be local-only.

## Problem

The projects directory was renamed `personal_projects` (underscore) -> `personal-projects` (hyphen),
but the old name was baked into many references and the rename was never fully propagated. On
2026-06-19 a compatibility symlink `~/personal_projects -> ~/personal-projects` was created so stale
references keep resolving, and the forward-looking EXECUTED scripts/configs were fixed to the real
path (so they no longer depend on the symlink):

- fixed: `export-public.sh` (`PROJECTS_HOME`), `worldweaver/ww_agent/scripts/_overnight_check.sh`,
  `worldweaver/scripts/prune_pick.py` (comment), the three `memory-management/instances/*/config.sh`
  `PROJECT_ROOT`s, `the-stable/research/writeups/{prose_census,build_census_svg}.py`, the global
  `~/.claude/CLAUDE.md` pointer, and a stale path in `worldweaver/.claude/settings.local.json`.

What remains, and why the symlink is still load-bearing:

- **~46 LIVE resident configs still hold the old name** -- `familiar.json` (`loft` path + MCP command
  paths) and `state.json` across `the-mews/familiar/*` and `the-stable/familiar/*`. The runtime
  resolves these at startup, so removing the symlink now would silently break running those residents.
- **Append-only history records the old name** -- ledgers / memory / `voice.jsonl` (~4 `.jsonl` files)
  plus some logs. These must NOT be rewritten: falsifying an append-only record is exactly what the
  project's honesty ethic forbids.
- **Cited metadata is stale** -- ~45 `.md` `source_paths` in the standing brief + procedural memory
  under `memory-management`. Harmless (not executed), but inaccurate.

## Why urgent

The compat symlink is an undeclared single point of failure. A fresh clone, a machine move, a
home-dir cleanup, or any CI runner that lacks the symlink will silently fail to resolve ~46 resident
configs and break resident startup, with no obvious cause (the path "looks" fine in the file). The
forward-looking code is already safe; this item closes the remaining live-config gap so the symlink
can be retired (or at least demoted to backing only immutable history).

## Proposed Solution

A forward-looking config sweep, leaving history intact:

- Rewrite the path-config fields (only) in the ~46 `familiar.json` / `state.json` files to the hyphen
  path: `loft`, MCP `command` paths, and any other resolved-at-runtime path field. Do NOT touch
  recorded-event fields.
- Fix the stale `.md` `source_paths` in the brief + procedural memory (correctness).
- Leave all append-only `.jsonl` (ledgers / memory / voice) and logs UNTOUCHED -- history stays.
- Then verify and remove the symlink: temporarily remove `~/personal_projects`, smoke-test starting
  one resident from `the-mews` and one from `the-stable` (confirm all paths resolve natively) and a
  memory-hygiene run, then delete the symlink for good if clean. If a residual live reference is
  found, fix it and retest before removal.

## Files Affected

- `the-mews/familiar/*/{familiar.json,state.json}` and `the-stable/familiar/*/{familiar.json,state.json}` (path-config fields only)
- `memory-management/instances/*/durable/standing-brief.md` and `memory/procedural/*.md` (`source_paths` frontmatter)
- the symlink `~/personal_projects` (removed once clean)
- explicitly NOT: any `*.jsonl` ledger/memory/voice, logs, `pokemon_project`, `claude-desktop-archive`, `.claude/file-history`, `.claude/backups`

## Acceptance Criteria

- [ ] No LIVE resident config (`familiar.json` / `state.json`) references `personal_projects`
- [ ] Starting a resident from `the-mews` and one from `the-stable` resolves all paths with the symlink REMOVED
- [ ] Append-only ledgers / memory / voice are byte-unchanged (history intact)
- [ ] The `~/personal_projects` symlink is deleted (or, if kept, only because it backs append-only records that legitimately cannot be rewritten, documented as such)
- [ ] Export + the already-fixed scripts continue to work unchanged

## Risks & Rollback

- A missed live reference breaks resident startup -> mitigate by the temporary-removal smoke test
  before deleting the symlink for good; do not delete until a clean cold start is observed.
- `state.json` may mix config and recorded data -> only rewrite resolved-at-runtime path fields,
  never recorded events. When unsure, leave it and let the symlink back it.
- Rollback: recreate the symlink (`ln -s ~/personal-projects ~/personal_projects`) -- instantly
  restores resolution for anything still on the old name.

## Lineage

Follow-up from the 2026-06-19 session that fixed the executed scripts/configs and shipped the-stable's
public AGPL + SPDX export. The symlink was created that day as a deliberate, reversible shim; this
item retires it.
