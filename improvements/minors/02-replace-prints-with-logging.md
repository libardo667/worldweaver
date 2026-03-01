# Replace print statements with structured logging

## Problem

`src/api/author.py` and `src/services/llm_service.py` use `print()` for
debug output (e.g., `author.py` line 613, `llm_service.py` lines 444-445,
457-459). Print statements bypass the logging framework, cannot be filtered
by level, and clutter stdout in production.

## Proposed Fix

1. Add `logger = logging.getLogger(__name__)` at the top of each affected
   file (some already have it).
2. Replace every `print(...)` with `logger.info(...)` or `logger.debug(...)`
   depending on whether the message is useful in normal operation or only
   during development.
3. Ensure the log messages include structured context (e.g., storylet count,
   trigger name) rather than bare f-strings.

## Files Affected

- `src/api/author.py`
- `src/services/llm_service.py`
- `src/services/story_smoother.py`
- `src/services/story_deepener.py`

## Acceptance Criteria

- [ ] `grep -rn "print(" src/` returns zero hits (excluding `__repr__` or
      intentional CLI output)
- [ ] All replacement log calls include `__name__` logger
