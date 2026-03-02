# Remove unused CLI stub main() functions from service files

## Problem

`src/services/story_smoother.py` (lines 656-679) and
`src/services/story_deepener.py` (lines 522-541) each contain a
`if __name__ == "__main__": main()` block with ad-hoc CLI runners. These
are never invoked by the application, are not documented, and bypass the
normal FastAPI startup (no lifespan hooks, no proper DB init). They
create confusion about how to run the services.

## Proposed Fix

Delete the `main()` function and the `if __name__` guard from both files.
If CLI access is needed in the future, it should be a proper management
command or script in `scripts/`.

## Files Affected

- `src/services/story_smoother.py`
- `src/services/story_deepener.py`

## Acceptance Criteria

- [ ] Neither file contains a `main()` function or `__name__` guard
- [ ] Application startup and tests are unaffected
