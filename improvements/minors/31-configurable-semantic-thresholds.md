# Configurable Semantic Selection Thresholds

## Problem

Constants like `FLOOR_PROBABILITY` and `RECENCY_PENALTY` in `semantic_selector.py` are currently hardcoded, making it difficult to tune the "feel" of story progression without code changes.

## Proposed Solution

1.  Add `llm_semantic_floor_probability` and `llm_recency_penalty` to `Settings` in `src/config.py`.
2.  Update `src/services/semantic_selector.py` to use these settings.
3.  Expose these values in the `.env` file for easy experimentation.

## Files Affected

- `src/config.py`
- `src/services/semantic_selector.py`

## Acceptance Criteria

- [ ] Changing `LLM_RECENCY_PENALTY` in `.env` immediately affects how often the same storylet is picked.
- [ ] Documentation explains how these values shift the narrative experience (e.g., "high floor = more random/diverse, low floor = highly focused/relevant").
