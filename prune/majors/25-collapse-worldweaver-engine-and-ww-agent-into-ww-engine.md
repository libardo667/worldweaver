# Collapse `worldweaver_engine` and `ww_agent` into a unified `ww_engine` runtime

## Status

**Reconciled 2026-06-17 against the substrate+pulse architecture.** This is an *optional
structural-clarity* consolidation, **not a mandate** — explicitly parked unless the two-tree
overhead genuinely bites. The Major 49 rebuild (loops → salience substrate + pulse) reinforced
that resident cognition and the world backend are *one shard boot contract*, which is the case
*for* a single `ww_engine/` root. But the current `worldweaver_engine/` + `ww_agent/` split
**works**, and a rename-and-move is cosmetic churn with real reference-breakage risk (paths,
imports, compose mounts, the leak guard, CI). It absorbs the still-relevant structural intent of
the old Majors 19/21 (both retired); several cross-cutting items it once cited (dormancy,
shard-creation) have since shipped and been archived.

**Decision rule:** collapse only if/when the split's cognitive overhead is costing real time on
cross-tree changes — otherwise leave it. Clarity, not consolidation-for-its-own-sake. (The
target layout below stands as the *how*, should that bar ever be met.)

## Problem

The workspace still presents `worldweaver_engine/` and `ww_agent/` as separate
top-level systems even though the shard runtime already treats them as one
operational unit.

Concrete symptoms:

- Shard compose files mount shared backend code from `worldweaver_engine/` and
  shared agent code from `ww_agent/`, but both are part of the same shard boot
  contract.
- Major architectural specs now live at the workspace root under `prune/`,
  which is already a signal that the important decisions span both codebases.
- Cross-cutting changes like resident dormancy, onboarding, shard creation,
  actor identity, and world visibility routinely require touching both trees.
- Maintenance scripts still carry split-era defaults and assumptions, which
  increases the chance of resetting or seeding the wrong resident root.
- Operators and contributors still have to mentally model two “engines” when the
  product behavior depends on one shared runtime surface.

The current split is mostly historical. It adds cognitive overhead, stale path
assumptions, and duplicated operational language without providing a clean
runtime boundary.

## Proposed Solution

Define `ww_engine/` as the canonical shared runtime root and migrate the current
backend and agent code into it under a lean, explicit layout.

Target shape:

```text
worldweaver/
  ww_engine/
    backend/
    agent/
    scripts/
    templates/
    docs/
  shards/
  prune/
```

This is a repository-structure consolidation, not a process merge. Backend and
agent still run as separate services; they simply stop pretending to be
independent top-level products.

### Phase 1 - Define the canonical layout

- Choose the exact `ww_engine/` directory structure.
- Map every current `worldweaver_engine/` and `ww_agent/` subtree into one of:
  - `ww_engine/backend`
  - `ww_engine/agent`
  - `ww_engine/scripts`
  - `ww_engine/templates`
  - `ww_engine/docs`
- Classify what remains outside `ww_engine/`:
  - shard instances
  - workspace-level prune/history
  - artifacts and backups

### Phase 2 - Move code and normalize import/launch paths

- Move backend application code from `worldweaver_engine/` into
  `ww_engine/backend/`.
- Move agent runtime code from `ww_agent/` into `ww_engine/agent/`.
- Relocate shared scripts that currently live in backend-only or agent-only
  roots into `ww_engine/scripts/` when they are runtime-wide concerns.
- Update Docker build contexts, compose files, readmes, and bootstrap commands
  to point at the new canonical locations.

### Phase 3 - Remove split-era defaults and ambiguous paths

- Update scripts like shard creation, seeding, canon reset, and resident tooling
  so they no longer default to legacy top-level roots.
- Remove path assumptions that still privilege `worldweaver_engine/` or
  `ww_agent/` as the “real” runtime root.
- Make shard-local resident and DB paths explicit and consistent under the new
  engine contract.

### Phase 4 - Refresh docs and operator language

- Rewrite docs so `ww_engine/` is the only shared runtime home described.
- Demote or delete stale references to the old split once migration is complete.
- Ensure active major and minor specs refer to root-level `prune/` paths
  and the unified `ww_engine/` structure.

### Phase 5 - Decommission legacy roots

- Leave temporary wrappers or compatibility symlinks only if required for a
  short transition.
- Remove `worldweaver_engine/` and `ww_agent/` as primary top-level runtime
  directories once shard boot, local dev, and maintenance flows are verified.

## Files Affected

- `prune/majors/21-prune-legacy-dev-architecture-and-unify-engine-kit.md`
- `prune/majors/22-stabilize-shard-first-runtime-and-frontend-flows.md`
- `prune/majors/11-shard-creation-framework.md`
- `worldweaver_engine/scripts/new_shard.py`
- `worldweaver_engine/scripts/seed_world.py`
- `worldweaver_engine/scripts/canon_reset.py`
- `shards/*/docker-compose.yml`
- top-level `.gitignore`
- future `ww_engine/` directory tree and migration wrappers
- any docs that still reference `worldweaver_engine/` or `ww_agent/` as the
  canonical shared runtime root

## Acceptance Criteria

- [ ] A single `ww_engine/` directory exists as the canonical shared runtime root
- [ ] Backend code lives under `ww_engine/backend/`
- [ ] Agent code lives under `ww_engine/agent/`
- [ ] Shard compose files and boot flows reference `ww_engine/` paths rather than split legacy roots
- [ ] Runtime-wide scripts no longer default to legacy top-level resident or engine paths
- [ ] Active architecture docs describe `ww_engine/` as the shared runtime home
- [ ] Operators can seed, reset, and run shards without needing to know whether code used to live in `worldweaver_engine/` or `ww_agent/`
- [ ] Legacy top-level roots are either removed or clearly marked as temporary compatibility wrappers

## Risks & Rollback

- This is a high-churn structural migration. The main risk is breaking shard
  compose paths, Docker build contexts, or maintenance scripts that still assume
  the current layout.
- Path-heavy scripts such as shard creation and reset tooling are especially
  likely to fail silently if moved without explicit verification.
- A partial migration that updates docs before paths are stable will increase
  confusion rather than reduce it.
- Rollback path: keep compatibility wrappers or symlink-like forwarding layers
  during the migration, and only remove the old roots after shard startup,
  reset, and seeding flows have all been re-verified end to end.
