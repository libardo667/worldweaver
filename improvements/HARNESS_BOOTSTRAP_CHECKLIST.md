# Harness Bootstrap Checklist (Current)

Project: `worldweaver`

## Canonical Command Surface

```bash
python scripts/dev.py install
python scripts/dev.py preflight
python scripts/dev.py backend
python scripts/dev.py client
python scripts/dev.py test
python scripts/dev.py build
python scripts/dev.py lint-all
python scripts/dev.py gate3
python scripts/dev.py verify
```

## Quality Gates

- Gate 1 (Contract): `python -m pytest tests/contract -q`
- Gate 2 (Correctness): `python -m pytest -q`
- Gate 3 (Build/static): `python scripts/dev.py gate3`
- Gate 4 (Runtime behavior): targeted endpoint/eval suites as needed
- Gate 5 (Operational safety): rollback evidence recorded in work-item docs

## Notes

- Historical harness bootstrap artifact remains at:
  - `improvements/history/HARNESS_BOOTSTRAP_CHECKLIST.md`
