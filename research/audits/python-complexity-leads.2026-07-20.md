# Python complexity leads — 2026-07-20

This is a review map, not a quality score or CI budget. It was recorded after replacing the inherited
320-column Python format with ordinary Black formatting. Ruff's cyclomatic-complexity check was run over both
source trees with its default warning threshold of 10. Tests, scripts, and generated clients were not ranked.

## Strongest leads

| Side | Function | Complexity | Why it deserves a code review |
| --- | --- | ---: | --- |
| Engine | `src/api/game/world.py:get_world_digest` | 74 | One read endpoint appears to assemble many unrelated projections and policies. |
| Engine | `src/services/city_pack_validation.py:_check_generated_map` | 49 | Map format, topology, and safety validation may be mixed in one decision tree. |
| Engine | `src/services/city_pack_validation.py:validate_city_pack` | 42 | Whole-pack orchestration and individual validation rules may be conflated. |
| Engine | `src/api/game/world.py:query_world_map` | 41 | Query parsing, visibility, filtering, and response shaping may share one route body. |
| Agent | `src/runtime/effectors.py:_do` | 32 | Many world verbs converge on one dispatcher, making authority and error paths hard to compare. |
| Agent | `src/runtime/ledger.py:_build_subjective_projection` | 32 | Several private-state reduction rules share one projection pass. |
| Agent | `src/identity/loader.py:render_situational_briefing` | 25 | Identity, current facts, and presentation policy may be mixed in one renderer. |
| Agent | `src/runtime/salience.py:derive_vital` | 26 | A scientific-sounding aggregate combines many branches and deserves conceptual as well as code review. |

## How to use this map

- Do not refactor a function only to lower its number. Reducers and strict validators can be legitimately
  branch-heavy.
- When work enters one of these functions, first identify its inputs, outputs, side effects, authority checks,
  and failure behavior. Add characterization tests before splitting it.
- Prefer extracting named policy decisions or pure validators. Do not replace visible branches with a generic
  framework that merely hides the same complexity.
- Keep this scan advisory. The normal CI gate should catch broken code and inconsistent formatting without
  turning a solo project into a complexity-budget exercise.

Commands used:

```bash
cd ww_agent && ../.venv/bin/python -m ruff check src --select C901
cd worldweaver_engine && ../.venv/bin/python -m ruff check src main.py --select C901
```
