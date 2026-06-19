# Add SPDX license headers to source files (AGPL-3.0-or-later)

> ✅ **STATUS: SHIPPED (2026-06-19).** Per-file SPDX/AGPL headers stamped across all first-party
> source (165 files: `worldweaver_engine/src`, `ww_agent/src`, `worldweaver_engine/client/src`,
> `scripts/`) via a scripted, idempotent insert — `scripts/add_spdx_headers.py` (run with `--check`
> to verify coverage). `ww-stable/` was already moved out, so it was correctly skipped. Lint-neutral
> (black/ruff unchanged vs main), all Python compiles, no vendored/generated files touched.

## Problem

The repository relicensed from MIT to AGPL-3.0-or-later on 2026-06-16 (LICENSE replaced with the
canonical AGPL-3.0 text; NOTICE, README "License" section, and package metadata updated). Individual
source files still carry no per-file license notice. Per-file SPDX headers
(`SPDX-License-Identifier: AGPL-3.0-or-later`) are the standard, tooling-friendly way to make each
file's license unambiguous when a file travels apart from the repo root — worth having for a
public-facing repo and for license scanners. Deferred from the relicense pass to keep that diff small
(it touches many files).

## Proposed Solution

Add a header to the top of first-party source files:

    # SPDX-License-Identifier: AGPL-3.0-or-later
    # Copyright (C) 2026 Levi Banks

- Python: header below any shebang/encoding cookie, above the module docstring.
- TS/JS (client `src/`): `// SPDX-License-Identifier: AGPL-3.0-or-later`.
- Scope: first-party source only (`worldweaver_engine/src`, `ww_agent/src`, `worldweaver_engine/client/src`,
  `scripts/`). Exclude third-party/vendored (`node_modules`, `client/dist`, `.venv`) and generated files.
- Do it as a scripted, idempotent bulk insert (skip files that already carry the header) so the diff is
  reviewable and re-runnable.
- Handle `ww-stable/` per the repo-cleanup outcome — it is a candidate for moving out of this repo, so
  stamp it only if it stays.

## Files Affected

- First-party `*.py` under `worldweaver_engine/src/`, `ww_agent/src/`, `scripts/`.
- First-party `*.ts` / `*.tsx` under `worldweaver_engine/client/src/`.
- A small helper script to insert/verify the headers idempotently.

## Acceptance Criteria

- [ ] Every first-party source file begins with an `SPDX-License-Identifier: AGPL-3.0-or-later` header.
- [ ] No third-party/vendored/generated file is touched.
- [ ] The insert is idempotent (re-running adds nothing).
- [ ] `ww-stable/` handled per the cleanup outcome (stamped if it stays, skipped if it moves out).

## Risks & Rollback

- Risk: a bulk insert can disturb files with unusual leading lines (encoding cookies, shebangs,
  generated banners). Mitigate with shebang/encoding-aware insertion and a diff review before commit.
- Rollback: revert the commit; the headers are additive and carry no behavior.
