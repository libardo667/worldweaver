# Engine guidance

Use the repository-level `../CLAUDE.md`, the active work item under `../prune/`, and live contracts/tests
as the authority for engine work. This file is deliberately short so the monorepo has one policy spine.

The engine owns canonical world facts, events, locations, identity routing, federation, world presentation, and
the HTTP boundary used by players and residents. Resident cognition belongs in `../ww_agent/`.

Use the repository-root `python dev.py ...` command for developer workflows. For non-trivial changes run
targeted tests and:

```bash
python dev.py check
```

When an architectural change invalidates prose, update `README.md`, the relevant module/API contract,
and the active `../prune/` item in the same slice.
