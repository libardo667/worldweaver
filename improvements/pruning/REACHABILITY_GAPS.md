# Reachability Gaps (Coverage-Backed)

Status: `evidence_only`  
Data source:
- `REACHABILITY_EVIDENCE.csv`
- `COVERAGE_SUMMARY.json`
- `COVERAGE_REPORT.txt`

## Method (Bulletproof Pass)
- Full dynamic execution coverage:
- `coverage run --source=src -m pytest tests -q`
- Static import graph across `main.py`, `src/**`, and `tests/**`.
- API route extraction from router decorators with placeholder-aware route matching against test path literals.
- Direct module-path string mentions in tests counted.

## Snapshot (`2026-03-06`)
- Test suite for dynamic evidence: `578 passed` (`tests/**`)
- Source modules assessed (non-`__init__.py`): `53`
- Executed in tests (`covered_lines > 0`): `53`
- Not executed in tests: `0`
- Final evidence tier:
- `strong`: `51`
- `executed_but_weak`: `2`

## Weak-Reachability Candidates
1. `src/services/story_deepener.py`
   - Coverage: `27.43%`
   - Static tier: `transitive_only`
2. `src/services/story_smoother.py`
   - Coverage: `8.37%`
   - Static tier: `transitive_only`

Interpretation:
- Both modules execute in suite runs, but reachability remains weak because direct route/test linkage is thin and dynamic coverage is low.
- These are prime candidates for targeted tests or demotion/isolation analysis before any structural pruning.

## Notable Improvement vs Prior Pass
- Prior pass relied on static evidence only.
- Current pass is coverage-backed and removes ambiguity about whether modules execute in real tests.

## Recommended Next Evidence Step
- Add focused tests raising coverage for:
1. `src/services/story_deepener.py`
2. `src/services/story_smoother.py`
