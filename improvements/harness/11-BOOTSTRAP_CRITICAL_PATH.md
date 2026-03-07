# Bootstrap Critical Path and Prompt Surface Report

## Purpose

Single authoritative artifact mapping the session bootstrap call graph, LLM prompt surfaces,
deterministic fallback paths, and the `bootstrap_diagnostics` response envelope introduced in
Minor 111. Updated whenever any of the listed files change.

---

## Call Graph — `/session/bootstrap`

```
POST /api/session/bootstrap
  └─ bootstrap_session_world()                  src/api/game/state.py:292
       ├─ _delete_session_world_rows()           purge stale world rows and caches
       ├─ bootstrap_world_storylets()            src/services/world_bootstrap_service.py
       │    ├─ _generate_world_bible()           narrator LLM → WorldBible structure
       │    │    └─ llm_service.generate_text()  narrator lane prompt
       │    ├─ generate_world_storylets()        referee LLM → batch storylet generation
       │    │    └─ loops in batches of 6        cross-batch title deduplication enforced
       │    └─ returns world_result dict         keys: storylets_created, world_bible,
       │                                              message, fallback_active
       ├─ state_manager.set_variable(...)        seeds _bootstrap_state, _bootstrap_source,
       │                                         _bootstrap_completed_at, _bootstrap_input_hash,
       │                                         world_theme, player_role, world_tone
       ├─ state_manager.set_world_bible()        persists world bible into session state
       ├─ save_state()                           commits session vars to DB
       └─ returns SessionBootstrapResponse       includes bootstrap_diagnostics envelope
```

## Call Graph — `/session/start`

```
POST /api/session/start
  └─ session_start()                            src/api/game/state.py:393
       ├─ same bootstrap path as above
       └─ run_next_turn_orchestration()          first turn — same pipeline as /api/next
            └─ returns SessionStartResponse      includes bootstrap_diagnostics + first_turn
```

---

## Data Seeded Before First Turn

| Variable | Source | Notes |
|---|---|---|
| `world_theme` | request payload | required, non-blank |
| `player_role` | request payload | required, non-blank |
| `character_profile` | request payload | copy of player_role |
| `world_tone` | payload or default `"adventure"` | |
| `world_key_elements` | payload list (max 20) | optional |
| `_bootstrap_state` | `"completed"` | |
| `_bootstrap_source` | payload field | e.g., `"web_ui"` |
| `_bootstrap_completed_at` | UTC ISO timestamp | |
| `_bootstrap_input_hash` | SHA-256 of key payload fields | replay guard |
| `_bootstrap_storylets_created` | `world_result["storylets_created"]` | |
| world bible | `world_result["world_bible"]` | persisted via `set_world_bible()` |

---

## LLM Prompt Surfaces on Critical Path

| Step | LLM Lane | Prompt Builder | Fallback |
|---|---|---|---|
| World-bible generation | narrator (`LLM_NARRATOR_MODEL`) | `_generate_world_bible()` in `world_bootstrap_service.py` | `world_bible_fallback=True`; empty structure returned |
| Storylet batch generation | referee (`LLM_REFEREE_MODEL`) | `generate_world_storylets()` batch loop | fallback batch returned; `fallback_active=True` |
| First-turn narration (session/start only) | narrator | `adapt_storylet_to_context()` | `first_turn_error` set; turn skipped |

Temperature is set per-lane via `LLM_NARRATOR_TEMPERATURE` / `LLM_REFEREE_TEMPERATURE`. Falls
back to `LLM_TEMPERATURE` if per-lane values are absent.

---

## Feature-Flag Gates

| Flag | Default | Effect when disabled |
|---|---|---|
| `WW_ENABLE_JIT_BEAT_GENERATION` | `true` | No JIT beats on first turn |
| `WW_ENABLE_SIMULATION_TICK` | `true` | No danger/resource ticks on first turn |
| `WW_ENABLE_V3_PROJECTION_EXPANSION` | `true` | Projection BFS skipped after bootstrap |
| `WW_ENABLE_FRONTIER_PREFETCH` | `true` | No prefetch scheduled after bootstrap |

---

## `bootstrap_diagnostics` Response Envelope

Present in both `SessionBootstrapResponse` and `SessionStartResponse` from Minor 111 onward.

```json
{
  "bootstrap_diagnostics": {
    "bootstrap_mode": "classic",
    "seeding_path": "bootstrap_world_storylets",
    "world_bible_generated": true,
    "world_bible_fallback": false,
    "storylets_created": 12,
    "fallback_active": false,
    "bootstrap_source": "web_ui"
  }
}
```

Field definitions:

| Field | Type | Meaning |
|---|---|---|
| `bootstrap_mode` | str | `"classic"` (only mode currently); reserved for future JIT bootstrap |
| `seeding_path` | str | Internal function name that ran world generation |
| `world_bible_generated` | bool | `true` if world bible dict was returned by bootstrap |
| `world_bible_fallback` | bool | `true` if world-bible LLM call failed and fallback was used |
| `storylets_created` | int | Number of storylets persisted to DB |
| `fallback_active` | bool | `true` if any batch fallback was used during generation |
| `bootstrap_source` | str | Caller-supplied provenance tag from request payload |

---

## Validation Commands

```bash
# Bootstrap diagnostics field presence test
pytest -q tests/api/test_game_endpoints.py -k "bootstrap_diagnostics"

# Full game endpoint suite
pytest -q tests/api/test_game_endpoints.py

# Strict gate
python scripts/dev.py quality-strict
```

---

## Files to Update When Any of These Change

| File | What changed | Update |
|---|---|---|
| `src/api/game/state.py` | bootstrap route handler | Update Call Graph and `bootstrap_diagnostics` fields |
| `src/services/world_bootstrap_service.py` | bootstrap service | Update LLM Prompt Surfaces table |
| `src/models/schemas.py` | `SessionBootstrapResponse` | Update envelope field table |
| `.env` / `LLM_*` env vars | temperature or model routing | Update Feature-Flag Gates and LLM Prompt Surfaces |
