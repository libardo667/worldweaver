# PRUNING Lane 4 Evidence

Date: `2026-03-03`  
Lane: `4` (Gate/Tooling Demotion)

## Files Changed

- `.github/workflows/narrative-eval-smoke.yml`
- `scripts/dev.py`
- `README.md`
- `client/README.md`
- `improvements/HARNESS_BOOTSTRAP_CHECKLIST.md`
- `improvements/ROADMAP.md`
- `improvements/refactor_phase_checklist.md` (new)
- `improvements/PRUNING_LANE_4_EVIDENCE.md` (new)

## Validations Run and Results

Required by lane plan:

1. `python -m ruff check src/api src/services src/models main.py`  
   Result: `FAIL`  
   Summary: `131` lint violations in existing backend/runtime modules (for example `E402`, `E501`, `F401`, `F541`, `F841`).

2. `python -m black --check src/api src/services src/models main.py`  
   Result: `FAIL`  
   Summary: `27` files would be reformatted.

3. `python scripts/dev.py verify`  
   Result: `FAIL`  
   Summary (run 1): `tests/integration/test_narrative_eval_harness.py::test_narrative_eval_smoke_runs_and_writes_artifacts` failed due:
   `ImportError: cannot import name 'save_storylets_with_postprocessing' from 'src.services.storylet_ingest'`.
   Summary (run 2 after lane edits): `tests/contract/test_error_envelopes.py::test_debug_endpoint_error_returns_500` failed due:
   `AttributeError: module 'src.api.author' has no attribute 'SessionVars'`.

Additional lane-local command checks:

4. `python scripts/dev.py static`  
   Result: `PASS`

5. `python scripts/dev.py lint scripts/dev.py`  
   Result: `PASS` (after formatting `scripts/dev.py` with `black`)

## Unresolved Risks

- Repository-wide lint debt remains high; full-scope lint/format commands are still red.
- `scripts/dev.py verify` is currently blocked by failures outside Lane 4 file boundaries (`src/api/author/__init__.py`, `src/services/storylet_ingest.py` and related test contracts).
- Because other lanes are actively modifying backend contract/compatibility surfaces, test failure signatures may continue shifting until integration order stabilizes.

## Handoff Notes for Integration

- Lane 4 demotes repo-wide lint to a non-blocking/deferred track in docs and workflow guidance; baseline static checks are now explicit via `python scripts/dev.py static`.
- Canonical lint entrypoint is now `python scripts/dev.py lint <paths>` with explicit opt-in full scope via `--all`.
- CI smoke workflow now uses the command surface wrapper (`python scripts/dev.py eval-smoke`) instead of directly invoking `scripts/eval_narrative.py`.
- Integrator should merge Lane 2 and Lane 3 first per coordination plan, then re-run:
  - `python -m ruff check src/api src/services src/models main.py`
  - `python -m black --check src/api src/services src/models main.py`
  - `python scripts/dev.py verify`
  to re-evaluate whether current failures are resolved or remain true blockers.
