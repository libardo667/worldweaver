# Refactor Phase Checklist

Use this checklist to record quality-gate evidence for each refactor phase
without changing API/payload contracts.

## Required Commands (All Phases)

```bash
python scripts/dev.py verify
```

## Gate 3 Static Policy (Repo-Wide Enforced)

- Required Gate 3 command:
  - `python scripts/dev.py gate3`
- Equivalent canonical lint/format command:
  - `python scripts/dev.py lint-all`
- Legacy targeted lint remains available for local iteration:
  - `python scripts/dev.py lint <touched_python_paths>`

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
