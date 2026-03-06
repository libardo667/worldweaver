# WorldWeaver

WorldWeaver is a narrative simulation engine where AI-generated storylets and persistent world memory shape what happens next.

## Project Anchors

- Vision: `improvements/VISION.md`
- Roadmap: `improvements/ROADMAP.md`
- Harness: `improvements/harness/README.md`
- LLM Playtest Protocol: `playtest_harness/LLM_PLAYTEST_GUIDE.md`

## Quickstart

### Canonical dev stack (single command)

1. Install dependencies:

```bash
python scripts/dev.py install
```

2. Copy environment file and set one API key:

```bash
cp .env.example .env
# set one of OPENROUTER_API_KEY / LLM_API_KEY / OPENAI_API_KEY
```

Lane-specific 3-layer tuning is supported in `.env`:

- Referee/Planner lane: `LLM_REFEREE_MODEL`, `LLM_REFEREE_TEMPERATURE`, `LLM_REFEREE_FREQUENCY_PENALTY`, `LLM_REFEREE_PRESENCE_PENALTY`
- Narrator lane: `LLM_NARRATOR_MODEL`, `LLM_NARRATOR_TEMPERATURE`, `LLM_NARRATOR_FREQUENCY_PENALTY`, `LLM_NARRATOR_PRESENCE_PENALTY`
- Embeddings: `EMBEDDING_MODEL` (default remains `openai/text-embedding-3-small`)

3. Start the full stack (backend + client):

```bash
python scripts/dev.py stack-up
```

4. Open client:

- `http://localhost:5173`

Compose defaults:

- Backend: `http://localhost:8000`
- Client: `http://localhost:5173`
- Client proxy target inside Compose: `http://backend:8000`

To stream logs:

```bash
python scripts/dev.py stack-logs --follow
```

To stop the stack:

```bash
python scripts/dev.py stack-down
```

To stop and remove volumes:

```bash
python scripts/dev.py stack-down --volumes
```

### Manual fallback runtime

The direct two-process workflow remains supported:

```bash
python scripts/dev.py preflight
python scripts/dev.py backend
python scripts/dev.py client
```

Equivalent direct commands:

```bash
uvicorn main:app --reload --port 8000
npm --prefix client run dev
```

## Task Surface

- `python scripts/dev.py install`: install backend + client dependencies.
- `python scripts/dev.py preflight`: validate env/tool prerequisites.
- `python scripts/dev.py stack-up`: fail-fast validation, then start Compose stack.
- `python scripts/dev.py stack-down`: stop Compose stack.
- `python scripts/dev.py stack-logs [service] [--follow]`: inspect Compose logs.
- `python scripts/dev.py reset-data --yes`: delete local runtime sqlite files.
- `python scripts/dev.py test`: run backend tests.
- `python scripts/dev.py build`: run client build.
- `python scripts/dev.py lint-all`: run canonical backend lint/format checks.
- `python scripts/dev.py lint-extended`: run strict extended lint/format checks (`src/api src/services src/models tests scripts main.py`).
- `python scripts/dev.py gate3`: run Gate 3 static health (`lint-all` + static checks).
- `python scripts/dev.py gate3-strict`: run strict Gate 3 static health (`lint-extended` + static checks).
- `python scripts/dev.py pytest-warning-budget`: run `pytest -q` and enforce warning budget from `improvements/pytest-warning-baseline.json`.
- `python scripts/dev.py quality-strict`: run strict static checks plus pytest warning-budget enforcement (canonical strict local/CI path).
- `python scripts/dev.py verify`: run tests + static checks.
- `python scripts/dev.py sweep --help`: run the two-phase parameter sweep harness (Phase A coarse grid + Phase B ranked seed analysis).
- `python scripts/dev.py llm-playtest --help`: run one managed LLM-driven golden transcript playtest.
- `python scripts/dev.py sweep --prefetch-wait-policy bounded --prefetch-wait-timeout-seconds 3`: keep sweep prefetch waits bounded for clearer wall-clock accounting.
- `python playtest_harness/long_run_harness.py --prefetch-wait-policy strict --prefetch-wait-timeout-seconds 15`: run strict post-turn prefetch waiting when diagnosing prefetch readiness.
- `python scripts/dev.py benchmark-three-layer --help`: benchmark strict 3-layer OFF vs ON `/next` latency and emit comparison reports.

## Validation Commands

```bash
python scripts/dev.py test
python scripts/dev.py lint-all
python scripts/dev.py gate3
python scripts/dev.py lint-extended
python scripts/dev.py gate3-strict
python scripts/dev.py pytest-warning-budget
python scripts/dev.py quality-strict
python scripts/dev.py sweep --help
python scripts/dev.py llm-playtest --help
python scripts/dev.py benchmark-three-layer --help
python scripts/dev.py build
python -m pytest -q
npm --prefix client run build
```

## Session Consistency Modes

Runtime session consistency is controlled by `WW_SESSION_CONSISTENCY_MODE`:

- `cache` (default): process-local state-manager cache with per-session in-process locking.
- `stateless`: rebuild session state per request from persisted DB state (safer under multi-worker).
- `shared_cache`: reserved for future external cache support; currently falls back to stateless behavior.

Worker guidance:

- Use `cache` for single-process local development.
- Use `stateless` when running multiple API workers unless/until external shared cache is configured.
- In-process locks prevent same-session races within one worker process only; they do not provide cross-process locking.
