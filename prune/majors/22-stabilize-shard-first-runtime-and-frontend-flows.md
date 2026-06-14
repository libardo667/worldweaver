# Stabilize shard-first runtime boot and primary frontend flows

## Problem

The workspace has now been unified under one root repository and the shard-first
architecture is the intended runtime model, but the user-facing app flow is still
too brittle to trust.

Concrete issues visible in the current system:

- Primary frontend flows can fail at boot or during entry because runtime/config
  assumptions are still leaking through from the old `worldweaver_engine`-root era.
- The client can still end up in a bad state when shard selection, auth state,
  session bootstrap, and backend readiness do not line up cleanly.
- `scripts/dev.py` still reflects older local-dev assumptions instead of making
  shard-first startup the canonical path.
- Shard manifests and compose files are closer to self-contained now, but operator
  confidence is still too dependent on tribal knowledge around env placement,
  startup order, and which backend the client is really targeting.
- The current architecture work is real, but it is not yet fully translated into
  a stable "open the site and use it without errors" experience.

Until this is stabilized, frontend bugs and architecture bugs will keep blurring
together, and each new UI issue will be harder to diagnose than it should be.

## Proposed Solution

Do a focused stabilization pass on the shard-first runtime and the primary frontend
entry/auth/session flows.

This work is explicitly about making the current architecture legible and reliable
before adding more surface area.

### Phase 1 - Canonical shard-first dev/runtime path

- Rewrite `scripts/dev.py` so the default local-dev flow boots:
  - `ww_world`
  - one chosen city shard
  - the client against that shard/federation pair
- Make the script print the actual URLs, ports, and required env expectations so
  the operator can see which shard is active and why.
- Demote `worldweaver_engine/docker-compose.yml` and any old engine-root startup
  assumptions into explicit legacy wrappers rather than silent defaults.

### Phase 2 - Runtime/config diagnostics

- Add one clear backend readiness/config endpoint or startup report that surfaces:
  - shard identity
  - federation connectivity settings
  - auth/JWT readiness
  - email readiness
  - human BYOK readiness
  - agent inference readiness
- Make client boot fail loudly and intelligibly when the selected shard is not
  correctly configured, instead of falling into ambiguous UI errors.
- Ensure shard `.env` ownership and precedence are the only runtime contract for
  shard boot; old root `.env` files must not silently rescue broken config.

### Phase 3 - Frontend entry/auth/session hardening

- Audit the frontend boot path across:
  - shard discovery
  - city selection
  - register/login
  - `/auth/me`
  - session bootstrap
  - digest/world preload
- Ensure the client does not make shard-bound requests until shard choice and base
  URL are resolved.
- Ensure auth/session code handles:
  - no token
  - legacy token
  - actor token
  - stale local storage
  - shard mismatch
- Add explicit recovery behavior for failed bootstrap rather than leaving the app
  in a broken semi-authenticated state.

### Phase 4 - Frontend error surfaces and operator sanity

- Add coherent UI handling for:
  - backend unavailable
  - shard unavailable
  - invalid auth state
  - missing required backend capability
  - observer-mode / BYOK requirement
- Prefer one visible, debuggable error surface over silent retries or broken
  partial renders.
- Make it obvious in the client which city/shard the user is connected to.

### Phase 5 - Documentation and workflow cleanup

- Update operator docs to describe the actual startup order for shard-first local
  development and the actual config ownership model.
- Refresh major 11 and major 21 status language once this stabilization slice lands.
- Document the difference between:
  - source code
  - shard manifests
  - live shard runtime state
  - federation root services

## Files Affected

- `worldweaver_engine/scripts/dev.py`
- `worldweaver_engine/docker-compose.yml`
- `worldweaver_engine/README.md`
- `worldweaver_engine/FEDERATION.md`
- `worldweaver_engine/scripts/new_shard.py`
- `worldweaver_engine/src/config.py`
- `worldweaver_engine/main.py`
- `worldweaver_engine/src/api/auth/routes.py`
- `worldweaver_engine/src/api/game/state.py`
- `worldweaver_engine/src/api/game/settings_api.py`
- `worldweaver_engine/src/api/federation/routes.py`
- `worldweaver_engine/client/src/App.tsx`
- `worldweaver_engine/client/src/api/wwClient.ts`
- `worldweaver_engine/client/src/components/EntryScreen.tsx`
- `worldweaver_engine/client/src/state/sessionStore.ts`
- `worldweaver_engine/client/src/components/SettingsDrawer.tsx`
- `worldweaver_engine/client/src/components/ErrorToastStack.tsx`
- `worldweaver_engine/tests/api/test_auth_identity.py`
- `worldweaver_engine/tests/api/test_settings_readiness.py`
- `worldweaver_engine/tests/api/test_route_smoke.py`
- `worldweaver_engine/tests/api/test_world_endpoints.py`
- `prune/majors/11-shard-creation-framework.md`
- `prune/majors/21-prune-legacy-dev-architecture-and-unify-engine-kit.md`

## Acceptance Criteria

- [ ] A local operator can start `ww_world`, one city shard, and the client through one documented shard-first path without relying on `worldweaver_engine/.env`
- [ ] The client always requires or resolves an explicit shard target before making shard-bound startup requests
- [ ] Register, login, `/auth/me`, and session bootstrap work cleanly against the selected shard without leaving stale broken state in local storage
- [ ] Missing shard config produces a clear backend or frontend diagnostic instead of a generic broken-screen failure
- [ ] The UI clearly shows which city/shard it is connected to
- [ ] Legacy auth tokens and actor-based auth tokens are both handled predictably during the migration window
- [ ] BYOK / observer-mode requirements surface as intentional UX, not mysterious action failures
- [ ] Operator docs reflect the current shard-first architecture and startup order
- [ ] The difference between source code, shard manifests, and live shard runtime state is documented and enforced by workflow

## Risks & Rollback

- This work touches both runtime startup and frontend boot state, so it is easy to
  accidentally "fix" symptoms while hiding the real configuration problem. Keep
  diagnostics explicit.
- Tightening config validation may break currently tolerated local setups. That is
  acceptable if the resulting errors are clear and the docs match the new contract.
- Reworking `scripts/dev.py` can disrupt existing personal workflows. Keep a legacy
  path temporarily if needed, but make it visibly legacy.
- Rollback path: preserve the current shard manifests and auth/session behavior while
  landing diagnostics first, then tighten startup and client gating in small steps.
