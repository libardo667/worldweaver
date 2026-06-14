# Actor usage ledger and spend caps

## Status

Open as of 2026-03-16.

This spec continues Phase 2 of major `17-per-user-api-key`. Phase 1 BYOK storage and
observer-mode enforcement are already shipped. Major `26-isolate-actor-billing-from-shared-simulation-inference`
now provides the call-scoped ownership contract this work depends on.

## Problem

Players can now save a personal narration key, but the product still lacks the
durable accounting and limits needed to make that safe and legible:

- there is no persistent ledger of actor-paid inference calls
- players cannot inspect what their key has paid for
- there is no budget ceiling or automatic lockout when a personal budget is exhausted

Without that, BYOK is only partially legible. The billing boundary exists in code,
but there is no durable record or enforcement layer around it.

## Scope

### Phase 2A — Durable actor-paid inference ledger

- Persist one row for every `actor_private` inference call.
- Record enough metadata to audit billing ownership:
  - `trace_id`
  - `route`
  - `actor_id`
  - `session_id` or equivalent owner context
  - `model_id`
  - `operation`
  - `prompt_tokens`
  - `completion_tokens`
  - `estimated_cost_usd`
  - `created_at`
- Exclude `platform_shared` and `agent_runtime` calls from actor spend totals.

### Phase 2B — Player-visible usage summary

- Add an authenticated endpoint that returns the current actor's usage summary.
- Include:
  - lifetime totals
  - rolling recent usage
  - per-model breakdown
  - current budget / cap state
- Add a lightweight client surface so a player can inspect their own narration spend.

### Phase 2C — Spend caps and automatic observer fallback

- Add a configurable actor spend ceiling.
- Enforce caps only for `actor_private` calls.
- When a cap is exceeded:
  - reject further actor-private action narration
  - return a deliberate product error code
  - push the actor into observer mode until the cap is raised or reset

## Files likely affected

- `worldweaver_engine/src/models/__init__.py` — usage ledger persistence models
- `worldweaver_engine/src/services/llm_client.py` — durable ledger writes for actor-private calls
- `worldweaver_engine/src/services/player_api_keys.py` — cap checks / observer fallback
- `worldweaver_engine/src/api/game/settings_api.py` — usage summary and budget status endpoints
- `worldweaver_engine/client/src/components/SettingsDrawer.tsx` — usage / cap UI
- `worldweaver_engine/client/src/App.tsx` — cap-exceeded recovery flow

## Acceptance Criteria

- [ ] Every actor-private inference call produces a durable ledger row
- [ ] Shared simulation and agent-runtime calls never count against actor usage
- [ ] Players can inspect their own narration usage in-app
- [ ] Spend caps can block further actor-private narration without affecting shared simulation
- [ ] Cap exhaustion transitions the player into a deliberate observer-mode recovery path

## Risks

- Cost attribution is only as accurate as the model/pricing metadata available at call time.
- Ledger writes must be best-effort but not silently lossy; if persistence fails, the request
  should log a traceable warning at minimum.
- Cap enforcement must happen only after ownership is explicit, or shared simulation could
  accidentally become actor-billed.
