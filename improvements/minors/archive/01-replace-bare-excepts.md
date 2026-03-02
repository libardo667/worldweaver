# Replace bare except clauses with specific exception handling

## Problem

Several files use `except:` or `except Exception:` with `pass`, silently
swallowing errors:

- `src/api/game.py` line 317 — `except: pass` in spatial navigation JSON
  parsing. A malformed `position` column crashes silently and the player
  sees no available directions.
- `src/services/story_smoother.py` lines 105-107 — bare `except:` catches
  everything including `KeyboardInterrupt`.
- `src/services/story_deepener.py` line 59 — bare except on JSON parsing
  during storylet loading.

These make debugging nearly impossible and mask real bugs.

## Proposed Fix

Replace each bare `except:` / `except: pass` with a specific exception
type (`json.JSONDecodeError`, `KeyError`, `ValueError` as appropriate) and
add a `logger.warning(...)` call with the exception context. Use the
existing `logging` import already present in each file.

## Files Affected

- `src/api/game.py`
- `src/services/story_smoother.py`
- `src/services/story_deepener.py`

## Acceptance Criteria

- [ ] Zero bare `except:` or `except: pass` clauses remain in the codebase
- [ ] Each replaced clause logs the exception at `warning` level with file
      and context
