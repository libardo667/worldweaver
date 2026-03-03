# WorldWeaver

WorldWeaver is a narrative simulation engine where AI-generated storylets and
persistent world memory shape what happens next.

## Project Anchors

- Vision: `improvements/VISION.md`
- Roadmap: `improvements/ROADMAP.md`
- Harness: `improvements/harness/README.md`

## Quickstart

Recommended command surface:

```bash
python scripts/dev.py preflight
python scripts/dev.py backend
python scripts/dev.py client
python scripts/dev.py eval-smoke
```

### Setup

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
npm --prefix client install
```

Environment:

1. Copy `.env.example` to `.env`.
2. For live LLM calls, set one of:
   - `OPENROUTER_API_KEY`
   - `LLM_API_KEY`
   - `OPENAI_API_KEY`

### Run backend

```bash
uvicorn main:app --reload --port 8000
# or
python scripts/dev.py backend
```

### Run client

```bash
npm --prefix client run dev
# or
python scripts/dev.py client
```

Client URL: `http://localhost:5173` (proxied to backend `http://localhost:8000`).

## Validation Commands

### Tests

```bash
python -m pytest -q
python -m pytest tests/contract -q
python -m pytest tests/integration -q
python -m pytest tests/api/test_route_smoke.py -q
# or canonical wrapper
python scripts/dev.py test
```

### Build / static checks

```bash
npm --prefix client run build
python -m compileall src main.py
# run lint/format checks against touched Python files in your change
python -m ruff check src/api/game/spatial.py
python -m black --check src/api/game/spatial.py
# or canonical wrappers
python scripts/dev.py build
python scripts/dev.py verify
python scripts/dev.py eval
python scripts/dev.py eval-smoke
```

## Notes

- Current local runtime uses two processes (backend + client).
- Single-command local stack orchestration is tracked in
  `improvements/majors/46-operationalize-dev-runtime-with-compose-and-tasks.md`.
