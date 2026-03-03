# Add end-to-end latency instrumentation for turns and LLM calls

## Problem
Long turn times are hard to improve without visibility into where time is spent (DB, embeddings, world facts, LLM inference, streaming). Right now the player experiences "waiting" but developers cannot attribute the delay precisely.

## Proposed Solution
Add lightweight timing instrumentation:
- measure duration for:
  - `/api/next` end-to-end,
  - `/api/action` and `/api/action/stream` end-to-end,
  - each LLM request (chat + embeddings),
  - world fact retrieval and projection overlays.
- log a single structured line per request with a correlation id.
- optionally return `X-WW-Trace-Id` response header.

## Files Affected
- `src/services/llm_client.py`
- `src/services/embedding_service.py`
- `src/api/game/story.py`
- `src/api/game/action.py`
- `src/services/world_memory.py` (optional: timing around fact pack calls)

## Acceptance Criteria
- [ ] Each request logs a correlation id and a timing breakdown.
- [ ] LLM chat and embeddings calls log duration and model used.
- [ ] No API payload shapes change.
- [ ] `pytest -q` passes.
