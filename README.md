# WorldWeaver

WorldWeaver is a narrative simulation engine where AI-generated storylets and persistent world memory shape what happens next.

## Project Anchors

- Vision: `improvements/VISION.md`
- Roadmap: `improvements/ROADMAP.md`
- Harness: `improvements/harness/README.md`

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
- `python scripts/dev.py verify`: run tests + static checks.

## Validation Commands

```bash
python scripts/dev.py test
python scripts/dev.py build
python -m pytest -q
npm --prefix client run build
```
