# Add a maintenance command to re-embed storylets and world events

## Problem

Embeddings can become stale when prompt format, model, or source text changes. There is no single command to refresh embeddings for all affected records.

## Proposed Solution

1. Add a script in `scripts/` to re-embed storylets and world events in batches.
2. Support dry-run mode and targeted scope (`storylets`, `events`, or both).
3. Log progress and failures with final counts.

## Files Affected

- `scripts/reembed.py` (new)
- `src/services/embedding_service.py`
- `src/services/world_memory.py`
- `tests/service/test_embedding_service.py`

## Acceptance Criteria

- [ ] Command re-embeds records in bounded batches without crashing on single-row failures.
- [ ] Dry-run mode reports intended counts without DB mutation.
- [ ] Script can run repeatedly without corrupting records.
