# Refactor Phase Checklist

Use this checklist to record quality-gate evidence for each refactor phase
without changing API/payload contracts.

## Required Commands (All Phases)

```bash
python scripts/dev.py verify
```

## Gate 3 Static Policy (Demoted Repo-Wide Lint)

- Required baseline static gate:
  - `python scripts/dev.py static`
- Required lint scope for routine changes:
  - `python scripts/dev.py lint <touched_python_paths>`
- Optional debt-tracking run (non-blocking while lint debt remains):
  - `python scripts/dev.py lint --all`

## Optional Targeted Reruns

```bash
python -m pytest tests/api -q
python -m pytest tests/service -q
python -m pytest tests/integration -q
python -m pytest tests/contract -q
```

## Phase Records

### Phase 0

- [ ] Completed
- Commit/branch:
- Contract checks run:
- Verification result:
- Risks/follow-ups:

### Phase 1

- [ ] Completed
- Commit/branch:
- Contract checks run:
- Verification result:
- Risks/follow-ups:

### Phase 2

- [ ] Completed
- Commit/branch:
- Contract checks run:
- Verification result:
- Risks/follow-ups:

### Phase 3

- [ ] Completed
- Commit/branch:
- Contract checks run:
- Verification result:
- Risks/follow-ups:

### Phase 4

- [ ] Completed
- Commit/branch:
- Contract checks run:
- Verification result:
- Risks/follow-ups:

### Phase 5

- [ ] Completed
- Commit/branch:
- Contract checks run:
- Verification result:
- Risks/follow-ups:

### Phase 6

- [ ] Completed
- Commit/branch:
- Contract checks run:
- Verification result:
- Risks/follow-ups:

### Phase 7

- [ ] Completed
- Commit/branch:
- Contract checks run:
- Verification result:
- Risks/follow-ups:
