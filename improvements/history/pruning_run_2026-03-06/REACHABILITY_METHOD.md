# Reachability Evidence Method

Goal: produce reproducible, coverage-backed reachability evidence for `src/**`.

## Commands
```powershell
coverage erase
coverage run --source=src -m pytest tests -q
coverage json -o improvements/pruning/COVERAGE_SUMMARY.json
coverage xml -o improvements/pruning/COVERAGE.xml
coverage report > improvements/pruning/COVERAGE_REPORT.txt
python improvements/pruning/build_reachability_evidence.py
```

## Evidence Sources
- Dynamic execution:
- `COVERAGE_SUMMARY.json`
- `COVERAGE_REPORT.txt`
- Static topology:
- import graph (`main.py`, `src/**`, `tests/**`)
- route definitions in `src/api/**` mapped to test path literals
- direct module-path mentions in tests

## Output
- `REACHABILITY_EVIDENCE.csv` with:
- coverage metrics (`statements`, `covered_lines`, `coverage_percent`, `coverage_band`)
- static evidence (`runtime_importer_count`, `test_importer_count`, route hits, mentions)
- consolidated tiers (`static_evidence_tier`, `final_evidence_tier`)
- weak-candidate flag (`weak_reachability_candidate`)

## Weak Candidate Rule
- `weak_reachability_candidate=yes` when:
1. module is not executed in tests, or
2. module is only transitively referenced and has low/very-low dynamic coverage.
