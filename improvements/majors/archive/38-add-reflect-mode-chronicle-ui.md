# Add Reflect mode chronicle UI for DF-style retellability

## Problem
Explore mode alone makes the world feel moment-to-moment, but it does not naturally produce DF-style retellability. Players need a “legends mode” surface that:
- makes history legible,
- helps them understand why the world is different now,
- creates shareable artifacts (screenshots, summaries, exports).

Without Reflect mode, the world’s persistent memory is mostly invisible to the player.

## Proposed Solution
Add a **Reflect mode** to the web client that visualizes world history and highlights a small number of causal/thematic links.

Scope: client-first, using existing endpoints; no new backend endpoints required for v1.

Implementation outline:
1. Add a mode toggle in the client UI: Explore | Reflect.
2. Reflect mode view:
   - Timeline list sourced from GET `/api/world/history` (limit configurable).
   - Event cards show: timestamp, event_type, summary, and a small “impact” badge (permanent_change vs normal).
   - A “Because of…” panel that selects 3–5 high-salience events (heuristic v1):
     - prefer `event_type == permanent_change`,
     - prefer events with non-empty `world_state_delta`,
     - prefer most recent events.
3. Pinning:
   - Allow player to pin an event or a person/topic; store pins locally (and optionally mirror to session vars).
4. Export:
   - Provide “Export Chronicle” button that downloads a markdown summary and a JSON bundle (client-side composition).

Recommended client additions:
- `client/src/views/ReflectView.tsx`
- `client/src/components/Timeline.tsx`
- `client/src/components/EventCard.tsx`
- `client/src/components/BecauseOfPanel.tsx`
- `client/src/utils/exportRun.ts`

## Files Affected
- client/src/App.tsx (modify to add mode toggle)
- client/src/views/ReflectView.tsx (new)
- client/src/components/Timeline.tsx (new)
- client/src/components/EventCard.tsx (new)
- client/src/components/BecauseOfPanel.tsx (new)
- client/src/utils/exportRun.ts (new)

## Acceptance Criteria
- [x] The client UI includes a mode toggle and can switch to Reflect mode without losing session state.
- [x] Reflect mode displays a timeline sourced from `/api/world/history`.
- [x] Reflect mode highlights 3–5 “Because of…” events using a deterministic heuristic.
- [x] Player can pin an event and see it in a “Pinned” section.
- [x] Player can export a markdown chronicle and JSON bundle for the current session.
- [x] Existing backend tests continue to pass (`pytest -q`).

## Risks & Rollback
Primary risks:
- Timeline becomes noisy without filtering (needs sensible defaults).
- Export formats become unstable early (limit scope to simple, versioned exports).

Rollback:
- Hide Reflect mode behind a feature flag in the client, or remove the Reflect view files. Backend unchanged.
