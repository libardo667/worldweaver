# Add a command to rebuild world projection from event history

## Problem

Once a projection layer is introduced, developers need a reliable way to rebuild it from `WorldEvent` history after schema changes or data fixes.

## Proposed Solution

1. Add a CLI/script command to replay events in order and rebuild projection tables.
2. Support full rebuild and session-scoped rebuild modes.
3. Output counts and timing for replay diagnostics.

## Files Affected

- `scripts/rebuild_projection.py` (new)
- `src/services/world_memory.py`
- `tests/service/test_world_memory.py`

## Acceptance Criteria

- [ ] Full replay rebuilds projection deterministically from an empty projection state.
- [ ] Session-scoped replay affects only targeted data.
- [ ] Script reports processed event count and final projection count.
