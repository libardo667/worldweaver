# PR Evidence: Minor 71 — Switch Default LLM to Fluency Model

## Item

`improvements/minors/71-switch-default-llm-to-fluency-model.md`

## Branch

`minor/71-switch-default-llm-to-fluency-model`

## What Changed

| File | Change |
|------|--------|
| `src/config.py` | Default `llm_model` changed from `deepseek/deepseek-r1` to `aion-labs/aion-2.0`; `llm_timeout_seconds` changed from `15` to `30` |
| `src/services/model_registry.py` | `deepseek/deepseek-r1` `creative_quality` downgraded `3` → `2`; notes updated to clarify reasoning model overhead |
| `improvements/majors/51-jit-beat-generation-pipeline.md` | New major item doc (companion to this work) |
| `improvements/minors/71-switch-default-llm-to-fluency-model.md` | Item doc for this change |
| `improvements/ROADMAP.md` | Added major 51 [P1] and minor 71 [P0] to queues; updated risks and execution order |

## Why

DeepSeek R1 is a reasoning model with internal chain-of-thought that adds 5–15s latency overhead for creative prose tasks. Aion 2.0 is purpose-built for narrative/roleplay, has `creative_quality: 4` (highest in budget tier), costs less on output ($1.60/M vs $2.50/M), and has no reasoning overhead. The timeout increase from 15s to 30s prevents premature truncation on larger generation requests.

## Quality Gate Evidence

### Gate 1: Contract Integrity ✅
No API route, payload, or response shape changes. Only config defaults changed.

### Gate 2: Correctness ✅
```
python -m pytest -q → 479 passed, 12 warnings in 22.71s (exit 0)
```

### Gate 3: Build and Static Health ✅
```
npm --prefix client run build → built in 1.29s (exit 0)
```

### Gate 5: Operational Safety ✅
- **Rollback**: Set `LLM_MODEL=deepseek/deepseek-r1` env var to revert instantly
- **Feature flag**: Users can override model via settings API or `LLM_MODEL` env var
- **No data migrations**: Config-only change, fully reversible

## Scope Compliance

- [x] Scope stayed within declared file boundary (`config.py`, `model_registry.py`)
- [x] Acceptance criteria verified via test suite (all 479 tests pass)
- [x] Tests/checks run and documented
- [x] Risks and rollback documented above
- [x] No drive-by refactors outside scope

## Remaining Risk

- Runtime behavior (Gate 4) requires live testing with the Aion 2.0 model to confirm prose quality and latency in practice. This is inherently model-dependent and cannot be validated by unit tests alone.
