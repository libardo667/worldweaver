# Wire JIT pipeline: bootstrap → world bible, api_next → JIT beat, story arc tracking

## Problem

Minors 72, 73, and 74 add the feature flag, world bible generator, and JIT beat generator respectively — but none of them change runtime behaviour. This final minor wires everything together:

1. Onboarding calls `generate_world_bible()` instead of the 15-storylet batch (when flag is on)
2. `api_next` calls `generate_next_beat()` instead of `pick_storylet_enhanced` + `adapt_storylet_to_context` (when flag is on and a bible exists)
3. Session state carries a lightweight `story_arc` dict that gets updated each turn

## Proposed Solution

### 1. World bible storage in session state (`state_manager.py`)

Add a `world_bible` property to `AdvancedStateManager` backed by `self.variables["_world_bible"]` (prefix underscore marks it as system-internal, not player-visible). Add:
- `set_world_bible(bible: Dict[str, Any])` — stores the validated bible
- `get_world_bible() -> Optional[Dict[str, Any]]` — retrieves it
- `get_story_arc() -> Dict[str, Any]` — returns or initialises the arc dict: `{"act": "setup", "tension": "", "turn_count": 0, "unresolved_threads": []}`
- `advance_story_arc(choices_made: List[Dict])` — deterministically increments `turn_count`, promotes `act` at thresholds (setup → rising_action at turn 3, rising_action → climax at turn 8, climax → resolution at turn 14)

### 2. Bootstrap wiring (`world_bootstrap_service.py`)

In `bootstrap_world_storylets()`, add a branch when `settings.enable_jit_beat_generation` is `True`:
- Call `generate_world_bible(description, theme, player_role, tone)` instead of `generate_world_storylets()`
- Store the bible result in the response payload as `world_bible`
- Still run `generate_starting_storylet()` using the bible's `entry_point` and `locations` to produce the opening beat (this reuses the existing starting storylet machinery for now)
- Skip `run_auto_improvements()` — not applicable to JIT path
- On any exception from `generate_world_bible()`, log a warning and fall back to the existing storylet path

### 3. `api_next` wiring (`src/api/game/story.py`)

In `api_next()`, after `contextual_vars = state_manager.get_contextual_variables()`, add:

```python
if settings.enable_jit_beat_generation and state_manager.get_world_bible():
    # JIT beat path
    recent_events = [...]  # from world_memory (existing pattern)
    story_arc = state_manager.get_story_arc()
    beat = generate_next_beat(
        world_bible=state_manager.get_world_bible(),
        recent_events=recent_events,
        current_vars=contextual_vars,
        story_arc=story_arc,
    )
    state_manager.advance_story_arc(beat.get("choices", []))
    text = beat["text"]
    choices = [ChoiceOut(**normalize_choice(c)) for c in beat["choices"]]
    out = NextResp(text=text, choices=choices, vars=contextual_vars)
else:
    # Existing storylet path — unchanged
    ...
```

This is an **additive branch** — the existing storylet path runs unchanged when the flag is off or no bible is present.

### 4. Enable the flag in config

Flip `enable_jit_beat_generation` default to `True` (was `False` in minor 72 for the initial rollout).

## Files Affected

- `src/services/state_manager.py` — add `set_world_bible()`, `get_world_bible()`, `get_story_arc()`, `advance_story_arc()`
- `src/services/world_bootstrap_service.py` — add JIT branch in `bootstrap_world_storylets()`
- `src/api/game/story.py` — add JIT branch in `api_next()`
- `src/config.py` — flip `enable_jit_beat_generation` default to `True`

## Acceptance Criteria

- [ ] With `WW_ENABLE_JIT_BEAT_GENERATION=false`, existing behaviour is completely unchanged
- [ ] With `WW_ENABLE_JIT_BEAT_GENERATION=true` and AI disabled, `api_next()` returns a valid deterministic beat
- [ ] `state_manager.get_story_arc()` returns an initialised arc dict on a fresh session
- [ ] `state_manager.advance_story_arc()` increments `turn_count` and promotes `act` at the correct thresholds
- [ ] `bootstrap_world_storylets()` with JIT flag on stores `world_bible` in the response payload
- [ ] If `generate_world_bible()` raises, bootstrap falls back to the existing storylet path without error
- [ ] If `generate_next_beat()` raises in `api_next()`, it falls back to the existing storylet pick path
- [ ] `python -m pytest -q` passes
- [ ] `npm --prefix client run build` passes

## Risks & Rollback

**Risk**: The `_world_bible` key in `variables` could conflict with player-authored variable names.
**Mitigation**: The underscore prefix is conventional for system-internal keys; player-visible variables never start with `_`.

**Risk**: `advance_story_arc()` uses hard turn thresholds (3, 8, 14) that may not suit all worlds.
**Mitigation**: Thresholds are defined as module-level constants, easily tunable. This is v1; a smarter signal-based arc advance can follow.

**Rollback**: Set `WW_ENABLE_JIT_BEAT_GENERATION=false`. No data migrations required. The `_world_bible` and `_story_arc` variables are ignored by the storylet path.
