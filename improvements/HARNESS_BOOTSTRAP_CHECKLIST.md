# Harness Bootstrap Checklist (WorldWeaver)

Project: `worldweaver`  
Date: `2026-03-03`  
Owner: `TBD`

## Install

- [x] Harness folder present at `improvements/harness/`.
- [ ] Harness index linked from a top-level project doc (`README.md` missing at repo root).

## Anchor Docs

- [x] Vision doc exists: `improvements/VISION.md`
- [x] Roadmap doc exists: `improvements/ROADMAP.md`
- [x] Work item schemas exist:
  - `improvements/majors/MAJOR_SCHEMA.md`
  - `improvements/minors/MINOR_SCHEMA.md`

## Canonical Command Surface (Current Repo)

### Setup / install

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
npm --prefix client install
```

Environment bootstrap:

- Copy `.env.example` to `.env`.
- For live LLM calls, set one of: `OPENROUTER_API_KEY`, `LLM_API_KEY`, `OPENAI_API_KEY`.

### Run backend

```bash
uvicorn main:app --reload --port 8000
```

### Run client

```bash
npm --prefix client run dev
```

Client default URL: `http://localhost:5173` (Vite proxy to backend `http://localhost:8000`).

### Tests

```bash
python -m pytest -q
python -m pytest tests/contract -q
python -m pytest tests/integration -q
python -m pytest tests/api/test_route_smoke.py -q
```

### Build / static checks

```bash
npm --prefix client run build
python -m compileall src main.py
```

### Production-like local stack

- Gap: no canonical compose/task runner entrypoint yet (tracked by major `46` and minor `67`).

## Quality Gates Mapped To Repo Commands

### Gate 1: Contract integrity

- `python -m pytest tests/contract -q`
- `python -m pytest tests/api/test_route_smoke.py -q`

### Gate 2: Correctness

- `python -m pytest -q`
- Optional targeted reruns for touched areas:
  - `python -m pytest tests/service -q`
  - `python -m pytest tests/api -q`
  - `python -m pytest tests/integration -q`

### Gate 3: Build and static health

- `npm --prefix client run build`
- `python -m compileall src main.py`
- Gap: no enforced backend lint/format/type gate currently (`ruff`/`black` minor `48` is open).

### Gate 4: Runtime behavior

- `python -m pytest tests/api/test_game_endpoints.py -q`
- `python -m pytest tests/diagnostic/test_llm_config.py -q`
- Gap: no automated latency/error-budget threshold command is currently required in CI.

### Gate 5: Operational safety

- Evidence source: work-item docs + PR notes (rollback path, disable path, migration safety).
- Command aid (presence check in majors):  
  `rg -n "^## Risks & Rollback" improvements/majors`
- Gap: no automated enforcement for rollback-note completeness.

## First Pilot Minor (Harness Trial)

Recommended pilot: `improvements/minors/67-add-dev-runtime-preflight-and-command-surface.md`

Why this first:

1. Directly addresses missing command-surface clarity required by this harness.
2. Low-risk scope (scripts/docs) with no intended API contract changes.
3. Creates immediate leverage for all later majors/minors.

Pilot verification commands:

```bash
python -m pytest -q
npm --prefix client run build
```

Pilot completion evidence should include:

- Implemented preflight command(s) and documented run sequence.
- Command surface documented in one place and matching actual scripts.
- Acceptance criteria checked in the minor doc.

## Open Gaps

- Root `README.md` is missing, so there is no single top-level runtime entrypoint doc yet.
- `run_true_tests.py` is referenced in older docs but is not present in repo root.
- No current single-command full-stack runtime (`compose`/`make`/task wrapper).
- Backend lint/format/type gates are not yet operationalized.
