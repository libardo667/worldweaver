# Provenance-tagged tool affect (knowing vs reaching)

## Metadata

- ID: 56-provenance-tagged-tool-affect
- Type: minor
- Owner: Levi
- Status: backlog
- Risk: low

## Problem

The `eats` tool returns real San Francisco spots from a *local* dataset ("false egress" — worldly feel, zero egress). Mr. Review (Q5): the quiet guarantee is about provenance honesty. Local data is not the problem; local data **wearing the affect of a lookup** is. A Mission local genuinely *knows* the taquerias — surfacing `eats` as *recall* ("I know a place") is honest character; dressing the same recall in *egress affect* ("let me look that up") performs an outward reach that didn't happen — faked worldliness. Same data, different performed provenance.

## Proposed Solution

Tag each tool's output by provenance (`local-knowledge` vs `world-egress`) and let the resident narrate from the tag: `eats` / `recall` / `places` = local-knowledge ("I know…"); a future `web`/egress tool = world-egress ("I looked it up"). The canon-provenance principle applied to tools — name a tool for what it *is* (knowing the neighborhood), never for the gesture it isn't (consulting an oracle).

## Files Affected

- `ww_agent/src/world/city_tools.py` — a provenance tag on each `Tool`; surface it in the result/affordance.
- the pulse prompt (`pulse_engine.py`) — narrate local-knowledge tools as knowing, not reaching.

## Acceptance Criteria

- [x] Each tool result carries a provenance tag (`local-knowledge` | `egress`). — `Tool.provenance` (default `local-knowledge`); `CityToolScope.call` returns it. All current tools are `local-knowledge` (served from within the world); `world-egress` is reserved for a future real-web tool. Test: `test_tool_results_carry_a_local_knowledge_provenance_tag`.
- [x] The resident is prompted to narrate local-knowledge tools as knowing, not as a lookup. — `CityWorld.get_scene` advertises local-knowledge tools as "things you know first-hand or can sense, so speak them as your own knowing, not as looking something up" (a future egress tool advertised as a deliberate reach); a reinforcing line in the pulse tool-loop template. Test: `test_advertisement_frames_local_knowledge_tools_as_knowing`.

## Status

**Built 2026-06-06.** `provenance` field on `Tool` + `CityToolScope.call`; provenance-aware advertisement in `city_world.py`; knowing-framing line in `pulse_engine.py`'s tool-loop template. 2 new tests (38 pass in `test_city_tools.py`).

## Validation Commands

- `cd ww_agent && PYTHONPATH=. python -m pytest tests/test_city_tools.py -q`

## Risks and Rollback

- Risk: low — additive metadata + a prompt nuance.
- Rollback: drop the tag; tools behave as today.
