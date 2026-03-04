# Add `enable_jit_beat_generation` feature flag to config

## Problem

Major 51 (JIT beat generation pipeline) touches six files across the LLM, bootstrap, and API layers. To safely introduce this new path without breaking the existing storylet pipeline, all new JIT code must be gated behind a feature flag that is off by default initially, then switched to on once the full pipeline is wired and verified.

Currently `src/config.py` has no such flag.

## Proposed Solution

Add a single boolean setting to `Settings` in `src/config.py`:

```python
enable_jit_beat_generation: bool = Field(
    default=False,
    validation_alias="WW_ENABLE_JIT_BEAT_GENERATION",
)
```

Default is `False` so that no existing behaviour changes until the full pipeline (minors 73–75) is complete and verified. Subsequent minors will branch on `settings.enable_jit_beat_generation` to activate the new path.

## Files Affected

- `src/config.py` — add `enable_jit_beat_generation` field

## Acceptance Criteria

- [ ] `settings.enable_jit_beat_generation` is `False` by default
- [ ] Setting `WW_ENABLE_JIT_BEAT_GENERATION=true` environment variable sets it to `True`
- [ ] `python -m pytest -q` passes (no regressions)
