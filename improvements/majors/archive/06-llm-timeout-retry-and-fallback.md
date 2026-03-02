# Add timeout, retry, and structured fallback to LLM calls

## Problem

Every OpenAI call in `llm_service.py` fires without a timeout or retry.
If the API is slow or down, the request hangs indefinitely and the player
sees nothing. The spec (`specs/06-llm-service.md`) explicitly requires
"Timeout and retry logic implemented for reliability" and "Fallback
storylets provided on timeout or error," but neither is implemented.

Additionally, JSON extraction from LLM responses is fragile — it searches
for bracket positions in raw text (`llm_service.py` lines 447-455) and
will break on responses that contain nested JSON or markdown formatting.

## Proposed Solution

1. Wrap every `openai.ChatCompletion.create` / `client.chat.completions.create`
   call in a helper that:
   - Sets `timeout=15` (seconds) on the HTTP call.
   - Retries up to 2 times with 1-second backoff on transient errors
     (timeout, 429, 500, 503).
   - Falls back to the deterministic fallback storylet generator on
     exhaustion.
2. Replace the bracket-position JSON extraction with a dedicated
   `_extract_json(text) -> list[dict]` function that:
   - Strips markdown code fences.
   - Tries `json.loads` on the full text first.
   - Falls back to regex extraction of the first `[...]` block.
   - Validates that each element has at least `title` and `text_template`.
3. Add unit tests that mock the OpenAI client to simulate timeout, 429,
   malformed JSON, and empty response scenarios.

## Files Affected

- `src/services/llm_service.py` — retry wrapper, JSON extractor
- `tests/service/test_llm_service.py` (new or extended)

## Acceptance Criteria

- [ ] A 16-second OpenAI hang results in a fallback response, not a hung
      request
- [ ] A 429 rate-limit is retried twice before falling back
- [ ] Malformed LLM JSON triggers fallback instead of a 500 error
- [ ] Test suite covers timeout, retry, and malformed JSON paths
- [ ] No change in behaviour when OpenAI responds normally

## Risks & Rollback

The retry wrapper is a single function; revert it to restore direct calls.
The 15-second timeout is conservative — adjust via config if needed.
