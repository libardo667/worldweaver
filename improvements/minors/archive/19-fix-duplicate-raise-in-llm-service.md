# Fix duplicate raise ValueError in llm_service.py

## Problem

`src/services/llm_service.py` line ~622 has an identical `raise ValueError`
statement duplicated on consecutive lines in `generate_starting_storylet`.
The second raise is unreachable dead code, suggesting the file was edited
without review.

## Proposed Fix

Delete the duplicate `raise ValueError("No JSON found in starting storylet response")` line.

## Files Affected

- `src/services/llm_service.py`

## Acceptance Criteria

- [ ] Only one `raise ValueError` remains at that location
- [ ] `generate_starting_storylet` still raises on missing JSON
