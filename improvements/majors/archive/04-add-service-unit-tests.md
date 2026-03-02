# Add unit tests for core service layer

## Problem

The service layer contains the bulk of the application logic (~4,300 LOC
across 11 files) but only `seed_data.py` has tests. The following services
have **zero** test coverage:

- `game_logic.py` — `pick_storylet`, `render`, `meets_requirements`,
  `apply_choice_set`
- `state_manager.py` — `AdvancedStateManager` inventory, relationship,
  environment, rollback
- `llm_service.py` — fallback paths, JSON extraction, contextual generation
- `storylet_analyzer.py` — gap analysis, recommendations
- `location_mapper.py` — semantic coordinate assignment

Without these tests, refactoring any service is a gamble.

## Proposed Solution

Create one test file per service, focusing on deterministic behaviour (no
live LLM calls):

1. `tests/service/test_game_logic.py` — requirement matching edge cases
   (numeric operators, missing keys, None values), weighted selection,
   template rendering with missing keys, `apply_choice_set` inc/dec.
2. `tests/service/test_state_manager.py` — add/remove inventory items,
   relationship updates and clamping, environment transitions,
   export/import round-trip, rollback.
3. `tests/service/test_llm_service.py` — mock `openai.ChatCompletion`,
   test fallback storylet generation when `DW_DISABLE_AI` is set, JSON
   extraction from markdown code blocks.
4. `tests/service/test_storylet_analyzer.py` — gap detection with known
   storylet sets, recommendation generation.
5. `tests/service/test_location_mapper.py` — pattern matching for known
   location names, hash fallback, collision avoidance.

## Files Affected

- `tests/service/test_game_logic.py` (new)
- `tests/service/test_state_manager.py` (new)
- `tests/service/test_llm_service.py` (new)
- `tests/service/test_storylet_analyzer.py` (new)
- `tests/service/test_location_mapper.py` (new)

## Acceptance Criteria

- [ ] Each new file has at least 8 test functions
- [ ] All tests pass without an OpenAI API key
- [ ] `pytest tests/service/` completes in < 15 seconds
- [ ] Coverage of `game_logic.py` reaches 80%+

## Risks & Rollback

Pure additive. Delete the files to roll back.
