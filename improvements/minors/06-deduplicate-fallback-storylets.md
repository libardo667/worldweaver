# Deduplicate fallback storylet definitions in llm_service.py

## Problem

`src/services/llm_service.py` defines the same set of fallback storylets
in two places — once around lines 100-122 and again around lines 126-148.
Both blocks produce identical storylet dicts with the same titles, text
templates, and choices. This means any change to the fallback content must
be made twice, and divergence is inevitable.

## Proposed Fix

Extract the fallback storylets into a single module-level constant
`_FALLBACK_STORYLETS: list[dict]` at the top of the file. Replace both
inline definitions with a reference to (or a copy of) this constant.

## Files Affected

- `src/services/llm_service.py`

## Acceptance Criteria

- [ ] Only one definition of fallback storylets exists in the file
- [ ] Both call sites return the same fallback content as before
